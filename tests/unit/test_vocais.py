"""Entrega do stem vocal sem prometer transcrição ou partitura."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile as sf

from thoth.domain.models import AudioAsset
from thoth.services.vocais import separar


@dataclass(frozen=True, slots=True)
class FonteLocal:
    asset: AudioAsset

    def fetch(self, ref: str, cache_dir: Path) -> AudioAsset:
        return self.asset


@dataclass(frozen=True, slots=True)
class SeparadorVocal:
    def separate(self, audio: Path, out_dir: Path) -> dict[str, Path]:
        out_dir.mkdir(parents=True, exist_ok=True)
        return {
            nome: Path(shutil.copy2(audio, out_dir / f"{nome}.wav"))
            for nome in ("vocals", "no_vocals")
        }


def test_separar_entrega_mix_vocais_e_playback_sem_vocais(tmp_path: Path) -> None:
    wav = tmp_path / "entrada.wav"
    sf.write(wav, np.zeros(44_100, dtype=np.float32), 44_100)
    asset = AudioAsset(wav=wav, source_id="voz", title="Música: teste", duration_s=1.0)

    resultado = separar(
        str(wav),
        tmp_path / "out",
        cache_dir=tmp_path / "cache",
        source=FonteLocal(asset),
        separator=SeparadorVocal(),
    )

    assert resultado.asset == asset
    assert resultado.stem == resultado.artefatos["vocais"]
    assert set(resultado.artefatos) == {"mix", "vocais", "sem-vocais"}
    assert {caminho.name for caminho in resultado.artefatos.values()} == {
        "Música- teste.mix.wav",
        "Música- teste.vocais.wav",
        "Música- teste.sem-vocais.wav",
    }
    pasta_esperada = tmp_path / "out" / "Música- teste"
    assert all(caminho.parent == pasta_esperada for caminho in resultado.artefatos.values())
