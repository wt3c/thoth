"""Modelos de domínio. Sem I/O, sem torch, sem dependência de ML."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

#: Afinações padrão, da corda mais grave para a mais aguda, em pitch MIDI.
TUNING_BASS_4 = (28, 33, 38, 43)  # E1 A1 D2 G2
TUNING_BASS_5 = (23, 28, 33, 38, 43)  # B0 E1 A1 D2 G2
TUNING_BASS_DROP_D = (26, 33, 38, 43)  # D1 A1 D2 G2


@dataclass(frozen=True, slots=True)
class AudioAsset:
    """Áudio normalizado (WAV 44.1 kHz) pronto para os estágios seguintes."""

    wav: Path
    source_id: str
    title: str
    artist: str | None = None
    duration_s: float = 0.0


@dataclass(frozen=True, slots=True)
class NoteEvent:
    """Nota transcrita, ainda em tempo absoluto (segundos)."""

    pitch: int
    onset_s: float
    offset_s: float
    instrument: str

    @property
    def duration_s(self) -> float:
        return self.offset_s - self.onset_s


@dataclass(frozen=True, slots=True)
class TabNote:
    """Nota posicionada no braço do instrumento."""

    event: NoteEvent
    string: int  # 0 = corda mais grave da afinação
    fret: int
