"""MusicXML de piano (ADR-044, M3) — XML cru, round-trip do music21 e o MuseScore.

Sistema de duas pautas numa parte: clave de Sol em cima, clave de Fá embaixo. A divisão
é fixa e não tenta adivinhar a mão: do dó central (60) para cima, pauta 1; abaixo,
pauta 2. Notas do mesmo tique e da mesma duração são um acorde; durações que se
sobrepõem na mesma pauta vão para vozes diferentes.
"""

from __future__ import annotations

import os
import random
import re
import shutil
import subprocess
from pathlib import Path
from xml.etree import ElementTree

import pytest
from music21 import converter, stream

from tests.sintetico import BPM as BPM_FIXTURE
from tests.sintetico_multi import FIXTURES_MULTI, referencia
from tests.unit.test_musicxml_export import _beams_mal_formados
from thoth.adapters.export.musicxml import MusicXmlPianoExporter
from thoth.domain.models import NoteEvent
from thoth.services.rhythm import GRADE, PPQ, para_ticks

BPM = 60  # semínima = 1 s: o tique de cada nota se lê direto do segundo


def _n(pitch: int, onset: float, dur: float) -> NoteEvent:
    return NoteEvent(pitch=pitch, onset_s=onset, offset_s=onset + dur, instrument="acoustic_piano")


def _exportar(notas: list[NoteEvent], destino: Path, bpm: float = BPM) -> Path:
    return MusicXmlPianoExporter(bpm=bpm, titulo="Estudo").exportar(notas, destino / "p.musicxml")


def _raiz(arquivo: Path) -> ElementTree.Element:
    return ElementTree.fromstring(re.sub(r"<!DOCTYPE[^>]*>", "", arquivo.read_text()))


Lida = tuple[int, int, int, int]  # pauta, tique de início, altura, duração em ticks


def _lidas(arquivo: Path) -> list[Lida]:
    """(pauta, início, altura, duração) de cada nota, relida pelo music21, sem ligaduras.

    Uma voz por vez: o `stripTies` de uma pauta com vozes emenda ligaduras de vozes
    diferentes (medido: alongou uma nota e partiu outras, com o XML certo).
    """
    score = converter.parse(str(arquivo))
    lidas: list[Lida] = []
    for pauta, parte in enumerate(score.parts, start=1):
        for voz in parte.voicesToParts().parts:
            for el in voz.stripTies().flatten().notes:
                for p in el.pitches:
                    lidas.append(
                        (pauta, round(el.offset * PPQ), p.midi, round(el.quarterLength * PPQ))
                    )
    return sorted(lidas)


def _esperadas(notas: list[NoteEvent], bpm: float = BPM) -> list[Lida]:
    return sorted(
        (
            1 if n.pitch >= 60 else 2,
            para_ticks(n.onset_s, bpm),
            n.pitch,
            max(GRADE, para_ticks(n.offset_s, bpm) - para_ticks(n.onset_s, bpm)),
        )
        for n in notas
    )


def test_duas_pautas_com_sol_em_cima_e_fa_embaixo(tmp_path: Path) -> None:
    raiz = _raiz(_exportar([_n(72, 0, 1), _n(48, 0, 1)], tmp_path))

    assert raiz.findtext(".//staves") == "2"
    claves = {c.get("number"): c.findtext("sign") for c in raiz.iter("clef")}
    assert claves == {"1": "G", "2": "F"}
    assert len(raiz.findall("part")) == 1, "piano é uma parte com duas pautas"


def test_o_do_central_fica_em_cima_e_o_si_abaixo_dele_embaixo(tmp_path: Path) -> None:
    raiz = _raiz(_exportar([_n(60, 0, 1), _n(59, 1, 1)], tmp_path))

    pautas = {
        (n.findtext("pitch/step"), n.findtext("pitch/octave")): n.findtext("staff")
        for n in raiz.iter("note")
        if n.find("rest") is None
    }
    assert pautas == {("C", "4"): "1", ("B", "3"): "2"}


def test_notas_do_mesmo_tique_e_duracao_sao_um_acorde(tmp_path: Path) -> None:
    arquivo = _exportar([_n(60, 0, 1), _n(64, 0, 1), _n(67, 0.01, 1)], tmp_path)

    notas = [n for n in _raiz(arquivo).iter("note") if n.find("rest") is None]
    assert [n.find("chord") is not None for n in notas] == [False, True, True]
    assert _lidas(arquivo) == [(1, 0, 60, PPQ), (1, 0, 64, PPQ), (1, 0, 67, PPQ)]


def test_duracoes_sobrepostas_na_mesma_pauta_viram_duas_vozes(tmp_path: Path) -> None:
    """Uma semibreve segurada enquanto a melodia anda em semínimas por cima."""
    notas = [_n(60, 0, 4), _n(72, 0, 1), _n(74, 1, 1), _n(76, 2, 1), _n(77, 3, 1)]

    arquivo = _exportar(notas, tmp_path)

    vozes = {
        n.findtext("voice")
        for n in _raiz(arquivo).iter("note")
        if n.find("rest") is None and n.findtext("staff") == "1"
    }
    assert len(vozes) == 2
    assert _lidas(arquivo) == _esperadas(notas)


def test_mesmo_tique_com_duracoes_diferentes_tambem_separa_vozes(tmp_path: Path) -> None:
    notas = [_n(48, 0, 2), _n(43, 0, 1), _n(45, 1, 1)]

    arquivo = _exportar(notas, tmp_path)

    assert _lidas(arquivo) == _esperadas(notas)


def test_nota_que_atravessa_a_barra_volta_inteira(tmp_path: Path) -> None:
    notas = [_n(64, 3, 2), _n(40, 0, 6)]

    arquivo = _exportar(notas, tmp_path)

    assert any(t.get("type") == "start" for t in _raiz(arquivo).iter("tie"))
    assert _lidas(arquivo) == _esperadas(notas)


def test_extremos_e_acorde_de_dez_notas_voltam_inteiros(tmp_path: Path) -> None:
    """A0 e C8 do teclado e dez dedos num ataque só, cinco em cada pauta."""
    dez = [36, 40, 43, 48, 55, 60, 64, 67, 72, 76]
    notas = [_n(21, 0, 1), *(_n(p, 1, 2) for p in dez), _n(108, 3, 1)]

    arquivo = _exportar(notas, tmp_path)

    assert _lidas(arquivo) == _esperadas(notas)


def test_a_referencia_da_fixture_volta_inteira(tmp_path: Path) -> None:
    notas = list(referencia(FIXTURES_MULTI["piano-acustico-isolada"]).notas)

    arquivo = _exportar(notas, tmp_path, bpm=BPM_FIXTURE)

    assert _lidas(arquivo) == _esperadas(notas, BPM_FIXTURE)


def test_titulo_andamento_e_instrumento(tmp_path: Path) -> None:
    raiz = _raiz(_exportar([_n(60, 0, 1)], tmp_path))

    assert (
        raiz.findtext(".//work-title") == "Estudo" or raiz.findtext(".//movement-title") == "Estudo"
    )
    assert raiz.find(".//sound[@tempo='60']") is not None
    assert raiz.findtext(".//midi-program") == "1"


def test_armadura_vale_nas_duas_pautas(tmp_path: Path) -> None:
    arquivo = MusicXmlPianoExporter(bpm=BPM, armadura=-2).exportar(
        [_n(70, 0, 1), _n(46, 0, 1)], tmp_path / "p.musicxml"
    )

    score = converter.parse(str(arquivo))
    armaduras = [
        k.sharps
        for parte in score.parts
        for k in parte.recurse().getElementsByClass("KeySignature")
    ]
    assert armaduras and set(armaduras) == {-2}
    assert len(score.parts) == 2


def _vozes_por_pauta(arquivo: Path) -> dict[str, set[str]]:
    vozes: dict[str, set[str]] = {}
    for n in _raiz(arquivo).iter("note"):
        vozes.setdefault(n.findtext("staff", "1"), set()).add(n.findtext("voice", "1"))
    return vozes


def _sem_duracao(lidas: list[Lida]) -> list[tuple[int, int, int]]:
    return sorted((pauta, inicio, altura) for pauta, inicio, altura, _ in lidas)


def test_mais_de_quatro_vozes_encurta_a_que_libera_primeiro(tmp_path: Path) -> None:
    """O MuseScore tem 4 vozes por pauta e descarta a 5ª calado (medido: 2 de 6 notas).

    Seis notas de dois tempos, uma a cada semicolcheia: a 5ª encurta a 1ª até o
    ataque dela, a 6ª encurta a 2ª. Altura e ataque nunca se perdem.
    """
    notas = [_n(60 + k, k * 0.25, 2) for k in range(6)]

    arquivo = _exportar(notas, tmp_path)

    assert all(len(v) <= 4 for v in _vozes_por_pauta(arquivo).values())
    assert _lidas(arquivo) == [
        (1, 0, 60, 4 * GRADE),
        (1, GRADE, 61, 4 * GRADE),
        (1, 2 * GRADE, 62, 2 * PPQ),
        (1, 3 * GRADE, 63, 2 * PPQ),
        (1, 4 * GRADE, 64, 2 * PPQ),
        (1, 5 * GRADE, 65, 2 * PPQ),
    ]


def test_quinta_duracao_no_mesmo_tique_vira_acorde_com_a_menor(tmp_path: Path) -> None:
    notas = [_n(60 + k, 0, 0.25 * (5 - k)) for k in range(5)]

    arquivo = _exportar(notas, tmp_path)

    assert all(len(v) <= 4 for v in _vozes_por_pauta(arquivo).values())
    assert _lidas(arquivo) == [
        (1, 0, 60, 5 * GRADE),
        (1, 0, 61, 4 * GRADE),
        (1, 0, 62, 3 * GRADE),
        (1, 0, 63, GRADE),
        (1, 0, 64, GRADE),
    ]


def test_trecho_denso_fecha_beams_e_so_encolhe_duracao(tmp_path: Path) -> None:
    """Sementes fixas de notas soltas em colcheias, semicolcheias e pontuadas.

    ADR-038 no piano: o music21 escreve `end` sem `begin` também dentro de vozes
    (antes do conserto, 11 compassos quebrados em 60 sementes). E a densidade passa
    de 4 vozes em 20 das 60: ali a duração pode encolher, ataque e altura não.
    """
    duracoes = [0.125, 0.25, 0.375, 0.5, 0.75, 1.0, 1.5]
    achados = []
    encurtadas = 0
    for semente in range(60):
        sorteio = random.Random(semente)
        notas = []
        for _ in range(40):
            inicio = sorteio.randrange(64) * 0.125
            notas.append(_n(sorteio.randint(36, 84), inicio, sorteio.choice(duracoes)))
        arquivo = _exportar(notas, tmp_path)
        achados += [f"semente {semente}: {a}" for a in _beams_mal_formados(arquivo)]
        lidas, esperadas = _lidas(arquivo), _esperadas(notas)
        assert all(len(v) <= 4 for v in _vozes_por_pauta(arquivo).values()), semente
        assert _sem_duracao(lidas) == _sem_duracao(esperadas), f"semente {semente}"
        # As duas listas ordenadas pareiam nota a nota, inclusive altura repetida no
        # mesmo tique: dentro de cada (pauta, início, altura), durações crescentes.
        for lida, esperada in zip(lidas, esperadas, strict=True):
            assert lida[3] <= esperada[3], f"semente {semente}: {lida} cresceu de {esperada}"
        pares = zip(lidas, esperadas, strict=True)
        encurtadas += sum(lida[3] < esperada[3] for lida, esperada in pares)

    print(f"\nDENSO: {encurtadas} de {60 * 40} notas encurtadas pelo teto de 4 vozes")
    assert achados == []


def test_sem_notas_recusa(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="sem notas"):
        MusicXmlPianoExporter().exportar([], tmp_path / "p.musicxml")


requer_musescore = pytest.mark.skipif(shutil.which("mscore") is None, reason="mscore ausente")


def _pelo_musescore(arquivo: Path) -> Path:
    """Importa no MuseScore e exporta de volta: o que ele entendeu, em MusicXML dele."""
    destino = arquivo.with_name("pelo-musescore.musicxml")
    subprocess.run(
        ["mscore", str(arquivo), "-o", str(destino)],
        check=True,
        capture_output=True,
        env=os.environ | {"QT_QPA_PLATFORM": "offscreen"},
    )
    return destino


@requer_musescore
@pytest.mark.slow
def test_o_musescore_preserva_alturas_tempos_duracoes_e_pautas(tmp_path: Path) -> None:
    dez = [36, 40, 43, 48, 55, 60, 64, 67, 72, 76]
    notas = [
        _n(21, 0, 1),
        *(_n(p, 1, 2) for p in dez),
        _n(108, 3, 1),
        _n(60, 4, 4),
        *(_n(p, 4 + i, 1) for i, p in enumerate((72, 74, 76, 77))),
        _n(64, 11, 2),
        *(_n(48 + k, 16 + k * 0.25, 2) for k in range(6)),  # seis vozes na pauta 2
    ]
    arquivo = _exportar(notas, tmp_path)

    relido = _pelo_musescore(arquivo)

    raiz = _raiz(relido)
    claves = {c.get("number"): c.findtext("sign") for c in raiz.iter("clef")}
    print(f"\nMUSESCORE piano: {len(_lidas(relido))} notas, ref={len(notas)} claves={claves}")
    assert claves == {"1": "G", "2": "F"}
    assert _lidas(relido) == _lidas(arquivo)
    assert _sem_duracao(_lidas(relido)) == _sem_duracao(_esperadas(notas))


def test_o_leitor_do_teste_ve_as_duas_pautas_do_music21(tmp_path: Path) -> None:
    """Guarda do próprio leitor: o music21 separa as pautas em partes."""
    score = converter.parse(str(_exportar([_n(72, 0, 1), _n(48, 0, 1)], tmp_path)))

    assert all(isinstance(p, stream.PartStaff) for p in score.parts)
