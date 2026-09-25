"""Contratos entre estágios. Cada adapter concreto implementa um destes."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from thoth.domain.models import (
    AudioAsset,
    EventoPercussivo,
    NoteEvent,
    Posicionamento,
    TabNote,
)


class AudioSource(Protocol):
    """Traz o áudio para o cache, normalizado em WAV 44.1 kHz."""

    def fetch(self, ref: str, cache_dir: Path) -> AudioAsset: ...


class Transcriber(Protocol):
    """Áudio → eventos de nota."""

    def transcribe(self, audio: Path, instrument: str | None = None) -> list[NoteEvent]: ...


class Separator(Protocol):
    """Mix → stems por instrumento. Etapa fixa antes de transcrever (ADR-010)."""

    def separate(self, audio: Path, out_dir: Path) -> dict[str, Path]: ...


class FretAssigner(Protocol):
    """Notas → posições (corda, traste) para uma afinação."""

    def assign(
        self, notes: list[NoteEvent], tuning: tuple[int, ...], max_fret: int = 24
    ) -> list[TabNote]: ...


class AtribuidorDeAcordes(Protocol):
    """Notas com acordes → posições, para instrumento de cordas polifônico (ADR-044).

    Separado do `FretAssigner` de propósito: aquele pressupõe linha monofônica, e o
    baixo não pode herdar polifonia por acidente. O acorde impossível volta em
    `impossiveis`, não como exceção: não pode custar a música inteira (ADR-014).
    """

    def posicionar(
        self, notas: list[NoteEvent], afinacao: tuple[int, ...], max_traste: int = 24
    ) -> Posicionamento: ...


class Exporter(Protocol):
    """Notas posicionadas → arquivo de partitura. Hoje GP5 e MusicXML."""

    def export(self, notes: list[TabNote], out: Path, tuning: tuple[int, ...]) -> Path: ...


class ExportadorDePercussao(Protocol):
    """Ataques de bateria → arquivo de partitura (ADR-044, M2).

    Contrato à parte do `Exporter`, como o `AtribuidorDeAcordes` do `FretAssigner`:
    bateria não tem corda, traste nem afinação, e o tipo impede que ela caia no
    exportador de cordas ou que o baixo passe a aceitar ataques.
    """

    def exportar(self, ataques: list[EventoPercussivo], out: Path) -> Path: ...


class Progresso(Protocol):
    """Recebe o nome de cada estágio quando ele começa (ADR-037).

    Um método só, e nenhum "terminou": o estágio seguinte fecha o anterior, e o
    último fecha quando `transcrever` devolve. Quem desenha sabe disso; o pipeline
    não precisa saber. É o que mantém o `rich` na CLI e fora dos services.
    """

    def inicia(self, etapa: str, detalhe: str = "") -> None: ...
