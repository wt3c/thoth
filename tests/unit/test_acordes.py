"""Acordes → posições no braço da guitarra (ADR-044, M4).

Contrato separado do `FretAssigner` do baixo, que pressupõe linha monofônica: aqui
cada nota de um acorde precisa de uma corda própria, e a mão tem alcance. O acorde
que não cabe é relatado inteiro, nunca reduzido a uma nota só em silêncio.
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from tests.sintetico_multi import FIXTURES_MULTI, referencia
from thoth.domain.instrumentos import TUNING_GUITARRA_6
from thoth.domain.models import NoteEvent, TabNote
from thoth.services.acordes import ABERTURA_MAXIMA, JANELA_ACORDE_S, ViterbiAcordes

ROTULO = "clean_electric_guitar"


def _acorde(pitches: tuple[int, ...], onset: float) -> list[NoteEvent]:
    return [NoteEvent(p, onset, onset + 0.4, ROTULO) for p in pitches]


def _formas(tab: tuple[TabNote, ...]) -> list[dict[int, int]]:
    """Cada acorde como {corda: traste}, na ordem do tempo."""
    por_onset: dict[float, dict[int, int]] = {}
    for t in tab:
        por_onset.setdefault(t.event.onset_s, {})[t.string] = t.fret
    return [por_onset[o] for o in sorted(por_onset)]


def test_sem_notas_nada_a_posicionar() -> None:
    r = ViterbiAcordes().posicionar([], TUNING_GUITARRA_6)

    assert r.tab == ()
    assert r.impossiveis == ()


def test_mi_maior_sai_na_forma_aberta() -> None:
    """E2 B2 E3 G#3 B3 E4: a digitação que todo método ensina, 0-2-2-1-0-0."""
    r = ViterbiAcordes().posicionar(_acorde((40, 47, 52, 56, 59, 64), 0.0), TUNING_GUITARRA_6)

    assert _formas(r.tab) == [{0: 0, 1: 2, 2: 2, 3: 1, 4: 0, 5: 0}]


def test_notas_dentro_da_janela_sao_um_acorde_e_fora_dela_nao() -> None:
    """Duas notas que só cabem na mesma corda: juntas, impossível; separadas, tocável."""
    juntas = [NoteEvent(40, 0.0, 0.4, ROTULO), NoteEvent(41, JANELA_ACORDE_S / 2, 0.4, ROTULO)]
    separadas = [NoteEvent(40, 0.0, 0.4, ROTULO), NoteEvent(41, 0.5, 0.9, ROTULO)]

    assert len(ViterbiAcordes().posicionar(juntas, TUNING_GUITARRA_6).impossiveis) == 1
    r = ViterbiAcordes().posicionar(separadas, TUNING_GUITARRA_6)
    assert r.impossiveis == ()
    assert [(t.string, t.fret) for t in r.tab] == [(0, 0), (0, 1)]


def test_acorde_de_sete_notas_e_relatado_e_o_resto_segue() -> None:
    notas = [
        *_acorde((40, 45, 50, 55, 59, 64, 67), 0.0),
        *_acorde((45, 52, 57, 61, 64), 1.0),
    ]

    r = ViterbiAcordes().posicionar(notas, TUNING_GUITARRA_6)

    (impossivel,) = r.impossiveis
    assert len(impossivel.notas) == 7
    assert "cordas" in impossivel.motivo
    assert {t.event.onset_s for t in r.tab} == {1.0}


def test_altura_fora_do_braco_derruba_o_acorde_com_motivo() -> None:
    r = ViterbiAcordes().posicionar(_acorde((35, 52), 0.0), TUNING_GUITARRA_6)

    (impossivel,) = r.impossiveis
    assert "35" in impossivel.motivo
    assert r.tab == ()


def test_acorde_que_passa_do_alcance_da_mao_e_impossivel() -> None:
    """F2 só existe na corda 0, traste 1; B4 só a partir do traste 7. A mão não abre tanto."""
    r = ViterbiAcordes().posicionar(_acorde((41, 71), 0.0), TUNING_GUITARRA_6)

    (impossivel,) = r.impossiveis
    assert "alcance" in impossivel.motivo


def test_fixture_de_guitarra_posiciona_todos_os_acordes() -> None:
    """Os 16 eventos do gerador foram escritos tocáveis na afinação padrão."""
    ref = referencia(FIXTURES_MULTI["guitarra-limpa-isolada"])

    r = ViterbiAcordes().posicionar(list(ref.notas), TUNING_GUITARRA_6)

    assert r.impossiveis == ()
    assert len(r.tab) == len(ref.notas)


_acordes = st.lists(
    st.lists(st.integers(38, 90), min_size=1, max_size=7),
    min_size=1,
    max_size=6,
)


@settings(max_examples=150, deadline=None)
@given(_acordes)
def test_propriedades_de_qualquer_posicionamento(acordes: list[list[int]]) -> None:
    notas = [n for i, a in enumerate(acordes) for n in _acorde(tuple(a), i * 0.5)]

    r = ViterbiAcordes().posicionar(notas, TUNING_GUITARRA_6)

    # Nenhuma nota some nem aparece: ou foi posicionada, ou está num acorde relatado.
    relatadas = [n for a in r.impossiveis for n in a.notas]
    assert sorted([t.event for t in r.tab] + relatadas, key=_chave) == sorted(notas, key=_chave)
    for t in r.tab:
        assert TUNING_GUITARRA_6[t.string] + t.fret == t.event.pitch
        assert 0 <= t.fret <= 24
    for forma in _formas(r.tab):
        pisados = [f for f in forma.values() if f > 0]
        assert not pisados or max(pisados) - min(pisados) <= ABERTURA_MAXIMA
    for onset in {t.event.onset_s for t in r.tab}:
        cordas = [t.string for t in r.tab if t.event.onset_s == onset]
        assert len(cordas) == len(set(cordas)), "duas notas do acorde na mesma corda"


def _chave(n: NoteEvent) -> tuple[float, int]:
    return (n.onset_s, n.pitch)


def test_inicios_de_acorde_conta_um_ataque_por_acorde() -> None:
    from thoth.services.acordes import inicios_de_acorde

    notas = [*_acorde((40, 47, 52), 0.0), NoteEvent(45, 0.02, 0.4, ROTULO), *_acorde((45,), 0.5)]

    assert inicios_de_acorde(notas) == [0.0, 0.5]
