"""Contrato MPRIS real numa sessão D-Bus descartável, sem player de terceiros."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import httpx
import pytest
from dbus_next import Variant
from dbus_next.aio import MessageBus
from dbus_next.service import PropertyAccess, ServiceInterface, dbus_property
from httpx import ASGITransport

from thoth.api.app import criar_app

pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(
        os.environ.get("THOTH_MPRIS_TEST_BUS") != "1"
        or not os.environ.get("DBUS_SESSION_BUS_ADDRESS"),
        reason="rode dentro de dbus-run-session com THOTH_MPRIS_TEST_BUS=1",
    ),
]

_CAMINHO = "/org/mpris/MediaPlayer2"
_NOME = "org.mpris.MediaPlayer2.thoth_test"


class _Player(ServiceInterface):
    def __init__(self) -> None:
        super().__init__("org.mpris.MediaPlayer2.Player")
        self.estado = "Playing"
        self.posicao = 12_500_000

    @dbus_property(access=PropertyAccess.READ)
    def PlaybackStatus(self) -> "s":  # noqa: F821, UP037
        return self.estado

    @dbus_property(access=PropertyAccess.READ)
    def Position(self) -> "x":  # noqa: F821, UP037
        return self.posicao

    @dbus_property(access=PropertyAccess.READ)
    def Metadata(self) -> "a{sv}":  # noqa: F722
        return {
            "mpris:length": Variant("x", 180_000_000),
            "xesam:title": Variant("s", "Música de teste"),
            "xesam:artist": Variant("as", ["Banda"]),
        }


class _Raiz(ServiceInterface):
    def __init__(self) -> None:
        super().__init__("org.mpris.MediaPlayer2")

    @dbus_property(access=PropertyAccess.READ)
    def Identity(self) -> "s":  # noqa: F821, UP037
        return "Player MPRIS de teste"


def test_le_a_posicao_e_os_metadados_de_um_servico_mpris_real(tmp_path: Path) -> None:
    async def executar() -> None:
        barramento = await MessageBus().connect()
        await barramento.request_name(_NOME)
        player = _Player()
        barramento.export(_CAMINHO, _Raiz())
        barramento.export(_CAMINHO, player)
        try:
            app = criar_app(out_dir=tmp_path / "out", cache_dir=tmp_path / "cache")
            async with httpx.AsyncClient(
                transport=ASGITransport(app=app), base_url="http://thoth.test"
            ) as cliente:
                resposta = await cliente.get("/playback/players")
                assert resposta.status_code == 200, resposta.text
                assert resposta.json() == [
                    {
                        "nome": _NOME,
                        "identidade": "Player MPRIS de teste",
                        "estado": "Playing",
                        "posicao_s": 12.5,
                        "duracao_s": 180.0,
                        "titulo": "Música de teste",
                        "artista": "Banda",
                        "album": None,
                    }
                ]

                player.estado = "Paused"
                player.posicao = 25_000_000
                pausa = await cliente.get("/playback/players")
                assert pausa.json()[0]["estado"] == "Paused"
                assert pausa.json()[0]["posicao_s"] == 25.0

                player.estado = "Stopped"
                parado = await cliente.get("/playback/players")
                assert parado.json()[0]["estado"] == "Stopped"

                barramento.unexport(_CAMINHO)
                await barramento.release_name(_NOME)
                sem_player = await cliente.get("/playback/players")
                assert sem_player.json() == []
        finally:
            barramento.disconnect()

    asyncio.run(executar())
