"""GP5 com acordes de guitarra (ADR-044, M4) — round-trip contra o PyGuitarPro real.

O baixo continua monofônico e recusando notas simultâneas (`test_gp5_export.py`).
Aqui o exportador é pedido com `acordes=True`: notas do mesmo tique viram **um beat
com várias notas**, uma por corda. O teste afirma estrutura — quantos beats, onde
cada um começa, quais cordas e trastes estão juntos —, nunca o conjunto achatado
(`tasks/lessons/exportadores.md`).
"""

from __future__ import annotations

from pathlib import Path

import guitarpro as gp
import pytest

from tests.sintetico import BPM as BPM_FIXTURE
from tests.sintetico_multi import FIXTURES_MULTI, referencia
from thoth.adapters.export.gp5 import Gp5Exporter
from thoth.domain.instrumentos import PERFIS, TUNING_GUITARRA_6
from thoth.domain.models import NoteEvent, TabNote
from thoth.services.acordes import ViterbiAcordes
from thoth.services.rhythm import para_ticks

BPM = 90
SEMINIMA = 60.0 / BPM
ROTULO = "clean_electric_guitar"
MI_MAIOR = (40, 47, 52, 56, 59, 64)


def _acorde(pitches: tuple[int, ...], onset: float, dur: float = SEMINIMA * 0.9) -> list[NoteEvent]:
    return [NoteEvent(p, onset, onset + dur, ROTULO) for p in pitches]


def _posicionar(notas: list[NoteEvent]) -> list[TabNote]:
    r = ViterbiAcordes().posicionar(notas, TUNING_GUITARRA_6)
    assert r.impossiveis == ()
    return list(r.tab)


def _exportar(tabs: list[TabNote], destino: Path, **kwargs: object) -> gp.Song:
    exportador = Gp5Exporter(acordes=True, **kwargs)  # type: ignore[arg-type]
    return gp.parse(str(exportador.export(tabs, destino / "g.gp5", TUNING_GUITARRA_6)))


def _beats(song: gp.Song) -> list[gp.Beat]:
    return [
        beat for medida in song.tracks[0].measures for beat in medida.voices[0].beats if beat.notes
    ]


def _inicio(song: gp.Song, beat: gp.Beat) -> int:
    return beat.start - song.measureHeaders[0].start


def _forma(beat: gp.Beat) -> set[tuple[int, int]]:
    return {(nota.string, nota.value) for nota in beat.notes}


def _em_gp(tabs: list[TabNote]) -> set[tuple[int, int]]:
    """Nossa corda 0 é a mais grave; a corda 1 do GP é a mais aguda."""
    return {(len(TUNING_GUITARRA_6) - t.string, t.fret) for t in tabs}


def test_acorde_sai_num_beat_so_com_uma_nota_por_corda(tmp_path: Path) -> None:
    tabs = _posicionar([*_acorde(MI_MAIOR, 0.0), *_acorde((45,), SEMINIMA)])

    song = _exportar(tabs, tmp_path, bpm=BPM)

    beats = _beats(song)
    assert [len(b.notes) for b in beats] == [6, 1]
    assert [_inicio(song, b) for b in beats] == [0, gp.Duration.quarterTime]
    assert _forma(beats[0]) == _em_gp(tabs[:6])
    assert _forma(beats[0]) == {(6, 0), (5, 2), (4, 2), (3, 1), (2, 0), (1, 0)}
    assert all(b.status is gp.BeatStatus.normal for b in beats)


def test_faixa_leva_afinacao_nome_e_programa_do_perfil(tmp_path: Path) -> None:
    perfil = PERFIS["guitarra-limpa"]
    tabs = _posicionar(_acorde(MI_MAIOR, 0.0))

    song = _exportar(tabs, tmp_path, bpm=BPM, faixa="Guitarra", programa_gm=perfil.programa_gm)

    faixa = song.tracks[0]
    assert faixa.name == "Guitarra"
    assert faixa.channel.instrument == perfil.programa_gm == 27
    assert [c.value for c in faixa.strings] == list(reversed(TUNING_GUITARRA_6))


def test_duas_notas_do_mesmo_tique_na_mesma_corda_sao_recusadas(tmp_path: Path) -> None:
    """Dois grupos a 60 ms caem no mesmo tique da grade: juntos não cabem numa corda."""
    tabs = [
        TabNote(NoteEvent(40, 0.0, 0.4, ROTULO), string=0, fret=0),
        TabNote(NoteEvent(41, 0.06, 0.4, ROTULO), string=0, fret=1),
    ]

    with pytest.raises(ValueError, match="mesma corda"):
        Gp5Exporter(bpm=BPM, acordes=True).export(tabs, tmp_path / "x.gp5", TUNING_GUITARRA_6)


def test_acorde_que_atravessa_a_barra_liga_todas_as_notas(tmp_path: Path) -> None:
    tabs = _posicionar(_acorde(MI_MAIOR, SEMINIMA * 3, dur=SEMINIMA * 2))

    song = _exportar(tabs, tmp_path, bpm=BPM)

    ataque, continuacao = _beats(song)
    assert {n.type for n in ataque.notes} == {gp.NoteType.normal}
    assert {n.type for n in continuacao.notes} == {gp.NoteType.tie}
    assert _forma(ataque) == _forma(continuacao)
    for medida in song.tracks[0].measures:
        assert sum(b.duration.time for b in medida.voices[0].beats) == gp.Duration.quarterTime * 4


def test_acorde_nao_recebe_nome_e_nota_solta_continua_recebendo(tmp_path: Path) -> None:
    """Seis nomes empilhados no beat seriam ruído; nome de acorde é outro problema."""
    tabs = _posicionar([*_acorde(MI_MAIOR, 0.0), *_acorde((45,), SEMINIMA)])

    textos = [b.text for b in _beats(_exportar(tabs, tmp_path, bpm=BPM))]

    assert textos == [None, "A"]


def test_fixture_de_guitarra_sobrevive_ao_round_trip(tmp_path: Path) -> None:
    """Altura, instante, corda, traste e simultaneidade — o que o ADR-044 pede."""
    ref = referencia(FIXTURES_MULTI["guitarra-limpa-isolada"])
    tabs = _posicionar(list(ref.notas))

    song = _exportar(tabs, tmp_path, bpm=BPM_FIXTURE)

    esperado: dict[int, set[tuple[int, int]]] = {}
    for t in tabs:
        esperado.setdefault(para_ticks(t.event.onset_s, BPM_FIXTURE), set()).update(_em_gp([t]))
    lido = {
        _inicio(song, b): _forma(b)
        for b in _beats(song)
        if all(n.type is gp.NoteType.normal for n in b.notes)
    }
    assert lido == esperado
    afinacao = {c.number: c.value for c in song.tracks[0].strings}
    alturas = sorted(
        afinacao[n.string] + n.value
        for b in _beats(song)
        for n in b.notes
        if n.type is gp.NoteType.normal
    )
    assert alturas == sorted(n.pitch for n in ref.notas)
