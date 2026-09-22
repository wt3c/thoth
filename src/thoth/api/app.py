"""API de jobs: o pipeline embrulhado em HTTP, para o alphaTab consumir.

Jobs vivem **em memória**, no processo. Não é descuido: é uso pessoal, uma música
por vez, e reiniciar o servidor perde o histórico — mas não perde nada caro, já
que os artefatos ficam em disco nomeados pelo `source_id` e um job repetido
reaproveita o cache de ingestão e de separação.

A UI é servida daqui, com o alphaTab **local** (ADR-006): estudar não pode
depender de CDN nem de internet. O `web/vendor/` não é versionado — se faltar, a
raiz responde dizendo qual comando o traz, em vez de entregar página quebrada.

Falha do pipeline vira **estado do job**, não 500: "nenhuma nota de baixo" é
diagnóstico para quem pediu, não defeito do servidor.
"""

from __future__ import annotations

import mimetypes
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from thoth.domain.models import TUNING_BASS_4, TUNING_BASS_5
from thoth.services import pipeline
from thoth.services.pipeline import Resultado

#: Raiz do `web/`, servida como está — a UI não passa por build.
WEB_PADRAO = Path(__file__).resolve().parents[3] / "web"

# O `mimetypes` do Python não conhece woff2, e a tabela do SO tampouco, em geral.
# Sem isto a fonte musical sai como `application/octet-stream`.
mimetypes.add_type("font/woff2", ".woff2")
mimetypes.add_type("font/woff", ".woff")


class Executor(Protocol):
    """O pipeline, injetável — rodar o real num teste custa minutos de CPU."""

    def __call__(
        self, ref: str, out_dir: Path, *, bpm: int, tuning: tuple[int, ...], cache_dir: Path
    ) -> Resultado: ...


class Pedido(BaseModel):
    """`bpm` é entrada e não estimativa (ADR-013); `cordas` escolhe a afinação."""

    ref: str = Field(..., description="Caminho do áudio ou URL do YouTube.")
    bpm: int = Field(120, ge=20, le=300)
    cordas: int = Field(4, ge=4, le=5)


@dataclass(slots=True)
class Job:
    id: str
    pedido: Pedido
    status: str = "rodando"  # rodando | pronto | erro
    resultado: Resultado | None = None
    erro: str | None = None


def _resumo(job: Job) -> dict[str, Any]:
    r = job.resultado
    return {
        "id": job.id,
        "status": job.status,
        "ref": job.pedido.ref,
        "bpm": job.pedido.bpm,
        "erro": job.erro,
        "titulo": r.asset.title if r else None,
        "notas": r.notas if r else None,
        "rotulos": r.rotulos if r else None,
        "descartadas": len(r.descartadas) if r else None,
        "fora_do_braco": len(r.fora_do_braco) if r else None,
        "avisos_de_oitava": (
            [
                {"pitch": a.event.pitch, "onset_s": round(a.event.onset_s, 2)}
                for a in r.avisos_de_oitava
            ]
            if r
            else None
        ),
        "formatos": sorted(r.artefatos) if r else [],
    }


@dataclass(slots=True)
class _Estado:
    out_dir: Path
    cache_dir: Path
    executar: Executor
    jobs: dict[str, Job] = field(default_factory=dict)


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
        try:
            job.resultado = estado.executar(
                job.pedido.ref,
                estado.out_dir,
                bpm=job.pedido.bpm,
                tuning=TUNING_BASS_5 if job.pedido.cordas == 5 else TUNING_BASS_4,
                cache_dir=estado.cache_dir,
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
