"""O motor de tablatura: notas → (corda, traste).

A mesma altura cabe em até quatro lugares no braço. Escolher é otimizar um
caminho, não classificar nota a nota — por isso Viterbi, e por isso os testes
cobram **frases**, não notas isoladas.
"""

from __future__ import annotations

from itertools import pairwise
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from tests.sintetico import FIXTURES
from thoth.domain.models import TUNING_BASS_4, TUNING_BASS_5, NoteEvent
from thoth.services.evaluation import notas_do_midi
from thoth.services.fretboard import (
    INICIANTE,
    PADRAO,
    PRIMEIRA_POSICAO,
    AlturaImpossivelError,
    Custos,
    ViterbiFretAssigner,
)


def _linha(pitches: list[int]) -> list[NoteEvent]:
    return [
        NoteEvent(pitch=p, onset_s=i * 0.5, offset_s=i * 0.5 + 0.4, instrument="electric_bass")
        for i, p in enumerate(pitches)
    ]


def _posicoes(pitches: list[int], **kwargs: object) -> list[tuple[int, int]]:
    tabs = ViterbiFretAssigner(**kwargs).assign(_linha(pitches), TUNING_BASS_4)  # type: ignore[arg-type]
    return [(t.string, t.fret) for t in tabs]


def test_corda_solta_grave() -> None:
    assert _posicoes([28]) == [(0, 0)]  # E1 = corda 4 solta


def test_cinco_cordas_alcanca_si_zero() -> None:
    tabs = ViterbiFretAssigner().assign(_linha([23]), TUNING_BASS_5)
    assert [(t.string, t.fret) for t in tabs] == [(0, 0)]


def test_grave_demais_para_a_afinacao_e_erro() -> None:
    with pytest.raises(AlturaImpossivelError, match="23"):
        _posicoes([23])  # B0 não existe num baixo de 4 cordas


def test_agudo_demais_para_o_braco_e_erro() -> None:
    with pytest.raises(AlturaImpossivelError, match="96"):
        _posicoes([96])


def test_max_fret_empurra_para_a_corda_seguinte() -> None:
    # A1 (33): corda 0 traste 5, ou corda 1 solta. Com o braço cortado no 4º
    # traste, só resta a corda 1.
    tabs = ViterbiFretAssigner().assign(_linha([33]), TUNING_BASS_4, max_fret=4)
    assert [(t.string, t.fret) for t in tabs] == [(1, 0)]


def test_iniciante_prefere_corda_solta_a_traste_equivalente() -> None:
    assert _posicoes([33], custos=INICIANTE) == [(1, 0)]


def test_iniciante_nao_sobe_o_braco_quando_ha_alternativa_grave() -> None:
    """D3 (50) cabe no traste 7 da corda 3 ou no 12 da corda 2: o iniciante fica embaixo."""
    assert _posicoes([50], custos=INICIANTE) == [(3, 7)]


def test_frase_nao_atravessa_o_braco_a_toa() -> None:
    """Escala de dó: cada nota tem alternativa longe; a frase toda cabe embaixo."""
    trastes = [f for _, f in _posicoes([36, 38, 40, 41, 43, 45, 47, 48], custos=INICIANTE)]
    assert max(trastes) - min(t for t in trastes if t > 0) <= 4


def test_salto_de_oitava_troca_corda_em_vez_de_correr_o_braco() -> None:
    """36→48: 12 trastes na mesma corda, ou duas cordas acima no mesmo traste."""
    posicoes = _posicoes([36, 48, 36, 48], custos=PADRAO)
    saltos = [abs(a[1] - b[1]) for a, b in pairwise(posicoes)]
    assert max(saltos) <= 2


def test_lista_vazia_devolve_vazio() -> None:
    assert ViterbiFretAssigner().assign([], TUNING_BASS_4) == []


def test_preserva_o_evento_original() -> None:
    notas = _linha([36, 43])
    tabs = ViterbiFretAssigner().assign(notas, TUNING_BASS_4)
    assert [t.event for t in tabs] == notas


@given(st.data())
def test_propriedade_altura_e_braco(dados: st.DataObject) -> None:
    """A tab tem que *soar* igual: corda + traste reconstrói a altura, sempre."""
    max_fret = dados.draw(st.integers(min_value=5, max_value=24))
    # O braço é o limite superior: acima dele a nota não existe, e a resposta
    # certa é IMPOSSIVEL — coberto pelo seu próprio teste, não por este.
    pitches = dados.draw(
        st.lists(
            st.integers(min_value=TUNING_BASS_4[0], max_value=TUNING_BASS_4[-1] + max_fret),
            min_size=1,
            max_size=40,
        )
    )
    tabs = ViterbiFretAssigner().assign(_linha(pitches), TUNING_BASS_4, max_fret=max_fret)

    assert len(tabs) == len(pitches)
    for tab, pitch in zip(tabs, pitches, strict=True):
        assert TUNING_BASS_4[tab.string] + tab.fret == pitch
        assert 0 <= tab.fret <= max_fret
        assert 0 <= tab.string < len(TUNING_BASS_4)


def test_iniciante_desce_o_braco_onde_o_experiente_nao_se_importa() -> None:
    """Sem este contraste, o "modo iniciante" do ADR-006 seria só um rótulo.

    O custo linear por traste não basta: ele empurra todas as opções na mesma
    direção e quase nunca inverte a escolha. Quem separa os modos é a penalidade
    fora da primeira posição.
    """
    linha = [46, 55, 57, 53]
    iniciante = _posicoes(linha, custos=INICIANTE)
    padrao = _posicoes(linha, custos=PADRAO)

    assert iniciante != padrao
    assert iniciante[0] == (3, 3)  # Bb2 na corda G, dentro da janela da mão
    assert padrao[0] == (2, 8)


@pytest.mark.parametrize(
    ("nome", "afinacao"),
    [
        ("escala", TUNING_BASS_4),
        ("walking", TUNING_BASS_4),
        ("groove16", TUNING_BASS_4),
        ("oitavas", TUNING_BASS_4),
        ("misto", TUNING_BASS_4),
        ("graves", TUNING_BASS_5),  # desce a B0: exige a quinta corda
    ],
)
def test_fixtures_cabem_na_primeira_posicao(
    nome: str, afinacao: tuple[int, ...], tmp_path: Path
) -> None:
    """Critério de pronto da Fase 3, verificado por propriedade — não no instrumento."""
    mid = tmp_path / f"{nome}.mid"
    FIXTURES[nome].write(str(mid))
    notas = notas_do_midi(mid)

    tabs = ViterbiFretAssigner(custos=INICIANTE).assign(notas, afinacao)

    assert notas, f"{nome}: fixture sem notas de baixo"
    assert max(t.fret for t in tabs) <= PRIMEIRA_POSICAO
    assert all(afinacao[t.string] + t.fret == t.event.pitch for t in tabs)


def test_entrada_fora_de_ordem_e_posicionada_pelo_tempo() -> None:
    """O custo de transição só significa algo entre vizinhas no tempo."""
    fora_de_ordem = [_linha([36, 48])[1], _linha([36, 48])[0]]

    tabs = ViterbiFretAssigner().assign(fora_de_ordem, TUNING_BASS_4)

    assert [t.event.pitch for t in tabs] == [36, 48]


def test_a_corda_solta_nao_apaga_a_posicao_da_mao() -> None:
    """ADR-032: a mão fica onde estava; a nota depois da solta parte dali.

    Perfil experiente, onde o teleporte disparava: o `acima_da_janela` do
    iniciante já prende a mão no grave e esconde o defeito.

    G3 (52) só é barato no traste 9; depois da corda solta, E2 (40) cabe no
    traste 2 (longe da mão) ou no 7 (do lado dela). Antes do ADR-032 a solta
    zerava a conta e o 2 saía de graça.
    """
    assert _posicoes([52, 28, 40], custos=PADRAO) == [(3, 9), (0, 0), (1, 7)]


def test_a_primeira_nota_solta_nao_ancora_a_mao_na_pestana() -> None:
    """Mão ainda não posicionada não paga deslocamento — nem contra o traste 0.

    Pesos escolhidos para isolar o termo: sem `traste_alto`, só o deslocamento
    ordena as opções. Ancorar a mão na pestana na abertura da linha jogaria E2
    (40) para o traste 2; com a mão indefinida, ela vai para onde a troca de
    corda é de graça.
    """
    so_deslocamento = Custos(
        traste_alto=0.0, corda_solta=1.0, deslocamento=1.0, troca_corda=0.5,
        acima_da_janela=0.0,
    )
    assert _posicoes([28, 40], custos=so_deslocamento) == [(0, 0), (0, 12)]
