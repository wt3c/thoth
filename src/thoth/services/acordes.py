"""Acordes → posições no braço, por Viterbi sobre digitações (ADR-044, M4).

O `ViterbiFretAssigner` do baixo pressupõe linha monofônica: duas notas simultâneas
podiam cair na mesma corda. Aqui a unidade é o **acorde** — notas que começam dentro
de `JANELA_ACORDE_S` —, e cada candidato é uma digitação inteira: uma corda distinta
por nota, com as casas pisadas a no máximo `ABERTURA_MAXIMA` trastes umas das outras.

Os custos são os mesmos `Custos` do baixo. A emissão soma a de cada nota; a transição
cobra o deslocamento da mão, que é o menor traste pisado do acorde. Acorde só de cordas
soltas não move a mão, pela mesma razão do ADR-032.

Acorde sem digitação possível é relatado inteiro em `impossiveis` (ADR-014): reduzi-lo a
uma nota esconderia o erro de transcrição que o produziu.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from thoth.domain.models import AcordeImpossivel, NoteEvent, Posicionamento, TabNote
from thoth.services.evaluation import TOLERANCIA_S
from thoth.services.fretboard import INICIANTE, Custos, _posicoes, custo_de_emissao

if TYPE_CHECKING:
    from thoth.domain.ports import AtribuidorDeAcordes

#: Notas que começam a menos disto uma da outra formam um acorde. É a tolerância com
#: que o avaliador considera dois ataques o mesmo instante.
JANELA_ACORDE_S = TOLERANCIA_S

#: Maior distância, em trastes, entre as casas pisadas de um acorde. Corda solta não
#: conta: não ocupa dedo nenhum.
ABERTURA_MAXIMA = 4

_Forma = tuple[tuple[int, int], ...]  # (corda, traste) por nota, na ordem do acorde


def _agrupar(notas: list[NoteEvent]) -> list[list[NoteEvent]]:
    grupos: list[list[NoteEvent]] = []
    for nota in sorted(notas, key=lambda n: (n.onset_s, n.pitch)):
        if grupos and nota.onset_s - grupos[-1][0].onset_s < JANELA_ACORDE_S:
            grupos[-1].append(nota)
        else:
            grupos.append([nota])
    return grupos


def inicios_de_acorde(notas: list[NoteEvent]) -> list[float]:
    """Um ataque por acorde: o que o andamento e a fase devem medir (ADR-024).

    Seis notas do mesmo acorde contadas uma a uma parecem cinco colisões na grade, e o
    desdobramento dobraria o andamento à toa.
    """
    return [grupo[0].onset_s for grupo in _agrupar(notas)]


def _digitacoes(
    acorde: list[NoteEvent], afinacao: tuple[int, ...], max_traste: int
) -> tuple[list[_Forma], str]:
    """Todas as digitações tocáveis, ou nenhuma e o motivo."""
    if len(acorde) > len(afinacao):
        return [], f"{len(acorde)} notas para {len(afinacao)} cordas"
    opcoes = [_posicoes(n.pitch, afinacao, max_traste) for n in acorde]
    for nota, op in zip(acorde, opcoes, strict=True):
        if not op:
            return [], f"altura {nota.pitch} fora do braço {afinacao} até o traste {max_traste}"

    formas: list[_Forma] = []

    def descer(i: int, parcial: list[tuple[int, int]]) -> None:
        if i == len(opcoes):
            formas.append(tuple(parcial))
            return
        usadas = {c for c, _ in parcial}
        pisados = [t for _, t in parcial if t]
        for corda, traste in opcoes[i]:
            if corda in usadas:
                continue
            if traste and pisados and max(*pisados, traste) - min(*pisados, traste) > (
                ABERTURA_MAXIMA
            ):
                continue
            descer(i + 1, [*parcial, (corda, traste)])

    descer(0, [])
    if not formas:
        motivo = f"sem digitação com cordas distintas no alcance de {ABERTURA_MAXIMA} trastes"
        return [], motivo
    return formas, ""


@dataclass(frozen=True, slots=True)
class ViterbiAcordes:
    """Implementa o `AtribuidorDeAcordes`. Ótimo global sobre a sequência de acordes."""

    custos: Custos = field(default=INICIANTE)

    def posicionar(
        self, notas: list[NoteEvent], afinacao: tuple[int, ...], max_traste: int = 24
    ) -> Posicionamento:
        tocaveis: list[tuple[list[NoteEvent], list[_Forma]]] = []
        impossiveis: list[AcordeImpossivel] = []
        for acorde in _agrupar(notas):
            formas, motivo = _digitacoes(acorde, afinacao, max_traste)
            if formas:
                tocaveis.append((acorde, formas))
            else:
                impossiveis.append(AcordeImpossivel(tuple(acorde), motivo))
        if not tocaveis:
            return Posicionamento((), tuple(impossiveis))

        # Estado = posição da mão; `None` antes do primeiro traste pisado. Cada camada
        # guarda, por mão de chegada, o melhor custo, a mão de origem e a digitação.
        camadas: list[dict[int | None, tuple[float, int | None, _Forma]]] = []
        custo: dict[int | None, float] = {None: 0.0}
        for _, formas in tocaveis:
            camada: dict[int | None, tuple[float, int | None, _Forma]] = {}
            for forma in formas:
                emissao = sum(custo_de_emissao(self.custos, t) for _, t in forma)
                pisados = [t for _, t in forma if t]
                for mao, acumulado in custo.items():
                    nova = min(pisados) if pisados else mao
                    chegada = acumulado + emissao
                    if pisados and mao is not None:
                        chegada += self.custos.deslocamento * abs(min(pisados) - mao)
                    if nova not in camada or chegada < camada[nova][0]:
                        camada[nova] = (chegada, mao, forma)
            camadas.append(camada)
            custo = {mao: c for mao, (c, _, _) in camada.items()}

        mao = min(custo, key=custo.__getitem__)
        escolhidas: list[_Forma] = []
        for camada in reversed(camadas):
            _, mao, forma = camada[mao]
            escolhidas.append(forma)
        escolhidas.reverse()

        tab = tuple(
            TabNote(event=nota, string=corda, fret=traste)
            for (acorde, _), forma in zip(tocaveis, escolhidas, strict=True)
            for nota, (corda, traste) in zip(acorde, forma, strict=True)
        )
        return Posicionamento(tab, tuple(impossiveis))


if TYPE_CHECKING:  # pragma: no cover — trava a assinatura contra o Protocol
    _: AtribuidorDeAcordes = ViterbiAcordes()
