"""Compara andamento e figuras sem corrigir a velocidade da estimativa para pontuá-la."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from itertools import pairwise
from statistics import median

import numpy as np


@dataclass(frozen=True, slots=True)
class EventoRitmico:
    altura: int
    inicio_s: float
    duracao_s: float
    inicio_pulsos: float
    duracao_pulsos: float
    #: Altura da corda solta: compara a digitação entre baixos de 4 e de 5 cordas.
    corda: int | None = None


@dataclass(frozen=True, slots=True)
class JanelaRitmica:
    """Velocidade dos intervalos que começam neste trecho da referência."""

    inicio_s: float
    intervalos: int
    velocidade_relativa: float


@dataclass(frozen=True, slots=True)
class ComparacaoRitmica:
    notas_referencia: int
    notas_geradas: int
    omissoes: int
    extras: int
    alturas_divergentes: int
    pares: int
    alinhamento_ambiguo: bool
    intervalos_comparaveis: int
    intervalos_ambiguos: int
    intervalos_corretos: int
    duracoes_corretas: int
    velocidade_relativa: float | None
    velocidade_p10: float | None
    velocidade_p90: float | None
    erro_intervalo_pulsos_mediano: float | None
    erro_duracao_pulsos_mediano: float | None
    janelas: tuple[JanelaRitmica, ...]
    posicoes_corretas: int
    digitacoes_comparaveis: int
    digitacoes_corretas: int


@dataclass(frozen=True, slots=True)
class Boletim:
    """Uma fração por dimensão; `None` quando não há material para comparar."""

    andamento: float | None
    figuras: float | None
    posicao_no_pulso: float | None
    altura: float
    digitacao: float | None


#: Janela com velocidade dentro disto conta como andamento certo.
_TOLERANCIA_DE_ANDAMENTO = 0.04


def _alinhar(
    ref: Sequence[EventoRitmico],
    est: Sequence[EventoRitmico],
) -> tuple[list[tuple[int, int]], int, int, int, bool]:
    """Distância de edição unitária de alturas; o relógio não escolhe os pares.

    Repetições podem admitir vários caminhos mínimos. O desempate favorece a
    diagonal, e a ambiguidade fica explícita no relatório.
    """
    n, m = len(ref), len(est)
    dist = np.empty((n + 1, m + 1), dtype=np.int32)
    colunas = np.arange(m + 1)
    dist[0] = colunas
    alturas = np.array([e.altura for e in est])
    for i, evento in enumerate(ref, start=1):
        direto = np.minimum(dist[i - 1, 1:] + 1, dist[i - 1, :-1] + (alturas != evento.altura))
        # Inserir j-k eventos custa j-k. O mínimo acumulado de custo[k]-k
        # calcula a recorrência da linha inteira sem um segundo laço Python.
        dist[i] = np.minimum.accumulate(np.concatenate(([i], direto - colunas[1:]))) + colunas
    i, j = n, m
    pares: list[tuple[int, int]] = []
    omissoes = extras = divergentes = 0
    ambiguo = False
    while i or j:
        diagonal = bool(
            i and j and dist[i, j] == dist[i - 1, j - 1] + (ref[i - 1].altura != est[j - 1].altura)
        )
        remover = bool(i and dist[i, j] == dist[i - 1, j] + 1)
        inserir = bool(j and dist[i, j] == dist[i, j - 1] + 1)
        ambiguo |= diagonal + remover + inserir > 1
        if diagonal:
            if ref[i - 1].altura == est[j - 1].altura:
                pares.append((i - 1, j - 1))
            else:
                divergentes += 1
            i, j = i - 1, j - 1
        elif remover:
            omissoes += 1
            i -= 1
        else:
            extras += 1
            j -= 1
    return list(reversed(pares)), omissoes, extras, divergentes, ambiguo


def _corridas(eventos: Sequence[EventoRitmico]) -> list[int]:
    """Tamanho da sequência de mesma altura a que cada evento pertence."""
    tamanhos: list[int] = []
    inicio = 0
    for fim in range(1, len(eventos) + 1):
        if fim == len(eventos) or eventos[fim].altura != eventos[inicio].altura:
            tamanhos.extend([fim - inicio] * (fim - inicio))
            inicio = fim
    return tamanhos


def comparar_ritmo(
    referencia: Sequence[EventoRitmico],
    estimativa: Sequence[EventoRitmico],
    janela_s: float = 20.0,
) -> ComparacaoRitmica:
    """Avalia arquivos na ordem de execução, sem DTW, deslocamento ou escala.

    Alturas só estabelecem âncoras melódicas; omissões, extras e substituições
    são contadas separadamente. IOIs usam apenas pares consecutivos em ambas as
    sequências. Uma nota perdida não vira um intervalo longo supostamente certo.
    Velocidade 2 significa tocar duas vezes mais rápido. Pulso = semínima.
    A mediana global esconde um trecho acelerado em música longa; por isso a
    velocidade também sai por janela de `janela_s` no relógio da referência.

    Numa repetição de mesma altura com tamanhos diferentes nos dois lados, as
    alturas não dizem qual nota falta: o par consecutivo pode saltar um ataque e
    medir meia velocidade. Intervalos que tocam essa repetição são contados como
    ambíguos e ficam fora da velocidade e do erro de intervalo.
    """
    if not referencia:
        raise ValueError("referência vazia: não há ritmo para avaliar")
    if janela_s <= 0:
        raise ValueError(f"janela precisa ser positiva: {janela_s}")
    pares, omissoes, extras, divergentes, ambiguo = _alinhar(referencia, estimativa)
    erros_duracao = [
        abs(estimativa[j].duracao_pulsos - referencia[i].duracao_pulsos) for i, j in pares
    ]
    # Posição dentro da semínima: anacruse e compasso 3/4 deslocariam o compasso
    # inteiro sem mudar o ritmo, e um pulso inteiro de diferença não é erro audível.
    posicoes = sum(
        abs((estimativa[j].inicio_pulsos - referencia[i].inicio_pulsos + 0.5) % 1.0 - 0.5) <= 1e-6
        for i, j in pares
    )
    digitacoes = [
        referencia[i].corda == estimativa[j].corda
        for i, j in pares
        if referencia[i].corda is not None and estimativa[j].corda is not None
    ]
    corridas_ref, corridas_est = _corridas(referencia), _corridas(estimativa)
    erros_intervalo: list[float] = []
    velocidades: list[float] = []
    ambiguos = 0
    por_janela: dict[int, list[float]] = {}
    for (i, j), (proxima_ref, proxima_est) in pairwise(pares):
        if proxima_ref != i + 1 or proxima_est != j + 1:
            continue
        if any(corridas_ref[a] != corridas_est[b] for a, b in ((i, j), (proxima_ref, proxima_est))):
            ambiguos += 1
            continue
        r, e = referencia[proxima_ref], estimativa[proxima_est]
        dr = r.inicio_s - referencia[i].inicio_s
        de = e.inicio_s - estimativa[j].inicio_s
        if dr > 0 and de > 0:
            velocidades.append(dr / de)
            janela = int((referencia[i].inicio_s - referencia[0].inicio_s) // janela_s)
            por_janela.setdefault(janela, []).append(dr / de)
        qr = r.inicio_pulsos - referencia[i].inicio_pulsos
        qe = e.inicio_pulsos - estimativa[j].inicio_pulsos
        erros_intervalo.append(abs(qe - qr))
    return ComparacaoRitmica(
        len(referencia),
        len(estimativa),
        omissoes,
        extras,
        divergentes,
        len(pares),
        ambiguo,
        len(erros_intervalo),
        ambiguos,
        int(sum(e <= 1e-8 for e in erros_intervalo)),
        int(sum(e <= 1e-8 for e in erros_duracao)),
        float(median(velocidades)) if velocidades else None,
        float(np.percentile(velocidades, 10)) if velocidades else None,
        float(np.percentile(velocidades, 90)) if velocidades else None,
        float(median(erros_intervalo)) if erros_intervalo else None,
        float(median(erros_duracao)) if erros_duracao else None,
        tuple(
            JanelaRitmica(referencia[0].inicio_s + k * janela_s, len(v), float(median(v)))
            for k, v in sorted(por_janela.items())
        ),
        int(posicoes),
        len(digitacoes),
        sum(digitacoes),
    )


def boletim(comparacao: ComparacaoRitmica) -> Boletim:
    """Resume a comparação nas cinco dimensões, para ver qual mais afasta da referência."""
    c = comparacao
    janelas = c.janelas
    return Boletim(
        sum(abs(j.velocidade_relativa - 1) < _TOLERANCIA_DE_ANDAMENTO for j in janelas)
        / len(janelas)
        if janelas
        else None,
        c.intervalos_corretos / c.intervalos_comparaveis if c.intervalos_comparaveis else None,
        c.posicoes_corretas / c.pares if c.pares else None,
        c.pares / c.notas_referencia,
        c.digitacoes_corretas / c.digitacoes_comparaveis if c.digitacoes_comparaveis else None,
    )
