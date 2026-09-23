"""Modelos de domínio. Sem I/O, sem torch, sem dependência de ML."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

#: Afinações padrão, da corda mais grave para a mais aguda, em pitch MIDI.
TUNING_BASS_4 = (28, 33, 38, 43)  # E1 A1 D2 G2
TUNING_BASS_5 = (23, 28, 33, 38, 43)  # B0 E1 A1 D2 G2
TUNING_BASS_DROP_D = (26, 33, 38, 43)  # D1 A1 D2 G2

#: As afinações com porta de entrada, por **nome** (ADR-028). Contar cordas não
#: serve de seletor: drop D tem quatro, como a padrão, e nenhuma corda igual.
AFINACOES: dict[str, tuple[int, ...]] = {
    "4": TUNING_BASS_4,
    "5": TUNING_BASS_5,
    "drop-d": TUNING_BASS_DROP_D,
}


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
        """Quanto a nota ocupa — que **não** é onde ela parou de soar (ADR-033).

        O MuScriptor preenche `offset_s` com o `onset_s` da nota seguinte: medido
        no acervo, 83% a 99,7% das notas têm lacuna exatamente zero, e o modelo
        real, contra uma fixture de notas de 0,45 s separadas por 0,10 s de
        silêncio, devolveu vãos contíguos (0,51→1,09→1,65→2,20). Então isto é
        tempo **até a próxima nota**, e nada aqui distingue staccato de legato.
        """
        return self.offset_s - self.onset_s


@dataclass(frozen=True, slots=True)
class TabNote:
    """Nota posicionada no braço do instrumento."""

    event: NoteEvent
    string: int  # 0 = corda mais grave da afinação
    fret: int
