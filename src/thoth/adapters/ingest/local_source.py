"""Ingestão a partir de arquivo local: qualquer formato → WAV 44.1 kHz estéreo."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from thoth.arquivos import escrita_atomica
from thoth.domain.models import AudioAsset
from thoth.processos import rodar

SAMPLE_RATE = 44_100
CHANNELS = 2
_TAMANHO_ID = 16


def _hash_do_conteudo(arquivo: Path) -> str:
    """SHA-256 do conteúdo, truncado. Identidade vem do áudio, não do nome."""
    digest = hashlib.sha256()
    with arquivo.open("rb") as f:
        while bloco := f.read(1 << 20):
            digest.update(bloco)
    return digest.hexdigest()[:_TAMANHO_ID]


def _duracao_s(arquivo: Path) -> float:
    saida = rodar(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "json", str(arquivo)]
    )
    return float(json.loads(saida)["format"]["duration"])


class LocalFileSource:
    """Implementa `AudioSource` para arquivos do disco."""

    def fetch(self, ref: str, cache_dir: Path) -> AudioAsset:
        origem = Path(ref).expanduser()
        if not origem.is_file():
            raise FileNotFoundError(f"Áudio não encontrado: {origem}")

        source_id = _hash_do_conteudo(origem)
        destino = cache_dir / source_id / "mix.wav"

        if not destino.exists():
            # Atômico (ADR-026): o teste de cache é `existe?`, então WAV truncado
            # por conversão interrompida seria reaproveitado para sempre.
            with escrita_atomica(destino) as parcial:
                rodar(
                    ["ffmpeg", "-y", "-i", str(origem),
                     "-ar", str(SAMPLE_RATE), "-ac", str(CHANNELS),
                     "-loglevel", "error", str(parcial)]
                )

        return AudioAsset(
            wav=destino,
            source_id=source_id,
            title=origem.stem,
            duration_s=_duracao_s(destino),
        )
