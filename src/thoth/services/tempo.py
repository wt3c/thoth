"""Estimativa de andamento a partir do áudio (ADR-019).

Dois estimadores independentes, porque medindo as fixtures cada um errou onde o
outro acertou: o `beat_track` leu o `misto` pela metade (45 onde eram 90) e o
`feature.tempo` leu o `groove16` a 117. Sozinho, nenhum dos dois é confiável; o
desacordo entre eles é o sinal honesto de que o resultado merece conferência.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, replace
from itertools import pairwise
from pathlib import Path

import librosa
import numpy as np
import numpy.typing as npt

from thoth.services.rhythm import MapaDeAndamento, para_ticks

# Faixa musical usual. Serve para desfazer o erro de dobro/metade, que é o modo
# de falha clássico de todo estimador de andamento.
_MIN, _MAX = 70.0, 160.0
#: Faixa do que se aceita como andamento *informado*, larga de propósito: fora dela
#: não há música, há erro de digitação. É mais ampla que a faixa musical acima, que
#: serve para desfazer dobro/metade de uma estimativa, não para recusar um pedido.
BPM_MINIMO, BPM_MAXIMO = 20, 300
_TOLERANCIA = 0.05
# Abaixo disto a taxa de colisão é ruído: numa música de 4 notas, uma colisão é 25%.
_MINIMO_DE_NOTAS = 8


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


# Acima disto a grade é grosseira demais para o material. Medido nas sete músicas do
# acervo: no BPM certo a colisão fica entre 0,0 e 2,8%; na grade pela metade, de 20 a 37%
# nos casos em que há semicolcheia. 10% está longe dos dois lados.
_LIMIAR_DE_COLISAO = 0.10
# Teto do desdobramento. Sem ele, gravação com ataques muito densos (trêmolo, ruído
# de transcrição) seria dobrada até um andamento que instrumento nenhum toca.
_DOBRAS_MAXIMAS = 2


def colisao_na_grade(onsets: Sequence[float], bpm: float) -> float:
    """Fração dos ataques que caem no mesmo tick de semicolcheia que outro.

    É a medida de "a grade é grosseira demais para este material". Vale num
    sentido só: colisão alta prova grade grossa; colisão baixa não prova nada —
    música sem semicolcheia não colide nem num andamento errado pela metade.
    """
    ticks = [para_ticks(t, bpm) for t in onsets]
    return (len(ticks) - len(set(ticks))) / len(ticks)


def desdobrar(onsets: Sequence[float], bpm: float) -> float:
    """Desfaz a dobra de `dobrar_para_faixa` quando as notas mostram que ela errou.

    `dobrar_para_faixa` decide antes de existir nota alguma — o andamento é
    estimado do mix, e a transcrição só vem depois da separação. Uma música a 170
    BPM sai dobrada para 85, e aí a semicolcheia da grade tem o dobro da duração:
    ataques distintos caem no mesmo tick e `monofonizar` os descarta. Medido: 64
    notas viram 33.

    Dobrar de volta é assimétrico de propósito. Grade mais fina nunca colide
    mais, então "menos colisão" escolheria sempre o candidato mais rápido; o que
    autoriza dobrar é a colisão estar **alta**, não o dobro estar melhor
    (ADR-024).
    """
    if bpm <= 0 or len(onsets) < _MINIMO_DE_NOTAS:
        return float(bpm)
    for _ in range(_DOBRAS_MAXIMAS):
        if colisao_na_grade(onsets, bpm) <= _LIMIAR_DE_COLISAO:
            break
        bpm *= 2
    return float(bpm)


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
    tempos = np.asarray(onsets)
    melhor = (float("inf"), float(bpm_inicial), 0.0)
    for bpm in candidatos:
        # Todas as fases de uma vez: a mesma conta do `residuo`, linha a linha.
        # O `argmin` devolve a primeira, como o `<` estrito do laço que substituiu.
        grade = 60.0 / bpm / 4
        fases = np.linspace(0.0, grade, _PASSOS_FASE, endpoint=False)
        desvio = (tempos[None, :] - fases[:, None]) / grade
        residuos = np.median(np.abs(desvio - np.round(desvio)) * grade, axis=1)
        i = int(np.argmin(residuos))
        if residuos[i] < melhor[0]:
            melhor = (float(residuos[i]), float(bpm), float(fases[i]))
    return melhor[1], melhor[2]


# Mapa de andamento (ADR-034, etapa 2 no ADR-053). Cada número aqui foi medido fora
# da amostra nas 21 fontes do acervo: janela de 20 s, faixa de ±10% em volta do
# andamento global, custo em ms e penalidade 2000 por troca — com ela nenhuma música
# piora e as estáveis não ganham troca nenhuma.
_JANELA_S = 20.0
_FASES = 128
_PASSO_BPM = 0.05
_FAIXA_DO_MAPA = 0.10
_PENALIDADE = 2000.0
_REFINO_BPM = 0.1
_PASSO_REFINO = 0.005


def _programacao_dinamica(
    on: npt.NDArray[np.float64], bpm: float, penalidade: float
) -> tuple[list[float], float]:
    """Andamento de cada janela e fase da grade em `t=0`, com a fase herdada entre janelas.

    O estado no início de cada janela é (andamento corrente, fase da semicolcheia),
    e a fase não é livre: sai da janela anterior. Ficar no andamento é de graça;
    trocar custa `penalidade` (ms·nota). O custo da janela é a mediana do resíduo
    vezes o número de notas.
    """
    cand = np.arange(bpm * (1 - _FAIXA_DO_MAPA), bpm * (1 + _FAIXA_DO_MAPA), _PASSO_BPM)
    nb = len(cand)
    fases = np.arange(_FASES) / _FASES
    nj = int(on.max() // _JANELA_S) + 1
    valor = np.zeros((_FASES, nb))  # fase e andamento iniciais livres
    trilha = []
    for k in range(nj):
        t0 = k * _JANELA_S
        sel = on[(on >= t0) & (on < t0 + _JANELA_S)] - t0
        n = len(sel)
        # custo[f, b']: a janela tocada no andamento b' a partir da fase f
        if n:
            s = fases[:, None, None] + sel[None, None, :] * cand[None, :, None] / 15.0
            d = np.abs(s - np.round(s)) * (15.0 / cand)[None, :, None]
            custo = np.median(d, axis=2) * 1000 * n
        else:
            custo = np.zeros((_FASES, nb))
        # b' a partir de (f, b): ficar em b' = b de graça, ou trocar pela penalidade
        troca = valor.min(axis=1, keepdims=True) + penalidade
        entrar = np.minimum(valor, troca)
        veio_de = np.where(valor <= troca, -1, valor.argmin(axis=1)[:, None])
        total = entrar + custo
        # a fase no fim da janela é a do início da seguinte
        fim = (fases[:, None] + _JANELA_S * cand[None, :] / 15.0) % 1.0
        idx = np.round(fim * _FASES).astype(int) % _FASES
        proximo = np.full((_FASES, nb), np.inf)
        origem = np.full((_FASES, nb), -1)
        colunas = np.arange(nb)
        for f in range(_FASES):
            alvo = idx[f]
            melhora = total[f] < proximo[alvo, colunas]
            proximo[alvo[melhora], colunas[melhora]] = total[f][melhora]
            origem[alvo[melhora], colunas[melhora]] = f
        trilha.append((origem, veio_de))
        valor = proximo
    f, b = (int(i) for i in np.unravel_index(np.argmin(valor), valor.shape))
    serie = []
    for origem, veio_de in reversed(trilha):
        f0 = origem[f, b]
        serie.append(float(cand[b]))
        vb = veio_de[f0, b]
        f, b = int(f0), int(b if vb == -1 else vb)
    serie.reverse()
    return serie, float(f) / _FASES


def _na_barra(
    on: npt.NDArray[np.float64],
    mapa: MapaDeAndamento,
    instante: float,
    bpm: float,
    limite: float,
) -> MapaDeAndamento:
    """Acrescenta a troca na barra de compasso que melhor serve às notas entre as vizinhas.

    A programação dinâmica só troca na fronteira de uma janela de 20 s, e com a fase
    herdada a troca no meio da janela sai deslocada de uma janela inteira ou mais: a
    grade que segue um andamento depois da troca real chega defasada à fronteira.
    Então `instante` diz só *que* houve troca entre a anterior e `limite`; *onde*, é a
    barra que deixa as notas desse intervalo mais perto da grade — a banda troca de
    andamento na barra. A grade continua sem salto através de cada candidata. Sem
    barra no intervalo, o trecho é mais curto que um compasso e não entra.
    """
    compasso = 240.0 / mapa.bpm
    anterior = mapa.trocas[-1][0] if mapa.trocas else 0.0
    primeira = math.floor(mapa.para_partitura(anterior) / compasso) + 1
    ultima = math.ceil(mapa.para_partitura(limite) / compasso) - 1
    afetados = on[(on >= anterior) & (on < limite)]
    if primeira > ultima or not len(afetados):
        return mapa
    # Antes da candidata vale o mapa como está; depois, a reta do andamento novo.
    andamento_antes = mapa.trocas[-1][1] if mapa.trocas else mapa.bpm
    partitura_antes = np.array([mapa.para_partitura(float(t)) for t in afetados])
    grade = 15.0 / mapa.bpm
    # O passo de 0,05 da programação dinâmica deriva ~10 ms por minuto, o bastante
    # para pesar na escolha da barra: o andamento novo se refina junto com ela.
    novos = bpm + np.arange(-_REFINO_BPM, _REFINO_BPM + _PASSO_REFINO / 2, _PASSO_REFINO)
    melhor = (math.inf, math.inf, mapa)
    for m in range(primeira, ultima + 1):
        c = mapa.para_audio(m * compasso)
        depois = afetados >= c
        antes = partitura_antes[~depois] / grade
        escala_antes = grade * mapa.bpm / andamento_antes
        custo_antes = float(np.sum(np.abs(antes - np.round(antes)))) * escala_antes
        decorrido = afetados[depois][None, :] - c
        posicao = (m * compasso + decorrido * novos[:, None] / mapa.bpm) / grade
        custos = np.sum(np.abs(posicao - np.round(posicao)), axis=1) * grade * mapa.bpm / novos
        k = int(np.argmin(custos))
        custo = custo_antes + float(custos[k])
        # Empate fica com a barra mais perto da troca da programação dinâmica.
        if (custo, abs(c - instante)) < melhor[:2]:
            troca = (c, float(novos[k]))
            melhor = (custo, abs(c - instante), replace(mapa, trocas=(*mapa.trocas, troca)))
    return melhor[2]


def mapa_de_andamento(
    onsets: Sequence[float], bpm: float, penalidade: float = _PENALIDADE
) -> MapaDeAndamento:
    """O andamento de cada trecho da música, com as trocas na barra de compasso.

    `bpm` é o andamento global, em volta do qual cada trecho pode ficar a ±10%. A
    música estável sai com um trecho só — e aí quem chamou fica com o `ajustar` de
    sempre, que mede mais fino. Trecho a mais de 10% do global é escrito no
    andamento mais próximo dentro da faixa: é o limite conhecido (ADR-034).
    """
    on = np.sort(np.asarray(onsets, dtype=float))
    if len(on) < _MINIMO_DE_NOTAS or on.max() < 2 * _JANELA_S:
        return MapaDeAndamento(float(bpm))
    serie, fase = _programacao_dinamica(on, bpm, penalidade)
    grade = 15.0 / serie[0]
    # Fase da grade em segundos, recuada como no `recuo_de_fase`: tempo negativo
    # nenhum formato de partitura representa.
    em_segundos = ((-fase) % 1.0) * grade
    recuo = em_segundos if on[0] >= em_segundos else em_segundos - grade
    brutas = [
        ((k + 1) * _JANELA_S, depois)
        for k, (antes, depois) in enumerate(pairwise(serie))
        if antes != depois
    ]
    mapa = _nas_barras(on, MapaDeAndamento(serie[0], recuo), brutas)
    if not mapa.trocas:
        return mapa
    # Com a troca no meio de uma janela, a programação dinâmica compensa no andamento
    # do primeiro trecho, e é ele que define a grade inteira. Ajustado às notas antes
    # da primeira troca, as barras se escolhem de novo sobre a grade certa.
    primeiro = on[on < mapa.trocas[0][0]]
    if len(primeiro) < _MINIMO_DE_NOTAS:
        return mapa
    andamento, fase = ajustar(primeiro.tolist(), mapa.bpm)
    grade = 15.0 / andamento
    recuo = fase if not fase or on[0] >= fase else fase - grade
    return _nas_barras(on, MapaDeAndamento(andamento, recuo), brutas)


def _nas_barras(
    on: npt.NDArray[np.float64], mapa: MapaDeAndamento, brutas: list[tuple[float, float]]
) -> MapaDeAndamento:
    for i, (instante, novo) in enumerate(brutas):
        limite = brutas[i + 1][0] if i + 1 < len(brutas) else float(on.max()) + _JANELA_S
        mapa = _na_barra(on, mapa, instante, novo, limite)
    return mapa
