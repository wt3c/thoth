"""Contrato do modo multifaixa: partitura ampla, áudio focado no baixo."""

from __future__ import annotations

import shutil
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

import guitarpro as gp
import numpy as np
import soundfile as sf

from thoth.domain.models import TUNING_BASS_5, AudioAsset, NoteEvent, Transcricao
from thoth.services.pipeline import transcrever


@dataclass(frozen=True, slots=True)
class FonteLocal:
    asset: AudioAsset

    def fetch(self, ref: str, cache_dir: Path) -> AudioAsset:
        return self.asset


@dataclass(frozen=True, slots=True)
class SeparadorDeTodasAsFamilias:
    def separate(self, audio: Path, out_dir: Path) -> dict[str, Path]:
        out_dir.mkdir(parents=True, exist_ok=True)
        caminhos: dict[str, Path] = {}
        for nome in ("bass", "other", "drums", "no_bass"):
            destino = out_dir / f"{nome}.wav"
            shutil.copy2(audio, destino)
            caminhos[nome] = destino
        return caminhos


@dataclass(frozen=True, slots=True)
class TranscritorPorStem:
    def transcribe(self, audio: Path) -> Transcricao:
        if audio.stem == "bass":
            return Transcricao.do_muscriptor([
                NoteEvent(36, 0.0, 0.45, "electric_bass"),
                NoteEvent(38, 0.5, 0.95, "electric_bass"),
            ])
        if audio.stem == "other":
            return Transcricao.do_muscriptor([
                NoteEvent(52, 0.0, 0.45, "clean_electric_guitar"),
                NoteEvent(53, 0.5, 0.95, "distorted_electric_guitar"),
                NoteEvent(55, 1.0, 1.45, "acoustic_guitar"),
            ])
        return Transcricao.do_muscriptor([
            NoteEvent(36, 0.0, 0.1, "drums"),
            NoteEvent(42, 0.5, 0.6, "drums"),
        ])


def test_todos_combina_partes_e_entrega_somente_wavs_de_baixo(tmp_path: Path) -> None:
    wav = tmp_path / "musica.wav"
    sf.write(wav, np.zeros(88_200, dtype=np.float32), 44_100)
    asset = AudioAsset(wav=wav, source_id="multifaixa", title="Música", duration_s=2.0)

    resultado = transcrever(
        str(wav),
        tmp_path / "out",
        bpm=120,
        instrumento="todos",
        tuning=TUNING_BASS_5,
        cache_dir=tmp_path / "cache",
        source=FonteLocal(asset),
        separator=SeparadorDeTodasAsFamilias(),
        transcriber=TranscritorPorStem(),
        _gerar_auralizacao=False,
    )

    musica = gp.parse(str(resultado.artefatos["gp5"]))
    xml = ET.parse(resultado.artefatos["musicxml"]).getroot()
    assert [faixa.name for faixa in musica.tracks] == [
        "Baixo",
        "Guitarra limpa",
        "Guitarra distorcida",
        "Guitarra acústica",
        "Bateria",
    ]
    assert [parte.text for parte in xml.iter("part-name")] == [
        "Baixo", "Guitarra limpa", "Guitarra distorcida", "Guitarra acústica", "Bateria"
    ]
    assert len(musica.tracks[0].strings) == 5
    assert resultado.instrumento == "todos"
    assert resultado.notas == 7
    assert {chave for chave in resultado.artefatos if chave not in {"gp5", "musicxml"}} <= {
        "mix",
        "baixo",
        "sem-baixo",
        "aural",
    }
    wavs = list(resultado.artefatos["gp5"].parent.glob("*.wav"))
    assert {caminho.name for caminho in wavs} <= {
        "Música.mix.wav",
        "Música.baixo.wav",
        "Música.sem-baixo.wav",
        "Música.aural.wav",
    }
