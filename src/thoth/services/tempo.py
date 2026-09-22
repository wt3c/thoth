"""Estimativa de andamento a partir do áudio (ADR-019).

Dois estimadores independentes, porque medindo as fixtures cada um errou onde o
outro acertou: o `beat_track` leu o `misto` pela metade (45 onde eram 90) e o
`feature.tempo` leu o `groove16` a 117. Sozinho, nenhum dos dois é confiável; o
desacordo entre eles é o sinal honesto de que o resultado merece conferência.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import librosa
import numpy as np
import numpy.typing as npt

# Faixa musical usual. Serve para desfazer o erro de dobro/metade, que é o modo
# de falha clássico de todo estimador de andamento.
_MIN, _MAX = 70.0, 160.0
_TOLERANCIA = 0.05


@dataclass(frozen=True, slots=True)
class Andamento:
    """O palpite e o quanto ele merece crédito — nunca um sem o outro."""

    bpm: int
    conferencia: int
    confiavel: bool


def dobrar_para_faixa(bpm: float) -> float:
    """Dobra ou divide até cair na faixa musical usual."""
    if bpm <= 0:
        return bpm
    while bpm < _MIN:
        bpm *= 2
    while bpm >= _MAX:
        bpm /= 2
    return bpm


def _primeiro(valor: npt.ArrayLike) -> float:
    """O librosa devolve ora escalar, ora array de um elemento, conforme a versão."""
    return float(np.asarray(valor).ravel()[0])


def estimar_andamento(wav: Path) -> Andamento:
    """Andamento do áudio inteiro, pelo mix: é onde a bateria dá o pulso."""
    y, sr = librosa.load(wav, sr=22050, mono=True)
    principal = _primeiro(librosa.beat.beat_track(y=y, sr=sr)[0])
    envelope = librosa.onset.onset_strength(y=y, sr=sr)
    segundo = _primeiro(librosa.feature.tempo(onset_envelope=envelope, sr=sr))

    bpm = dobrar_para_faixa(principal)
    conferencia = dobrar_para_faixa(segundo)
    return Andamento(
        bpm=round(bpm),
        conferencia=round(conferencia),
        confiavel=abs(bpm - conferencia) <= _TOLERANCIA * bpm,
    )
