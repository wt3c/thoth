"""Contratos entre estágios. Cada adapter concreto implementa um destes."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from thoth.domain.models import AudioAsset, NoteEvent, TabNote


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


class Exporter(Protocol):
    """Notas posicionadas → arquivo (GP5, MusicXML, MIDI)."""

    def export(self, notes: list[TabNote], out: Path, tuning: tuple[int, ...]) -> Path: ...
