"""A avaliação completa não confunde altura com ritmo e corda/casa."""

import pytest

from thoth.domain.models import NoteEvent, TabNote
from thoth.services.evaluation import avaliar_tablatura


def _tab(
    corda: int = 1,
    casa: int = 5,
    inicio: float = 0.0,
    duracao: float = 0.5,
    altura: int = 38,
) -> TabNote:
    return TabNote(NoteEvent(altura, inicio, inicio + duracao, "electric_bass"), corda, casa)


def test_re_solto_nao_equivale_ao_re_na_corda_la() -> None:
    resultado = avaliar_tablatura([_tab()], [_tab(corda=2, casa=0)])

    assert resultado.alturas == 1
    assert resultado.posicoes == 0
    assert resultado.completas == 0
    assert not resultado.coincide


def test_duracao_diferente_impede_coincidencia() -> None:
    resultado = avaliar_tablatura([_tab()], [_tab(duracao=0.25)])

    assert resultado.alturas == resultado.posicoes == 1
    assert resultado.duracoes == resultado.completas == 0
    assert not resultado.coincide


def test_altura_errada_nao_vira_acerto_de_posicao() -> None:
    resultado = avaliar_tablatura([_tab()], [_tab(casa=6, altura=39)])

    assert resultado.ataques == resultado.duracoes == 1
    assert resultado.alturas == resultado.posicoes == resultado.completas == 0
    assert not resultado.coincide


def test_nota_extra_nao_pode_reusar_um_ataque_do_gabarito() -> None:
    resultado = avaliar_tablatura([_tab()], [_tab(), _tab()])

    assert resultado.ataques == resultado.completas == 1
    assert resultado.faltantes == 0
    assert resultado.extras == 1
    assert not resultado.coincide


def test_pausa_maior_muda_o_ritmo_mesmo_com_alturas_iguais() -> None:
    resultado = avaliar_tablatura([_tab(), _tab(inicio=1)], [_tab(), _tab(inicio=1.25)])

    assert resultado.ataques == resultado.completas == 1
    assert resultado.faltantes == resultado.extras == 1
    assert not resultado.coincide


def test_arquivos_equivalentes_coincidem_na_tolerancia_declarada() -> None:
    resultado = avaliar_tablatura([_tab(), _tab(inicio=1)], [_tab(inicio=1), _tab()])

    assert resultado.coincide
    assert resultado.faltantes == resultado.extras == 0
    assert resultado.completas == 2


def test_estimativa_vazia_nao_coincide() -> None:
    resultado = avaliar_tablatura([_tab()], [])

    assert resultado.faltantes == 1
    assert resultado.extras == resultado.completas == 0
    assert not resultado.coincide


def test_referencia_vazia_nao_e_um_gabarito_valido() -> None:
    with pytest.raises(ValueError, match="referência"):
        avaliar_tablatura([], [_tab()])


@pytest.mark.parametrize("campo", ["tolerancia_s", "tolerancia_duracao_s"])
def test_recusa_tolerancia_negativa(campo: str) -> None:
    with pytest.raises(ValueError, match="tolerância"):
        avaliar_tablatura([_tab()], [_tab()], **{campo: -0.01})


def test_tolerancia_e_explicita_para_tempo_e_duracao() -> None:
    referencia = [_tab()]
    estimada = [_tab(inicio=0.02, duracao=0.52)]

    assert avaliar_tablatura(referencia, estimada, tolerancia_s=0.03).coincide
    assert not avaliar_tablatura(referencia, estimada, tolerancia_s=0).coincide
    assert not avaliar_tablatura(
        referencia, estimada, tolerancia_s=0.03, tolerancia_duracao_s=0.01
    ).coincide
