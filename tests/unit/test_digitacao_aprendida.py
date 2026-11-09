"""Digitação aprendida nas tabs humanas, só para baixo de 4 cordas (ADR-055)."""

from __future__ import annotations

import pytest

from thoth.domain.models import NoteEvent
from thoth.services.digitacao_aprendida import (
    ACEITACAO,
    TESTE_LIMPO,
    DigitacaoAprendida,
    carregar_modelo,
)
from thoth.services.fretboard import PADRAO, AlturaImpossivelError, ViterbiFretAssigner

QUATRO = (28, 33, 38, 43)
CINCO = (23, 28, 33, 38, 43)


def _frase(alturas_e_tempos: list[tuple[int, float]]) -> list[NoteEvent]:
    return [
        NoteEvent(pitch=p, onset_s=t, offset_s=t + 0.1, instrument="electric_bass")
        for p, t in alturas_e_tempos
    ]


def _posicoes(tabs: list) -> list[tuple[int, int]]:  # type: ignore[type-arg]
    return [(t.string, t.fret) for t in tabs]


#: Frase real de _Watashi Igai Watashi Ja Nai No_ (tab de treino): Ré e Fá alternados.
#: O baixista pisa o Ré na casa 5 da corda Lá; o `experiente` usa a corda Ré solta.
GESU = _frase([(38, 0.0), (41, 0.11), (38, 0.221), (41, 0.441)])


def test_aprendida_pisa_o_re_como_o_baixista_da_tab_humana() -> None:
    aprendida = DigitacaoAprendida(carregar_modelo().pesos)

    assert _posicoes(aprendida.assign(GESU, QUATRO)) == [(1, 5), (2, 3), (1, 5), (2, 3)]
    assert _posicoes(ViterbiFretAssigner(custos=PADRAO).assign(GESU, QUATRO)) == [
        (2, 0),
        (2, 3),
        (2, 0),
        (2, 3),
    ]


def test_cinco_cordas_fica_com_o_experiente() -> None:
    """Na validação, as tabs de 5 e 6 cordas perderam com o modelo aprendido (ADR-055)."""
    aprendida = DigitacaoAprendida(carregar_modelo().pesos)
    experiente = ViterbiFretAssigner(custos=PADRAO)

    assert aprendida.assign(GESU, CINCO) == experiente.assign(GESU, CINCO)


def test_ordena_por_onset_como_o_viterbi() -> None:
    aprendida = DigitacaoAprendida(carregar_modelo().pesos)

    tabs = aprendida.assign(list(reversed(GESU)), QUATRO)

    assert [t.event.onset_s for t in tabs] == [n.onset_s for n in GESU]


def test_frase_vazia_nao_tem_posicao() -> None:
    assert DigitacaoAprendida(carregar_modelo().pesos).assign([], QUATRO) == []


def test_altura_fora_do_braco_e_recusada_como_no_viterbi() -> None:
    with pytest.raises(AlturaImpossivelError):
        DigitacaoAprendida(carregar_modelo().pesos).assign(_frase([(20, 0.0)]), QUATRO)


def test_tabs_de_teste_nunca_entram_no_treino() -> None:
    """_Você_ e _Fear of the Dark_ só medem; o modelo nunca viu corda/casa delas."""
    modelo = carregar_modelo()

    assert ACEITACAO not in modelo.treino
    assert TESTE_LIMPO not in modelo.treino
    assert len(modelo.treino) == 5
