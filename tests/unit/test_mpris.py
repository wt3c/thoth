"""Regras locais da integração MPRIS."""

from __future__ import annotations

import asyncio
import sys

from dbus_next.errors import InvalidAddressError

from thoth.adapters.playback import mpris
from thoth.adapters.playback.mpris import LeitorMpris, _eh_spotify


def test_nao_expoe_fontes_spotify_por_nome_identidade_ou_url() -> None:
    assert _eh_spotify("org.mpris.MediaPlayer2.spotify")
    assert _eh_spotify("org.mpris.MediaPlayer2.player", "Spotify")
    assert _eh_spotify("org.mpris.MediaPlayer2.chromium", "Chrome", "https://open.spotify.com")
    assert not _eh_spotify("org.mpris.MediaPlayer2.vlc", "VLC media player", "file:///tmp/faixa.flac")


def test_fora_do_linux_a_lista_mpris_e_vazia(monkeypatch) -> None:
    monkeypatch.setattr(sys, "platform", "win32")

    assert asyncio.run(LeitorMpris().listar()) == []


def test_sem_endereco_de_sessao_dbus_a_lista_e_vazia(monkeypatch) -> None:
    class SemBarramento:
        def __init__(self, **_: object) -> None: ...

        async def connect(self) -> None:
            raise InvalidAddressError("sessão D-Bus ausente")

    monkeypatch.setattr(mpris, "MessageBus", SemBarramento)

    assert asyncio.run(LeitorMpris().listar()) == []
