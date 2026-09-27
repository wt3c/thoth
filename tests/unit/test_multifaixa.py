"""Composição real dos formatos editáveis em uma partitura multifaixa."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import guitarpro as gp
from music21 import converter

from thoth.adapters.export.gp5 import Gp5Exporter, Gp5PercussaoExporter
from thoth.adapters.export.multifaixa import CompositorGp5, CompositorMusicXml
from thoth.adapters.export.musicxml import MusicXmlExporter, MusicXmlPercussaoExporter
from thoth.domain.models import TUNING_BASS_4, EventoPercussivo, NoteEvent, TabNote


def _baixo() -> list[TabNote]:
    return [
        TabNote(NoteEvent(28, 0.0, 0.5, "electric_bass"), string=0, fret=0),
        TabNote(NoteEvent(33, 0.5, 1.0, "electric_bass"), string=1, fret=0),
    ]


def test_gp5_combina_cordas_e_percussao_em_faixas_reais(tmp_path: Path) -> None:
    baixo = Gp5Exporter(bpm=120, faixa="Baixo").export(
        _baixo(), tmp_path / "baixo.gp5", TUNING_BASS_4
    )
    bateria = Gp5PercussaoExporter(bpm=120).exportar(
        [EventoPercussivo(0.0, 36), EventoPercussivo(0.5, 42)],
        tmp_path / "bateria.gp5",
    )

    saida = CompositorGp5().combinar([baixo, bateria], tmp_path / "todos.gp5")
    musica = gp.parse(str(saida))

    assert [faixa.name for faixa in musica.tracks] == ["Baixo", "Bateria"]
    assert musica.tracks[0].channel.instrument == 33
    assert musica.tracks[1].isPercussionTrack is True
    assert len(musica.tracks[0].measures) == len(musica.tracks[1].measures)


def test_musicxml_combina_partes_sem_colidir_ids(tmp_path: Path) -> None:
    baixo = MusicXmlExporter(bpm=120, titulo="Estudo").export(
        _baixo(), tmp_path / "baixo.musicxml", TUNING_BASS_4
    )
    bateria = MusicXmlPercussaoExporter(bpm=120, titulo="Estudo").exportar(
        [EventoPercussivo(0.0, 36), EventoPercussivo(0.5, 42)],
        tmp_path / "bateria.musicxml",
    )

    saida = CompositorMusicXml().combinar([baixo, bateria], tmp_path / "todos.musicxml")
    raiz = ET.parse(saida).getroot()
    partes = raiz.findall("part")
    ids = [parte.attrib["id"] for parte in partes]
    instrumentos = [elemento.attrib["id"] for elemento in raiz.iter("score-instrument")]

    assert len(partes) == 2  # baixo em duas pautas dentro de uma parte, e percussão
    assert len(ids) == len(set(ids))
    assert len(instrumentos) == len(set(instrumentos))
    nomes = {
        elemento.text
        for tag in ("part-name", "instrument-name")
        for elemento in raiz.iter(tag)
    }
    assert nomes >= {"Electric Bass", "Bateria"}
    # O music21 expande as duas pautas da parte de baixo em objetos separados.
    assert len(converter.parse(str(saida)).parts) == 3
