"""Notas transcritas → JSONL no cache da fonte.

A transcrição é o estágio caro do pipeline (minutos de CPU por música), e até
aqui o resultado dela morria com o processo: sobravam só o `.gp5` e o
`.musicxml`, ambos já quantizados. Quem quiser as notas em tempo absoluto — a
auralização, qualquer medição futura — teria que pagar a transcrição de novo.

JSONL, e não JSON: música longa passa de três mil notas, e linha a linha o
arquivo continua legível com `head` sem carregar tudo.
"""

from __future__ import annotations

import json
from pathlib import Path

from thoth.domain.models import NoteEvent


def gravar(notas: list[NoteEvent], destino: Path) -> Path:
    """Grava as notas, criando o diretório se ele ainda não existir."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(
        "".join(
            json.dumps(
                {
                    "pitch": n.pitch,
                    "onset_s": n.onset_s,
                    "offset_s": n.offset_s,
                    "instrument": n.instrument,
                }
            )
            + "\n"
            for n in notas
        )
    )
    return destino


def ler(origem: Path) -> list[NoteEvent]:
    """Lê o JSONL de volta. Ausência do arquivo é `FileNotFoundError`, não lista vazia."""
    return [
        NoteEvent(**json.loads(linha))
        for linha in origem.read_text().splitlines()
        if linha.strip()
    ]
