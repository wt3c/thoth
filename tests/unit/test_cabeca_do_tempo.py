"""Qual semicolcheia é a cabeça do tempo (ADR-054) — serviço puro, dados sintéticos."""

from __future__ import annotations

import pytest

from thoth.services.cabeca_do_tempo import deslocamento, recuo_na_cabeca
from thoth.services.rhythm import MapaDeAndamento

PULSO = 0.5  # 120 BPM
MAPA = MapaDeAndamento(bpm=120)


def _batidas(fracao: float, n: int = 40, passo: float = PULSO) -> list[float]:
    return [fracao * PULSO + i * passo for i in range(n)]


@pytest.mark.parametrize(("fracao", "esperado"), [(0.0, 0), (0.25, 1), (0.5, 2), (0.75, 3)])
def test_as_batidas_dizem_a_semicolcheia_da_cabeca(fracao: float, esperado: int) -> None:
    assert deslocamento(_batidas(fracao), MAPA) == esperado


def test_batidas_a_meio_tempo_decidem_do_mesmo_jeito() -> None:
    """Uma batida a cada dois pulsos ainda cai sempre na mesma fração."""
    assert deslocamento(_batidas(0.75, passo=2 * PULSO), MAPA) == 3


def test_batidas_em_dobro_sem_paridade_se_abstem() -> None:
    """Batida a cada meio pulso vota em ¼ e ¾ por igual: não há como escolher."""
    assert deslocamento(_batidas(0.25, passo=PULSO / 2), MAPA) is None


def test_sem_batidas_se_abstem() -> None:
    assert deslocamento([], MAPA) is None


def test_a_batida_e_lida_na_partitura_e_nao_no_audio() -> None:
    """Com recuo de uma semicolcheia, a batida no ¾ do áudio cai no ½ da partitura."""
    recuado = MapaDeAndamento(bpm=120, recuo=PULSO / 4)
    assert deslocamento(_batidas(0.75), recuado) == 2


def test_batida_antes_do_zero_da_partitura_conta_pela_fracao() -> None:
    recuado = MapaDeAndamento(bpm=120, recuo=0.4)
    assert deslocamento([0.4 - PULSO / 4 + i * PULSO for i in range(40)], recuado) == 3


def test_o_recuo_anda_ate_a_cabeca() -> None:
    grade = PULSO / 4
    assert recuo_na_cabeca(0.01, 3, grade, primeiro=1.0) == pytest.approx(0.01 + 3 * grade)


def test_nota_que_cairia_antes_do_zero_ganha_um_pulso_de_pausa() -> None:
    """Anacruse: o recuo volta um pulso inteiro, e a música começa com pausa."""
    grade = PULSO / 4
    assert recuo_na_cabeca(0.01, 3, grade, primeiro=0.05) == pytest.approx(0.01 - grade)


def test_sem_deslocamento_o_recuo_nao_muda() -> None:
    assert recuo_na_cabeca(-0.02, 0, PULSO / 4, primeiro=0.0) == -0.02


def test_sobra_menor_que_meia_semicolcheia_nao_vira_pausa() -> None:
    """O BPM refinado deixa a primeira nota 0,02 ms antes do zero: ela cai no tique
    zero do mesmo jeito, e um pulso de pausa ali seria inventado."""
    grade = 15 / 89.997  # 3 semicolcheias = 0,50002 s
    assert recuo_na_cabeca(0.0, 3, grade, primeiro=0.5) == pytest.approx(3 * grade)
