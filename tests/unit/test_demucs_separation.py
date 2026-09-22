"""Separador do Demucs: montagem do comando, descoberta do stem e cache."""

from __future__ import annotations

import subprocess
import wave
from pathlib import Path

import pytest

from tests.sintetico import SOUNDFONT, renderizar
from thoth.adapters.separation import DemucsSeparator, localizar_stems


def _toca(caminho: Path) -> Path:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_bytes(b"")
    return caminho


def test_comando_carrega_numpy_antigo() -> None:
    """O demucs declara mal as dependências e quebra com numpy 2 (ADR-010)."""
    comando = DemucsSeparator()._comando(Path("a.wav"), Path("/saida"))
    assert comando[:4] == ["uvx", "--with", "numpy<2", "demucs"]


def test_comando_fixa_modelo_dispositivo_e_dois_stems() -> None:
    comando = DemucsSeparator()._comando(Path("a.wav"), Path("/saida"))
    assert comando[comando.index("-n") + 1] == "htdemucs_ft"
    assert comando[comando.index("-d") + 1] == "cpu"  # a estação não tem CUDA
    assert comando[comando.index("--two-stems") + 1] == "bass"
    assert comando[comando.index("-o") + 1] == "/saida"
    assert comando[-1] == "a.wav"


def test_localizar_encontra_stem_em_subdiretorio_com_hash(tmp_path: Path) -> None:
    """O demucs aninha por modelo e nome do arquivo — que aqui é um SHA-256."""
    ninho = tmp_path / "htdemucs_ft" / ("a" * 64)
    esperado = _toca(ninho / "bass.wav")
    _toca(ninho / "no_bass.wav")

    assert localizar_stems(tmp_path)["bass"] == esperado


def test_localizar_reclama_quando_nao_ha_stem(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match=r"bass\.wav"):
        localizar_stems(tmp_path)


def test_separar_reaproveita_stem_existente(tmp_path: Path) -> None:
    """Separar custa ~88s por 30s de áudio: repetir à toa é caro demais."""
    _toca(tmp_path / "htdemucs_ft" / "x" / "bass.wav")
    # `false` falha na hora: se o cache não pegar, o subprocesso denuncia.
    separador = DemucsSeparator(binary=("false",))

    assert separador.separate(Path("a.wav"), tmp_path)["bass"].name == "bass.wav"


def test_separar_propaga_falha_do_demucs(tmp_path: Path) -> None:
    with pytest.raises(subprocess.CalledProcessError):
        DemucsSeparator(binary=("false",)).separate(Path("a.wav"), tmp_path)


@pytest.mark.slow
@pytest.mark.skipif(not SOUNDFONT.exists(), reason="soundfont ausente")
def test_stem_real_sai_em_pcm_16_bits(tmp_path: Path) -> None:
    """O `octave_check` lê com `wave` e divide por 32768 — só serve PCM 16."""
    wav, _ = renderizar("escala", tmp_path)

    stems = DemucsSeparator().separate(wav, tmp_path / "stems")

    assert stems["bass"].exists()
    with wave.open(str(stems["bass"])) as f:
        assert f.getsampwidth() == 2
        assert f.getframerate() == 44100
