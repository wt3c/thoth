"""Leitura somente local de players compatíveis com MPRIS 2 no Linux."""

from __future__ import annotations

import asyncio
import sys
from typing import Any, cast

from dbus_next import BusType, DBusError, Message, MessageType  # type: ignore[attr-defined]
from dbus_next.aio import MessageBus  # type: ignore[attr-defined]
from dbus_next.errors import InvalidAddressError

from thoth.domain.reproducao import ReproducaoExterna

_PREFIXO = "org.mpris.MediaPlayer2."
_CAMINHO = "/org/mpris/MediaPlayer2"
_PROPRIEDADES = "org.freedesktop.DBus.Properties"
_PLAYER = "org.mpris.MediaPlayer2.Player"
_INTERFACE = "org.mpris.MediaPlayer2"
_MICROSSEGUNDOS = 1_000_000


def _valor(propriedades: dict[str, Any], nome: str, padrao: Any = None) -> Any:
    """Desembrulha o Variant D-Bus; ausências são comuns em metadata opcional."""
    propriedade = propriedades.get(nome)
    return propriedade.value if propriedade is not None else padrao


def _texto(valor: Any) -> str | None:
    if isinstance(valor, str) and valor.strip():
        return valor.strip()
    if isinstance(valor, (list, tuple)) and valor and isinstance(valor[0], str):
        return valor[0].strip() or None
    return None


def _eh_spotify(nome: str, identidade: str = "", url: str | None = None) -> bool:
    """O escopo pedido exclui Spotify, inclusive quando a fonte é um player MPRIS."""
    return any("spotify" in texto.casefold() for texto in (nome, identidade, url or ""))


async def _get_all(barramento: MessageBus, destino: str, interface: str) -> dict[str, Any]:
    """Properties.GetAll sem depender de o player listar Properties na introspecção."""
    resposta = await asyncio.wait_for(
        barramento.call(
            Message(
                destination=destino,
                path=_CAMINHO,
                interface=_PROPRIEDADES,
                member="GetAll",
                signature="s",
                body=[interface],
            )
        ),
        timeout=1.0,
    )
    if resposta is None:
        raise TimeoutError("D-Bus não respondeu ao GetAll")
    if resposta.message_type == MessageType.ERROR:
        raise DBusError(  # type: ignore[no-untyped-call]
            resposta.error_name or "org.freedesktop.DBus.Error.Failed", "GetAll falhou"
        )
    return cast(dict[str, Any], resposta.body[0])


class LeitorMpris:
    """Consulta snapshots sob demanda e fecha a conexão para reconectar sem estado velho."""

    async def listar(self) -> list[ReproducaoExterna]:
        if sys.platform != "linux":
            return []

        barramento: MessageBus | None = None
        try:
            barramento = await asyncio.wait_for(
                MessageBus(bus_type=BusType.SESSION).connect(), timeout=1.0
            )
            resposta = await asyncio.wait_for(
                barramento.call(
                    Message(
                        destination="org.freedesktop.DBus",
                        path="/org/freedesktop/DBus",
                        interface="org.freedesktop.DBus",
                        member="ListNames",
                    )
                ),
                timeout=1.0,
            )
            if resposta is None or resposta.message_type == MessageType.ERROR:
                return []
            nomes = cast(list[str], resposta.body[0])
            players = sorted(
                nome
                for nome in nomes
                if nome.startswith(_PREFIXO) and not _eh_spotify(nome)
            )
            snapshots = await asyncio.gather(
                *(self._snapshot(barramento, nome) for nome in players),
                return_exceptions=False,
            )
            return [
                player
                for player in snapshots
                if not _eh_spotify(player.nome, player.identidade, player.url)
            ]
        except (OSError, DBusError, InvalidAddressError, TimeoutError):
            return []
        finally:
            if barramento is not None:
                barramento.disconnect()  # type: ignore[no-untyped-call]

    async def _snapshot(self, barramento: MessageBus, nome: str) -> ReproducaoExterna:
        try:
            player, media = await asyncio.gather(
                _get_all(barramento, nome, _PLAYER),
                _get_all(barramento, nome, _INTERFACE),
            )
            metadata = _valor(player, "Metadata", {})
            posicao = max(0, int(_valor(player, "Position", 0))) / _MICROSSEGUNDOS
            duracao = _valor(metadata, "mpris:length")
            return ReproducaoExterna(
                nome=nome,
                identidade=str(_valor(media, "Identity", nome.removeprefix(_PREFIXO))),
                estado=str(_valor(player, "PlaybackStatus", "Stopped")),
                posicao_s=posicao,
                duracao_s=max(0, int(duracao)) / _MICROSSEGUNDOS if duracao is not None else None,
                titulo=_texto(_valor(metadata, "xesam:title")),
                artista=_texto(_valor(metadata, "xesam:artist")),
                album=_texto(_valor(metadata, "xesam:album")),
                url=_texto(_valor(metadata, "xesam:url")),
            )
        except (OSError, DBusError, TimeoutError):
            # Um player pode encerrar entre ListNames e GetAll; os demais continuam úteis.
            return ReproducaoExterna(
                nome=nome,
                identidade=nome.removeprefix(_PREFIXO),
                estado="Unavailable",
                posicao_s=0.0,
                duracao_s=None,
                titulo=None,
                artista=None,
                album=None,
                url=None,
            )
