"""O avaliador é tão capaz de produzir decisão errada quanto o transcritor.

Estes testes batem no mir_eval real: ele é biblioteca pura, e é justamente o
contrato dele (ordem dos argumentos, semântica de `offset_ratio`, janela) que um
mock esconderia.
"""

from __future__ import annotations

import pretty_midi
import pytest

from thoth.domain.models import EventoPercussivo, NoteEvent
from thoth.services.evaluation import (
    Prf,
    Scores,
    avaliar,
    avaliar_bateria,
    avaliar_polifonico,
    notas_do_midi,
    revocacao_por_acorde,
)


def _nota(pitch: int, inicio: float, dur: float = 0.4) -> NoteEvent:
    return NoteEvent(pitch=pitch, onset_s=inicio, offset_s=inicio + dur,
                     instrument="electric_bass")


REFERENCIA = [_nota(36, 0.0), _nota(38, 0.5), _nota(40, 1.0), _nota(41, 1.5)]


def test_identico_pontua_um() -> None:
    assert avaliar(REFERENCIA, list(REFERENCIA)) == Scores(1.0, 1.0, 4, 4, 1.0, 1.0)


def test_desvio_dentro_da_tolerancia_ainda_acerta() -> None:
    deslocada = [_nota(n.pitch, n.onset_s + 0.04) for n in REFERENCIA]
    assert avaliar(deslocada[:], REFERENCIA).onset_f1 == 1.0


def test_desvio_acima_da_tolerancia_zera() -> None:
    deslocada = [_nota(n.pitch, n.onset_s + 0.09) for n in REFERENCIA]
    assert avaliar(REFERENCIA, deslocada).onset_f1 == 0.0


def test_oitava_errada_mantem_onset_e_derruba_nota() -> None:
    """A distinção que motivou o verificador de oitavas: o onset não a enxerga."""
    resultado = avaliar(REFERENCIA, [_nota(n.pitch + 12, n.onset_s) for n in REFERENCIA])
    assert resultado.onset_f1 == 1.0
    assert resultado.note_f1 == 0.0


def test_estimativa_vazia_pontua_zero_sem_estourar() -> None:
    assert avaliar(REFERENCIA, []) == Scores(0.0, 0.0, 4, 0, 0.0, None)


def test_nota_de_duracao_nula_nao_quebra_o_avaliador() -> None:
    """O MuScriptor já emitiu `end_time == start_time`; mir_eval rejeita isso."""
    degenerada = [*REFERENCIA[:3], _nota(41, 1.5, dur=0.0)]
    assert avaliar(REFERENCIA, degenerada).onset_f1 == 1.0


def test_referencia_vazia_e_erro_do_chamador() -> None:
    with pytest.raises(ValueError, match="referência vazia"):
        avaliar([], REFERENCIA)


def test_notas_do_midi_le_apenas_o_baixo(tmp_path) -> None:
    """A fixture `misto` tem piano no instrumento 1 — ele é distrator, não alvo."""
    pm = pretty_midi.PrettyMIDI()
    baixo = pretty_midi.Instrument(program=33)
    baixo.notes.append(pretty_midi.Note(velocity=100, pitch=36, start=0.5, end=0.9))
    baixo.notes.append(pretty_midi.Note(velocity=100, pitch=31, start=0.0, end=0.4))
    piano = pretty_midi.Instrument(program=0)
    piano.notes.append(pretty_midi.Note(velocity=80, pitch=60, start=0.0, end=1.0))
    pm.instruments += [baixo, piano]
    caminho = tmp_path / "x.mid"
    pm.write(str(caminho))

    notas = notas_do_midi(caminho)

    assert [n.pitch for n in notas] == [31, 36]  # ordenado por onset, sem o piano


# --- Duração: a régua que faltava (ADR-023) ----------------------------------


def test_identico_acerta_a_duracao_tambem() -> None:
    resultado = avaliar(REFERENCIA, list(REFERENCIA))
    assert resultado.nota_offset_f1 == 1.0
    assert resultado.duracao_ratio == 1.0


def test_duracao_pela_metade_passa_nas_duas_metricas_antigas() -> None:
    """Exatamente o defeito que o ADR-022 corrigiu: invisível para onset e nota."""
    curtas = [_nota(n.pitch, n.onset_s, dur=0.2) for n in REFERENCIA]
    resultado = avaliar(REFERENCIA, curtas)

    assert resultado.onset_f1 == 1.0
    assert resultado.note_f1 == 1.0
    assert resultado.nota_offset_f1 == 0.0
    assert resultado.duracao_ratio == 0.5


def test_duracao_dentro_da_tolerancia_de_offset_ainda_acerta() -> None:
    """`offset_ratio=0.2` é o padrão do mir_eval: 10% a mais continua a mesma nota."""
    longas = [_nota(n.pitch, n.onset_s, dur=0.44) for n in REFERENCIA]
    resultado = avaliar(REFERENCIA, longas)

    assert resultado.nota_offset_f1 == 1.0
    assert resultado.duracao_ratio == 1.1


def test_sem_nota_casada_a_duracao_nao_tem_o_que_medir() -> None:
    """`None`, não zero: zero se leria como 'todas as durações saíram nulas'."""
    assert avaliar(REFERENCIA, []).duracao_ratio is None
    deslocada = [_nota(n.pitch, n.onset_s + 0.09) for n in REFERENCIA]
    assert avaliar(REFERENCIA, deslocada).duracao_ratio is None


# --- Polifonia e bateria (ADR-044) -------------------------------------------------

ACORDES = [
    _nota(p, t) for t in (0.0, 1.0) for p in (40, 47, 52, 56, 59, 64)
]


def test_polifonico_identico_pontua_um_em_ataque_e_nota() -> None:
    s = avaliar_polifonico(ACORDES, list(ACORDES))

    assert s.ataque == Prf(1.0, 1.0, 1.0)
    assert s.nota == Prf(1.0, 1.0, 1.0)
    assert (s.n_ref, s.n_est) == (12, 12)


def test_polifonico_conta_cada_nota_do_acorde_e_nao_so_o_instante() -> None:
    """Um acorde de seis notas transcrito com duas perde revocação, não só precisão."""
    duas_por_acorde = [n for n in ACORDES if n.pitch in (40, 64)]

    s = avaliar_polifonico(ACORDES, duas_por_acorde)

    assert s.nota.precisao == 1.0
    assert s.nota.revocacao == round(4 / 12, 3)


def test_polifonico_altura_errada_mantem_ataque_e_derruba_nota() -> None:
    meio_tom_acima = [_nota(n.pitch + 1, n.onset_s) for n in ACORDES]

    s = avaliar_polifonico(ACORDES, meio_tom_acima)

    assert s.ataque.f1 == 1.0
    assert s.nota.f1 == 0.0


def test_polifonico_nao_cobra_duracao() -> None:
    curtas = [_nota(n.pitch, n.onset_s, dur=0.05) for n in ACORDES]

    assert avaliar_polifonico(ACORDES, curtas).nota.f1 == 1.0


def test_polifonico_recusa_referencia_vazia_e_zera_estimativa_vazia() -> None:
    with pytest.raises(ValueError):
        avaliar_polifonico([], ACORDES)
    assert avaliar_polifonico(ACORDES, []).nota == Prf(0.0, 0.0, 0.0)


def test_revocacao_por_acorde_separa_pelo_tamanho_do_acorde_da_referencia() -> None:
    """Uma nota perdida no acorde de seis não pode se esconder atrás da nota solta."""
    ref = [*ACORDES[:6], _nota(45, 1.0)]
    sem_a_mais_aguda = [n for n in ref if n.pitch != 64]

    assert revocacao_por_acorde(ref, sem_a_mais_aguda) == {1: (1, 1), 6: (5, 6)}


def test_revocacao_por_acorde_identica_casa_tudo() -> None:
    assert revocacao_por_acorde(ACORDES, list(ACORDES)) == {6: (12, 12)}


def test_ataques_a_menos_de_50_ms_sao_o_mesmo_acorde() -> None:
    """A mesma tolerância com que o avaliador casa ataques e o `ViterbiAcordes` agrupa."""
    rasgueado = [_nota(40, 0.0), _nota(47, 0.02), _nota(52, 0.04)]
    separadas = [_nota(40, 0.0), _nota(47, 0.06)]

    assert revocacao_por_acorde(rasgueado, rasgueado) == {3: (3, 3)}
    assert revocacao_por_acorde(separadas, separadas) == {1: (2, 2)}


def test_revocacao_por_acorde_recusa_referencia_vazia_e_zera_estimativa_vazia() -> None:
    with pytest.raises(ValueError):
        revocacao_por_acorde([], ACORDES)
    assert revocacao_por_acorde(ACORDES, []) == {6: (0, 12)}


GROOVE = [
    EventoPercussivo(t, p)
    for t, pecas in [(0.0, (36, 42)), (0.5, (38, 42)), (1.0, (36, 42)), (1.5, (38, 42))]
    for p in pecas
]


def test_bateria_identica_pontua_um_micro_e_macro() -> None:
    s = avaliar_bateria(GROOVE, list(GROOVE))

    assert s.micro == Prf(1.0, 1.0, 1.0)
    assert s.macro_f1 == 1.0
    assert set(s.por_peca) == {36, 38, 42}


def test_bateria_troca_de_peca_conta_como_erro() -> None:
    """Caixa lida como bumbo: o instante está certo, a peça não."""
    trocada = [EventoPercussivo(a.instante_s, 36 if a.peca_gm == 38 else a.peca_gm)
               for a in GROOVE]

    s = avaliar_bateria(GROOVE, trocada)

    assert s.por_peca[38].revocacao == 0.0
    assert s.por_peca[36].precisao == 0.5
    assert s.por_peca[42] == Prf(1.0, 1.0, 1.0)
    assert s.micro.f1 < 1.0


def test_bateria_ataque_deslocado_alem_de_50_ms_erra() -> None:
    deslocado = [EventoPercussivo(a.instante_s + 0.06, a.peca_gm) for a in GROOVE]

    assert avaliar_bateria(GROOVE, deslocado).micro.f1 == 0.0
    dentro = [EventoPercussivo(a.instante_s + 0.04, a.peca_gm) for a in GROOVE]
    assert avaliar_bateria(GROOVE, dentro).micro.f1 == 1.0


def test_macro_ignora_peca_ausente_da_referencia_mas_micro_a_cobra() -> None:
    """Peça só na estimativa não tem revocação definida: não vira zero no macro."""
    com_prato = [*GROOVE, EventoPercussivo(0.0, 49)]

    s = avaliar_bateria(GROOVE, com_prato)

    assert 49 not in s.por_peca
    assert s.macro_f1 == 1.0
    assert s.micro.precisao == round(8 / 9, 3)
