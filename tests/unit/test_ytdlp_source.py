"""YtDlpSource: parsing de URL e cache sem rede; download real marcado `network`."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from thoth.adapters.ingest.ytdlp_source import IngestError, YtDlpSource, extrair_video_id

URL_TESTE = "https://www.youtube.com/watch?v=QTOyeFQgZKk"


@pytest.mark.parametrize(
    "url",
    [
        "https://www.youtube.com/watch?v=QTOyeFQgZKk",
        "https://youtu.be/QTOyeFQgZKk",
        "https://www.youtube.com/watch?v=QTOyeFQgZKk&list=PLabc&index=2",
        "https://m.youtube.com/watch?v=QTOyeFQgZKk",
        "https://www.youtube.com/embed/QTOyeFQgZKk",
    ],
)
def test_extrai_video_id_de_todas_as_formas_de_url(url: str) -> None:
    assert extrair_video_id(url) == "QTOyeFQgZKk"


def test_url_sem_video_id_falha_claro() -> None:
    with pytest.raises(IngestError, match="ID do vídeo"):
        extrair_video_id("https://www.youtube.com/results?search_query=baixo")


def test_cache_hit_nao_toca_a_rede(tmp_path: Path) -> None:
    """Com mix.wav e meta.json no cache, fetch devolve sem chamar o yt-dlp."""
    destino = tmp_path / "yt_QTOyeFQgZKk"
    destino.mkdir(parents=True)
    (destino / "mix.wav").write_bytes(b"fake")
    (destino / "meta.json").write_text(
        json.dumps({"title": "Everything Changes", "artist": "SOJA", "duration_s": 309.0})
    )

    ativo = YtDlpSource().fetch(URL_TESTE, tmp_path)

    assert ativo.source_id == "yt_QTOyeFQgZKk"
    assert ativo.title == "Everything Changes"
    assert ativo.artist == "SOJA"
    assert ativo.duration_s == 309.0


@pytest.mark.network
@pytest.mark.slow
def test_baixa_de_verdade_do_youtube(tmp_path: Path) -> None:
    """Canário: quando o YouTube quebrar o yt-dlp, este teste avisa."""
    import wave

    ativo = YtDlpSource().fetch(URL_TESTE, tmp_path)

    assert ativo.wav.exists()
    assert ativo.source_id == "yt_QTOyeFQgZKk"
    assert "SOJA" in f"{ativo.title} {ativo.artist}"
    assert ativo.duration_s == pytest.approx(309, abs=5)
    with wave.open(str(ativo.wav)) as w:
        assert w.getframerate() == 44100
        assert w.getnchannels() == 2
