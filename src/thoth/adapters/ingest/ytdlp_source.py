"""Ingestão a partir do YouTube via yt-dlp (ADR-005).

Usa o binário do sistema em vez da biblioteca: o yt-dlp quebra com frequência
quando o YouTube muda, e o pacman mantém o binário atualizado sem mexer no lock
de dependências do projeto.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from thoth.domain.models import AudioAsset

SAMPLE_RATE = 44_100
CHANNELS = 2
TIMEOUT_S = 900

_PADRAO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")


class IngestError(RuntimeError):
    """Falha ao obter o áudio da fonte."""


def extrair_video_id(url: str) -> str:
    """Aceita watch?v=, youtu.be/, /embed/ e /shorts/, com ou sem parâmetros."""
    partes = urlparse(url)

    if partes.hostname and partes.hostname.endswith("youtu.be"):
        candidato = partes.path.lstrip("/")
    elif match := re.match(r"^/(?:embed|shorts|v)/([^/?]+)", partes.path):
        candidato = match.group(1)
    else:
        candidato = next(iter(parse_qs(partes.query).get("v", [])), "")

    if not _PADRAO_ID.match(candidato):
        raise IngestError(f"Não consegui extrair o ID do vídeo de: {url}")
    return candidato


class YtDlpSource:
    """Implementa `AudioSource` para URLs do YouTube."""

    def fetch(self, ref: str, cache_dir: Path) -> AudioAsset:
        source_id = f"yt_{extrair_video_id(ref)}"
        destino = cache_dir / source_id
        wav = destino / "mix.wav"
        meta = destino / "meta.json"

        if wav.exists() and meta.exists():
            dados = json.loads(meta.read_text())
        else:
            destino.mkdir(parents=True, exist_ok=True)
            dados = self._baixar(ref, wav)
            meta.write_text(json.dumps(dados, ensure_ascii=False))

        return AudioAsset(
            wav=wav,
            source_id=source_id,
            title=dados["title"],
            artist=dados["artist"],
            duration_s=dados["duration_s"],
        )

    def _baixar(self, url: str, wav: Path) -> dict[str, object]:
        comando = [
            "yt-dlp",
            "--no-playlist",
            "-f", "bestaudio/best",
            "-x", "--audio-format", "wav",
            "--postprocessor-args", f"ffmpeg:-ar {SAMPLE_RATE} -ac {CHANNELS}",
            "--print-to-file", "%(title)s\t%(artist,uploader)s\t%(duration)s",
            str(wav.with_suffix(".meta.tsv")),
            "--no-simulate",
            "-o", str(wav.with_suffix("")),
            url,
        ]
        try:
            subprocess.run(comando, check=True, capture_output=True, text=True, timeout=TIMEOUT_S)
        except subprocess.CalledProcessError as erro:
            raise IngestError(
                f"yt-dlp falhou ({erro.returncode}). O YouTube muda com frequência — "
                f"tente `sudo pacman -Syu yt-dlp`.\n{erro.stderr.strip()[-500:]}"
            ) from erro
        except subprocess.TimeoutExpired as erro:
            raise IngestError(f"yt-dlp excedeu {TIMEOUT_S}s em {url}") from erro

        if not wav.exists():
            raise IngestError(f"yt-dlp terminou sem produzir {wav}")

        return self._ler_metadados(wav.with_suffix(".meta.tsv"))

    @staticmethod
    def _ler_metadados(tsv: Path) -> dict[str, object]:
        titulo, artista, duracao = "desconhecido", None, 0.0
        if tsv.exists():
            campos = tsv.read_text().strip().split("\t")
            titulo = campos[0] or titulo
            artista = campos[1] if len(campos) > 1 and campos[1] != "NA" else None
            if len(campos) > 2:
                duracao = float(campos[2] or 0)
            tsv.unlink()
        return {"title": titulo, "artist": artista, "duration_s": duracao}
