"""MusicXML de bateria (ADR-044, M2) — XML cru, round-trip do music21 e o MuseScore.

Pauta não afinada: cada peça GM tem uma posição e uma cabeça na pauta (`<unpitched>`,
`<notehead>`) e um instrumento próprio (`<score-instrument>` com `<midi-unpitched>`),
ao qual cada nota aponta (`<instrument id>`). Posição e cabeça sozinhas não bastam: a
caixa acústica (38) e a eletrônica (40) caem as duas em C5 com cabeça normal, e o leitor
escolheria uma. O music21 10.5 só escreve um instrumento genérico por parte; o resto é
escrito depois, no XML.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path
from xml.etree import ElementTree

import pytest
from music21 import converter, percussion, stream

from tests.sintetico import BPM as BPM_FIXTURE
from tests.sintetico_multi import FIXTURES_MULTI, referencia
from thoth.adapters.export.musicxml import MAPA_PERCUSSAO, MusicXmlPercussaoExporter
from thoth.domain.models import EventoPercussivo
from thoth.services.rhythm import COMPASSO, GRADE, PPQ, para_ticks

BPM = 120  # semicolcheia = 0,125 s


def _exportar(ataques: list[EventoPercussivo], destino: Path, bpm: float = BPM) -> Path:
    return MusicXmlPercussaoExporter(bpm=bpm, titulo="Groove").exportar(
        ataques, destino / "b.musicxml"
    )


def _raiz(arquivo: Path) -> ElementTree.Element:
    return ElementTree.fromstring(re.sub(r"<!DOCTYPE[^>]*>", "", arquivo.read_text()))


def _lidas(arquivo: Path) -> list[tuple[int, set[int]]]:
    """(tique, peças GM) de cada acorde, pela cadeia nota → instrumento → midi-unpitched."""
    raiz = _raiz(arquivo)
    gm = {
        m.get("id"): int(m.findtext("midi-unpitched") or 0) - 1
        for m in raiz.iter("midi-instrument")
    }
    divisoes = int(raiz.findtext(".//divisions") or 1)
    lidas: list[tuple[int, set[int]]] = []
    cursor = anterior = 0
    for nota in raiz.iter("note"):
        if nota.find("chord") is None:
            anterior = cursor
            cursor += int(nota.findtext("duration") or 0)
        if nota.find("rest") is not None:
            continue
        instrumento = nota.find("instrument")
        assert instrumento is not None, "nota sem <instrument id>"
        tique = anterior * PPQ // divisoes
        if not lidas or lidas[-1][0] != tique:
            lidas.append((tique, set()))
        lidas[-1][1].add(gm[instrumento.get("id")])
    return lidas


def test_posicao_e_cabeca_saem_do_mapa(tmp_path: Path) -> None:
    raiz = _raiz(_exportar([EventoPercussivo(0.0, 36), EventoPercussivo(0.0, 42)], tmp_path))

    assert raiz.findtext(".//clef/sign") == "percussion"
    notas = list(raiz.iter("note"))
    lidas = [
        (
            f"{n.findtext('unpitched/display-step')}{n.findtext('unpitched/display-octave')}",
            n.findtext("notehead") or "normal",
            n.find("chord") is not None,
        )
        for n in notas
        if n.find("unpitched") is not None
    ]
    assert lidas == [
        (MAPA_PERCUSSAO[36].altura, MAPA_PERCUSSAO[36].cabeca, False),
        (MAPA_PERCUSSAO[42].altura, MAPA_PERCUSSAO[42].cabeca, True),
    ]
    assert MAPA_PERCUSSAO[42].cabeca == "x"


def test_cada_peca_tem_instrumento_proprio_no_canal_dez(tmp_path: Path) -> None:
    """38 e 40 no mesmo tique: mesma posição e cabeça, instrumentos distintos."""
    arquivo = _exportar(
        [EventoPercussivo(0.0, 38), EventoPercussivo(0.0, 40), EventoPercussivo(0.5, 36)],
        tmp_path,
    )

    raiz = _raiz(arquivo)
    assert MAPA_PERCUSSAO[38].altura == MAPA_PERCUSSAO[40].altura
    assert {m.findtext("midi-channel") for m in raiz.iter("midi-instrument")} == {"10"}
    ids = {s.get("id") for s in raiz.iter("score-instrument")}
    assert len(ids) == 3
    assert {m.get("id") for m in raiz.iter("midi-instrument")} == ids
    assert _lidas(arquivo) == [(0, {38, 40}), (PPQ, {36})]


def test_cada_grupo_comeca_no_seu_tique_e_o_resto_e_pausa(tmp_path: Path) -> None:
    arquivo = _exportar(
        [EventoPercussivo(0.0, 36), EventoPercussivo(0.25, 38), EventoPercussivo(1.0, 42)],
        tmp_path,
    )

    assert _lidas(arquivo) == [(0, {36}), (2 * GRADE, {38}), (2 * PPQ, {42})]


def test_ataque_perto_da_barra_e_cortado_nela_sem_ligadura(tmp_path: Path) -> None:
    fim = 60 / BPM * 4
    arquivo = _exportar(
        [EventoPercussivo(fim - 0.25, 49), EventoPercussivo(fim + 0.25, 36)], tmp_path
    )

    assert _lidas(arquivo) == [(COMPASSO - 2 * GRADE, {49}), (COMPASSO + 2 * GRADE, {36})]
    assert "<tie" not in arquivo.read_text()


def test_o_music21_rele_os_mesmos_grupos(tmp_path: Path) -> None:
    """Leitor independente do pós-processamento: offset, posição e cabeça de cada acorde."""
    ataques = [EventoPercussivo(0.0, 36), EventoPercussivo(0.0, 42), EventoPercussivo(0.25, 38)]

    lido = converter.parse(str(_exportar(ataques, tmp_path)))

    grupos = []
    for el in lido.recurse().notes:
        pecas = el.notes if isinstance(el, percussion.PercussionChord) else [el]
        offset = el.getOffsetInHierarchy(lido)
        grupos.append((offset, {(p.displayName, p.notehead) for p in pecas}))
    m = MAPA_PERCUSSAO
    assert grupos == [
        (0.0, {(m[36].altura, m[36].cabeca), (m[42].altura, m[42].cabeca)}),
        (0.5, {(m[38].altura, m[38].cabeca)}),
    ]
    assert isinstance(lido, stream.Score)
    # O `<work-title>` relido vai para `bestTitle`, não `title` (test_musicxml_export).
    assert lido.metadata.bestTitle == "Groove"


def test_referencia_da_bateria_volta_inteira(tmp_path: Path) -> None:
    ref = referencia(FIXTURES_MULTI["bateria-isolada"])

    arquivo = _exportar(list(ref.ataques), tmp_path, bpm=BPM_FIXTURE)

    esperado: dict[int, set[int]] = {}
    for a in ref.ataques:
        esperado.setdefault(para_ticks(a.instante_s, BPM_FIXTURE), set()).add(a.peca_gm)
    assert _lidas(arquivo) == sorted(esperado.items())
    assert sum(len(p) for _, p in _lidas(arquivo)) == len(ref.ataques) == 48


def test_sem_ataques_recusa() -> None:
    with pytest.raises(ValueError, match="sem ataques"):
        MusicXmlPercussaoExporter().exportar([], Path("nunca.musicxml"))


def test_peca_fora_do_mapa_recusa(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="peça 81"):
        MusicXmlPercussaoExporter().exportar([EventoPercussivo(0.0, 81)], tmp_path / "b.xml")


requer_musescore = pytest.mark.skipif(shutil.which("mscore") is None, reason="mscore ausente")


def _pelo_musescore(arquivo: Path) -> list[tuple[str, frozenset[int]]]:
    destino = arquivo.with_suffix(".mscx")
    subprocess.run(
        ["mscore", str(arquivo), "-o", str(destino)],
        check=True,
        capture_output=True,
        env=os.environ | {"QT_QPA_PLATFORM": "offscreen"},
    )
    mscx = destino.read_text()
    assert "<useDrumset>1</useDrumset>" in mscx
    return [
        (figura, frozenset(int(p) for p in re.findall(r"<pitch>(\d+)</pitch>", corpo)))
        for figura, corpo in re.findall(
            r"<(?:Chord|Rest)>.*?<durationType>(\w+)</durationType>(.*?)</(?:Chord|Rest)>",
            mscx,
            re.S,
        )
    ]


@requer_musescore
@pytest.mark.slow
def test_o_musescore_le_a_referencia_com_as_pecas(tmp_path: Path) -> None:
    ref = referencia(FIXTURES_MULTI["bateria-isolada"])
    arquivo = _exportar(list(ref.ataques), tmp_path, bpm=BPM_FIXTURE)

    lidos = _pelo_musescore(arquivo)

    esperado: dict[int, set[int]] = {}
    for a in ref.ataques:
        esperado.setdefault(para_ticks(a.instante_s, BPM_FIXTURE), set()).add(a.peca_gm)
    grupos = [frozenset(esperado[t]) for t in sorted(esperado)]
    figuras = ["eighth"] * (len(grupos) - 1) + ["16th"]
    print(f"\nMUSESCORE bateria xml: {len(lidos)} figuras, ref={len(grupos)} grupos")
    assert lidos[: len(grupos)] == list(zip(figuras, grupos, strict=True))
    assert all(not pecas for _, pecas in lidos[len(grupos) :])


@requer_musescore
@pytest.mark.slow
def test_o_musescore_separa_pecas_de_mesma_posicao(tmp_path: Path) -> None:
    """Sem o instrumento por nota, o MuseScore decide pela posição e funde 38 com 40."""
    ataques = [
        EventoPercussivo(0.0, 38),
        EventoPercussivo(0.0, 40),
        EventoPercussivo(0.5, 41),
        EventoPercussivo(1.0, 43),
    ]

    lidos = _pelo_musescore(_exportar(ataques, tmp_path))

    assert [p for _, p in lidos if p] == [
        frozenset({38, 40}),
        frozenset({41}),
        frozenset({43}),
    ]
