"""CLI do Thoth."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import typer
import uvicorn
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TaskID, TextColumn, TimeElapsedColumn
from rich.text import Text

from thoth.adapters.ingest import resolver_fonte
from thoth.adapters.separation import localizar_stems
from thoth.api.app import criar_app
from thoth.domain.models import AFINACOES, AcordeImpossivel
from thoth.services import pipeline
from thoth.services.acordes import ViterbiAcordes
from thoth.services.alinhamento_audio import alinhar_ao_stem
from thoth.services.auralizacao import auralizar as _auralizar
from thoth.services.cache_notas import ler
from thoth.services.comparacao import JanelaDeNota, veredito_de_nota
from thoth.services.comparacao import comparar as _comparar
from thoth.services.fretboard import DIGITACOES, ViterbiFretAssigner
from thoth.services.nomes import nome_de_arquivo
from thoth.services.octave_check import OctaveWarning
from thoth.services.rotulos import TrechoSemBaixo
from thoth.services.tab_referencia import ler_tab
from thoth.services.tempo import BPM_MAXIMO, BPM_MINIMO
from thoth.services.tonalidade import Tonalidade, tom_de_texto

app = typer.Typer(help="Áudio → partitura e tablatura, com foco em contrabaixo.")

CACHE_PADRAO = Path("cache")

#: `highlight=False` porque nome de música não é código: o rich colore número e
#: pontuação no meio do título e o nome fica ilegível.
console = Console(highlight=False)


def _diz(texto: str, estilo: str = "") -> None:
    """Uma linha na tela, sem o rich interpretar nada dentro dela.

    `markup=False` porque título de música tem `[` (`[Official Video]`), e como
    marcação ele engoliria o resto da linha. `soft_wrap` porque caminho quebrado em
    duas linhas não se copia.
    """
    console.print(texto, style=estilo, markup=False, soft_wrap=True)


@dataclass(slots=True)
class _Etapas:
    """Desenha na tela os estágios que o pipeline anuncia — implementa `Progresso`.

    O estágio seguinte fecha o anterior; o último fecha em `encerrar`, quando
    `transcrever` devolve. É por isso que o `Protocol` tem um método só.

    Fora de terminal (log, CI, teste) o rich não anima: imprime cada estágio
    concluído como uma linha, o que é exatamente o que se quer num log.
    """

    barra: Progress
    atual: TaskID | None = None

    def inicia(self, etapa: str, detalhe: str = "") -> None:
        self.encerrar()
        self.atual = self.barra.add_task(f"{etapa} — {detalhe}" if detalhe else etapa, total=1)

    def encerrar(self) -> None:
        if self.atual is not None:
            self.barra.update(self.atual, completed=1)
            self.atual = None


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
        _diz(
            f"sem notas em cache para {ativo.title!r}: rode `thoth transcribe {ref}` antes",
            "bold red",
        )
        raise typer.Exit(code=1)

    # Mesma pasta que o `transcribe` usa (ADR-037): fora dela, este comando gravaria
    # uma segunda cópia num segundo lugar.
    nome = nome_de_arquivo(ativo)
    destino = _auralizar(ativo.wav, ler(notas_jsonl), out / nome / f"{nome}.aural.wav")
    _diz(str(destino), "green")


@app.command()
def comparar(
    tab: Path = typer.Argument(..., help="Tab .gp5 baixada à mão (ADR-007)."),
    ref: str = typer.Argument(..., help="O áudio já transcrito: caminho ou URL do YouTube."),
    faixa: int | None = typer.Option(None, help="Faixa da tab (1 = primeira), se ambígua."),
    cache: Path = typer.Option(CACHE_PADRAO, help="Diretório de cache."),
) -> None:
    """Transcrição contra tab humana: a oitava confere (ADR-041)? E a nota (ADR-042)?"""
    ativo = resolver_fonte(ref).fetch(ref, cache)
    notas_jsonl = cache / ativo.source_id / "notas.jsonl"
    if not notas_jsonl.exists():
        _diz(
            f"sem notas em cache para {ativo.title!r}: rode `thoth transcribe {ref}` antes",
            "bold red",
        )
        raise typer.Exit(code=1)
    try:
        referencia = ler_tab(tab, faixa)
        c = _comparar(referencia.notas, ler(notas_jsonl))
    except ValueError as erro:
        _diz(str(erro), "bold red")
        raise typer.Exit(code=1) from erro

    _diz(f"faixa {referencia.faixa!r}: {c.n_ref} notas na tab, {c.n_est} na transcrição")
    _diz(f"alinhamento: escala {c.escala:.4f}, deslocamento {c.deslocamento_s:+.3f} s")
    _diz(
        f"{c.casadas} pares de mesmo nome de nota ({100 * c.casadas / c.n_ref:.0f}% da tab):",
        "bold",
    )
    for rotulo, n in (
        ("mesma oitava", c.mesma_oitava),
        ("oitava acima", c.oitava_acima),
        ("oitava abaixo", c.oitava_abaixo),
    ):
        _diz(f"  {rotulo} {n} ({100 * n / c.casadas if c.casadas else 0:.1f}%)")
    # Sem o piso ao lado, o número não diz quanto dele é sorte (ADR-041).
    _diz(
        f"piso de acaso (tab deslocada ±0,25 e ±0,5 s): {c.piso_casadas} pares, "
        f"{100 * c.piso_mesma_oitava:.1f}% na mesma oitava",
        "dim",
    )

    try:
        stem = localizar_stems(cache / "stems" / ativo.source_id)["bass"]
    except FileNotFoundError:
        _diz("sem stem do baixo em cache: nota errada não medida (ADR-042)", "dim")
        return
    estimativa = ler(notas_jsonl)
    _relatar_nota_errada(veredito_de_nota(alinhar_ao_stem(referencia.notas, stem), estimativa))


def _relatar_nota_errada(janelas: list[JanelaDeNota]) -> None:
    """Janela abaixo do piso + margem não entra na conta: ali alinhamento falho e
    transcrição muito errada dão o mesmo número (ADR-042)."""
    _diz("nota errada, com a tab alinhada ao stem (ADR-042), por janela:", "bold")
    for j in janelas:
        numeros = (
            f"certa {100 * j.fracao_certa:.0f}% contra piso {100 * j.piso_certa:.0f}%, "
            f"oitava {100 * j.oitava / j.com_ataque:.0f}%, "
            f"errada {100 * j.errada / j.com_ataque:.0f}% de {j.com_ataque}; "
            f"sem ataque {j.sem}"
        )
        if j.conclusiva:
            _diz(f"  {j.inicio_s:5.0f} s  {numeros}")
        else:
            _diz(f"  {j.inicio_s:5.0f} s  inconclusivo — {numeros}", "dim")
    conclusivas = [j for j in janelas if j.conclusiva]
    total = sum(j.com_ataque for j in conclusivas)
    plural = "janela conclusiva" if len(janelas) == 1 else "janelas conclusivas"
    if not total:
        _diz(f"0 de {len(janelas)} {plural}: nota errada não medida")
        return
    certa, oitava, errada = (
        sum(getattr(j, k) for j in conclusivas) for k in ("certa", "oitava", "errada")
    )
    _diz(
        f"{len(conclusivas)} de {len(janelas)} {plural}, {total} notas: "
        f"certa {100 * certa / total:.1f}%, oitava {100 * oitava / total:.1f}%, "
        f"errada {100 * errada / total:.1f}% — limite inferior: só onde o Thoth "
        "concorda com a tab o bastante para confirmar o alinhamento",
        "bold",
    )


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
    instrumento: str = typer.Option(
        "baixo", help=f"Parte a transcrever: {', '.join(pipeline.INSTRUMENTOS)} (ADR-044)."
    ),
    afinacao: str | None = typer.Option(
        None, help=f"Afinação do baixo, por nome: {', '.join(AFINACOES)}. Padrão: 4."
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

    _escolher(pipeline.INSTRUMENTOS, instrumento, "--instrumento")
    # As afinações do catálogo são de baixo; a guitarra usa a do perfil (ADR-044).
    if instrumento != "baixo" and afinacao is not None:
        raise typer.BadParameter(
            f"só vale para o baixo; {instrumento} usa a afinação padrão",
            param_hint="--afinacao",
        )
    cordas = _escolher(AFINACOES, afinacao or "4", "--afinacao") if instrumento == "baixo" else None
    custos = _escolher(DIGITACOES, digitacao, "--digitacao")
    # O tempo por estágio é o que faltava: a separação e a transcrição levam
    # minutos cada, e uma frase solta antes da chamada não dizia em qual delas se
    # estava — nem se algo havia travado (ADR-037).
    with Progress(
        SpinnerColumn(finished_text=Text("✓", style="bold green")),
        TextColumn("{task.description}", style="cyan", markup=False),
        TimeElapsedColumn(),
        console=console,
    ) as barra:
        etapas = _Etapas(barra)
        r = pipeline.transcrever(
            ref,
            out,
            bpm=bpm,
            tuning=cordas,
            instrumento=instrumento,
            cache_dir=cache,
            assigner=ViterbiFretAssigner(custos=custos),
            atribuidor_de_acordes=ViterbiAcordes(custos=custos),
            progresso=etapas,
        )
        etapas.encerrar()

    if r.andamento is not None:
        recado = (
            f"andamento ESTIMADO: {r.bpm:.2f} BPM"
            if r.andamento.confiavel
            else f"andamento ESTIMADO: {r.bpm:.2f} BPM — pouca confiança, o segundo "
            f"método leu {r.andamento.conferencia}"
        )
        _diz(recado, "yellow")
        if r.desdobrado:
            _diz(
                f"a dobra para a faixa musical foi desfeita: as notas colidiam na grade "
                f"de {r.andamento.bpm} BPM (ADR-024)",
                "yellow",
            )
        _diz("confira ouvindo; se soar errado, reexporte com --bpm", "yellow")

    if r.tonalidade:
        _diz(_tom(r.tonalidade))
    _diz(f"{r.notas} notas de {r.instrumento} em {r.rotulos}", "bold")
    # Três causas, três linhas: somadas, não se saberia se o erro é do modelo, que
    # trocou uma guitarra pela outra, ou do stem, que trouxe outro instrumento.
    if r.erro_de_rotulo:
        _diz(f"fora da parte por erro de rótulo: {_contagem(r.erro_de_rotulo)}", "yellow")
    if r.contaminacao:
        _diz(f"fora da parte por contaminação do stem: {_contagem(r.contaminacao)}", "yellow")
    if r.ataques_descartados:
        contagem = {motivo: len(a) for motivo, a in r.ataques_descartados.items()}
        _diz(f"ataque(s) fora da partitura: {_contagem(contagem)}", "yellow")
    if r.acordes_impossiveis:
        _diz(f"{len(r.acordes_impossiveis)} acorde(s) impossível(is):", "yellow")
        for acorde in r.acordes_impossiveis:
            _diz(f"  {_acorde_impossivel(acorde)}", "yellow")
    if r.descartadas:
        _diz(f"{len(r.descartadas)} descartada(s): simultâneas ou fora do braço", "yellow")
    for trecho in r.trechos_sem_baixo:
        _diz(_aviso_sem_baixo(trecho), "yellow")
    if r.falha_na_auralizacao:
        _diz(f"sem auralização: {r.falha_na_auralizacao}", "yellow")
    if r.avisos_de_oitava:
        _diz(f"{len(r.avisos_de_oitava)} oitava(s) a conferir:", "yellow")
        for a in r.avisos_de_oitava:
            _diz(f"  {_aviso_de_oitava(a)}", "yellow")
    _artefatos(r.artefatos)


def _artefatos(artefatos: Mapping[str, Path]) -> None:
    """A pasta uma vez, os arquivos embaixo — eles compartilham o nome (ADR-037).

    Repetir o caminho inteiro em seis linhas quase idênticas obrigava a comparar
    caractere por caractere para achar a diferença.
    """
    pastas = {c.parent for c in artefatos.values()}
    for pasta in sorted(pastas):
        _diz(str(pasta), "bold green")
        for caminho in sorted(c for c in artefatos.values() if c.parent == pasta):
            _diz(f"  {caminho.name}", "green")


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


def _minutos(segundos: float) -> str:
    minutos, resto = divmod(int(segundos), 60)
    return f"{minutos}:{resto:02d}"


def _contagem(rotulos: Mapping[str, int]) -> str:
    return ", ".join(f"{n} {r}" for r, n in sorted(rotulos.items()))


def _acorde_impossivel(acorde: AcordeImpossivel) -> str:
    """Onde ouvir e o que o modelo ouviu; o motivo diz por que não cabe."""
    inicio = min(n.onset_s for n in acorde.notas)
    alturas = " ".join(str(n.pitch) for n in sorted(acorde.notas, key=lambda n: n.pitch))
    return f"{_minutos(inicio)} {alturas}: {acorde.motivo}"


def _aviso_sem_baixo(trecho: TrechoSemBaixo) -> str:
    """Onde ouvir: se ali não há baixo, o que entrou na partitura é vazamento."""
    rotulos = ", ".join(f"{n} {r}" for r, n in trecho.rotulos.items())
    return (
        f"sem baixo em {_minutos(trecho.inicio_s)} a {_minutos(trecho.fim_s)}: "
        f"readmitidas {rotulos} como baixo — se ali não há baixo, é vazamento"
    )


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
