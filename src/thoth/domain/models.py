"""Modelos de domínio. Sem I/O, sem torch, sem dependência de ML."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

#: Afinações padrão, da corda mais grave para a mais aguda, em pitch MIDI.
TUNING_BASS_4 = (28, 33, 38, 43)  # E1 A1 D2 G2
TUNING_BASS_5 = (23, 28, 33, 38, 43)  # B0 E1 A1 D2 G2
TUNING_BASS_6 = (23, 28, 33, 38, 43, 48)  # B0 E1 A1 D2 G2 C3
TUNING_BASS_DROP_D = (26, 33, 38, 43)  # D1 A1 D2 G2

#: As afinações com porta de entrada, por **nome** (ADR-028). Contar cordas não
#: serve de seletor: drop D tem quatro, como a padrão, e nenhuma corda igual.
AFINACOES: dict[str, tuple[int, ...]] = {
    "4": TUNING_BASS_4,
    "5": TUNING_BASS_5,
    "6": TUNING_BASS_6,
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


#: Rótulo que o MuScriptor dá à bateria; nele, `pitch` é a peça GM, não altura.
ROTULO_BATERIA = "drums"


@dataclass(frozen=True, slots=True)
class EventoPercussivo:
    """Ataque de bateria: instante e peça GM (ADR-044).

    Sem altura e sem duração. O MuScriptor fecha a nota de bateria logo depois do
    ataque; isso transporta o instante, não mede sustentação, e um `NoteEvent`
    faria as duas coisas parecerem dado.
    """

    instante_s: float
    peca_gm: int
    rotulo: str = ROTULO_BATERIA

    def __post_init__(self) -> None:
        if self.instante_s < 0:
            raise ValueError(f"instante negativo: {self.instante_s}")
        if not 0 <= self.peca_gm <= 127:
            raise ValueError(f"peça GM fora de 0 a 127: {self.peca_gm}")


@dataclass(frozen=True, slots=True)
class Transcricao:
    """Saída livre do transcritor: notas com altura e ataques de bateria, ordenados."""

    notas: tuple[NoteEvent, ...]
    ataques: tuple[EventoPercussivo, ...]

    def __post_init__(self) -> None:
        if any(n.instrument == ROTULO_BATERIA for n in self.notas):
            raise ValueError(f"nota com rótulo {ROTULO_BATERIA!r}: bateria vai em `ataques`")
        object.__setattr__(
            self, "notas", tuple(sorted(self.notas, key=lambda n: (n.onset_s, n.pitch)))
        )
        object.__setattr__(
            self, "ataques",
            tuple(sorted(self.ataques, key=lambda a: (a.instante_s, a.peca_gm))),
        )

    @classmethod
    def do_muscriptor(cls, notas: list[NoteEvent]) -> Transcricao:
        """Separa na borda o que o MuScriptor entrega junto como nota."""
        return cls(
            notas=tuple(n for n in notas if n.instrument != ROTULO_BATERIA),
            ataques=tuple(
                EventoPercussivo(n.onset_s, n.pitch)
                for n in notas if n.instrument == ROTULO_BATERIA
            ),
        )
