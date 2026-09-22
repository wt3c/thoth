"""Notas → posições no braço, por Viterbi.

A mesma altura cabe em até quatro lugares num baixo de quatro cordas, e a
escolha certa depende das notas vizinhas: nota isolada não tem posição ótima,
frase tem. O custo se divide em dois:

- **emissão** — quanto custa *estar* naquela posição (traste alto cansa, corda
  solta é de graça e soa melhor);
- **transição** — quanto custa *chegar* nela vindo da anterior (deslocar a mão,
  atravessar cordas).

O "modo iniciante" do ADR-006 não é um modo à parte: é outro peso. Ele compra
tocabilidade (primeira posição, cordas soltas) pagando em deslocamento — o
oposto do que um baixista experiente escolheria.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import pairwise

from thoth.domain.models import NoteEvent, TabNote


class IMPOSSIVEL(ValueError):
    """A altura não existe neste braço: grave demais, ou acima do último traste."""


#: Último traste da primeira posição — onde a mão de quem está aprendendo fica.
PRIMEIRA_POSICAO = 5


@dataclass(frozen=True, slots=True)
class Custos:
    """Pesos do caminho. Todos em "unidades de custo" arbitrárias, só comparáveis entre si."""

    traste_alto: float
    """Por traste, linear. É o que segura a mão na parte grave do braço."""

    corda_solta: float
    """Desconto de estar no traste 0: nada a pisar, e a mão fica livre."""

    deslocamento: float
    """Por traste percorrido entre duas notas pisadas. É a janela da mão."""

    troca_corda: float
    """Por corda atravessada. Barato demais e a linha vira zigue-zague."""

    acima_da_janela: float
    """Por traste acima da primeira posição. É o termo que separa os dois modos:
    o custo linear de `traste_alto` desloca todas as opções na mesma direção e
    quase nunca inverte a escolha; este só morde fora da zona confortável."""


#: Baixista experiente: deslocar é barato, subir o braço nem incomoda.
PADRAO = Custos(traste_alto=0.3, corda_solta=1.0, deslocamento=0.6, troca_corda=0.4,
                acima_da_janela=0.0)

#: ADR-006 — quem está aprendendo. Traste alto e deslocamento custam caro;
#: corda solta vale muito. Resultado: fica na primeira posição sempre que a
#: linha permitir, mesmo trocando de corda com mais frequência.
INICIANTE = Custos(traste_alto=1.2, corda_solta=3.0, deslocamento=1.5, troca_corda=0.3,
                   acima_da_janela=2.0)


def _posicoes(pitch: int, tuning: tuple[int, ...], max_fret: int) -> list[tuple[int, int]]:
    return [
        (corda, pitch - solta)
        for corda, solta in enumerate(tuning)
        if 0 <= pitch - solta <= max_fret
    ]


@dataclass(frozen=True, slots=True)
class ViterbiFretAssigner:
    """Implementa o `FretAssigner`. Ótimo global sobre a frase, não guloso nota a nota."""

    custos: Custos = field(default=INICIANTE)

    def _emissao(self, fret: int) -> float:
        custo = self.custos.traste_alto * fret
        custo += self.custos.acima_da_janela * max(0, fret - PRIMEIRA_POSICAO)
        return custo - (self.custos.corda_solta if fret == 0 else 0.0)

    def _transicao(self, de: tuple[int, int], para: tuple[int, int]) -> float:
        corda_a, traste_a = de
        corda_b, traste_b = para
        custo = self.custos.troca_corda * abs(corda_b - corda_a)
        # Corda solta não move a mão: ela fica onde estava, e a nota seguinte
        # parte dali. Cobrar deslocamento contra o traste 0 inventaria um salto.
        if traste_a and traste_b:
            custo += self.custos.deslocamento * abs(traste_b - traste_a)
        return custo

    def assign(
        self, notes: list[NoteEvent], tuning: tuple[int, ...], max_fret: int = 24
    ) -> list[TabNote]:
        if not notes:
            return []

        estados: list[list[tuple[int, int]]] = []
        for nota in notes:
            opcoes = _posicoes(nota.pitch, tuning, max_fret)
            if not opcoes:
                raise IMPOSSIVEL(
                    f"pitch {nota.pitch} em {nota.onset_s:.2f}s não cabe na afinação "
                    f"{tuning} até o traste {max_fret}"
                )
            estados.append(opcoes)

        # Viterbi: melhor custo até cada estado, com ponteiro para a origem.
        custo = [self._emissao(f) for _, f in estados[0]]
        origem: list[list[int]] = []
        for anterior, atual in pairwise(estados):
            melhor: list[float] = []
            de_onde: list[int] = []
            for posicao in atual:
                alcances = [
                    c + self._transicao(p, posicao)
                    for c, p in zip(custo, anterior, strict=True)
                ]
                i = min(range(len(alcances)), key=alcances.__getitem__)
                melhor.append(alcances[i] + self._emissao(posicao[1]))
                de_onde.append(i)
            custo = melhor
            origem.append(de_onde)

        i = min(range(len(custo)), key=custo.__getitem__)
        caminho = [i]
        for de_onde in reversed(origem):
            i = de_onde[i]
            caminho.append(i)
        caminho.reverse()

        return [
            TabNote(event=nota, string=opcoes[i][0], fret=opcoes[i][1])
            for nota, opcoes, i in zip(notes, estados, caminho, strict=True)
        ]
