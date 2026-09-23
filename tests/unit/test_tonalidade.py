"""Estimativa de tonalidade — a grafia do acidente depende dela (ADR-031).

A grafia sempre com sustenido está errada em tom bemol, e o acervo tem: dois de
sete estimam fá menor e um ré menor. Mas a estimativa erra, e armadura errada é
pior que armadura nenhuma — daí a margem, que é o assunto da metade destes testes.
"""

from __future__ import annotations

import pytest

from thoth.domain.models import NoteEvent
from thoth.services.tonalidade import MARGEM_MINIMA, Tonalidade, estimar_tom, tom_de_texto


def _linha(pitches: list[int]) -> list[NoteEvent]:
    return [
        NoteEvent(pitch=p, onset_s=i * 0.5, offset_s=(i + 1) * 0.5, instrument="electric_bass")
        for i, p in enumerate(pitches)
    ]


def test_linha_em_tom_bemol_pede_bemois() -> None:
    """Fá menor: fá, láb, sib, dó, mib — escrever G# no lugar de Ab é o defeito."""
    fa_menor = _linha([29, 32, 34, 36, 39, 29, 36, 34, 32, 29, 39, 36] * 3)

    tom = estimar_tom(fa_menor)

    assert tom.sharps < 0, tom
    assert tom.bemois, tom


def test_linha_em_tom_sustenido_nao_vira_bemol() -> None:
    """Mi menor: mi, fá#, sol, si — o comportamento de hoje, agora medido."""
    mi_menor = _linha([28, 30, 31, 33, 35, 28, 35, 33, 31, 28, 30, 35] * 3)

    tom = estimar_tom(mi_menor)

    assert tom.sharps >= 0, tom
    assert not tom.bemois, tom


def test_margem_curta_nao_muda_a_grafia() -> None:
    """Empate entre fá menor e dó maior: o acervo tem um caso exato (0,590 contra 0,590).

    Armadura errada imprime mais acidente que armadura nenhuma (11 contra 9 numa linha
    de 12 notas), então abaixo da margem o Thoth fica com o que já fazia.
    """
    duvidosa = Tonalidade(nome="f minor", sharps=-4, margem=MARGEM_MINIMA / 2)

    assert not duvidosa.confiavel
    assert not duvidosa.bemois
    assert duvidosa.armadura is None, "sem confiança não se escreve armadura nenhuma"


def test_margem_folgada_escreve_a_armadura() -> None:
    confiante = Tonalidade(nome="f minor", sharps=-4, margem=0.33)

    assert confiante.confiavel and confiante.bemois
    assert confiante.armadura == -4


def test_sem_notas_nao_ha_o_que_estimar() -> None:
    assert estimar_tom([]) is None


@pytest.mark.parametrize(
    ("texto", "sharps"),
    [("F maior", -1), ("f menor", -4), ("Bb maior", -2), ("C# menor", 4), ("C maior", 0)],
)
def test_tom_informado_e_lido_em_portugues(texto: str, sharps: int) -> None:
    """Quem informa o tom manda — como o `--bpm` manda sobre o andamento (ADR-019)."""
    tom = tom_de_texto(texto)

    assert tom.armadura == sharps
    assert tom.confiavel, "tom informado não passa por margem nenhuma"


@pytest.mark.parametrize("texto", ["", "H menor", "F", "F maior menor", "Bb bemol"])
def test_tom_ilegivel_e_recusado_em_vez_de_virar_do_maior(texto: str) -> None:
    with pytest.raises(ValueError):
        tom_de_texto(texto)
