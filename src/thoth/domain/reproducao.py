"""Contrato de uma fonte local de posição de reprodução (ADR-046)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ReproducaoExterna:
    """Snapshot do estado que um player publica pelo MPRIS."""

    nome: str
    identidade: str
    estado: str
    posicao_s: float
    duracao_s: float | None
    titulo: str | None
    artista: str | None
    album: str | None
    url: str | None


class LeitorDeReproducao(Protocol):
    """Descobre e consulta players locais sem assumir um fornecedor específico."""

    async def listar(self) -> list[ReproducaoExterna]: ...
