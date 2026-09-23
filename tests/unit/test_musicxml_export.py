"""Exportador MusicXML — round-trip contra o music21 real, gravando arquivo.

A clave é o detalhe que mais erra em partitura de baixo: o instrumento soa uma
oitava abaixo do escrito, e sem `Bass8vb` a leitura sai uma oitava acima.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from music21 import articulations, clef, converter, key, note, tempo

from thoth.adapters.export.musicxml import MusicXmlExporter
from thoth.domain.models import TUNING_BASS_4, TUNING_BASS_5, NoteEvent, TabNote
from thoth.services.fretboard import ViterbiFretAssigner

BPM = 90
SEMINIMA = 60.0 / BPM


def _tabs(pitches: list[int], passo: float = SEMINIMA) -> list[TabNote]:
    notas = [
        NoteEvent(pitch=p, onset_s=i * passo, offset_s=i * passo + passo * 0.9,
                  instrument="electric_bass")
        for i, p in enumerate(pitches)
    ]
    return ViterbiFretAssigner().assign(notas, TUNING_BASS_4)


def _arquivo(tabs: list[TabNote], destino: Path, **kw: object) -> Path:
    alvo = MusicXmlExporter(bpm=BPM, **kw).export(  # type: ignore[arg-type]
        tabs, destino / "tab.musicxml", TUNING_BASS_4
    )
    assert alvo.exists()
    return alvo


def _exportar(tabs: list[TabNote], destino: Path):  # type: ignore[no-untyped-def]
    """A pauta de notação. A de tablatura é `parts[1]` (ADR-035).

    Ancorar em `parts[0]` não é detalhe: sem isso cada nota aparece duas vezes e
    asserções que contam notas mudam de significado sem ficarem vermelhas.
    """
    return converter.parse(str(_arquivo(tabs, destino))).parts[0]


def test_round_trip_preserva_as_alturas(tmp_path: Path) -> None:
    pitches = [36, 38, 40, 41, 43, 45, 47, 48]
    lido = _exportar(_tabs(pitches), tmp_path)

    assert [n.pitch.midi for n in lido.flatten().notes] == pitches


def test_clave_de_fa_oitava_abaixo(tmp_path: Path) -> None:
    lido = _exportar(_tabs([36, 38]), tmp_path)

    claves = lido.flatten().getElementsByClass(clef.Clef)
    assert isinstance(claves[0], clef.Bass8vbClef)


def test_andamento_vai_no_arquivo(tmp_path: Path) -> None:
    lido = _exportar(_tabs([36, 38]), tmp_path)

    marcas = lido.flatten().getElementsByClass(tempo.MetronomeMark)
    assert [m.number for m in marcas] == [BPM]


def test_corda_e_traste_acompanham_cada_nota(tmp_path: Path) -> None:
    """Na tablatura, que é onde o número do traste se lê (ADR-035)."""
    tabs = _tabs([36, 43, 31])
    lido = converter.parse(str(_arquivo(tabs, tmp_path))).parts[1]

    lidas = [
        (
            next(a.number for a in n.articulations
                 if isinstance(a, articulations.StringIndication)),
            next(a.number for a in n.articulations
                 if isinstance(a, articulations.FretIndication)),
        )
        for n in lido.flatten().notes
    ]
    # MusicXML numera as cordas como o GP: 1 = mais aguda.
    assert lidas == [(len(TUNING_BASS_4) - t.string, t.fret) for t in tabs]


def test_duracoes_seguem_a_grade(tmp_path: Path) -> None:
    """Semínima, colcheia e semicolcheia — a grade não pode arredondar para zero."""
    notas = [
        NoteEvent(pitch=36, onset_s=0.0, offset_s=SEMINIMA, instrument="electric_bass"),
        NoteEvent(pitch=38, onset_s=SEMINIMA, offset_s=SEMINIMA * 1.5,
                  instrument="electric_bass"),
        NoteEvent(pitch=40, onset_s=SEMINIMA * 1.5, offset_s=SEMINIMA * 1.75,
                  instrument="electric_bass"),
    ]
    lido = _exportar(ViterbiFretAssigner().assign(notas, TUNING_BASS_4), tmp_path)

    assert [n.quarterLength for n in lido.flatten().notes] == [1.0, 0.5, 0.25]


def test_silencio_vira_pausa(tmp_path: Path) -> None:
    notas = [
        NoteEvent(pitch=36, onset_s=0.0, offset_s=SEMINIMA, instrument="electric_bass"),
        NoteEvent(pitch=36, onset_s=SEMINIMA * 3, offset_s=SEMINIMA * 4,
                  instrument="electric_bass"),
    ]
    lido = _exportar(ViterbiFretAssigner().assign(notas, TUNING_BASS_4), tmp_path)

    pausas = lido.flatten().getElementsByClass(note.Rest)
    assert sum(p.quarterLength for p in pausas) == 2.0


def test_sem_notas_e_erro(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="sem notas"):
        MusicXmlExporter().export([], tmp_path / "vazio.musicxml", TUNING_BASS_4)


def test_notas_simultaneas_sao_recusadas(tmp_path: Path) -> None:
    simultaneas = [
        NoteEvent(pitch=36, onset_s=0.0, offset_s=0.4, instrument="electric_bass"),
        NoteEvent(pitch=43, onset_s=0.01, offset_s=0.4, instrument="electric_bass"),
    ]
    tabs = ViterbiFretAssigner().assign(simultaneas, TUNING_BASS_4)

    with pytest.raises(ValueError, match="simultâne"):
        MusicXmlExporter(bpm=BPM).export(tabs, tmp_path / "acorde.musicxml", TUNING_BASS_4)


def test_escreve_o_nome_da_nota_sob_a_pauta(tmp_path: Path) -> None:
    """No MusicXML o nome vai como lyric — é o que o MuseScore desenha sob a nota."""
    partitura = _exportar(_tabs([28, 34, 36]), tmp_path)

    lidos = [n.lyric for n in partitura.recurse().notes]
    assert lidos == ["E", "A#", "C"]


# --- Ligadura através da barra (ADR-022) -------------------------------------


def _atravessando_a_barra(tmp_path: Path):  # type: ignore[no-untyped-def]
    """Uma nota no 'quatro e', sustentada 1,5 semínima: entra no compasso seguinte."""
    nota = NoteEvent(pitch=36, onset_s=SEMINIMA * 3.5, offset_s=SEMINIMA * 5.0,
                     instrument="electric_bass")
    return _exportar(ViterbiFretAssigner().assign([nota], TUNING_BASS_4), tmp_path)


def test_nota_atravessa_a_barra_como_ligadura(tmp_path: Path) -> None:
    """Cortar na barra trocava sustentação por ataque curto — o groove muda."""
    lido = _atravessando_a_barra(tmp_path)

    notas = list(lido.flatten().notes)
    assert len(notas) == 2
    assert [n.tie.type for n in notas] == ["start", "stop"]


def test_a_ligadura_preserva_a_duracao_somada(tmp_path: Path) -> None:
    """A soma é o que o leitor toca: 1,5 semínima, não o que coube no compasso."""
    lido = _atravessando_a_barra(tmp_path)

    assert sum(n.quarterLength for n in lido.flatten().notes) == 1.5


def test_a_ligadura_nao_repete_o_nome_da_nota(tmp_path: Path) -> None:
    """Nome repetido na continuação se lê como outro ataque — é o oposto de ligar."""
    lido = _atravessando_a_barra(tmp_path)

    assert [n.lyric for n in lido.flatten().notes] == ["C", None]


def test_a_armadura_estimada_e_escrita_na_partitura(tmp_path: Path) -> None:
    """Quatro bemóis na pauta, e o nome sob a nota concorda com eles (ADR-031)."""
    lido = converter.parse(str(_arquivo(_tabs([28, 34, 36]), tmp_path, armadura=-4))).parts[0]

    assert [k.sharps for k in lido.recurse().getElementsByClass(key.KeySignature)] == [-4]
    assert [n.lyric for n in lido.recurse().notes] == ["E", "Bb", "C"]


def test_sem_tom_confiavel_a_partitura_sai_como_sempre(tmp_path: Path) -> None:
    """Armadura errada imprime mais bequadro do que armadura nenhuma (ADR-031)."""
    lido = _exportar(_tabs([28, 34, 36]), tmp_path)

    assert list(lido.recurse().getElementsByClass(key.KeySignature)) == []
    assert [n.lyric for n in lido.recurse().notes] == ["E", "A#", "C"]


def test_o_titulo_da_musica_vai_no_arquivo(tmp_path: Path) -> None:
    """Partitura sem título é folha anônima: o nome do arquivo não se lê no papel.

    Sem `Metadata` o music21 imprimia `Music21 Fragment` — o placeholder da
    biblioteca, que é o que o MuseScore mostrava.

    Afirmo o XML cru porque é o que os leitores abrem: na volta pelo music21 10.5
    o `<work-title>` não reaparece em `metadata.title`, e sim em `bestTitle`.
    """
    alvo = _arquivo(_tabs([36, 38]), tmp_path, titulo="Smooth Operator")

    assert "<work-title>Smooth Operator</work-title>" in alvo.read_text()
    assert converter.parse(str(alvo)).metadata.bestTitle == "Smooth Operator"


# --- Pauta de tablatura (ADR-035) --------------------------------------------


requer_musescore = pytest.mark.skipif(
    shutil.which("mscore") is None, reason="mscore ausente"
)


def test_o_arquivo_traz_partitura_e_tablatura(tmp_path: Path) -> None:
    """Duas pautas na mesma parte: notação em cima, tablatura embaixo."""
    lido = converter.parse(str(_arquivo(_tabs([36, 38]), tmp_path)))

    claves = [type(p.recurse().getElementsByClass(clef.Clef)[0]) for p in lido.parts]
    assert claves == [clef.Bass8vbClef, clef.TabClef]


def test_a_tablatura_declara_linhas_e_afinacao(tmp_path: Path) -> None:
    """Sem `staff-details` o leitor não sabe quantas cordas nem como estão afinadas.

    O music21 10.5 emite `<staves>`, `<staff>` e a clave TAB, mas não isto — daí a
    injeção depois da escrita. Afirmo o XML cru porque é o contrato com o leitor.

    A linha 1 é a de baixo da tablatura, logo a corda mais grave: trocar a ordem
    gera arquivo que abre sem erro e mostra os trastes errados.
    """
    xml = _arquivo(_tabs([36, 38]), tmp_path).read_text()

    assert "<staff-lines>4</staff-lines>" in xml
    afinacao = re.findall(
        r'<staff-tuning line="(\d)">\s*<tuning-step>(\w)</tuning-step>\s*'
        r"<tuning-octave>(\d)</tuning-octave>",
        xml,
    )
    assert afinacao == [("1", "E", "1"), ("2", "A", "1"), ("3", "D", "2"), ("4", "G", "2")]


def test_a_afinacao_de_cinco_cordas_vai_inteira(tmp_path: Path) -> None:
    """O si grave é a corda que some quando a afinação é escrita em tamanho fixo."""
    tabs = ViterbiFretAssigner().assign(
        [NoteEvent(pitch=23, onset_s=0.0, offset_s=SEMINIMA, instrument="electric_bass")],
        TUNING_BASS_5,
    )
    alvo = MusicXmlExporter(bpm=BPM).export(tabs, tmp_path / "cinco.musicxml", TUNING_BASS_5)

    xml = alvo.read_text()
    assert "<staff-lines>5</staff-lines>" in xml
    assert '<staff-tuning line="1">\n            <tuning-step>B</tuning-step>' in xml


def test_o_nome_da_nota_fica_so_na_partitura(tmp_path: Path) -> None:
    """Na tablatura o nome duplica o traste, que já está ali — vira ruído."""
    lido = converter.parse(str(_arquivo(_tabs([28, 34, 36]), tmp_path)))

    assert [n.lyric for n in lido.parts[0].recurse().notes] == ["E", "A#", "C"]
    assert [n.lyric for n in lido.parts[1].recurse().notes] == [None, None, None]


def test_as_duas_pautas_tocam_as_mesmas_notas(tmp_path: Path) -> None:
    """Pauta que discorda da outra é pior que pauta nenhuma."""
    lido = converter.parse(str(_arquivo(_tabs([36, 38, 40, 41]), tmp_path)))

    alturas = [[n.pitch.midi for n in p.flatten().notes] for p in lido.parts]
    assert alturas[0] == alturas[1] == [36, 38, 40, 41]


@requer_musescore
@pytest.mark.slow
def test_o_musescore_monta_a_tablatura_com_a_nossa_digitacao(tmp_path: Path) -> None:
    """O leitor de verdade, não o round-trip pelo music21 (Regra 3).

    Afirmo a digitação, não só a existência da pauta: se o MuseScore recalculasse
    os trastes, a tablatura abriria bonita e jogaria fora o Viterbi (ADR-032).
    """
    tabs = _tabs([36, 43, 31])
    alvo = _arquivo(tabs, tmp_path)
    destino = tmp_path / "lido.mscx"
    subprocess.run(
        ["mscore", str(alvo), "-o", str(destino)],
        check=True,
        capture_output=True,
        env=os.environ | {"QT_QPA_PLATFORM": "offscreen"},
    )

    mscx = destino.read_text()
    assert '<StaffType group="tablature">' in mscx
    # O MuseScore guarda a afinação em `StringData`, do grave para o agudo.
    cordas = re.search(r"<StringData>.*?</StringData>", mscx, re.S)
    assert cordas is not None
    assert re.findall(r"<string>(\d+)</string>", cordas.group()) == [
        str(v) for v in TUNING_BASS_4
    ]
    # E as cordas dele são 0 no topo, ao contrário das nossas.
    corpo = mscx[mscx.index('<Staff id="2"') :]
    lidos = re.findall(r"<fret>(\d+)</fret>\s*<string>(\d+)</string>", corpo)
    assert lidos == [(str(t.fret), str(len(TUNING_BASS_4) - 1 - t.string)) for t in tabs]


def test_corda_alterada_leva_o_acidente_na_afinacao(tmp_path: Path) -> None:
    """Nenhuma afinação do domínio tem corda alterada — o formato, sim.

    Sem `tuning-alter` um sol sustenido sairia como sol e a tablatura inteira
    deslizaria um semitom. A afinação aqui é arbitrária, só para exercitar o ramo:
    não é afinação que o `domain/models.py` ofereça. A grafia é a do music21, que
    escolhe bemol para 27 e sustenido para os outros — o que cobre os dois sinais.
    """
    afinacao = (27, 32, 37, 42)
    tabs = ViterbiFretAssigner().assign(
        [NoteEvent(pitch=27, onset_s=0.0, offset_s=SEMINIMA, instrument="electric_bass")],
        afinacao,
    )
    alvo = MusicXmlExporter(bpm=BPM).export(tabs, tmp_path / "alterada.musicxml", afinacao)

    xml = alvo.read_text()
    alterados = re.findall(
        r"<tuning-step>(\w)</tuning-step>\s*<tuning-alter>(-?\d)</tuning-alter>", xml
    )
    assert alterados == [("E", "-1"), ("G", "1"), ("C", "1"), ("F", "1")]
