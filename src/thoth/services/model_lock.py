"""Trava os pesos do modelo por SHA-256.

Dois riscos reais, os dois já observados neste projeto:

- **O checkpoint some.** O `beat_this-final0.ckpt` ficou inalcançável durante a
  Fase 0 (`cloud.cp.jku.at` sem rota daqui). Sem registro de qual arquivo era, a
  reprodução do resultado morre junto com o host.
- **O checkpoint muda em silêncio.** Os pesos do MuScriptor moram em repositório
  de terceiro sob CC BY-NC 4.0; republicar o `model.safetensors` com outro
  conteúdo mudaria toda transcrição daqui pra frente sem nenhum sinal.

O lock não impede nenhum dos dois — ele os torna **visíveis**.
"""

from __future__ import annotations

import hashlib
import tomllib
from dataclasses import dataclass
from pathlib import Path

#: Blocos de 1 MiB: pesos passam de 1 GB e não cabem confortavelmente na memória.
_BLOCO = 1024 * 1024


class IntegridadeError(RuntimeError):
    """O arquivo no disco não é o que o lock descreve."""


@dataclass(frozen=True, slots=True)
class ArquivoTravado:
    path: str
    sha256: str
    bytes: int


@dataclass(frozen=True, slots=True)
class ModeloTravado:
    repo: str
    revision: str
    arquivos: tuple[ArquivoTravado, ...]
    licenca: str | None = None


def carregar_lock(lock: Path) -> dict[str, ModeloTravado]:
    dados = tomllib.loads(lock.read_text())
    return {
        nome: ModeloTravado(
            repo=str(bloco["repo"]),
            revision=str(bloco["revision"]),
            licenca=bloco.get("licenca"),
            arquivos=tuple(
                ArquivoTravado(path=str(a["path"]), sha256=str(a["sha256"]), bytes=int(a["bytes"]))
                for a in bloco["arquivos"]
            ),
        )
        for nome, bloco in dados.items()
    }


def sha256_de(arquivo: Path) -> str:
    digest = hashlib.sha256()
    with arquivo.open("rb") as f:
        while bloco := f.read(_BLOCO):
            digest.update(bloco)
    return digest.hexdigest()


def conferir(arquivo: Path, esperado: ArquivoTravado) -> None:
    """Levanta `IntegridadeError` se o arquivo sumiu, truncou ou mudou de conteúdo."""
    if not arquivo.is_file():
        raise IntegridadeError(f"{esperado.path}: não encontrado em {arquivo}")

    tamanho = arquivo.stat().st_size
    if tamanho != esperado.bytes:
        # Checagem barata primeiro: hashear 1,2 GB para descobrir truncamento é desperdício.
        raise IntegridadeError(
            f"{esperado.path}: esperado {esperado.bytes} bytes, encontrado {tamanho}"
        )

    obtido = sha256_de(arquivo)
    if obtido != esperado.sha256:
        raise IntegridadeError(
            f"{esperado.path}: sha256 diverge — esperado {esperado.sha256}, obtido {obtido}"
        )


def caminho_no_cache(
    modelo: ModeloTravado, arquivo: ArquivoTravado, cache: Path | None = None
) -> Path | None:
    """Localiza o arquivo no cache do HuggingFace, ou `None` se o modelo não foi baixado."""
    raiz = cache or Path.home() / ".cache" / "huggingface" / "hub"
    destino = (
        raiz
        / f"models--{modelo.repo.replace('/', '--')}"
        / "snapshots"
        / modelo.revision
        / arquivo.path
    )
    return destino if destino.exists() else None
