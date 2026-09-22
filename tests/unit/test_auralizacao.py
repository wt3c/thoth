"""Auralização — fluidsynth e ffmpeg reais, nunca mock.

O artefato é um WAV que uma pessoa vai ouvir: mock provaria que chamo o
fluidsynth do jeito que imagino, e é justamente aí que o erro moraria. Todo
teste aqui renderiza de verdade e relê o que saiu.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from tests.sintetico import SOUNDFONT
from thoth.domain.models import NoteEvent
from thoth.services.auralizacao import auralizar

requer_ferramentas = pytest.mark.skipif(
    not SOUNDFONT.exists()
    or shutil.which("fluidsynth") is None
    or shutil.which("ffmpeg") is None,
    reason="fluidsynth, ffmpeg ou soundfont ausente",
)

NOTAS = [
    NoteEvent(pitch=40, onset_s=0.0, offset_s=0.9, instrument="electric_bass"),
    NoteEvent(pitch=45, onset_s=1.0, offset_s=1.9, instrument="electric_bass"),
]


@pytest.fixture
def original(tmp_path: Path) -> Path:
    """Dois segundos de tom puro a 440 Hz — serve de referência reconhecível."""
    alvo = tmp_path / "original.wav"
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
         "-i", "sine=frequency=440:duration=2", "-ar", "44100", str(alvo)],
        check=True,
    )
    return alvo


@requer_ferramentas
def test_sai_estereo_com_original_e_transcricao_separados(original: Path, tmp_path: Path) -> None:
    """O ponto inteiro da auralização: ouvir um em cada ouvido e notar o descolamento."""
    saida = auralizar(original, NOTAS, tmp_path / "aural.wav")
    audio, _ = sf.read(str(saida))

    assert audio.ndim == 2 and audio.shape[1] == 2
    esquerdo, direito = audio[:, 0], audio[:, 1]
    assert np.abs(esquerdo).max() > 0.01, "canal do original mudo"
    assert np.abs(direito).max() > 0.01, "canal da transcrição mudo"
    # Se os canais fossem o mesmo sinal, a auralização não mostraria nada.
    assert not np.allclose(esquerdo, direito)


@requer_ferramentas
def test_duracao_acompanha_o_original(original: Path, tmp_path: Path) -> None:
    """Truncar no fim esconderia justamente o trecho onde o erro costuma acumular."""
    saida = auralizar(original, NOTAS, tmp_path / "aural.wav")
    audio, taxa = sf.read(str(saida))
    esperado, _ = sf.read(str(original))

    assert abs(len(audio) / taxa - len(esperado) / 44100) < 0.05


@requer_ferramentas
def test_a_transcricao_soa_quando_a_nota_soa(original: Path, tmp_path: Path) -> None:
    """Sem isto, um canal direito preenchido de silêncio passaria como sucesso."""
    saida = auralizar(original, NOTAS, tmp_path / "aural.wav")
    audio, taxa = sf.read(str(saida))
    direito = audio[:, 1]

    durante = np.abs(direito[int(0.1 * taxa) : int(0.8 * taxa)]).max()
    intervalo = np.abs(direito[int(0.93 * taxa) : int(0.99 * taxa)]).max()
    assert durante > intervalo * 2, "a nota não se distingue do intervalo entre notas"


@requer_ferramentas
def test_sem_notas_e_erro(original: Path, tmp_path: Path) -> None:
    """Auralizar o nada produziria um arquivo mudo que parece um problema de áudio."""
    with pytest.raises(ValueError, match="sem notas"):
        auralizar(original, [], tmp_path / "aural.wav")
