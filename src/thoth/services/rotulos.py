"""Onde o baixo sumiu dos rótulos sem sumir do stem (emenda do ADR-008).

O filtro de rótulo é o que separa o baixo do vazamento (ADR-008, ADR-010), e o seu
modo de falha é silencioso: o rótulo depende de contexto, e quando o MuScriptor
passa a chamar o baixo de outra coisa, a linha inteira sai do filtro. Em *And Plague
Flowers* isso levou os dois minutos finais — rotulados `clean_electric_guitar`.

Nota de outro rótulo **perto** de uma nota de baixo é vazamento ou duplicata, e o
filtro está certo em descartá-la. O sintoma é a outra: longe de qualquer baixo, em
sequência. Essa volta para a partitura, e o trecho é relatado — se ali não há
baixo, o que voltou é vazamento, e só o ouvido decide.
"""

from __future__ import annotations

from bisect import bisect_left
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

from thoth.domain.models import NoteEvent

#: Rótulos sem altura: bateria no stem de baixo é vazamento, nunca linha de baixo.
SEM_ALTURA = frozenset({"drums"})
#: Mais longe que isto de qualquer ataque de baixo, a nota está num trecho sem baixo;
#: e mais longe que isto da órfã anterior, começa outro trecho.
LACUNA_S = 5.0
#: Abaixo disto, o trecho é vazamento esparso — não vale um aviso.
MINIMO_DE_NOTAS = 10


@dataclass(frozen=True, slots=True)
class TrechoSemBaixo:
    inicio_s: float
    fim_s: float
    rotulos: dict[str, int]


def _longe_do_baixo(ataques: Sequence[float], t: float) -> bool:
    i = bisect_left(ataques, t)
    vizinhos = ataques[max(i - 1, 0) : i + 1]
    return all(abs(t - a) > LACUNA_S for a in vizinhos)


def trechos_sem_baixo(
    baixo: Sequence[NoteEvent], outras: Sequence[NoteEvent]
) -> list[TrechoSemBaixo]:
    """Sequências de notas com rótulo de outro instrumento, longe de qualquer baixo."""
    ataques = sorted(n.onset_s for n in baixo)
    orfas = sorted(
        (
            n
            for n in outras
            if n.instrument not in SEM_ALTURA and _longe_do_baixo(ataques, n.onset_s)
        ),
        key=lambda n: n.onset_s,
    )
    grupos: list[list[NoteEvent]] = []
    for nota in orfas:
        if grupos and nota.onset_s - grupos[-1][-1].onset_s <= LACUNA_S:
            grupos[-1].append(nota)
        else:
            grupos.append([nota])
    return [
        TrechoSemBaixo(g[0].onset_s, g[-1].onset_s, dict(Counter(n.instrument for n in g)))
        for g in grupos
        if len(g) >= MINIMO_DE_NOTAS
    ]


def readmitidas(
    outras: Sequence[NoteEvent], trechos: Sequence[TrechoSemBaixo]
) -> list[NoteEvent]:
    """As notas de outro rótulo que caem dentro de um trecho sem baixo."""
    return [
        n
        for n in outras
        if n.instrument not in SEM_ALTURA
        and any(t.inicio_s <= n.onset_s <= t.fim_s for t in trechos)
    ]
