"""A digitação aprendida contra as tabs humanas reais de `samples/` (ADR-055).

As tabs ficam fora do repositório (ADR-005); sem elas, `skip`. O modelo versionado
guarda o sha256 de cada tab de treino: tab trocada aparece aqui, não em silêncio.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from thoth.services.digitacao_aprendida import (
    ACEITACAO,
    TESTE_LIMPO,
    DigitacaoAprendida,
    carregar_modelo,
    sha256,
    treinar,
)
from thoth.services.fretboard import PADRAO, ViterbiFretAssigner
from thoth.services.tab_referencia import Referencia, ler_tab

SAMPLES = Path("samples")

pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(not SAMPLES.is_dir(), reason=f"tabs humanas ausentes em {SAMPLES}"),
]


def _acerto(assigner: object, r: Referencia) -> float:
    tabs = assigner.assign(r.notas, r.afinacao)  # type: ignore[attr-defined]
    iguais = sum(
        (h.string, h.fret) == (e.string, e.fret) for h, e in zip(r.tablatura, tabs, strict=True)
    )
    return iguais / len(r.notas)


def test_tabs_de_treino_sao_as_do_modelo() -> None:
    for nome, esperado in carregar_modelo().treino.items():
        assert sha256(SAMPLES / nome) == esperado, nome


def test_treino_reproduz_os_pesos_versionados() -> None:
    modelo = carregar_modelo()

    pesos = treinar({nome: ler_tab(SAMPLES / nome) for nome in modelo.treino})

    assert pesos == modelo.pesos


@pytest.mark.parametrize(
    ("nome", "faixa", "piso"),
    [
        # Medidos uma vez em 2026-10-30, com régua congelada antes: 0,395 → 0,800 e 0,738 → 0,858.
        (TESTE_LIMPO, 4, 0.415),
        (ACEITACAO, None, 0.738),
    ],
)
def test_tab_fora_do_treino_supera_o_experiente(nome: str, faixa: int | None, piso: float) -> None:
    r = ler_tab(SAMPLES / nome, faixa)

    medido = _acerto(DigitacaoAprendida(carregar_modelo().pesos), r)
    experiente = _acerto(ViterbiFretAssigner(custos=PADRAO), r)

    print(f"{nome}: experiente {experiente:.3f}, aprendida {medido:.3f}, piso {piso}")
    assert medido > piso
