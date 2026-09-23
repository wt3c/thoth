"""CLI do Thoth."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import typer
import uvicorn

from thoth.adapters.ingest import resolver_fonte
from thoth.api.app import criar_app
from thoth.domain.models import AFINACOES
from thoth.services import pipeline
from thoth.services.auralizacao import auralizar as _auralizar
from thoth.services.cache_notas import ler
from thoth.services.fretboard import DIGITACOES, ViterbiFretAssigner
from thoth.services.nomes import nome_de_arquivo
from thoth.services.octave_check import OctaveWarning
from thoth.services.tempo import BPM_MAXIMO, BPM_MINIMO
from thoth.services.tonalidade import Tonalidade, tom_de_texto

app = typer.Typer(help="Áudio → partitura e tablatura, com foco em contrabaixo.")

CACHE_PADRAO = Path("cache")

def _escolher[T](catalogo: Mapping[str, T], nome: str, opcao: str) -> T:
    """Nome fora do catálogo é erro de uso, não sinônimo do default (ADR-025).

    Recusar sem listar o que existe não ensina nada, e o catálogo é curto o
    bastante para caber na mensagem.
    """
    if nome not in catalogo:
        raise typer.BadParameter(
            f"{nome!r} não existe; há {', '.join(catalogo)}", param_hint=opcao
        )
    return catalogo[nome]


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
        None,
        min=BPM_MINIMO,
        max=BPM_MAXIMO,
        help="Andamento. Sem ele, o Thoth estima do áudio e avisa (ADR-019).",
    ),
    tom: str = typer.Option(
        "", help="Tom, p.ex. 'Bb maior' ou 'f menor'. Vazio: estimado das notas (ADR-031)."
    ),
    afinacao: str = typer.Option(
        "4", help=f"Afinação, por nome: {', '.join(AFINACOES)}."
    ),
    digitacao: str = typer.Option(
        "iniciante", help=f"Perfil de digitação: {', '.join(DIGITACOES)} (ADR-006)."
    ),
    cache: Path = typer.Option(CACHE_PADRAO, help="Diretório de cache."),
) -> None:
    """Áudio → tablatura: separa, transcreve, posiciona e exporta."""
    # Recusar aqui, e não depois dos minutos de CPU: a mensagem do `ValueError`
    # já diz o formato aceito.
    if tom:
        try:
            tom_de_texto(tom)
        except ValueError as erro:
            raise typer.BadParameter(str(erro), param_hint="--tom") from erro

    cordas = _escolher(AFINACOES, afinacao, "--afinacao")
    custos = _escolher(DIGITACOES, digitacao, "--digitacao")
    typer.echo("separando e transcrevendo — ~2,5x a duração do áudio em CPU…")
    r = pipeline.transcrever(
        ref,
        out,
        bpm=bpm,
        tuning=cordas,
        cache_dir=cache,
        assigner=ViterbiFretAssigner(custos=custos),
    )

    if r.andamento is not None:
        recado = (
            f"andamento ESTIMADO: {r.bpm:.2f} BPM"
            if r.andamento.confiavel
            else f"andamento ESTIMADO: {r.bpm:.2f} BPM — pouca confiança, o segundo "
            f"método leu {r.andamento.conferencia}"
        )
        typer.secho(recado, fg=typer.colors.YELLOW)
        if r.desdobrado:
            typer.secho(
                f"a dobra para a faixa musical foi desfeita: as notas colidiam na grade "
                f"de {r.andamento.bpm} BPM (ADR-024)",
                fg=typer.colors.YELLOW,
            )
        typer.secho("confira ouvindo; se soar errado, reexporte com --bpm", fg=typer.colors.YELLOW)

    if r.tonalidade:
        typer.echo(_tom(r.tonalidade))
    typer.echo(f"{r.notas} notas de baixo em {r.rotulos}")
    if r.descartadas:
        typer.echo(f"{len(r.descartadas)} descartada(s): simultâneas ou fora do braço")
    if r.avisos_de_oitava:
        typer.echo(f"{len(r.avisos_de_oitava)} oitava(s) a conferir:")
        for a in r.avisos_de_oitava:
            typer.echo(f"  {_aviso_de_oitava(a)}")
    for caminho in r.artefatos.values():
        typer.echo(str(caminho))


def _tom(tonalidade: Tonalidade) -> str:
    """A grafia só muda com margem folgada — dizer qual foi é o que torna isso auditável."""
    if tonalidade.margem is None:
        return f"tom informado: {tonalidade.nome} — grafia com {_grafia(tonalidade)}"
    origem = f"tom ESTIMADO: {tonalidade.nome} (margem {tonalidade.margem:.2f})"
    if tonalidade.confiavel:
        return f"{origem} — grafia com {_grafia(tonalidade)}"
    return f"{origem} — margem curta, grafia com sustenidos e sem armadura"


def _grafia(tonalidade: Tonalidade) -> str:
    return "bemóis" if tonalidade.bemois else "sustenidos"


def _aviso_de_oitava(aviso: OctaveWarning) -> str:
    """A altura sozinha não diz o que conferir; a alternativa ranqueada diz (ADR-030)."""
    alternativa = (
        f"{aviso.suggested_pitch} (razão {aviso.suggested_ratio:.2f} contra "
        f"{aviso.fundamental_ratio:.2f})"
        if aviso.suggested_pitch is not None
        else f"nenhuma oitava explica melhor (razão {aviso.fundamental_ratio:.2f})"
    )
    return f"{aviso.event.pitch}@{aviso.event.onset_s:.1f}s → {alternativa}"


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
