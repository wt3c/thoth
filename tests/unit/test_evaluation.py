"""O avaliador é tão capaz de produzir decisão errada quanto o transcritor.

Estes testes batem no mir_eval real: ele é biblioteca pura, e é justamente o
contrato dele (ordem dos argumentos, semântica de `offset_ratio`, janela) que um
mock esconderia.
"""

from __future__ import annotations

import pretty_midi
import pytest

from thoth.domain.models import NoteEvent
from thoth.services.evaluation import Scores, avaliar, notas_do_midi


def _nota(pitch: int, inicio: float, dur: float = 0.4) -> NoteEvent:
    return NoteEvent(pitch=pitch, onset_s=inicio, offset_s=inicio + dur,
                     instrument="electric_bass")


REFERENCIA = [_nota(36, 0.0), _nota(38, 0.5), _nota(40, 1.0), _nota(41, 1.5)]


def test_identico_pontua_um() -> None:
    assert avaliar(REFERENCIA, list(REFERENCIA)) == Scores(1.0, 1.0, 4, 4)


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
    assert avaliar(REFERENCIA, []) == Scores(0.0, 0.0, 4, 0)


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
