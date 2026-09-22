"""CLI do Thoth."""

from __future__ import annotations

from pathlib import Path

import typer

from thoth.adapters.ingest.local_source import LocalFileSource

app = typer.Typer(help="Áudio → partitura e tablatura, com foco em contrabaixo.")

CACHE_PADRAO = Path("cache")


@app.callback()
def main() -> None:
    """Sem o callback, o Typer colapsa o único subcomando na raiz."""


@app.command()
def fetch(
    arquivo: str = typer.Argument(..., help="Caminho do áudio de entrada."),
    cache: Path = typer.Option(CACHE_PADRAO, help="Diretório de cache."),
) -> None:
    """Normaliza o áudio para WAV 44.1 kHz estéreo no cache."""
    ativo = LocalFileSource().fetch(arquivo, cache)
    typer.echo(f"{ativo.source_id}  {ativo.duration_s:.1f}s  {ativo.wav}")
