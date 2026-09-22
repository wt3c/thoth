"""Altura MIDI → nome da nota (ADR-018)."""

from __future__ import annotations

# Sem armadura de clave o acidente é ambíguo: a tecla preta entre lá e si é
# tanto A# quanto Bb. O Thoth não estima tonalidade, então fixa o sustenido.
_NOMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")


def nome_da_nota(pitch: int) -> str:
    """Classe de altura, sem oitava: a oitava já está na corda e no traste."""
    return _NOMES[pitch % 12]
