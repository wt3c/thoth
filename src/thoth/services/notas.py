"""Altura MIDI → nome da nota (ADR-018, ADR-031)."""

from __future__ import annotations

# Sem tonalidade o acidente é ambíguo: a tecla preta entre lá e si é tanto A#
# quanto Bb. O sustenido continua sendo o default — é o que o Thoth escreve
# quando não sabe o tom, ou quando sabe sem confiança (ADR-031).
_SUSTENIDOS = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
_BEMOIS = ("C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B")


def nome_da_nota(pitch: int, *, bemois: bool = False) -> str:
    """Classe de altura, sem oitava: a oitava já está na corda e no traste."""
    return (_BEMOIS if bemois else _SUSTENIDOS)[pitch % 12]
