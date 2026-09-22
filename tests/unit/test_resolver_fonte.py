"""O despachante decide o adapter pela forma da referência."""

from __future__ import annotations

import pytest

from thoth.adapters.ingest import LocalFileSource, YtDlpSource, resolver_fonte


@pytest.mark.parametrize(
    "ref",
    [
        "https://www.youtube.com/watch?v=QTOyeFQgZKk",
        "https://youtu.be/QTOyeFQgZKk",
        "http://youtube.com/watch?v=QTOyeFQgZKk",
    ],
)
def test_url_vai_para_o_youtube(ref: str) -> None:
    assert isinstance(resolver_fonte(ref), YtDlpSource)


@pytest.mark.parametrize(
    "ref",
    ["musica.mp3", "/home/boladuz/Music/a.flac", "~/b.wav", "./c.m4a"],
)
def test_caminho_vai_para_o_arquivo_local(ref: str) -> None:
    assert isinstance(resolver_fonte(ref), LocalFileSource)
