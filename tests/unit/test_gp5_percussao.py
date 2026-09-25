"""GP5 de bateria (ADR-044, M2) — round-trip contra o PyGuitarPro real.

Faixa de percussão nativa: `isPercussionTrack`, canal MIDI 10, o número da peça GM no
`value` da nota e uma corda por peça, para várias caberem no mesmo beat. O teste
afirma estrutura — quantos beats, onde cada um começa, quais peças estão juntas — e que
nenhuma nota sai ligada: ligadura é sustentação, e a bateria não tem sustentação
medida (`tasks/lessons/exportadores.md`).
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import guitarpro as gp
import pytest

from tests.sintetico import BPM as BPM_FIXTURE
from tests.sintetico_multi import FIXTURES_MULTI, referencia
from thoth.adapters.export.gp5 import Gp5PercussaoExporter
from thoth.domain.models import EventoPercussivo
from thoth.services.rhythm import COMPASSO, GRADE, PPQ, para_ticks

BPM = 120  # semicolcheia = 0,125 s


def _exportar(ataques: list[EventoPercussivo], destino: Path, bpm: float = BPM) -> gp.Song:
    arquivo = Gp5PercussaoExporter(bpm=bpm).exportar(ataques, destino / "b.gp5")
    return gp.parse(str(arquivo))


def _beats(song: gp.Song) -> list[gp.Beat]:
    return [b for m in song.tracks[0].measures for b in m.voices[0].beats]


def _com_nota(song: gp.Song) -> list[tuple[int, set[int]]]:
    inicio = song.measureHeaders[0].start
    return [(b.start - inicio, {n.value for n in b.notes}) for b in _beats(song) if b.notes]


def test_a_faixa_e_de_percussao_no_canal_dez(tmp_path: Path) -> None:
    song = _exportar([EventoPercussivo(0.0, 36)], tmp_path)

    faixa = song.tracks[0]
    assert faixa.isPercussionTrack
    assert faixa.channel.channel == 9  # 0-indexado: o canal 10 do GM


def test_pecas_do_mesmo_tique_saem_no_mesmo_beat_em_cordas_distintas(tmp_path: Path) -> None:
    song = _exportar(
        [EventoPercussivo(0.0, 36), EventoPercussivo(0.01, 42), EventoPercussivo(0.0, 49)],
        tmp_path,
    )

    assert _com_nota(song) == [(0, {36, 42, 49})]
    (beat,) = [b for b in _beats(song) if b.notes]
    assert len({n.string for n in beat.notes}) == 3


def test_cada_grupo_comeca_no_seu_tique_e_o_resto_e_pausa(tmp_path: Path) -> None:
    song = _exportar(
        [EventoPercussivo(0.0, 36), EventoPercussivo(0.25, 38), EventoPercussivo(1.0, 42)],
        tmp_path,
    )

    assert _com_nota(song) == [(0, {36}), (2 * GRADE, {38}), (2 * PPQ, {42})]
    for beat in _beats(song):
        esperado = gp.BeatStatus.normal if beat.notes else gp.BeatStatus.rest
        assert beat.status == esperado
    medida = song.tracks[0].measures[0]
    assert sum(b.duration.time for b in medida.voices[0].beats) == COMPASSO


def test_ataque_perto_da_barra_e_cortado_nela_sem_ligadura(tmp_path: Path) -> None:
    """Último colcheia do compasso e o próximo ataque uma semínima depois: sem corte,
    a figura atravessaria a barra; com ligadura, leria como prato soando."""
    fim = 60 / BPM * 4
    song = _exportar([EventoPercussivo(fim - 0.25, 49), EventoPercussivo(fim + 0.25, 36)], tmp_path)

    assert _com_nota(song) == [(COMPASSO - 2 * GRADE, {49}), (COMPASSO + 2 * GRADE, {36})]
    assert all(n.type == gp.NoteType.normal for b in _beats(song) for n in b.notes)
    segundo = song.tracks[0].measures[1].voices[0].beats
    assert segundo[0].status == gp.BeatStatus.rest


def test_referencia_da_bateria_volta_inteira(tmp_path: Path) -> None:
    """32 colcheias, até três peças juntas: peça, tique e simultaneidade preservados."""
    ref = referencia(FIXTURES_MULTI["bateria-isolada"])

    song = _exportar(list(ref.ataques), tmp_path, bpm=BPM_FIXTURE)

    esperado: dict[int, set[int]] = {}
    for a in ref.ataques:
        esperado.setdefault(para_ticks(a.instante_s, BPM_FIXTURE), set()).add(a.peca_gm)
    assert _com_nota(song) == sorted(esperado.items())
    assert sum(len(p) for _, p in _com_nota(song)) == len(ref.ataques) == 48


def test_sem_ataques_recusa() -> None:
    with pytest.raises(ValueError, match="sem ataques"):
        Gp5PercussaoExporter().exportar([], Path("nunca.gp5"))


def test_mais_pecas_juntas_que_cordas_recusa(tmp_path: Path) -> None:
    ataques = [EventoPercussivo(0.0, p) for p in (35, 36, 38, 42, 45, 49, 51)]

    with pytest.raises(ValueError, match="7 peças"):
        Gp5PercussaoExporter().exportar(ataques, tmp_path / "b.gp5")


@pytest.mark.skipif(shutil.which("mscore") is None, reason="mscore ausente")
@pytest.mark.slow
def test_o_musescore_le_pauta_de_percussao_com_as_pecas(tmp_path: Path) -> None:
    """Leitor independente: o PyGuitarPro relendo o próprio arquivo não prova nada
    sobre o MuseScore (`lessons/exportadores.md`)."""
    ref = referencia(FIXTURES_MULTI["bateria-isolada"])
    arquivo = Gp5PercussaoExporter(bpm=BPM_FIXTURE).exportar(list(ref.ataques), tmp_path / "b.gp5")
    destino = tmp_path / "lido.mscx"
    subprocess.run(
        ["mscore", str(arquivo), "-o", str(destino)],
        check=True,
        capture_output=True,
        env=os.environ | {"QT_QPA_PLATFORM": "offscreen"},
    )

    mscx = destino.read_text()
    assert 'group="percussion"' in mscx
    # Em ordem, figura e peças de cada acorde e cada pausa. 31 colcheias seguidas e o
    # último grupo em semicolcheia (sem ninguém depois), completado por pausa, fixam o
    # tique de cada grupo.
    lidos = [
        (figura, frozenset(int(p) for p in re.findall(r"<pitch>(\d+)</pitch>", corpo)))
        for figura, corpo in re.findall(
            r"<(?:Chord|Rest)>.*?<durationType>(\w+)</durationType>(.*?)</(?:Chord|Rest)>",
            mscx,
            re.S,
        )
    ]
    esperado: dict[int, set[int]] = {}
    for a in ref.ataques:
        esperado.setdefault(para_ticks(a.instante_s, BPM_FIXTURE), set()).add(a.peca_gm)
    grupos = [frozenset(esperado[t]) for t in sorted(esperado)]
    figuras = ["eighth"] * (len(grupos) - 1) + ["16th"]
    print(f"\nMUSESCORE bateria: {len(lidos)} figuras, ref={len(grupos)} grupos")
    assert lidos == [*zip(figuras, grupos, strict=True), ("16th", frozenset())]
