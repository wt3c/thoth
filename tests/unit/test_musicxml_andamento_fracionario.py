"""Andamento fracionário não deve virar deriva na reprodução do MusicXML."""

from pathlib import Path
from xml.etree import ElementTree

import pytest
from music21 import converter, note

from thoth.adapters.export.musicxml import (
    MusicXmlExporter,
    MusicXmlPercussaoExporter,
    MusicXmlPianoExporter,
)
from thoth.domain.models import TUNING_BASS_4, EventoPercussivo, NoteEvent
from thoth.services.fretboard import ViterbiFretAssigner
from thoth.services.rhythm import COMPASSO


@pytest.mark.parametrize("instrumento", ["baixo", "piano", "bateria"])
def test_andamento_fracionario_preserva_o_instante_da_nota_distante(
    tmp_path: Path, instrumento: str
) -> None:
    """Reproduz 119,86 → 120: em quatro minutos, a nota adiantava 280 ms."""
    bpm = 119.86
    seminima = 60 / bpm
    inicio = 480 * seminima
    caminho = tmp_path / "fracionario.musicxml"
    notas = [NoteEvent(40, t, t + seminima, "electric_bass") for t in (0.0, inicio)]
    if instrumento == "baixo":
        tabs = ViterbiFretAssigner().assign(notas, TUNING_BASS_4)
        MusicXmlExporter(bpm=bpm).export(tabs, caminho, TUNING_BASS_4)
    elif instrumento == "piano":
        MusicXmlPianoExporter(bpm=bpm).exportar(notas, caminho)
    else:
        MusicXmlPercussaoExporter(bpm=bpm).exportar(
            [EventoPercussivo(n.onset_s, 36) for n in notas], caminho
        )

    raiz = ElementTree.parse(caminho).getroot()
    assert [float(s.attrib["tempo"]) for s in raiz.findall(".//sound[@tempo]")] == [bpm]
    score = converter.parse(caminho)
    # O piano pode pôr a nota na pauta inferior; o baixo duplica em notação e TAB.
    ataques = [
        evento["offsetSeconds"]
        for evento in score.flatten().secondsMap
        if isinstance(evento["element"], (note.Note, note.Unpitched))
    ]
    assert max(ataques) == pytest.approx(inicio, abs=0.001)


@pytest.mark.parametrize("instrumento", ["baixo", "bateria"])
def test_troca_fracionaria_preserva_o_andamento_no_arquivo(
    tmp_path: Path, instrumento: str
) -> None:
    caminho = tmp_path / "troca.musicxml"
    marcas = ((COMPASSO, 100.4),)
    if instrumento == "baixo":
        notas = [NoteEvent(40, i * 0.5, (i + 1) * 0.5, "electric_bass") for i in range(12)]
        tabs = ViterbiFretAssigner().assign(notas, TUNING_BASS_4)
        MusicXmlExporter(bpm=120, marcas=marcas).export(tabs, caminho, TUNING_BASS_4)
    else:
        MusicXmlPercussaoExporter(bpm=120, marcas=marcas).exportar(
            [EventoPercussivo(i * 0.5, 36) for i in range(12)], caminho
        )
    pauta = converter.parse(caminho).parts[0]
    lidas = [
        (m.getContextByClass("Measure").number, m.number)
        for m in pauta.recurse().getElementsByClass("MetronomeMark")
    ]
    assert lidas == [(1, 120), (2, 100.4)]
