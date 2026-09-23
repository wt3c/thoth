"""Grade rítmica: colisão na semicolcheia e política de monofonia."""

from __future__ import annotations

import pytest

from thoth.domain.models import NoteEvent, TabNote
from thoth.services.rhythm import PPQ, alinhar, eventos, monofonizar


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


# --- Alinhamento à fase da grade (ADR-021) -----------------------------------


def test_alinhar_desloca_onset_e_offset_juntos() -> None:
    """Deslocar só o ataque esticaria a nota — a duração é a mesma música."""
    (nota,) = alinhar([_nota(31, 1.0)], bpm=120, fase=0.1)

    assert nota.onset_s == pytest.approx(0.9)
    assert nota.offset_s == pytest.approx(1.3)


def test_alinhar_nao_produz_tempo_negativo() -> None:
    """A fase é uma grade inteira: adiantar para antes do zero é o mesmo retículo."""
    grade = 60.0 / 120 / 4

    (nota,) = alinhar([_nota(31, 0.02)], bpm=120, fase=0.1)

    assert nota.onset_s >= 0
    assert nota.onset_s == pytest.approx(0.02 - 0.1 + grade)


def test_alinhar_sem_fase_e_inocuo() -> None:
    notas = [_nota(31, 0.0), _nota(36, 1.0)]

    assert alinhar(notas, bpm=120, fase=0.0) == notas


def test_deduplicar_e_exportar_tem_que_ser_a_mesma_grade() -> None:
    """Fases diferentes nas duas contas deixam passar um par que `eventos` recusa.

    As duas notas caem em retículos distintos na fase 0 e no mesmo depois do
    deslocamento: se `monofonizar` rodar antes de `alinhar`, aprova o par e
    `eventos` estoura. Deslocar primeiro é o que mantém as contas coerentes.
    """
    grade = 60.0 / 120 / 4
    notas = [_nota(31, 4.4 * grade), _nota(36, 4.6 * grade)]
    fase = 0.45 * grade

    mantidas, descartadas = monofonizar(alinhar(notas, 120, fase), bpm=120)

    assert len(mantidas) == 1 and len(descartadas) == 1
    eventos([TabNote(event=n, string=0, fret=0) for n in mantidas], bpm=120)


# --- Sustentação através da barra (ADR-022) ----------------------------------


def test_nota_sustentada_mantem_a_duracao_real_atraves_da_barra() -> None:
    """Cortar na barra trocava legato por ataque curto: 1,5 semínima virava 0,5.

    Quem decide como representar a continuação é o exportador — aqui a duração
    sai inteira, porque nenhum dos dois formatos consegue ligar o que não recebeu.
    """
    nota = NoteEvent(pitch=36, onset_s=3.5 * 0.5, offset_s=5.0 * 0.5,
                     instrument="electric_bass")

    (inicio, duracao, _), = eventos([TabNote(event=nota, string=0, fret=8)], bpm=120)

    assert inicio == PPQ * 7 // 2
    assert duracao == PPQ * 3 // 2


def test_a_nota_seguinte_ainda_corta_a_anterior() -> None:
    """Soltar a barra não pode soltar a monofonia: sobreposição é tab impossível."""
    notas = [
        NoteEvent(pitch=36, onset_s=0.0, offset_s=2.0, instrument="electric_bass"),
        NoteEvent(pitch=38, onset_s=0.5, offset_s=1.0, instrument="electric_bass"),
    ]
    tabs = [TabNote(event=n, string=0, fret=0) for n in notas]

    (_, primeira, _), _ = eventos(tabs, bpm=120)

    assert primeira == PPQ  # cortada na segunda, não em 2 s
