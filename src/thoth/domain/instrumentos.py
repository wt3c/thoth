"""Perfis de instrumento da expansão multi-instrumento (ADR-044).

Um perfil diz o que o Thoth aceita do MuScriptor para uma parte-alvo: quais
rótulos, de qual stem do Demucs, com qual programa GM e, se houver braço, qual
afinação. Os três rótulos de guitarra ficam em perfis separados: somá-los faria
duas guitarras virarem um acorde impossível.

Por enquanto só a medição usa estes perfis; o pipeline segue produzindo baixo.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from thoth.domain.models import ROTULO_BATERIA, TUNING_BASS_4

Familia = Literal["baixo", "bateria", "piano", "guitarra"]

#: Afinação padrão de guitarra, E2 A2 D3 G3 B3 E4, da corda mais grave para a mais aguda.
TUNING_GUITARRA_6 = (40, 45, 50, 55, 59, 64)


@dataclass(frozen=True, slots=True)
class PerfilInstrumento:
    familia: Familia
    rotulos: frozenset[str]
    stem: str
    programa_gm: int
    afinacao: tuple[int, ...] | None = None


PERFIS: dict[str, PerfilInstrumento] = {
    "baixo": PerfilInstrumento(
        "baixo", frozenset({"electric_bass", "acoustic_bass", "contrabass"}), "bass", 33,
        TUNING_BASS_4,
    ),
    "bateria": PerfilInstrumento("bateria", frozenset({ROTULO_BATERIA}), "drums", 0),
    "piano-acustico": PerfilInstrumento("piano", frozenset({"acoustic_piano"}), "other", 0),
    "piano-eletrico": PerfilInstrumento("piano", frozenset({"electric_piano"}), "other", 4),
    "guitarra-acustica": PerfilInstrumento(
        "guitarra", frozenset({"acoustic_guitar"}), "other", 25, TUNING_GUITARRA_6
    ),
    "guitarra-limpa": PerfilInstrumento(
        "guitarra", frozenset({"clean_electric_guitar"}), "other", 27, TUNING_GUITARRA_6
    ),
    "guitarra-distorcida": PerfilInstrumento(
        "guitarra", frozenset({"distorted_electric_guitar"}), "other", 30, TUNING_GUITARRA_6
    ),
}
