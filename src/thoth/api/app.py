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

import math
import mimetypes
import threading
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Protocol

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from thoth.domain.models import AFINACOES
from thoth.domain.ports import FretAssigner
from thoth.services import pipeline
from thoth.services.fretboard import DIGITACOES, ViterbiFretAssigner
from thoth.services.octave_check import OctaveWarning
from thoth.services.pipeline import Resultado
from thoth.services.tempo import BPM_MAXIMO, BPM_MINIMO
from thoth.services.tonalidade import Tonalidade, tom_de_texto

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
        tuning: tuple[int, ...],
        cache_dir: Path,
        tom: str | None,
        assigner: FretAssigner,
    ) -> Resultado: ...


class Pedido(BaseModel):
    """`bpm` vazio faz o Thoth estimar do áudio (ADR-019); os outros dois são nomes.

    Afinação e digitação vêm por **nome**, não por contagem de cordas: drop D tem
    quatro, como a padrão, e nenhuma corda afinada igual (ADR-028).
    """

    ref: str = Field(..., description="Caminho do áudio ou URL do YouTube.")
    bpm: int | None = Field(None, ge=BPM_MINIMO, le=BPM_MAXIMO)
    tom: str | None = Field(
        None, description="Tom, p.ex. 'Bb maior'. Vazio: estimado das notas (ADR-031)."
    )
    afinacao: str = Field("4", description=f"Uma de: {', '.join(AFINACOES)}.")
    digitacao: str = Field("iniciante", description=f"Uma de: {', '.join(DIGITACOES)}.")

    @field_validator("tom")
    @classmethod
    def _tom_legivel(cls, valor: str | None) -> str | None:
        if valor:
            tom_de_texto(valor)  # levanta ValueError, que o Pydantic vira 422
        return valor

    @field_validator("afinacao")
    @classmethod
    def _afinacao_conhecida(cls, valor: str) -> str:
        if valor not in AFINACOES:
            raise ValueError(f"{valor!r} não existe; há {', '.join(AFINACOES)}")
        return valor

    @field_validator("digitacao")
    @classmethod
    def _digitacao_conhecida(cls, valor: str) -> str:
        if valor not in DIGITACOES:
            raise ValueError(f"{valor!r} não existe; há {', '.join(DIGITACOES)}")
        return valor


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


def _resumo(job: Job) -> dict[str, Any]:
    r = job.resultado
    return {
        "id": job.id,
        "status": job.status,
        "ref": job.pedido.ref,
        "bpm": r.bpm if r else job.pedido.bpm,
        "erro": job.erro,
        "titulo": r.asset.title if r else None,
        "notas": r.notas if r else None,
        "rotulos": r.rotulos if r else None,
        "descartadas": len(r.descartadas) if r else None,
        "fora_do_braco": len(r.fora_do_braco) if r else None,
        "trechos_sem_baixo": [asdict(t) for t in r.trechos_sem_baixo] if r else None,
        "avisos_de_oitava": [_oitava(a) for a in r.avisos_de_oitava] if r else None,
        "tom": _tom(r.tonalidade) if r else None,
        "formatos": sorted(r.artefatos) if r else [],
        "bpm_estimado": bool(r and r.andamento),
        "bpm_confiavel": bool(r and r.andamento and r.andamento.confiavel),
    }


@dataclass(slots=True)
class _Estado:
    out_dir: Path
    cache_dir: Path
    executar: Executor
    jobs: dict[str, Job] = field(default_factory=dict)
    #: Serializa a execução (ADR-027). Dois pipelines simultâneos escrevem no
    #: mesmo diretório encenado do cache e no mesmo artefato nomeado pelo título.
    trava: threading.Lock = field(default_factory=threading.Lock)


def criar_app(
    *,
    out_dir: Path = Path("out"),
    cache_dir: Path = Path("cache"),
    executar: Executor | None = None,
    web_dir: Path = WEB_PADRAO,
) -> FastAPI:
    estado = _Estado(out_dir, cache_dir, executar or pipeline.transcrever)
    app = FastAPI(title="Thoth", summary="Áudio → tablatura de contrabaixo.")

    def _rodar(job: Job) -> None:
        # Um por vez (ADR-027): esperar na fila é o que o pedido seguinte faz aqui.
        with estado.trava:
            job.status = "rodando"
            try:
                job.resultado = estado.executar(
                    job.pedido.ref,
                    estado.out_dir,
                    bpm=job.pedido.bpm,
                    tuning=AFINACOES[job.pedido.afinacao],
                    cache_dir=estado.cache_dir,
                    tom=job.pedido.tom,
                    assigner=ViterbiFretAssigner(custos=DIGITACOES[job.pedido.digitacao]),
                )
                job.status = "pronto"
            except Exception as erro:  # vira estado do job, não 500 do servidor
                job.status, job.erro = "erro", str(erro)

    def _buscar(ident: str) -> Job:
        if (job := estado.jobs.get(ident)) is None:
            raise HTTPException(404, f"job {ident} não existe")
        return job

    @app.post("/jobs", status_code=202)
    def criar(pedido: Pedido, tarefas: BackgroundTasks) -> dict[str, Any]:
        job = Job(id=uuid.uuid4().hex[:12], pedido=pedido)
        estado.jobs[job.id] = job
        descartar_antigos(estado.jobs)
        tarefas.add_task(_rodar, job)
        return _resumo(job)

    @app.get("/jobs")
    def listar() -> list[dict[str, Any]]:
        return [_resumo(j) for j in estado.jobs.values()]

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
