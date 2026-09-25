"""MusicXML de guitarra com acordes (ADR-044, M4) — arquivo gravado e relido.

Partitura em clave de Sol 8vb e tablatura de seis linhas, as duas com o acorde
inteiro no mesmo instante. O music21 10.5 só escreve corda e traste na primeira nota
de um acorde; por isso a digitação é afirmada no **XML cru**, nota por nota, que é o
que MuseScore e TuxGuitar leem (`tasks/lessons/exportadores.md`).
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path
from xml.etree import ElementTree

import pytest
from music21 import chord, clef, converter, pitch

from tests.sintetico import BPM as BPM_FIXTURE
from tests.sintetico_multi import FIXTURES_MULTI, referencia
from thoth.adapters.export.musicxml import MusicXmlExporter
from thoth.domain.instrumentos import PERFIS, TUNING_GUITARRA_6
from thoth.domain.models import NoteEvent, TabNote
from thoth.services.acordes import ViterbiAcordes

BPM = 90
SEMINIMA = 60.0 / BPM
ROTULO = "clean_electric_guitar"
MI_MAIOR = (40, 47, 52, 56, 59, 64)
CORDAS = len(TUNING_GUITARRA_6)


def _acorde(pitches: tuple[int, ...], onset: float, dur: float = SEMINIMA * 0.9) -> list[NoteEvent]:
    return [NoteEvent(p, onset, onset + dur, ROTULO) for p in pitches]


def _posicionar(notas: list[NoteEvent]) -> list[TabNote]:
    r = ViterbiAcordes().posicionar(notas, TUNING_GUITARRA_6)
    assert r.impossiveis == ()
    return list(r.tab)


def _arquivo(tabs: list[TabNote], destino: Path, bpm: float = BPM) -> Path:
    exportador = MusicXmlExporter(
        bpm=bpm, familia="guitarra", programa_gm=PERFIS["guitarra-limpa"].programa_gm
    )
    return exportador.export(tabs, destino / "g.musicxml", TUNING_GUITARRA_6)


def _digitacao(xml: Path) -> list[tuple[float, int, int, int, bool]]:
    """`(instante em semínimas, altura, corda MusicXML, traste, ligada)` da pauta 2.

    Anda o cursor do MusicXML à mão (`duration`, `chord`, `backup`, `forward`):
    é o mesmo caminho que um leitor faz para saber onde cada nota cai.
    """
    raiz = ElementTree.parse(xml).getroot()
    divisoes = int(raiz.findtext(".//divisions") or 1)
    lidas = []
    inicio_do_compasso = 0
    for compasso in raiz.iter("measure"):
        cursor = inicio_do_compasso
        fim = cursor
        anterior = cursor
        for el in compasso:
            if el.tag == "backup":
                cursor -= int(el.findtext("duration") or 0)
            elif el.tag == "forward":
                cursor += int(el.findtext("duration") or 0)
            elif el.tag == "note":
                duracao = int(el.findtext("duration") or 0)
                inicio = anterior if el.find("chord") is not None else cursor
                if el.find("chord") is None:
                    anterior = cursor
                    cursor += duracao
                altura = el.find("pitch")
                if el.findtext("staff") == "2" and altura is not None:
                    p = pitch.Pitch(
                        step=altura.findtext("step"),
                        octave=int(altura.findtext("octave") or 0),
                        accidental=int(altura.findtext("alter") or 0) or None,
                    )
                    tecnica = el.find("notations/technical")
                    assert tecnica is not None, f"nota {p} sem corda nem traste"
                    ligada = any(t.get("type") == "stop" for t in el.iter("tie"))
                    lidas.append(
                        (
                            inicio / divisoes,
                            p.midi,
                            int(tecnica.findtext("string") or 0),
                            int(tecnica.findtext("fret") or 0),
                            ligada,
                        )
                    )
            fim = max(fim, cursor)
        inicio_do_compasso = fim
    return lidas


def _esperado(tabs: list[TabNote], bpm: float) -> set[tuple[float, int, int, int]]:
    from thoth.services.rhythm import PPQ, para_ticks

    return {
        (para_ticks(t.event.onset_s, bpm) / PPQ, t.event.pitch, CORDAS - t.string, t.fret)
        for t in tabs
    }


def _ataques(lidas: list[tuple[float, int, int, int, bool]]) -> set[tuple[float, int, int, int]]:
    return {(t, p, s, f) for t, p, s, f, ligada in lidas if not ligada}


def test_acorde_sai_como_acorde_nas_duas_pautas(tmp_path: Path) -> None:
    tabs = _posicionar([*_acorde(MI_MAIOR, 0.0), *_acorde((45,), SEMINIMA)])

    lido = converter.parse(str(_arquivo(tabs, tmp_path)))

    for pauta in lido.parts:
        primeiro, segundo = list(pauta.recurse().notes)
        assert isinstance(primeiro, chord.Chord)
        assert [p.midi for p in primeiro.pitches] == list(MI_MAIOR)
        assert not isinstance(segundo, chord.Chord)
        assert segundo.pitch.midi == 45


def test_cada_nota_do_acorde_leva_a_propria_corda_e_traste(tmp_path: Path) -> None:
    """O music21 só escreve a técnica na primeira nota do acorde; as outras cinco
    sairiam sem corda e o leitor escolheria uma por conta própria."""
    tabs = _posicionar([*_acorde(MI_MAIOR, 0.0), *_acorde((45,), SEMINIMA)])

    lidas = _digitacao(_arquivo(tabs, tmp_path))

    assert _ataques(lidas) == _esperado(tabs, BPM)
    assert {(s, f) for t, _, s, f, _ in lidas if t == 0} == {
        (6, 0),
        (5, 2),
        (4, 2),
        (3, 1),
        (2, 0),
        (1, 0),
    }


def test_clave_de_sol_oitava_abaixo_e_tablatura_de_seis_cordas(tmp_path: Path) -> None:
    alvo = _arquivo(_posicionar(_acorde(MI_MAIOR, 0.0)), tmp_path)

    lido = converter.parse(str(alvo))
    claves = [type(p.recurse().getElementsByClass(clef.Clef)[0]) for p in lido.parts]
    assert claves == [clef.Treble8vbClef, clef.TabClef]
    xml = alvo.read_text()
    assert "<staff-lines>6</staff-lines>" in xml
    afinacao = re.findall(
        r"<tuning-step>(\w)</tuning-step>\s*<tuning-octave>(\d)</tuning-octave>", xml
    )
    assert afinacao == [("E", "2"), ("A", "2"), ("D", "3"), ("G", "3"), ("B", "3"), ("E", "4")]


def test_instrumento_vem_do_programa_do_perfil(tmp_path: Path) -> None:
    """O MusicXML conta programa a partir de 1; o GM do perfil, a partir de 0."""
    xml = _arquivo(_posicionar(_acorde(MI_MAIOR, 0.0)), tmp_path).read_text()

    assert re.findall(r"<midi-program>(\d+)</midi-program>", xml) == ["28"]


def test_duas_notas_do_mesmo_tique_na_mesma_corda_sao_recusadas(tmp_path: Path) -> None:
    tabs = [
        TabNote(NoteEvent(40, 0.0, 0.4, ROTULO), string=0, fret=0),
        TabNote(NoteEvent(41, 0.06, 0.4, ROTULO), string=0, fret=1),
    ]

    with pytest.raises(ValueError, match="mesma corda"):
        _arquivo(tabs, tmp_path)


def test_acorde_ligado_atraves_da_barra_mantem_a_digitacao(tmp_path: Path) -> None:
    tabs = _posicionar(_acorde(MI_MAIOR, SEMINIMA * 3, dur=SEMINIMA * 2))

    lidas = _digitacao(_arquivo(tabs, tmp_path))

    ataque = {(p, s, f) for _, p, s, f, ligada in lidas if not ligada}
    continuacao = {(p, s, f) for _, p, s, f, ligada in lidas if ligada}
    assert ataque == continuacao
    assert len(ataque) == 6


def test_acorde_nao_recebe_nome_e_nota_solta_recebe(tmp_path: Path) -> None:
    tabs = _posicionar([*_acorde(MI_MAIOR, 0.0), *_acorde((45,), SEMINIMA)])

    lido = converter.parse(str(_arquivo(tabs, tmp_path)))

    assert [n.lyric for n in lido.parts[0].recurse().notes] == [None, "A"]
    assert [n.lyric for n in lido.parts[1].recurse().notes] == [None, None]


def test_fixture_de_guitarra_sobrevive_ao_round_trip(tmp_path: Path) -> None:
    """Altura, instante, corda, traste e simultaneidade — o que o ADR-044 pede."""
    ref = referencia(FIXTURES_MULTI["guitarra-limpa-isolada"])
    tabs = _posicionar(list(ref.notas))

    alvo = _arquivo(tabs, tmp_path, bpm=BPM_FIXTURE)

    assert _ataques(_digitacao(alvo)) == _esperado(tabs, BPM_FIXTURE)
    partitura = converter.parse(str(alvo)).parts[0].flatten().notes
    alturas = sorted(
        p.midi for n in partitura if not (n.tie and n.tie.type != "start") for p in n.pitches
    )
    assert alturas == sorted(n.pitch for n in ref.notas)


requer_musescore = pytest.mark.skipif(shutil.which("mscore") is None, reason="mscore ausente")


@requer_musescore
@pytest.mark.slow
def test_o_musescore_mantem_uma_digitacao_valida_alternativa(tmp_path: Path) -> None:
    """E3 A3 D4 na casa 12 das três cordas graves: tocável, e nenhum custo escolheria.

    Se o MuseScore recalculasse, sairia na forma aberta — é o que prova que ele lê
    a nossa corda e traste em vez de decidir sozinho (`lessons/exportadores.md`).
    """
    tabs = [
        TabNote(NoteEvent(52, 0.0, 0.5, ROTULO), string=0, fret=12),
        TabNote(NoteEvent(57, 0.0, 0.5, ROTULO), string=1, fret=12),
        TabNote(NoteEvent(62, 0.0, 0.5, ROTULO), string=2, fret=12),
    ]
    destino = tmp_path / "lido.mscx"
    subprocess.run(
        ["mscore", str(_arquivo(tabs, tmp_path)), "-o", str(destino)],
        check=True,
        capture_output=True,
        env=os.environ | {"QT_QPA_PLATFORM": "offscreen"},
    )

    mscx = destino.read_text()
    assert '<StaffType group="tablature">' in mscx
    corpo = mscx[mscx.index('<Staff id="2"') :]
    lidos = re.findall(
        r"<pitch>(\d+)</pitch>.*?<fret>(\d+)</fret>\s*<string>(\d+)</string>", corpo, re.S
    )
    # As cordas do MuseScore são 0 no topo, ao contrário das nossas.
    assert sorted(lidos) == sorted(
        (str(t.event.pitch), str(t.fret), str(CORDAS - 1 - t.string)) for t in tabs
    )
