"""Escrita no cache que ou vale inteira, ou não existe (ADR-026).

O cache do Thoth guarda o que custou caro: o WAV convertido, o stem do Demucs, as
notas transcritas. Todos eram escritos direto no destino final, e o teste de cache
é só `existe?` — então uma execução interrompida no meio (Ctrl-C, disco cheio, a
ferramenta morrendo) deixava arquivo pela metade que **toda execução seguinte
aceitava como pronto**. O erro não aparece na hora: aparece como áudio truncado ou
stem sem fim, minutos de processamento depois.

O padrão é o clássico: escreve ao lado, renomeia por cima. `os.replace` é atômico
dentro do mesmo sistema de arquivos — e é por isso que o provisório é **vizinho do
destino**, nunca `/tmp`, que nesta estação é outro ponto de montagem (renomear
entre montagens levanta `Invalid cross-device link`).
"""

from __future__ import annotations

import os
import shutil
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

#: Marca do que ainda não vale. Fora do que qualquer verificação de cache procura.
SUFIXO = ".parcial"


@contextmanager
def escrita_atomica(destino: Path) -> Iterator[Path]:
    """Dá um caminho vizinho para escrever; promove a destino ao sair sem erro.

    A extensão do destino é preservada no provisório (`mix.wav` →
    `mix.parcial.wav`): ffmpeg e yt-dlp escolhem o formato de saída por ela.
    """
    destino.parent.mkdir(parents=True, exist_ok=True)
    parcial = destino.with_name(f"{destino.stem}{SUFIXO}{destino.suffix}")
    parcial.unlink(missing_ok=True)
    try:
        yield parcial
        os.replace(parcial, destino)
    finally:
        parcial.unlink(missing_ok=True)


@contextmanager
def diretorio_atomico(destino: Path) -> Iterator[Path]:
    """O mesmo para uma árvore inteira — o Demucs escreve um diretório, não um arquivo.

    `os.replace` recusa destino que já exista com conteúdo, e sobra de execução
    anterior é justamente o caso a tratar: o destino é removido logo antes da
    troca. É cache, e o que se apaga aqui é material que já se provou incompleto.
    """
    destino.parent.mkdir(parents=True, exist_ok=True)
    parcial = destino.with_name(f"{destino.name}{SUFIXO}")
    shutil.rmtree(parcial, ignore_errors=True)
    parcial.mkdir()
    try:
        yield parcial
        shutil.rmtree(destino, ignore_errors=True)
        os.replace(parcial, destino)
    finally:
        shutil.rmtree(parcial, ignore_errors=True)
