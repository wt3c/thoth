"""LocalFileSource contra o ffmpeg real — conversão é I/O, não se testa com mock."""

from __future__ import annotations

import subprocess
import wave
from pathlib import Path

import pytest

from thoth.adapters.ingest.local_source import LocalFileSource


@pytest.fixture
def mp3_de_teste(tmp_path: Path) -> Path:
    """Gera um MP3 real de 2 s (seno em 110 Hz, um Lá grave de baixo)."""
    origem = tmp_path / "entrada.mp3"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=110:duration=2",
         "-ac", "2", "-loglevel", "error", str(origem)],
        check=True,
    )
    return origem


def test_converte_para_wav_44100_estereo(mp3_de_teste: Path, tmp_path: Path) -> None:
    ativo = LocalFileSource().fetch(str(mp3_de_teste), tmp_path / "cache")

    assert ativo.wav.exists()
    with wave.open(str(ativo.wav)) as w:
        assert w.getframerate() == 44100
        assert w.getnchannels() == 2


def test_source_id_e_estavel_e_vem_do_conteudo(mp3_de_teste: Path, tmp_path: Path) -> None:
    fonte = LocalFileSource()
    primeiro = fonte.fetch(str(mp3_de_teste), tmp_path / "a")
    segundo = fonte.fetch(str(mp3_de_teste), tmp_path / "b")

    assert primeiro.source_id == segundo.source_id
    assert len(primeiro.source_id) == 16


def test_conteudo_diferente_gera_source_id_diferente(mp3_de_teste: Path, tmp_path: Path) -> None:
    outro = tmp_path / "outro.mp3"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=220:duration=2",
         "-ac", "2", "-loglevel", "error", str(outro)],
        check=True,
    )
    fonte = LocalFileSource()

    assert fonte.fetch(str(mp3_de_teste), tmp_path / "c").source_id != (
        fonte.fetch(str(outro), tmp_path / "c").source_id
    )


def test_cache_hit_nao_reconverte(mp3_de_teste: Path, tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    primeiro = LocalFileSource().fetch(str(mp3_de_teste), cache)
    assinatura = primeiro.wav.stat().st_mtime_ns

    segundo = LocalFileSource().fetch(str(mp3_de_teste), cache)

    assert segundo.wav == primeiro.wav
    assert segundo.wav.stat().st_mtime_ns == assinatura, "reconverteu apesar do cache"


def test_duracao_detectada(mp3_de_teste: Path, tmp_path: Path) -> None:
    ativo = LocalFileSource().fetch(str(mp3_de_teste), tmp_path / "cache")
    assert ativo.duration_s == pytest.approx(2.0, abs=0.2)


def test_arquivo_inexistente_falha_claro(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="não encontrado"):
        LocalFileSource().fetch(str(tmp_path / "nao_existe.mp3"), tmp_path / "cache")
