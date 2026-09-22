"""Métricas de transcrição contra ground truth (Camada 1 do ADR-006).

Duas métricas, porque uma só engana:

- **onset F1** — acertou *quando*. Cego para altura: uma linha inteira uma oitava
  abaixo pontua 1,000 aqui.
- **nota F1** — acertou *quando e qual*, com `offset_ratio=None`, ou seja,
  ignorando a duração. O MuScriptor não é confiável em offset, e cobrar isso
  mediria o sustain do soundfont, não a transcrição.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pretty_midi
from mir_eval.onset import f_measure
from mir_eval.transcription import precision_recall_f1_overlap

from thoth.domain.models import NoteEvent

#: Padrão do mir_eval e da literatura de AMT.
TOLERANCIA_S = 0.05


@dataclass(frozen=True, slots=True)
class Scores:
    onset_f1: float
    note_f1: float
    n_ref: int
    n_est: int


def notas_do_midi(mid: Path, instrumento: int = 0) -> list[NoteEvent]:
    """Lê um instrumento do MIDI como referência, ordenado por onset."""
    notas = sorted(pretty_midi.PrettyMIDI(str(mid)).instruments[instrumento].notes,
                   key=lambda n: (n.start, n.pitch))
    return [
        NoteEvent(pitch=n.pitch, onset_s=float(n.start), offset_s=float(n.end),
                  instrument="electric_bass")
        for n in notas
    ]


def _arrays(notas: Sequence[NoteEvent]) -> tuple[np.ndarray, np.ndarray]:
    intervalos = np.array([[n.onset_s, n.offset_s] for n in notas], dtype=float)
    alturas = np.array([pretty_midi.note_number_to_hz(n.pitch) for n in notas], dtype=float)
    return intervalos, alturas


def avaliar(
    referencia: Sequence[NoteEvent],
    estimativa: Sequence[NoteEvent],
    *,
    tolerancia_s: float = TOLERANCIA_S,
) -> Scores:
    if not referencia:
        raise ValueError("referência vazia: não há o que avaliar")
    if not estimativa:
        return Scores(0.0, 0.0, len(referencia), 0)

    ref_iv, ref_hz = _arrays(referencia)
    est_iv, _ = _arrays(estimativa)
    _, _, onset_f1 = f_measure(ref_iv[:, 0], est_iv[:, 0], window=tolerancia_s)

    # Duração nula faz o mir_eval levantar, e o MuScriptor às vezes emite uma. O
    # descarte vale só aqui: o onset dessa nota é legítimo, quem não a suporta é
    # a métrica que compara intervalos.
    validas = [n for n in estimativa if n.offset_s > n.onset_s]
    if not validas:
        return Scores(round(float(onset_f1), 3), 0.0, len(referencia), len(estimativa))
    val_iv, val_hz = _arrays(validas)
    _, _, nota_f1, _ = precision_recall_f1_overlap(
        ref_iv, ref_hz, val_iv, val_hz, onset_tolerance=tolerancia_s, offset_ratio=None
    )
    return Scores(round(float(onset_f1), 3), round(float(nota_f1), 3),
                  len(referencia), len(estimativa))
