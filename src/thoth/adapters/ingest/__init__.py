"""Escolha do adapter de ingestão conforme a referência recebida."""

from __future__ import annotations

from urllib.parse import urlparse

from thoth.adapters.ingest.local_source import LocalFileSource
from thoth.adapters.ingest.ytdlp_source import YtDlpSource
from thoth.domain.ports import AudioSource

__all__ = ["LocalFileSource", "YtDlpSource", "resolver_fonte"]


def resolver_fonte(ref: str) -> AudioSource:
    """URL http(s) → YouTube; qualquer outra coisa → arquivo local."""
    return YtDlpSource() if urlparse(ref).scheme in {"http", "https"} else LocalFileSource()
