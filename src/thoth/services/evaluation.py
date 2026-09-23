"""Métricas de transcrição contra ground truth (Camada 1 do ADR-006).

Duas métricas, porque uma só engana:

- **onset F1** — acertou *quando*. Cego para altura: uma linha inteira uma oitava
  abaixo pontua 1,000 aqui.
- **nota F1** — acertou *quando e qual*, com `offset_ratio=None`, ou seja,
  ignorando a duração. O MuScriptor não é confiável em offset, e cobrar isso
  mediria o sustain do soundfont, não a transcrição.
- **nota+offset F1** e **razão de duração** — acertou *quanto tempo* (ADR-023).
  São **informativas, não portão**: a ressalva acima continua valendo, e é por
  isso que estas duas não entram em nenhum piso de regressão. Existem porque sem
  elas não havia régua nenhuma para sustentação, e o corte de duração que o
  ADR-022 corrigiu passou invisível pelas duas primeiras — as duas pontuavam
  1,000 enquanto um quarto da música virava pausa.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pretty_midi
from mir_eval.onset import f_measure
from mir_eval.transcription import match_notes, precision_recall_f1_overlap

from thoth.domain.models import NoteEvent

#: Padrão do mir_eval e da literatura de AMT.
TOLERANCIA_S = 0.05
#: Quanto a duração pode errar e ainda contar como a mesma nota — padrão do mir_eval.
OFFSET_RATIO = 0.2


@dataclass(frozen=True, slots=True)
class Scores:
    onset_f1: float
    note_f1: float
    n_ref: int
    n_est: int
    #: Nota F1 cobrando também a duração, com `offset_ratio=OFFSET_RATIO`.
    nota_offset_f1: float
    #: Mediana de duração estimada ÷ duração de referência, nas notas casadas por
    #: onset e altura. `None` quando nenhuma casou: zero se leria como duração nula.
    duracao_ratio: float | None


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


def _razao_de_duracao(
    ref_iv: np.ndarray, ref_hz: np.ndarray, est_iv: np.ndarray, est_hz: np.ndarray,
    tolerancia_s: float,
) -> float | None:
    """Mediana de duração estimada ÷ referência, só nas notas que casaram.

    O casamento ignora a duração (`offset_ratio=None`) de propósito: é a razão
    que se quer medir, então filtrar por ela antes escolheria só os acertos.
    """
    pares = match_notes(
        ref_iv, ref_hz, est_iv, est_hz, onset_tolerance=tolerancia_s, offset_ratio=None
    )
    if not pares:
        return None
    razoes = [
        (est_iv[j, 1] - est_iv[j, 0]) / (ref_iv[i, 1] - ref_iv[i, 0]) for i, j in pares
    ]
    return round(float(np.median(razoes)), 3)


def avaliar(
    referencia: Sequence[NoteEvent],
    estimativa: Sequence[NoteEvent],
    *,
    tolerancia_s: float = TOLERANCIA_S,
) -> Scores:
    if not referencia:
        raise ValueError("referência vazia: não há o que avaliar")
    if not estimativa:
        return Scores(0.0, 0.0, len(referencia), 0, 0.0, None)

    ref_iv, ref_hz = _arrays(referencia)
    est_iv, _ = _arrays(estimativa)
    _, _, onset_f1 = f_measure(ref_iv[:, 0], est_iv[:, 0], window=tolerancia_s)

    # Duração nula faz o mir_eval levantar, e o MuScriptor às vezes emite uma. O
    # descarte vale só aqui: o onset dessa nota é legítimo, quem não a suporta é
    # a métrica que compara intervalos.
    validas = [n for n in estimativa if n.offset_s > n.onset_s]
    if not validas:
        return Scores(round(float(onset_f1), 3), 0.0, len(referencia), len(estimativa),
                      0.0, None)
    val_iv, val_hz = _arrays(validas)
    _, _, nota_f1, _ = precision_recall_f1_overlap(
        ref_iv, ref_hz, val_iv, val_hz, onset_tolerance=tolerancia_s, offset_ratio=None
    )
    _, _, offset_f1, _ = precision_recall_f1_overlap(
        ref_iv, ref_hz, val_iv, val_hz, onset_tolerance=tolerancia_s,
        offset_ratio=OFFSET_RATIO,
    )
    return Scores(round(float(onset_f1), 3), round(float(nota_f1), 3),
                  len(referencia), len(estimativa), round(float(offset_f1), 3),
                  _razao_de_duracao(ref_iv, ref_hz, val_iv, val_hz, tolerancia_s))
