"""Exportador GP5 — round-trip contra a biblioteca real, nunca mock.

O formato é binário e de terceiro: um mock provaria que chamo a API do jeito que
imagino, que é exatamente a suposição em teste. Todo teste aqui grava um arquivo
e o relê.
"""

from __future__ import annotations

from pathlib import Path

import guitarpro as gp
import pytest

from thoth.adapters.export.gp5 import Gp5Exporter
from thoth.domain.models import (
    TUNING_BASS_4,
    TUNING_BASS_5,
    TUNING_BASS_6,
    NoteEvent,
    TabNote,
)
from thoth.services.fretboard import ViterbiFretAssigner

BPM = 90
SEMINIMA = 60.0 / BPM


def _tabs(pitches: list[int], passo: float = SEMINIMA,
          afinacao: tuple[int, ...] = TUNING_BASS_4) -> list[TabNote]:
    notas = [
        NoteEvent(pitch=p, onset_s=i * passo, offset_s=i * passo + passo * 0.9,
                  instrument="electric_bass")
        for i, p in enumerate(pitches)
    ]
    return ViterbiFretAssigner().assign(notas, afinacao)


def _exportar(tabs: list[TabNote], destino: Path, **kwargs: object) -> gp.Song:
    alvo = Gp5Exporter(**kwargs).export(tabs, destino / "tab.gp5", TUNING_BASS_4)  # type: ignore[arg-type]
    assert alvo.exists()
    return gp.parse(str(alvo))


def _lidas(song: gp.Song) -> list[tuple[int, int]]:
    return [
        (nota.string, nota.value)
        for medida in song.tracks[0].measures
        for beat in medida.voices[0].beats
        for nota in beat.notes
    ]


def test_round_trip_preserva_corda_e_traste(tmp_path: Path) -> None:
    tabs = _tabs([36, 38, 40, 41, 43, 45, 47, 48])
    song = _exportar(tabs, tmp_path, bpm=BPM)

    # A corda do GP é numerada da mais aguda para a mais grave; a nossa, o contrário.
    esperado = [(len(TUNING_BASS_4) - t.string, t.fret) for t in tabs]
    assert _lidas(song) == esperado


def test_round_trip_preserva_afinacao_tempo_e_instrumento(tmp_path: Path) -> None:
    song = _exportar(_tabs([36, 38]), tmp_path, bpm=BPM)
    track = song.tracks[0]

    assert song.tempo == BPM
    assert [corda.value for corda in track.strings] == list(reversed(TUNING_BASS_4))
    assert track.channel.instrument == 33  # GM Electric Bass (finger)


def test_cinco_cordas_sobrevive(tmp_path: Path) -> None:
    tabs = _tabs([23, 24, 26, 28], afinacao=TUNING_BASS_5)
    alvo = Gp5Exporter(bpm=BPM).export(tabs, tmp_path / "b.gp5", TUNING_BASS_5)
    track = gp.parse(str(alvo)).tracks[0]

    assert [corda.value for corda in track.strings] == list(reversed(TUNING_BASS_5))
    assert len(track.strings) == 5


def test_seis_cordas_sobrevive(tmp_path: Path) -> None:
    tabs = _tabs([23, 48, 52], afinacao=TUNING_BASS_6)
    alvo = Gp5Exporter(bpm=BPM).export(tabs, tmp_path / "b.gp5", TUNING_BASS_6)
    track = gp.parse(str(alvo)).tracks[0]

    assert [corda.value for corda in track.strings] == list(reversed(TUNING_BASS_6))


def test_quebra_em_compassos_de_quatro_tempos(tmp_path: Path) -> None:
    song = _exportar(_tabs([36] * 9), tmp_path, bpm=BPM)  # 9 semínimas = 2 compassos e 1 tempo

    assert len(song.tracks[0].measures) == 3
    assert len(_lidas(song)) == 9


def test_semicolcheias_sobrevivem_a_grade(tmp_path: Path) -> None:
    song = _exportar(_tabs([36, 38, 40, 41] * 4, passo=SEMINIMA / 4), tmp_path, bpm=BPM)

    assert len(_lidas(song)) == 16
    assert len(song.tracks[0].measures) == 1  # 16 semicolcheias = 1 compasso


def test_silencio_vira_pausa_e_nao_desloca_a_nota(tmp_path: Path) -> None:
    """Sem pausa, a segunda nota subiria para o tempo 2 e a leitura ficaria errada."""
    notas = [
        NoteEvent(pitch=36, onset_s=0.0, offset_s=0.4, instrument="electric_bass"),
        NoteEvent(pitch=36, onset_s=SEMINIMA * 3, offset_s=SEMINIMA * 3 + 0.4,
                  instrument="electric_bass"),
    ]
    song = _exportar(ViterbiFretAssigner().assign(notas, TUNING_BASS_4), tmp_path, bpm=BPM)

    medida = song.tracks[0].measures[0]
    beats = medida.voices[0].beats
    assert len(_lidas(song)) == 2
    # O que se lê numa tablatura é o ataque: a segunda nota tem que cair no quarto
    # tempo, três semínimas depois da primeira, com pausas cobrindo o intervalo.
    ataques = [beat.start - medida.start for beat in beats if beat.notes]
    assert ataques == [0, gp.Duration.quarterTime * 3]
    assert sum(beat.duration.time for beat in beats) == gp.Duration.quarterTime * 4


def test_sem_notas_e_erro(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="sem notas"):
        Gp5Exporter().export([], tmp_path / "vazio.gp5", TUNING_BASS_4)


def test_notas_simultaneas_sao_recusadas(tmp_path: Path) -> None:
    """O motor de tablatura é monofônico; exportar acorde produziria tab impossível."""
    simultaneas = [
        NoteEvent(pitch=36, onset_s=0.0, offset_s=0.4, instrument="electric_bass"),
        NoteEvent(pitch=43, onset_s=0.01, offset_s=0.4, instrument="electric_bass"),
    ]
    tabs = ViterbiFretAssigner().assign(simultaneas, TUNING_BASS_4)

    with pytest.raises(ValueError, match="simultâne"):
        Gp5Exporter(bpm=BPM).export(tabs, tmp_path / "acorde.gp5", TUNING_BASS_4)


def test_escreve_o_nome_da_nota_no_beat(tmp_path: Path) -> None:
    """O nome viaja como texto do beat: é o que o Guitar Pro e o alphaTab mostram."""
    song = _exportar(_tabs([28, 34, 36]), tmp_path, bpm=BPM)

    textos = [
        beat.text
        for medida in song.tracks[0].measures
        for beat in medida.voices[0].beats
        if beat.notes
    ]
    assert textos == ["E", "A#", "C"]


def test_pausa_nao_recebe_texto(tmp_path: Path) -> None:
    """Texto em pausa apareceria como rótulo solto no meio do compasso."""
    song = _exportar(_tabs([28], passo=SEMINIMA * 4), tmp_path, bpm=BPM)

    assert all(
        beat.text is None
        for medida in song.tracks[0].measures
        for beat in medida.voices[0].beats
        if not beat.notes
    )


def test_cada_nota_ocupa_um_beat_proprio(tmp_path: Path) -> None:
    """Regressão: sem `status`, o beat sai `empty`, vale duração zero na releitura e
    todo o compasso desaba num beat só — as notas sobrevivem, a rítmica não."""
    song = _exportar(_tabs([36, 38, 40, 41]), tmp_path, bpm=BPM)

    beats = song.tracks[0].measures[0].voices[0].beats
    assert [len(beat.notes) for beat in beats] == [1, 1, 1, 1]
    assert all(beat.status is gp.BeatStatus.normal for beat in beats)


# --- Ligadura através da barra (ADR-022) -------------------------------------


def _atravessando_a_barra(tmp_path: Path) -> gp.Song:
    """Uma nota no 'quatro e', sustentada 1,5 semínima: entra no compasso seguinte."""
    nota = NoteEvent(pitch=36, onset_s=SEMINIMA * 3.5, offset_s=SEMINIMA * 5.0,
                     instrument="electric_bass")
    tabs = ViterbiFretAssigner().assign([nota], TUNING_BASS_4)
    return _exportar(tabs, tmp_path, bpm=BPM)


def test_nota_atravessa_a_barra_como_ligadura(tmp_path: Path) -> None:
    """Cortar na barra trocava sustentação por ataque curto — o groove muda."""
    song = _atravessando_a_barra(tmp_path)
    medidas = song.tracks[0].measures

    assert len(medidas) == 2
    tipos = [
        nota.type
        for medida in medidas
        for beat in medida.voices[0].beats
        for nota in beat.notes
    ]
    assert tipos == [gp.NoteType.normal, gp.NoteType.tie]


def test_a_ligadura_preserva_a_duracao_somada(tmp_path: Path) -> None:
    """A soma é o que o leitor toca: 1,5 semínima, não a maior figura que coube."""
    song = _atravessando_a_barra(tmp_path)

    tocado = sum(
        beat.duration.time
        for medida in song.tracks[0].measures
        for beat in medida.voices[0].beats
        if beat.notes
    )
    assert tocado == gp.Duration.quarterTime * 3 // 2


def test_cada_compasso_continua_fechando_em_quatro_tempos(tmp_path: Path) -> None:
    """Ligadura que estoura o compasso produz arquivo que o leitor realinha sozinho."""
    song = _atravessando_a_barra(tmp_path)

    for medida in song.tracks[0].measures:
        assert sum(beat.duration.time for beat in medida.voices[0].beats) == (
            gp.Duration.quarterTime * 4
        )


def test_nota_longa_dentro_do_compasso_liga_em_vez_de_virar_pausa(tmp_path: Path) -> None:
    """Meia semínima sobrando virava pausa: a nota soava mais curta do que é."""
    nota = NoteEvent(pitch=36, onset_s=0.0, offset_s=SEMINIMA * 3.5,
                     instrument="electric_bass")
    song = _exportar(ViterbiFretAssigner().assign([nota], TUNING_BASS_4), tmp_path, bpm=BPM)

    beats = song.tracks[0].measures[0].voices[0].beats
    com_nota = [beat for beat in beats if beat.notes]
    assert [nota.type for beat in com_nota for nota in beat.notes] == [
        gp.NoteType.normal,
        gp.NoteType.tie,
    ]
    assert sum(beat.duration.time for beat in com_nota) == gp.Duration.quarterTime * 7 // 2


def test_a_ligadura_nao_repete_o_nome_da_nota(tmp_path: Path) -> None:
    """Nome repetido na continuação se lê como outro ataque — é o oposto de ligar."""
    song = _atravessando_a_barra(tmp_path)

    textos = [
        beat.text
        for medida in song.tracks[0].measures
        for beat in medida.voices[0].beats
        if beat.notes
    ]
    assert textos == ["C", None]


def test_em_tom_bemol_o_texto_do_beat_sai_bemol(tmp_path: Path) -> None:
    """A armadura não existe no GP5 do Thoth; o nome do beat é onde o tom aparece."""
    song = _exportar(_tabs([28, 34, 36]), tmp_path, bpm=BPM, armadura=-4)

    textos = [
        beat.text
        for medida in song.tracks[0].measures
        for beat in medida.voices[0].beats
        if beat.notes
    ]
    assert textos == ["E", "Bb", "C"]


def test_o_titulo_da_musica_vai_no_arquivo(tmp_path: Path) -> None:
    """O GP5 já tinha o campo; quem não o preenchia era o pipeline."""
    song = _exportar(_tabs([36, 38]), tmp_path, titulo="Smooth Operator")

    assert song.title == "Smooth Operator"
