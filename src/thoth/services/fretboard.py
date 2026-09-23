"""Notas → posições no braço, por Viterbi.

A mesma altura cabe em até quatro lugares num baixo de quatro cordas, e a
escolha certa depende das notas vizinhas: nota isolada não tem posição ótima,
frase tem. O custo se divide em dois:

- **emissão** — quanto custa *estar* naquela posição (traste alto cansa, corda
  solta é de graça e soa melhor);
- **transição** — quanto custa *chegar* nela vindo da anterior (deslocar a mão,
  atravessar cordas).

A posição da mão faz parte do estado, não da nota (ADR-032): corda solta não
move a mão nem a apaga, então o deslocamento da nota seguinte é medido contra o
último traste **pisado**, não contra o traste 0 que acabou de soar.

O "modo iniciante" do ADR-006 não é um modo à parte: é outro peso. Ele compra
tocabilidade (primeira posição, cordas soltas) pagando em deslocamento — o
oposto do que um baixista experiente escolheria.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from thoth.domain.models import NoteEvent, TabNote
from thoth.domain.ports import FretAssigner

#: Estado do Viterbi: corda, traste e a posição da mão — o último traste pisado,
#: `None` enquanto a mão ainda não foi colocada no braço (ADR-032).
_Estado = tuple[int, int, int | None]


class AlturaImpossivelError(ValueError):
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

#: Os dois perfis com porta de entrada, por nome (ADR-028). **`INICIANTE` é o
#: default** do `ViterbiFretAssigner`, apesar de `PADRAO` se chamar assim: o
#: ADR-006 escolheu quem está aprendendo. `PADRAO` é o perfil do experiente.
DIGITACOES: dict[str, Custos] = {"iniciante": INICIANTE, "experiente": PADRAO}


def _posicoes(pitch: int, tuning: tuple[int, ...], max_fret: int) -> list[tuple[int, int]]:
    return [
        (corda, pitch - solta)
        for corda, solta in enumerate(tuning)
        if 0 <= pitch - solta <= max_fret
    ]


def cabe_no_braco(pitch: int, tuning: tuple[int, ...], max_fret: int = 24) -> bool:
    """Existe alguma casa para esta altura nesta afinação?

    Serve a quem precisa **filtrar** antes de posicionar: o `assign` levanta
    erro, e para um pipeline inteiro uma nota fora do braço não pode custar a
    música toda.
    """
    return bool(_posicoes(pitch, tuning, max_fret))


@dataclass(frozen=True, slots=True)
class ViterbiFretAssigner:
    """Implementa o `FretAssigner`. Ótimo global sobre a frase, não guloso nota a nota."""

    custos: Custos = field(default=INICIANTE)

    def _emissao(self, fret: int) -> float:
        custo = self.custos.traste_alto * fret
        custo += self.custos.acima_da_janela * max(0, fret - PRIMEIRA_POSICAO)
        return custo - (self.custos.corda_solta if fret == 0 else 0.0)

    def _transicao(self, de: _Estado, para: tuple[int, int]) -> float:
        corda_a, _, mao = de
        corda_b, traste_b = para
        custo = self.custos.troca_corda * abs(corda_b - corda_a)
        # Corda solta não move a mão: ela fica onde estava, e a nota seguinte
        # parte dali (ADR-032). Mão `None` é mão ainda não posicionada — antes
        # do primeiro traste pisado há o tempo do mundo para colocá-la, e cobrar
        # a distância contra a pestana inventaria um salto que não existe.
        if traste_b and mao is not None:
            custo += self.custos.deslocamento * abs(traste_b - mao)
        return custo

    def assign(
        self, notes: list[NoteEvent], tuning: tuple[int, ...], max_fret: int = 24
    ) -> list[TabNote]:
        """Posiciona a linha, em ordem de onset.

        **Pressupõe linha monofônica.** Notas simultâneas são tratadas como
        sequência, então nada impede que duas caiam na mesma corda — o que é
        impossível de tocar. O corpus de baixo medido até aqui não tem
        simultaneidade; acordes exigem um passo a mais, não este algoritmo.
        """
        if not notes:
            return []

        # A ordem é parte do problema: o custo de transição só faz sentido entre
        # vizinhas no tempo. O `FretAssigner` não exige entrada ordenada.
        notes = sorted(notes, key=lambda n: (n.onset_s, n.pitch))

        opcoes_por_nota: list[list[tuple[int, int]]] = []
        for nota in notes:
            opcoes = _posicoes(nota.pitch, tuning, max_fret)
            if not opcoes:
                raise AlturaImpossivelError(
                    f"pitch {nota.pitch} em {nota.onset_s:.2f}s não cabe na afinação "
                    f"{tuning} até o traste {max_fret}"
                )
            opcoes_por_nota.append(opcoes)

        # Viterbi: melhor custo até cada estado, com ponteiro para a origem. O
        # estado carrega a posição da mão, e é ela que faz o número de estados
        # não explodir ao longo da linha: nota pisada colapsa a mão no próprio
        # traste, então as mãos só ramificam dentro de uma corrida de cordas
        # soltas consecutivas — no máximo tantas quantas a última nota pisada
        # tinha opções (ADR-032).
        estados: list[list[_Estado]] = [
            [(corda, fret, fret or None) for corda, fret in opcoes_por_nota[0]]
        ]
        custo = [self._emissao(f) for _, f, _ in estados[0]]
        origem: list[list[int]] = []
        for opcoes in opcoes_por_nota[1:]:
            melhor: dict[_Estado, tuple[float, int]] = {}
            for posicao in opcoes:
                corda_b, traste_b = posicao
                for i, anterior in enumerate(estados[-1]):
                    chegada = custo[i] + self._transicao(anterior, posicao)
                    chegada += self._emissao(traste_b)
                    chave = (corda_b, traste_b, traste_b or anterior[2])
                    if chave not in melhor or chegada < melhor[chave][0]:
                        melhor[chave] = (chegada, i)
            estados.append(list(melhor))
            custo = [melhor[k][0] for k in estados[-1]]
            origem.append([melhor[k][1] for k in estados[-1]])

        i = min(range(len(custo)), key=custo.__getitem__)
        caminho = [i]
        for de_onde in reversed(origem):
            i = de_onde[i]
            caminho.append(i)
        caminho.reverse()

        return [
            TabNote(event=nota, string=passo[i][0], fret=passo[i][1])
            for nota, passo, i in zip(notes, estados, caminho, strict=True)
        ]


if TYPE_CHECKING:  # pragma: no cover — trava a assinatura contra o Protocol
    _: FretAssigner = ViterbiFretAssigner()
