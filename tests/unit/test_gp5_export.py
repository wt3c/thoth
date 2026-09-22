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
from thoth.domain.models import TUNING_BASS_4, TUNING_BASS_5, NoteEvent, TabNote
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

    beats = song.tracks[0].measures[0].voices[0].beats
    assert len(_lidas(song)) == 2
    assert [bool(b.notes) for b in beats] == [True, False, True]  # nota, pausa, nota


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
