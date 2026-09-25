"""Transcrição contra tab humana: a oitava confere (ADR-041)? E a nota (ADR-042)?

A tab está em tempo de partitura; a gravação, em tempo de execução — banda sem
metrônomo, intro que a tab não tem. Antes de comparar, a tab é trazida para o tempo do
áudio.

**Só o ataque não basta para isso.** Foi a primeira tentativa, e falhou medida: numa
linha de baixo de quatro, cinco notas por segundo, a tab deslocada de propósito casava
quase tantos ataques quanto a alinhada, e em *Dance of Death* deslocá-la melhorava o
acerto de altura. O alinhamento então usa o **nome da nota** (a classe de altura, sem
oitava): um ataque da tab só conta se houver, perto dele, um ataque da transcrição com
o mesmo nome.

O preço é o que se pode concluir. Como o nome da nota já escolheu o encaixe, "nota
errada" não é medida com ele — o encaixe foi feito para ela acertar. A oitava ficou fora do
alinhamento, e é ela o veredito: entre os pares de mesmo nome, mesma oitava, oitava
acima ou abaixo.

Duas etapas:

- **global**: escala e deslocamento para a música inteira, em grade, e a escala na
  borda da grade é recusada — o melhor encaixe pode estar do lado de fora. A recusa
  não pega toda falha: fora da grade, o acaso às vezes faz um pico no interior;
- **local**: por trecho de `JANELA_S`, a mediana dos resíduos, limitada a
  `CORRECAO_MAXIMA_S` — acompanha a banda que acelera, sem saltar para a nota vizinha.

E o **piso de acaso**: o mesmo veredito com a tab deslocada de propósito. Linha densa
casa por sorte; o resultado só vale o quanto fica acima do piso.

**Nota errada** (ADR-042) é outra medida, sobre a tab já alinhada ao stem por
`alinhamento_audio`, que não olha a transcrição: `veredito_de_nota`, por janela de
`JANELA_DO_VEREDITO_S`. A janela só é conclusiva se a fração certa passa do piso dela por
`MARGEM_SOBRE_O_PISO`; abaixo disso, alinhamento falho e transcrição muito errada dão o
mesmo número, e a janela sai inconclusiva. Por isso a nota errada medida é limite inferior.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from mir_eval.util import match_events

from thoth.domain.models import NoteEvent

#: A tab é grade, não execução: 50 ms (a tolerância do ADR-006 contra MIDI) cobraria do
#: Thoth o swing da banda. 100 ms ainda é menos que meia semicolcheia a 120 bpm.
TOLERANCIA_S = 0.1
JANELA_S = 10.0
CORRECAO_MAXIMA_S = 0.08
ESCALAS = np.arange(0.90, 1.10, 0.002)
DESLOCAMENTO_MAXIMO_S = 30.0
#: Uma e duas notas de distância numa linha de colcheias: o erro em que o alinhamento
#: cairia, e portanto o competidor que ele precisa vencer.
DESLOCAMENTOS_DO_PISO_S = (-0.5, -0.25, 0.25, 0.5)
JANELA_DO_VEREDITO_S = 60.0
#: Alinhando a tab ao stem de outra música, certa passou do piso por no máximo 7 pontos
#: (ADR-042); com a música certa, por 10 a 38.
MARGEM_SOBRE_O_PISO = 0.10


@dataclass(frozen=True, slots=True)
class Alinhamento:
    escala: float
    deslocamento_s: float
    notas: list[NoteEvent]


@dataclass(frozen=True, slots=True)
class Comparacao:
    n_ref: int
    n_est: int
    #: Pares de mesmo nome de nota, casados por ataque.
    casadas: int
    mesma_oitava: int
    oitava_acima: int
    oitava_abaixo: int
    escala: float
    deslocamento_s: float
    #: O deslocamento de `DESLOCAMENTOS_DO_PISO_S` que mais casou: quantos pares e que
    #: fração deles na mesma oitava.
    piso_casadas: int
    piso_mesma_oitava: float


def _residuos(mapas: np.ndarray, classes: np.ndarray, est: Sequence[NoteEvent]) -> np.ndarray:
    """Por ataque da tab, a distância (com sinal) ao ataque estimado mais próximo **de
    mesmo nome de nota**; `inf` quando esse nome nem aparece na transcrição."""
    ataques = np.array([n.onset_s for n in est])
    nomes = np.array([n.pitch % 12 for n in est])
    saida = np.full(mapas.shape, np.inf)
    for nome in range(12):
        alvo = np.sort(ataques[nomes == nome])
        coluna = classes == nome
        if len(alvo) < 2 or not coluna.any():
            continue
        m = mapas[..., coluna]
        i = np.clip(np.searchsorted(alvo, m), 1, len(alvo) - 1)
        antes, depois = alvo[i - 1] - m, alvo[i] - m
        saida[..., coluna] = np.where(np.abs(antes) <= np.abs(depois), antes, depois)
    return saida


def _global(ref: np.ndarray, classes: np.ndarray, est: Sequence[NoteEvent]) -> tuple[float, float]:
    """Grade grossa acha a região; mínimos quadrados sobre os pares acha o centro dela.

    Só a grade não basta: a contagem de casados é um platô, e a primeira borda dele
    fica dezenas de milissegundos fora.
    """
    primeiro = min(n.onset_s for n in est)
    deslocamentos = np.arange(-DESLOCAMENTO_MAXIMO_S, DESLOCAMENTO_MAXIMO_S, 0.05)
    melhor = (-1, 0, 0.0)
    for k_escala, a in enumerate(ESCALAS):
        # Todos os deslocamentos de uma vez: uma linha da matriz por candidato.
        candidatos = primeiro - a * ref[0] + deslocamentos
        mapas = ref * a + candidatos[:, None]
        contagens = (np.abs(_residuos(mapas, classes, est)) <= TOLERANCIA_S).sum(axis=1)
        k = int(np.argmax(contagens))
        if contagens[k] > melhor[0]:
            melhor = (int(contagens[k]), k_escala, float(candidatos[k]))
    _, k_escala, b = melhor
    if k_escala in (0, len(ESCALAS) - 1):
        raise ValueError(
            f"sem encaixe: a escala parou na borda da busca ({ESCALAS[k_escala]:.3f}) — "
            "tab e gravação podem ser versões diferentes"
        )
    a = float(ESCALAS[k_escala])
    for _ in range(3):
        residuo = _residuos(ref * a + b, classes, est)
        perto = np.abs(residuo) <= TOLERANCIA_S
        a, b = (float(x) for x in np.polyfit(ref[perto], ref[perto] * a + b + residuo[perto], 1))
    return a, b


def alinhar(referencia: Sequence[NoteEvent], estimativa: Sequence[NoteEvent]) -> Alinhamento:
    """Leva a tab ao tempo do áudio pelo ataque e pelo nome da nota — nunca pela oitava."""
    ref = np.array([n.onset_s for n in referencia])
    classes = np.array([n.pitch % 12 for n in referencia])
    a, b = _global(ref, classes, estimativa)

    mapa = ref * a + b
    residuo = _residuos(mapa, classes, estimativa)
    for inicio in np.arange(ref[0], ref[-1] + JANELA_S, JANELA_S):
        trecho = (ref >= inicio) & (ref < inicio + JANELA_S)
        perto = trecho & (np.abs(residuo) <= TOLERANCIA_S)
        if perto.sum() >= 4:
            mapa[trecho] += np.clip(
                np.median(residuo[perto]), -CORRECAO_MAXIMA_S, CORRECAO_MAXIMA_S
            )

    notas_alinhadas = [
        NoteEvent(n.pitch, float(t), float(t) + (n.offset_s - n.onset_s) * a, n.instrument)
        for n, t in zip(referencia, mapa, strict=True)
    ]
    return Alinhamento(a, b, notas_alinhadas)


def _diferencas(ref: Sequence[NoteEvent], est: Sequence[NoteEvent], extra_s: float) -> list[int]:
    """Diferença de altura (estimada menos tab) de cada par de mesmo nome, casado por ataque."""
    diferencas: list[int] = []
    for nome in range(12):
        r = [n for n in ref if n.pitch % 12 == nome]
        e = [n for n in est if n.pitch % 12 == nome]
        if not r or not e:
            continue
        pares = match_events(
            np.array([n.onset_s + extra_s for n in r]),
            np.array([n.onset_s for n in e]),
            TOLERANCIA_S,
        )
        diferencas += [e[j].pitch - r[i].pitch for i, j in pares]
    return diferencas


def comparar(referencia: Sequence[NoteEvent], estimativa: Sequence[NoteEvent]) -> Comparacao:
    if not referencia or not estimativa:
        raise ValueError("referência e transcrição precisam ter notas")
    alinhada = alinhar(referencia, estimativa)
    diferencas = _diferencas(alinhada.notas, estimativa, 0.0)
    piso = max(
        (_diferencas(alinhada.notas, estimativa, x) for x in DESLOCAMENTOS_DO_PISO_S), key=len
    )
    return Comparacao(
        n_ref=len(referencia),
        n_est=len(estimativa),
        casadas=len(diferencas),
        mesma_oitava=sum(d == 0 for d in diferencas),
        oitava_acima=sum(d > 0 for d in diferencas),
        oitava_abaixo=sum(d < 0 for d in diferencas),
        escala=round(alinhada.escala, 4),
        deslocamento_s=round(alinhada.deslocamento_s, 3),
        piso_casadas=len(piso),
        piso_mesma_oitava=sum(d == 0 for d in piso) / len(piso) if piso else 0.0,
    )


@dataclass(frozen=True, slots=True)
class JanelaDeNota:
    """Notas da tab com ataque em `[inicio_s, inicio_s + JANELA_DO_VEREDITO_S)`."""

    inicio_s: float
    certa: int
    oitava: int
    errada: int
    #: Sem ataque da transcrição a `TOLERANCIA_S`: fica fora das frações.
    sem: int
    piso_certa: float

    @property
    def com_ataque(self) -> int:
        return self.certa + self.oitava + self.errada

    @property
    def fracao_certa(self) -> float:
        return self.certa / self.com_ataque if self.com_ataque else 0.0

    @property
    def conclusiva(self) -> bool:
        return self.com_ataque > 0 and self.fracao_certa >= self.piso_certa + MARGEM_SOBRE_O_PISO


def _contar(
    alturas: np.ndarray, tempos: np.ndarray, ataques: np.ndarray, estimadas: np.ndarray,
    inicio: float,
) -> tuple[int, int, int, int]:
    """Por nota da tab, entre os ataques da transcrição a `TOLERANCIA_S`: a mesma altura,
    o mesmo nome em outra oitava, outro nome ou nenhum ataque."""
    certa = oitava = errada = sem = 0
    dentro = (tempos >= inicio) & (tempos < inicio + JANELA_DO_VEREDITO_S)
    for altura, t in zip(alturas[dentro], tempos[dentro], strict=True):
        a, b = np.searchsorted(ataques, [t - TOLERANCIA_S, t + TOLERANCIA_S])
        candidatas = estimadas[a:b]
        if len(candidatas) == 0:
            sem += 1
        elif altura in candidatas:
            certa += 1
        elif altura % 12 in candidatas % 12:
            oitava += 1
        else:
            errada += 1
    return certa, oitava, errada, sem


def veredito_de_nota(
    tab_no_audio: Sequence[NoteEvent], estimativa: Sequence[NoteEvent]
) -> list[JanelaDeNota]:
    """Nota errada por janela, com a tab já no tempo do áudio (`alinhar_ao_stem`)."""
    if not tab_no_audio or not estimativa:
        raise ValueError("referência e transcrição precisam ter notas")
    ordem = sorted(estimativa, key=lambda n: n.onset_s)
    ataques = np.array([n.onset_s for n in ordem])
    estimadas = np.array([n.pitch for n in ordem])
    alturas = np.array([n.pitch for n in tab_no_audio])
    tempos = np.array([n.onset_s for n in tab_no_audio])

    janelas: list[JanelaDeNota] = []
    fim = float(tempos.max())
    for inicio in np.arange(0.0, fim + JANELA_DO_VEREDITO_S, JANELA_DO_VEREDITO_S):
        certa, oitava, errada, sem = _contar(alturas, tempos, ataques, estimadas, inicio)
        if certa + oitava + errada == 0:
            continue
        pisos = []
        for x in DESLOCAMENTOS_DO_PISO_S:
            c, o, e, _ = _contar(alturas, tempos + x, ataques, estimadas, inicio)
            pisos.append(c / (c + o + e) if c + o + e else 0.0)
        janelas.append(JanelaDeNota(float(inicio), certa, oitava, errada, sem, max(pisos)))
    return janelas
