"""Grade rítmica: colisão na semicolcheia e política de monofonia."""

from __future__ import annotations

from thoth.domain.models import NoteEvent, TabNote
from thoth.services.rhythm import eventos, monofonizar


def _nota(pitch: int, onset: float) -> NoteEvent:
    return NoteEvent(pitch=pitch, onset_s=onset, offset_s=onset + 0.4, instrument="electric_bass")


def test_monofonizar_mantem_a_nota_mais_grave_do_grupo() -> None:
    """Num acorde de baixo a nota que sustenta a harmonia é a fundamental."""
    mantidas, descartadas = monofonizar([_nota(43, 0.0), _nota(31, 0.0)], bpm=120)

    assert [n.pitch for n in mantidas] == [31]
    assert [n.pitch for n in descartadas] == [43]


def test_monofonizar_colide_na_grade_e_nao_no_onset_cru() -> None:
    """20 ms separam no relógio e não separam na semicolcheia — é a grade que decide."""
    mantidas, descartadas = monofonizar([_nota(31, 0.0), _nota(43, 0.02)], bpm=120)

    assert len(mantidas) == 1
    assert len(descartadas) == 1


def test_monofonizar_preserva_notas_em_semicolcheias_vizinhas() -> None:
    passo = 60 / 120 / 4  # uma semicolcheia a 120 BPM
    notas = [_nota(36 + i, i * passo) for i in range(4)]

    mantidas, descartadas = monofonizar(notas, bpm=120)

    assert len(mantidas) == 4
    assert descartadas == []


def test_monofonizar_devolve_saida_que_eventos_aceita() -> None:
    """O contrato: o que sai daqui não pode mais fazer `eventos` levantar erro."""
    mantidas, _ = monofonizar([_nota(31, 0.0), _nota(43, 0.0), _nota(38, 0.5)], bpm=120)
    tabs = [TabNote(event=n, string=0, fret=n.pitch - 28) for n in mantidas]

    assert len(eventos(tabs, bpm=120)) == 2
