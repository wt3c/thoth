"""Ferramenta externa por subprocesso, com o `stderr` preservado (ADR-026).

O Thoth chama seis ferramentas de linha de comando (ffmpeg, ffprobe, demucs,
muscriptor, fluidsynth, yt-dlp) e nenhuma delas é biblioteca: quando falham, o
que explica o motivo é o `stderr`. Com `capture_output=True` e `check=True`, o
`CalledProcessError` do Python guarda esse texto num atributo e **não o põe na
mensagem** — a falha chegava como "returned non-zero exit status 1", e o motivo,
que a ferramenta havia escrito por extenso, era descartado.

`FileNotFoundError` continua passando direto: "a ferramenta não está instalada" é
outra conversa, e quem a trata (a auralização, com o fluidsynth) depende disso.
"""

from __future__ import annotations

import subprocess
from collections.abc import Sequence

#: Só o fim do `stderr` entra na mensagem. O começo é banner de versão; o fim é
#: onde a ferramenta diz o que deu errado.
LIMITE_DE_STDERR = 800


class ErroDeProcesso(RuntimeError):
    """Ferramenta externa falhou. A mensagem carrega o que ela disse."""


def rodar(comando: Sequence[str], *, timeout: float | None = None) -> str:
    """Roda e devolve o `stdout`. Falha ou estouro de tempo → `ErroDeProcesso`."""
    try:
        concluido = subprocess.run(
            list(comando), check=True, capture_output=True, text=True, timeout=timeout
        )
    except subprocess.CalledProcessError as erro:
        fim = (erro.stderr or "").strip()[-LIMITE_DE_STDERR:]
        raise ErroDeProcesso(
            f"{comando[0]} falhou ({erro.returncode}): {fim or 'sem nada no stderr'}"
        ) from erro
    except subprocess.TimeoutExpired as erro:
        raise ErroDeProcesso(f"{comando[0]} excedeu {timeout}s") from erro
    return concluido.stdout
