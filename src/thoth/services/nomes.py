"""Título da fonte → nome de arquivo (ADR-017)."""

from __future__ import annotations

import re

from thoth.domain.models import AudioAsset

# `/` e NUL são os únicos proibidos no Linux; os demais vêm do Windows, e
# títulos de YouTube trazem `:` e `?` o bastante para valer a portabilidade.
_HOSTIS = re.compile(r'[/\\:*?"<>|\x00-\x1f]')
_LIMITE = 120


def nome_de_arquivo(asset: AudioAsset) -> str:
    """Nome legível e seguro, sem extensão; `source_id` quando nada sobra do título."""
    nome = _HOSTIS.sub("-", asset.title)
    nome = re.sub(r"\s+", " ", nome)
    nome = re.sub(r"-{2,}", "-", nome)
    nome = nome[:_LIMITE].strip(" .-")
    return nome or asset.source_id
