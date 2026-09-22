"""CLI do Thoth."""

from __future__ import annotations

from pathlib import Path

import typer

from thoth.adapters.ingest import resolver_fonte
from thoth.domain.models import TUNING_BASS_4, TUNING_BASS_5
from thoth.services import pipeline

app = typer.Typer(help="Áudio → partitura e tablatura, com foco em contrabaixo.")

CACHE_PADRAO = Path("cache")


@app.callback()
def main() -> None:
    """Sem o callback, o Typer colapsa o único subcomando na raiz."""


@app.command()
def fetch(
    ref: str = typer.Argument(..., help="Caminho do áudio ou URL do YouTube."),
    cache: Path = typer.Option(CACHE_PADRAO, help="Diretório de cache."),
) -> None:
    """Normaliza o áudio para WAV 44.1 kHz estéreo no cache."""
    ativo = resolver_fonte(ref).fetch(ref, cache)
    typer.echo(f"{ativo.source_id}  {ativo.duration_s:.1f}s  {ativo.wav}")


@app.command()
def transcribe(
    ref: str = typer.Argument(..., help="Caminho do áudio ou URL do YouTube."),
    out: Path = typer.Option(Path("out"), help="Onde gravar .gp5 e .musicxml."),
    bpm: int = typer.Option(120, help="Andamento: entrada, não estimativa (ADR-013)."),
    cordas: int = typer.Option(4, help="4 ou 5 cordas."),
    cache: Path = typer.Option(CACHE_PADRAO, help="Diretório de cache."),
) -> None:
    """Áudio → tablatura: separa, transcreve, posiciona e exporta."""
    afinacao = TUNING_BASS_5 if cordas == 5 else TUNING_BASS_4
    typer.echo("separando e transcrevendo — ~2,5x a duração do áudio em CPU…")
    r = pipeline.transcrever(ref, out, bpm=bpm, tuning=afinacao, cache_dir=cache)

    typer.echo(f"{r.notas} notas de baixo em {r.rotulos}")
    if r.descartadas:
        typer.echo(f"{len(r.descartadas)} descartada(s): simultâneas ou fora do braço")
    if r.avisos_de_oitava:
        alturas = ", ".join(f"{a.event.pitch}@{a.event.onset_s:.1f}s" for a in r.avisos_de_oitava)
        typer.echo(f"{len(r.avisos_de_oitava)} oitava(s) a conferir: {alturas}")
    for caminho in r.artefatos.values():
        typer.echo(str(caminho))
