"""Qual das quatro semicolcheias do pulso é a cabeça do tempo (ADR-054).

`ajustar` acha a fase da grade só dentro de uma semicolcheia, e `recuo_de_fase`
escolhe entre `fase` e `fase - grade`: a grade fica certa, mas nada decide em qual
das quatro semicolcheias o pulso começa. Quem decide são as batidas do mix (as do
`beat_track`, que `estimar_andamento` já calcula): a moda da fração do pulso, na
partitura, onde elas caem.

Batida em dobro vota em duas frações por igual, e mapa que deriva entre as batidas
espalha os votos pelas quatro. Nos dois casos não há escolha a fazer, e a fase de
antes fica: o limiar de abstenção foi fixado antes da medição e é ele que segura
*Você*, que sem ele escolheria a fração errada.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence

from thoth.services.rhythm import MapaDeAndamento

# A segunda fração mais votada com pelo menos isto dos votos da primeira: empate.
_EMPATE = 0.8


def deslocamento(batidas: Sequence[float], mapa: MapaDeAndamento) -> int | None:
    """Semicolcheias (0 a 3) da cabeça do tempo além do zero da grade; `None` se empata."""
    votos = Counter(
        round((mapa.para_partitura(t) * mapa.bpm / 60) % 1.0 * 4) % 4 for t in batidas
    ).most_common(2)
    if not votos or (len(votos) > 1 and votos[1][1] >= _EMPATE * votos[0][1]):
        return None
    return votos[0][0]


def recuo_na_cabeca(recuo: float, semicolcheias: int, grade: float, primeiro: float) -> float:
    """O recuo que leva a cabeça do tempo ao zero da grade.

    Se a primeira nota cair antes do zero, o recuo volta um pulso inteiro: a música
    começa com pausa (anacruse), porque tempo negativo nenhum formato representa.
    Antes do zero quer dizer antes do tique zero: a sobra de menos de meia
    semicolcheia que o BPM refinado deixa arredonda para ele.
    """
    novo = recuo + semicolcheias * grade
    return novo if primeiro >= novo - grade / 2 else novo - 4 * grade
