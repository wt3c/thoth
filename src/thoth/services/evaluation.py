"""Métricas de transcrição contra ground truth (Camada 1 do ADR-006).

Duas métricas, porque uma só engana:

- **onset F1** — acertou *quando*. Cego para altura: uma linha inteira uma oitava
  abaixo pontua 1,000 aqui.
- **nota F1** — acertou *quando e qual*, com `offset_ratio=None`, ou seja,
  ignorando a duração. O MuScriptor não é confiável em offset, e cobrar isso
  mediria o sustain do soundfont, não a transcrição.
- **nota+offset F1** e **razão de duração** — acertou *quanto tempo* (ADR-023).
  São **informativas, não critério de aprovação**: a ressalva acima continua valendo, e é por
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
from mir_eval.util import match_events

from thoth.domain.models import EventoPercussivo, NoteEvent

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


# --- Polifonia e bateria (ADR-044) -------------------------------------------------


@dataclass(frozen=True, slots=True)
class Prf:
    precisao: float
    revocacao: float
    f1: float


_ZERO = Prf(0.0, 0.0, 0.0)


def _prf(acertos: int, n_ref: int, n_est: int) -> Prf:
    p = acertos / n_est if n_est else 0.0
    r = acertos / n_ref if n_ref else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return Prf(round(p, 3), round(r, 3), round(f, 3))


@dataclass(frozen=True, slots=True)
class ScoresPolifonicos:
    """Piano e guitarra: cada nota do acorde conta. Duração não é cobrada."""

    ataque: Prf
    nota: Prf
    n_ref: int
    n_est: int


def avaliar_polifonico(
    referencia: Sequence[NoteEvent],
    estimativa: Sequence[NoteEvent],
    *,
    tolerancia_s: float = TOLERANCIA_S,
) -> ScoresPolifonicos:
    """Precisão, revocação e F1 de ataque (cego para altura) e de nota (ataque + altura).

    O casamento é um para um: seis notas no mesmo instante precisam de seis
    estimadas, e não de um ataque só, como no `f_measure` de onsets do `avaliar`.
    """
    if not referencia:
        raise ValueError("referência vazia: não há o que avaliar")
    if not estimativa:
        return ScoresPolifonicos(_ZERO, _ZERO, len(referencia), 0)
    ref_iv, ref_hz = _arrays(referencia)
    est_iv, est_hz = _arrays(estimativa)
    # Casar só por instante: altura igual para todas neutraliza o critério de altura.
    uma_altura = np.full(len(referencia), 440.0), np.full(len(estimativa), 440.0)
    ataques = match_notes(ref_iv, uma_altura[0], est_iv, uma_altura[1],
                          onset_tolerance=tolerancia_s, offset_ratio=None)
    notas = match_notes(ref_iv, ref_hz, est_iv, est_hz,
                        onset_tolerance=tolerancia_s, offset_ratio=None)
    n_ref, n_est = len(referencia), len(estimativa)
    return ScoresPolifonicos(_prf(len(ataques), n_ref, n_est), _prf(len(notas), n_ref, n_est),
                             n_ref, n_est)


def revocacao_por_acorde(
    referencia: Sequence[NoteEvent],
    estimativa: Sequence[NoteEvent],
    *,
    tolerancia_s: float = TOLERANCIA_S,
) -> dict[int, tuple[int, int]]:
    """`{tamanho do acorde: (notas casadas, notas na referência)}` — o teto do ADR-011.

    O acorde é o da **referência**: notas que começam a menos de `tolerancia_s` da
    primeira do grupo, a mesma regra do `services/acordes.py`. Só revocação, porque
    uma nota falsa não pertence a acorde nenhum da referência. O casamento é o mesmo
    do `avaliar_polifonico`, um para um por ataque e altura.
    """
    if not referencia:
        raise ValueError("referência vazia: não há o que avaliar")
    ordem = sorted(range(len(referencia)), key=lambda i: referencia[i].onset_s)
    grupos: list[list[int]] = []
    for i in ordem:
        if grupos and referencia[i].onset_s - referencia[grupos[-1][0]].onset_s < tolerancia_s:
            grupos[-1].append(i)
        else:
            grupos.append([i])
    casadas: set[int] = set()
    if estimativa:
        ref_iv, ref_hz = _arrays(referencia)
        est_iv, est_hz = _arrays(estimativa)
        pares = match_notes(ref_iv, ref_hz, est_iv, est_hz,
                            onset_tolerance=tolerancia_s, offset_ratio=None)
        casadas = {int(r) for r, _ in pares}
    contagem: dict[int, tuple[int, int]] = {}
    for grupo in grupos:
        acertos, total = contagem.get(len(grupo), (0, 0))
        contagem[len(grupo)] = (acertos + len(casadas.intersection(grupo)), total + len(grupo))
    return dict(sorted(contagem.items()))


@dataclass(frozen=True, slots=True)
class ScoresBateria:
    """Ataque certo na peça certa, por peça GM. Sem métrica de duração."""

    micro: Prf
    #: Média do F1 das peças **presentes na referência**. Peça só na estimativa não
    #: tem revocação definida; ela pesa no micro, como falso positivo, e não aqui.
    macro_f1: float
    por_peca: dict[int, Prf]
    n_ref: int
    n_est: int


def avaliar_bateria(
    referencia: Sequence[EventoPercussivo],
    estimativa: Sequence[EventoPercussivo],
    *,
    tolerancia_s: float = TOLERANCIA_S,
) -> ScoresBateria:
    if not referencia:
        raise ValueError("referência vazia: não há o que avaliar")

    def instantes(eventos: Sequence[EventoPercussivo], peca: int) -> np.ndarray:
        return np.array(sorted(a.instante_s for a in eventos if a.peca_gm == peca))

    por_peca: dict[int, Prf] = {}
    acertos_total = 0
    for peca in sorted({a.peca_gm for a in referencia} | {a.peca_gm for a in estimativa}):
        ref, est = instantes(referencia, peca), instantes(estimativa, peca)
        acertos = len(match_events(ref, est, tolerancia_s)) if len(ref) and len(est) else 0
        acertos_total += acertos
        if len(ref):
            por_peca[peca] = _prf(acertos, len(ref), len(est))
    macro = round(float(np.mean([s.f1 for s in por_peca.values()])), 3)
    return ScoresBateria(_prf(acertos_total, len(referencia), len(estimativa)), macro,
                         por_peca, len(referencia), len(estimativa))
