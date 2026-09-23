"""Estimativa de andamento a partir do áudio (ADR-019).

Dois estimadores independentes, porque medindo as fixtures cada um errou onde o
outro acertou: o `beat_track` leu o `misto` pela metade (45 onde eram 90) e o
`feature.tempo` leu o `groove16` a 117. Sozinho, nenhum dos dois é confiável; o
desacordo entre eles é o sinal honesto de que o resultado merece conferência.
"""

from __future__ import annotations

from collections.abc import Sequence
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


# Quanto o ajuste pode se afastar da estimativa do áudio. O mix é a âncora: as
# notas transcritas refinam o andamento, não o escolhem — transcrição ruim
# arrastaria o resultado para o dobro ou a metade se a busca fosse livre.
_FAIXA = 0.03
_MINIMO_DE_NOTAS = 8
_PASSOS_BPM = 400
_PASSOS_FASE = 120


def residuo(onsets: Sequence[float], bpm: float, fase: float) -> float:
    """Distância mediana de cada onset à semicolcheia mais próxima, em segundos."""
    grade = 60.0 / bpm / 4
    desvio = (np.asarray(onsets) - fase) / grade
    return float(np.median(np.abs(desvio - np.round(desvio)) * grade))


def ajustar(
    onsets: Sequence[float], bpm_inicial: float, faixa: float | None = None
) -> tuple[float, float]:
    """Andamento fracionário e fase da grade, ajustados às notas transcritas.

    `estimar_andamento` devolve inteiro, e arredondar é caro: 107,5 → 108 são
    0,46% de erro, que em 756 s de Equus acumulam 3,5 s — dezenas de posições de
    semicolcheia. O erro não aparece no começo da música, só no fim; é
    exatamente o "ritmo descolando" relatado na escuta.

    Os dois parâmetros são ajustados **juntos** porque são acoplados: medindo as
    sete músicas do acervo, refinar o BPM mantendo a âncora em `t=0` piora quatro
    delas (Equus 34 → 57 ms). Uma grade mais precisa ancorada no lugar errado
    erra mais que uma grade grosseira por acaso alinhada.
    """
    if len(onsets) < _MINIMO_DE_NOTAS:
        return float(bpm_inicial), 0.0

    # `faixa=0` ajusta só a fase: é o caso do BPM que você informou, que manda
    # sempre — a âncora da grade ainda precisa ser encontrada, o número não.
    faixa = _FAIXA if faixa is None else faixa
    passos = _PASSOS_BPM if faixa else 1
    candidatos = np.linspace(bpm_inicial * (1 - faixa), bpm_inicial * (1 + faixa), passos)
    melhor = (float("inf"), float(bpm_inicial), 0.0)
    for bpm in candidatos:
        grade = 60.0 / bpm / 4
        for fase in np.linspace(0.0, grade, _PASSOS_FASE, endpoint=False):
            atual = residuo(onsets, bpm, fase)
            if atual < melhor[0]:
                melhor = (atual, float(bpm), float(fase))
    return melhor[1], melhor[2]
