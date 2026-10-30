"""Notas → posições no braço, por Viterbi.

A mesma altura cabe em até quatro lugares num baixo de quatro cordas, e a
escolha certa depende das notas vizinhas: nota isolada não tem posição ótima,
frase tem. O custo se divide em dois:

- **emissão** — quanto custa *estar* naquela posição (traste alto e a preferência
  por corda solta são escolhas do perfil, não prova da execução original);
- **transição** — quanto custa *chegar* nela vindo da anterior (deslocar a mão,
  atravessar cordas).

A posição da mão faz parte do estado, não da nota (ADR-032): corda solta não
move a mão nem a apaga. Com alcance zero, a posição é o último traste pisado;
com alcance positivo, é o início da janela de casas alcançáveis. Deslocamento
se mede entre janelas, sem cobrar como movimento da mão a troca de dedo dentro
delas (emenda de 2026-10-30).

O "modo iniciante" do ADR-006 não é um modo à parte: é outro peso. Ele compra
tocabilidade (primeira posição, cordas soltas) pagando em deslocamento — o
oposto do que um baixista experiente escolheria.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from thoth.domain.models import NoteEvent, TabNote
from thoth.domain.ports import FretAssigner

#: Estado do Viterbi: corda, traste e início da janela da mão. Com alcance zero,
#: coincide com o último traste pisado (ADR-032); `None` antes de posicioná-la.
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


#: Baixista experiente: quase só mover a mão e atravessar cordas custa.
#: Calibrado contra seis tabs humanas (ADR-050): custo por traste de verdade
#: puxa a linha para o grave e afasta a tab da do baixista. O `traste_alto`
#: residual só desempata a mesma forma tocada em alturas diferentes do braço,
#: que sem ele custariam igual e cairiam na ordem das cordas.
PADRAO = Custos(
    traste_alto=0.002, corda_solta=0.0, deslocamento=1.0, troca_corda=0.4, acima_da_janela=0.0
)

#: ADR-006 — quem está aprendendo. Traste alto e deslocamento custam caro;
#: corda solta vale muito. Resultado: fica na primeira posição sempre que a
#: linha permitir, mesmo trocando de corda com mais frequência.
INICIANTE = Custos(
    traste_alto=1.2, corda_solta=3.0, deslocamento=1.5, troca_corda=0.3, acima_da_janela=2.0
)

#: Os dois perfis com porta de entrada, por nome (ADR-028). **`INICIANTE` é o
#: default** do `ViterbiFretAssigner`, apesar de `PADRAO` se chamar assim: o
#: ADR-006 escolheu quem está aprendendo. `PADRAO` é o perfil do experiente.
DIGITACOES: dict[str, Custos] = {"iniciante": INICIANTE, "experiente": PADRAO}


def custo_de_emissao(custos: Custos, fret: int) -> float:
    """Quanto custa *estar* num traste. Comum à linha do baixo e aos acordes (ADR-044)."""
    custo = custos.traste_alto * fret
    custo += custos.acima_da_janela * max(0, fret - PRIMEIRA_POSICAO)
    return custo - (custos.corda_solta if fret == 0 else 0.0)


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
    alcance_da_mao: int = 0
    """Distância entre as casas extremas alcançáveis sem deslocar a mão.

    Zero preserva a aproximação do ADR-032. Três permite quatro casas inclusivas,
    sem afirmar quais dedos ou qual corda o músico efetivamente usou.
    """

    def __post_init__(self) -> None:
        if self.alcance_da_mao < 0:
            raise ValueError("alcance da mão não pode ser negativo")

    def _emissao(self, fret: int) -> float:
        return custo_de_emissao(self.custos, fret)

    def _estados(self, posicao: tuple[int, int], mao: int | None) -> list[_Estado]:
        corda, traste = posicao
        if traste == 0:
            return [(corda, traste, mao)]
        return [
            (corda, traste, inicio)
            for inicio in range(max(1, traste - self.alcance_da_mao), traste + 1)
        ]

    def _transicao(self, de: _Estado, para: _Estado) -> float:
        corda_a, _, mao = de
        corda_b, _, nova_mao = para
        custo = self.custos.troca_corda * abs(corda_b - corda_a)
        # Corda solta não move a mão: ela fica onde estava, e a nota seguinte
        # parte dali (ADR-032). Mão `None` é mão ainda não posicionada — antes
        # do primeiro traste pisado há o tempo do mundo para colocá-la, e cobrar
        # a distância contra a pestana inventaria um salto que não existe.
        if mao is not None and nova_mao is not None:
            custo += self.custos.deslocamento * abs(nova_mao - mao)
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

        # A nota pisada admite cada janela capaz de alcançá-la; a corda solta
        # mantém a janela anterior. Estados com a mesma posição e janela se
        # fundem, limitando a busca pelo braço, não pelo histórico da música.
        estados: list[list[_Estado]] = [
            [estado for posicao in opcoes_por_nota[0] for estado in self._estados(posicao, None)]
        ]
        custo = [self._emissao(f) for _, f, _ in estados[0]]
        origem: list[list[int]] = []
        for opcoes in opcoes_por_nota[1:]:
            melhor: dict[_Estado, tuple[float, int]] = {}
            for posicao in opcoes:
                for i, anterior in enumerate(estados[-1]):
                    for chave in self._estados(posicao, anterior[2]):
                        chegada = custo[i] + self._transicao(anterior, chave)
                        chegada += self._emissao(chave[1])
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
