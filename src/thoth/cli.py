"""CLI do Thoth."""

from __future__ import annotations

from pathlib import Path

import typer
import uvicorn

from thoth.adapters.ingest import resolver_fonte
from thoth.api.app import criar_app
from thoth.domain.models import TUNING_BASS_4, TUNING_BASS_5
from thoth.services import pipeline
from thoth.services.auralizacao import auralizar as _auralizar
from thoth.services.cache_notas import ler
from thoth.services.nomes import nome_de_arquivo

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
def auralizar(
    ref: str = typer.Argument(..., help="Caminho do áudio ou URL do YouTube."),
    out: Path = typer.Option(Path("out"), help="Onde gravar o WAV estéreo."),
    cache: Path = typer.Option(CACHE_PADRAO, help="Diretório de cache."),
) -> None:
    """Original à esquerda, transcrição à direita — ouvir se descola."""
    ativo = resolver_fonte(ref).fetch(ref, cache)
    notas_jsonl = cache / ativo.source_id / "notas.jsonl"
    if not notas_jsonl.exists():
        typer.secho(
            f"sem notas em cache para {ativo.title!r}: rode `thoth transcribe {ref}` antes",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

    destino = _auralizar(ativo.wav, ler(notas_jsonl), out / f"{nome_de_arquivo(ativo)}.aural.wav")
    typer.echo(destino)


@app.command()
def transcribe(
    ref: str = typer.Argument(..., help="Caminho do áudio ou URL do YouTube."),
    out: Path = typer.Option(Path("out"), help="Onde gravar .gp5 e .musicxml."),
    bpm: int | None = typer.Option(
        None, help="Andamento. Sem ele, o Thoth estima do áudio e avisa (ADR-019)."
    ),
    cordas: int = typer.Option(4, help="4 ou 5 cordas."),
    cache: Path = typer.Option(CACHE_PADRAO, help="Diretório de cache."),
) -> None:
    """Áudio → tablatura: separa, transcreve, posiciona e exporta."""
    afinacao = TUNING_BASS_5 if cordas == 5 else TUNING_BASS_4
    typer.echo("separando e transcrevendo — ~2,5x a duração do áudio em CPU…")
    r = pipeline.transcrever(ref, out, bpm=bpm, tuning=afinacao, cache_dir=cache)

    if r.andamento is not None:
        recado = (
            f"andamento ESTIMADO: {r.bpm} BPM"
            if r.andamento.confiavel
            else f"andamento ESTIMADO: {r.bpm} BPM — pouca confiança, o segundo "
            f"método leu {r.andamento.conferencia}"
        )
        typer.secho(recado, fg=typer.colors.YELLOW)
        typer.secho("confira ouvindo; se soar errado, reexporte com --bpm", fg=typer.colors.YELLOW)

    typer.echo(f"{r.notas} notas de baixo em {r.rotulos}")
    if r.descartadas:
        typer.echo(f"{len(r.descartadas)} descartada(s): simultâneas ou fora do braço")
    if r.avisos_de_oitava:
        alturas = ", ".join(f"{a.event.pitch}@{a.event.onset_s:.1f}s" for a in r.avisos_de_oitava)
        typer.echo(f"{len(r.avisos_de_oitava)} oitava(s) a conferir: {alturas}")
    for caminho in r.artefatos.values():
        typer.echo(str(caminho))


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", help="Local por padrão: nada sai da máquina."),
    port: int = typer.Option(8000),
    out: Path = typer.Option(Path("out"), help="Onde ficam os artefatos."),
    cache: Path = typer.Option(CACHE_PADRAO, help="Diretório de cache."),
) -> None:
    """Sobe a API e a página de estudo (alphaTab local, sem CDN)."""
    typer.echo(f"http://{host}:{port}")
    uvicorn.run(criar_app(out_dir=out, cache_dir=cache), host=host, port=port)
