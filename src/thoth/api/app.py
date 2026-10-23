"""API de jobs: o pipeline embrulhado em HTTP, para o alphaTab consumir.

Jobs vivem **em memória**, no processo. Não é descuido: é uso pessoal, uma música
por vez, e reiniciar o servidor perde o histórico — mas não perde nada caro, já
que os artefatos ficam em disco nomeados pelo título (ADR-017) e um job repetido
reaproveita o cache de ingestão e de separação.

A UI é servida daqui, com o alphaTab **local** (ADR-006): estudar não pode
depender de CDN nem de internet. O `web/vendor/` não é versionado — se faltar, a
raiz responde dizendo qual comando o traz, em vez de entregar página quebrada.

Falha do pipeline vira **estado do job**, não 500: "nenhuma nota de baixo" é
diagnóstico para quem pediu, não defeito do servidor.
"""

from __future__ import annotations

import hashlib
import math
import mimetypes
import os
import queue
import threading
import uuid
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator, model_validator
from starlette.concurrency import run_in_threadpool

from thoth.adapters.ingest.ytdlp_source import IngestError, extrair_video_id
from thoth.adapters.playback.mpris import LeitorMpris
from thoth.arquivos import SUFIXO
from thoth.domain.models import AFINACOES, AcordeImpossivel
from thoth.domain.ports import AtribuidorDeAcordes, FretAssigner
from thoth.domain.reproducao import LeitorDeReproducao
from thoth.services import pipeline
from thoth.services.acordes import ViterbiAcordes
from thoth.services.fretboard import DIGITACOES, ViterbiFretAssigner
from thoth.services.octave_check import OctaveWarning
from thoth.services.pipeline import Resultado
from thoth.services.tempo import BPM_MAXIMO, BPM_MINIMO
from thoth.services.tonalidade import Tonalidade, tom_de_texto

#: O maior áudio que a página sobe. Dez minutos de WAV estéreo a 96 kHz/24 bits cabem.
TETO_DE_UPLOAD = 512 * 2**20

#: Os nomes desta máquina. `serve --host` acrescenta o que você escolher.
HOSTS_LOCAIS = ("127.0.0.1", "localhost")

#: Raiz do `web/`, servida como está — a UI não passa por build.
WEB_PADRAO = Path(__file__).resolve().parents[3] / "web"

# O `mimetypes` do Python não conhece woff2, e a tabela do SO tampouco, em geral.
# Sem isto a fonte musical sai como `application/octet-stream`.
mimetypes.add_type("font/woff2", ".woff2")
mimetypes.add_type("font/woff", ".woff")


class Executor(Protocol):
    """O pipeline, injetável — rodar o real num teste custa minutos de CPU."""

    def __call__(
        self,
        ref: str,
        out_dir: Path,
        *,
        bpm: int | None,
        tuning: tuple[int, ...] | None,
        cache_dir: Path,
        tom: str | None,
        assigner: FretAssigner,
        instrumento: str,
        atribuidor_de_acordes: AtribuidorDeAcordes,
    ) -> Resultado: ...


#: O que sobe para transcrever. Partitura (GP5, MusicXML) abre no navegador (ADR-051).
EXTENSOES_DE_AUDIO = frozenset({".mp3", ".wav"})


class Pedido(BaseModel):
    """`bpm` vazio faz o Thoth estimar do áudio (ADR-019); os outros dois são nomes.

    Afinação e digitação vêm por **nome**, não por contagem de cordas: drop D tem
    quatro, como a padrão, e nenhuma corda afinada igual (ADR-028).

    `instrumento` escolhe o perfil (ADR-044). A afinação da guitarra vem do perfil:
    `afinacao` só vale para o baixo, e vazia nele é a de quatro cordas.
    """

    ref: str = Field(..., description="Caminho do áudio ou URL do YouTube.")
    bpm: int | None = Field(None, ge=BPM_MINIMO, le=BPM_MAXIMO)
    tom: str | None = Field(
        None, description="Tom, p.ex. 'Bb maior'. Vazio: estimado das notas (ADR-031)."
    )
    instrumento: str = Field("baixo", description=f"Uma de: {', '.join(pipeline.INSTRUMENTOS)}.")
    afinacao: str | None = Field(
        None, description=f"Só para o baixo; uma de: {', '.join(AFINACOES)}. Vazia: '4'."
    )
    digitacao: str = Field("iniciante", description=f"Uma de: {', '.join(DIGITACOES)}.")

    @field_validator("ref")
    @classmethod
    def _ref_de_audio(cls, valor: str) -> str:
        # O `ref` decide o que o servidor lê do disco e de onde o yt-dlp baixa: uma URL
        # tem de ser do YouTube, e um caminho, de áudio. A CLI segue aceitando qualquer
        # coisa que o ffmpeg leia; quem a chama é você, não uma página.
        if urlparse(valor).scheme in {"http", "https"}:
            try:
                extrair_video_id(valor)
            except IngestError as erro:
                raise ValueError(str(erro)) from erro
        elif Path(valor).suffix.lower() not in EXTENSOES_DE_AUDIO:
            raise ValueError(
                f"{valor!r} não é áudio; aceitos: {', '.join(sorted(EXTENSOES_DE_AUDIO))}"
            )
        return valor

    @field_validator("tom")
    @classmethod
    def _tom_legivel(cls, valor: str | None) -> str | None:
        if valor:
            tom_de_texto(valor)  # levanta ValueError, que o Pydantic vira 422
        return valor

    @field_validator("instrumento")
    @classmethod
    def _instrumento_conhecido(cls, valor: str) -> str:
        if valor not in pipeline.INSTRUMENTOS:
            raise ValueError(f"{valor!r} não existe; há {', '.join(pipeline.INSTRUMENTOS)}")
        return valor

    @field_validator("afinacao")
    @classmethod
    def _afinacao_conhecida(cls, valor: str | None) -> str | None:
        if valor is not None and valor not in AFINACOES:
            raise ValueError(f"{valor!r} não existe; há {', '.join(AFINACOES)}")
        return valor

    @model_validator(mode="after")
    def _afinacao_so_no_baixo(self) -> Pedido:
        if self.afinacao is not None and self.instrumento != "baixo":
            raise ValueError(f"afinacao só vale para o baixo; {self.instrumento} usa a do perfil")
        return self

    @field_validator("digitacao")
    @classmethod
    def _digitacao_conhecida(cls, valor: str) -> str:
        if valor not in DIGITACOES:
            raise ValueError(f"{valor!r} não existe; há {', '.join(DIGITACOES)}")
        return valor


def _afinacao(pedido: Pedido) -> tuple[int, ...] | None:
    """Fora do baixo: `None`, e o pipeline usa a do perfil (a bateria não tem nenhuma)."""
    if pedido.instrumento != "baixo":
        return None
    return AFINACOES[pedido.afinacao or "4"]


@dataclass(slots=True)
class Job:
    id: str
    pedido: Pedido
    status: str = "na fila"  # na fila | rodando | pronto | erro
    resultado: Resultado | None = None
    erro: str | None = None


#: Quantos jobs o histórico guarda. Não há paginação nem banco: o teto é o que
#: impede o processo de longa vida de crescer para sempre (ADR-027).
LIMITE_DE_JOBS = 50
#: Estados em que o job já não tem nada acontecendo — os únicos descartáveis.
TERMINADOS = frozenset({"pronto", "erro"})


def descartar_antigos(jobs: dict[str, Job], limite: int = LIMITE_DE_JOBS) -> None:
    """Joga fora os jobs concluídos mais antigos até caber no limite.

    Job que ainda está na fila ou rodando **nunca** é descartado, mesmo que seja o
    mais antigo: quem o pediu ainda espera minutos de CPU por ele. Só sobrar coisa
    inacabada é o caso em que o histórico passa do teto de propósito.
    """
    for ident, job in list(jobs.items()):  # dict preserva a ordem de inserção
        if len(jobs) <= limite:
            return
        if job.status in TERMINADOS:
            del jobs[ident]


def _finito(razao: float) -> float | None:
    """`inf` vira `null`: `Infinity` é JSON inválido e o `JSON.parse` da página
    recusa o corpo inteiro por causa dele (ADR-030)."""
    return round(razao, 3) if math.isfinite(razao) else None


def _oitava(aviso: OctaveWarning) -> dict[str, Any]:
    """Altura e instante não dizem o que conferir — a alternativa ranqueada diz."""
    return {
        "pitch": aviso.event.pitch,
        "onset_s": round(aviso.event.onset_s, 2),
        "sugestao": aviso.suggested_pitch,
        "razao": _finito(aviso.fundamental_ratio),
        "razao_sugerida": _finito(aviso.suggested_ratio),
    }


def _tom(tonalidade: Tonalidade | None) -> dict[str, Any] | None:
    """`margem` nula é tom informado — não passou por ranqueamento nenhum."""
    if tonalidade is None:
        return None
    return {
        "nome": tonalidade.nome,
        "armadura": tonalidade.armadura,
        "margem": round(tonalidade.margem, 3) if tonalidade.margem is not None else None,
    }


def _acorde_impossivel(acorde: AcordeImpossivel) -> dict[str, Any]:
    return {
        "onset_s": round(min(n.onset_s for n in acorde.notas), 2),
        "alturas": sorted(n.pitch for n in acorde.notas),
        "motivo": acorde.motivo,
    }


def _resumo(job: Job) -> dict[str, Any]:
    r = job.resultado
    return {
        "id": job.id,
        "status": job.status,
        "ref": job.pedido.ref,
        "instrumento": job.pedido.instrumento,
        "bpm": r.bpm if r else job.pedido.bpm,
        "erro": job.erro,
        "titulo": r.asset.title if r else None,
        "notas": r.notas if r else None,
        "rotulos": r.rotulos if r else None,
        "descartadas": len(r.descartadas) if r else None,
        "erro_de_rotulo": r.erro_de_rotulo if r else None,
        "contaminacao": r.contaminacao if r else None,
        "ataques_descartados": {m: len(a) for m, a in r.ataques_descartados.items()} if r else None,
        "acordes_impossiveis": [_acorde_impossivel(a) for a in r.acordes_impossiveis]
        if r
        else None,
        "fora_do_braco": len(r.fora_do_braco) if r else None,
        "trechos_sem_baixo": [asdict(t) for t in r.trechos_sem_baixo] if r else None,
        "avisos_de_oitava": [_oitava(a) for a in r.avisos_de_oitava] if r else None,
        "tom": _tom(r.tonalidade) if r else None,
        "formatos": sorted(r.artefatos) if r else [],
        "partes_ausentes": r.partes_ausentes if r else [],
        "bpm_estimado": bool(r and r.andamento),
        "bpm_confiavel": bool(r and r.andamento and r.andamento.confiavel),
    }


@dataclass(slots=True)
class _Estado:
    out_dir: Path
    cache_dir: Path
    executar: Executor
    jobs: dict[str, Job] = field(default_factory=dict)
    #: Os jobs esperando o trabalhador. Um por vez (ADR-027): dois pipelines
    #: simultâneos escrevem no mesmo diretório encenado do cache e no mesmo artefato
    #: nomeado pelo título.
    fila: queue.Queue[Job] = field(default_factory=queue.Queue)
    #: Guarda `jobs`: as requisições chegam por threads do pool e o descarte dos
    #: antigos percorre o dicionário enquanto outra requisição o altera.
    trava: threading.Lock = field(default_factory=threading.Lock)


def criar_app(
    *,
    out_dir: Path = Path("out"),
    cache_dir: Path = Path("cache"),
    executar: Executor | None = None,
    web_dir: Path = WEB_PADRAO,
    leitor_reproducao: LeitorDeReproducao | None = None,
    teto_de_upload: int = TETO_DE_UPLOAD,
    hosts: Sequence[str] = (),
) -> FastAPI:
    estado = _Estado(out_dir, cache_dir, executar or pipeline.transcrever)
    leitor = leitor_reproducao or LeitorMpris()
    app = FastAPI(title="Thoth", summary="Áudio → tablatura de contrabaixo e guitarra.")
    # DNS rebinding: uma página de fora que resolve o próprio domínio para 127.0.0.1
    # fala com o servidor como se fosse daqui. O `Host` dela denuncia, e é recusado.
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=[*HOSTS_LOCAIS, *hosts])

    def _rodar(job: Job) -> None:
        job.status = "rodando"
        custos = DIGITACOES[job.pedido.digitacao]
        try:
            job.resultado = estado.executar(
                job.pedido.ref,
                estado.out_dir,
                bpm=job.pedido.bpm,
                tuning=_afinacao(job.pedido),
                cache_dir=estado.cache_dir,
                tom=job.pedido.tom,
                assigner=ViterbiFretAssigner(custos=custos),
                instrumento=job.pedido.instrumento,
                atribuidor_de_acordes=ViterbiAcordes(custos=custos),
            )
            job.status = "pronto"
        except Exception as erro:  # vira estado do job, não 500 do servidor
            job.status, job.erro = "erro", str(erro)

    def _trabalhar() -> None:
        while True:
            _rodar(estado.fila.get())

    # Um trabalhador só, numa fila (ADR-027): os jobs rodam um por vez e na ordem em
    # que chegaram, e a requisição volta na hora em vez de segurar uma thread do pool.
    threading.Thread(target=_trabalhar, name="thoth-jobs", daemon=True).start()

    def _buscar(ident: str) -> Job:
        with estado.trava:
            job = estado.jobs.get(ident)
        if job is None:
            raise HTTPException(404, f"job {ident} não existe")
        return job

    @app.post("/jobs", status_code=202)
    def criar(pedido: Pedido) -> dict[str, Any]:
        job = Job(id=uuid.uuid4().hex[:12], pedido=pedido)
        with estado.trava:
            estado.jobs[job.id] = job
            descartar_antigos(estado.jobs)
        estado.fila.put(job)
        return _resumo(job)

    @app.post("/uploads", status_code=201)
    async def enviar(nome: str, requisicao: Request) -> dict[str, str]:
        """Corpo cru, não `multipart`: um arquivo só, sem dependência nova (ADR-051).

        O diretório é o hash do conteúdo: reenviar o mesmo áudio cai no mesmo lugar e
        reaproveita o cache. O nome vira o título. O hash vai inteiro, e não truncado
        como o `source_id`: uma pasta de 16 hex com `mix.wav` dentro é o que o
        `LocalFileSource` reconhece como cache, e trocaria o título pelo id.
        """
        nome = Path(nome).name  # o caminho do cliente não decide onde se grava
        if Path(nome).suffix.lower() not in EXTENSOES_DE_AUDIO:
            raise HTTPException(
                422, f"{nome!r} não é áudio; aceitos: {', '.join(sorted(EXTENSOES_DE_AUDIO))}"
            )
        # Em blocos, e não `body()`: o arquivo inteiro na memória antes de qualquer
        # verificação. O hash sai junto, e o disco é escrito fora do laço de eventos.
        uploads = estado.cache_dir / "uploads"
        uploads.mkdir(parents=True, exist_ok=True)
        parcial = uploads / f"{uuid.uuid4().hex}{SUFIXO}"
        resumo, tamanho = hashlib.sha256(), 0
        try:
            with parcial.open("wb") as arquivo:
                async for bloco in requisicao.stream():
                    tamanho += len(bloco)
                    if tamanho > teto_de_upload:
                        raise HTTPException(413, f"{nome!r} passa de {teto_de_upload // 2**20} MiB")
                    resumo.update(bloco)
                    await run_in_threadpool(arquivo.write, bloco)
            if not tamanho:
                raise HTTPException(422, f"{nome!r} chegou vazio")
            destino = uploads / resumo.hexdigest() / nome
            if not destino.exists():
                destino.parent.mkdir(exist_ok=True)
                os.replace(parcial, destino)
        finally:
            parcial.unlink(missing_ok=True)
        return {"ref": str(destino)}

    @app.get("/jobs")
    def listar() -> list[dict[str, Any]]:
        with estado.trava:
            jobs = list(estado.jobs.values())
        return [_resumo(j) for j in jobs]

    @app.get("/playback/players")
    async def players_de_reproducao() -> list[dict[str, Any]]:
        """Estado de players MPRIS locais; sem player/barramento, a lista é vazia."""
        return [
            {
                "nome": player.nome,
                "identidade": player.identidade,
                "estado": player.estado,
                "posicao_s": player.posicao_s,
                "duracao_s": player.duracao_s,
                "titulo": player.titulo,
                "artista": player.artista,
                "album": player.album,
            }
            for player in await leitor.listar()
        ]

    @app.get("/jobs/{ident}")
    def consultar(ident: str) -> dict[str, Any]:
        return _resumo(_buscar(ident))

    @app.get("/jobs/{ident}/artifacts/{formato}")
    def artefato(ident: str, formato: str) -> FileResponse:
        job = _buscar(ident)
        if job.resultado is None:
            raise HTTPException(409, f"job {ident} está {job.status}: {job.erro or 'aguarde'}")
        if (caminho := job.resultado.artefatos.get(formato)) is None:
            disponiveis = sorted(job.resultado.artefatos)
            raise HTTPException(404, f"formato {formato!r} não existe; há {disponiveis}")
        return FileResponse(caminho, filename=caminho.name)

    if (web_dir / "vendor" / "alphatab" / "alphaTab.min.mjs").exists():
        app.mount("/", StaticFiles(directory=web_dir, html=True), name="web")
    else:

        @app.get("/", response_class=PlainTextResponse)
        def sem_alphatab() -> PlainTextResponse:
            return PlainTextResponse(
                "alphaTab ausente — a UI é servida localmente, sem CDN (ADR-006).\n"
                "Traga-o com: uv run python scripts/vendor_alphatab.py",
                status_code=503,
            )

    return app
