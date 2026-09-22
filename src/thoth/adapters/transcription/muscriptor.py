"""MuScriptor 0.3.0 atrás do `Protocol Transcriber`.

Invocado por subprocesso via `uvx`, e não como dependência do projeto: o
MuScriptor arrasta torch e exige Python 3.10 a 3.12, e não há razão para que a
CLI do Thoth carregue esse peso só para converter um arquivo.

Decisões da Fase 0 embutidas aqui:

- **`small`, não `medium`** (ADR-009): o `medium` degenera em áudio sintético.
- **Decodificação livre, nunca `--instruments`** (ADR-008): a flag não seleciona
  instrumento, ela proíbe todos os outros — e força áudio alheio para o rótulo
  permitido. O filtro é nosso, depois da decodificação.
- **`--detect-tempo false`**: a detecção baixa o checkpoint do Beat This! de
  `cloud.cp.jku.at`, inalcançável desta estação. Quantização é problema nosso.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from thoth.domain.models import NoteEvent

#: Duração atribuída a nota cujo evento `end` não veio (truncamento no fim do áudio).
_DURACAO_ORFA_S = 0.1


def parse_jsonl(texto: str, instrument: str | None = None) -> list[NoteEvent]:
    """Converte o JSONL do MuScriptor em notas, ordenadas por onset.

    O formato separa início e fim em duas linhas, ligadas por `index` ↔
    `start_event_index`.
    """
    inicios: dict[int, dict[str, object]] = {}
    fins: dict[int, float] = {}
    for linha in texto.splitlines():
        if not linha.strip():
            continue
        evento = json.loads(linha)
        if evento["type"] == "start":
            inicios[int(evento["index"])] = evento
        elif evento["type"] == "end":
            fins[int(evento["start_event_index"])] = float(evento["end_time"])

    notas = [
        NoteEvent(
            pitch=int(str(e["pitch"])),
            onset_s=float(str(e["start_time"])),
            offset_s=fins.get(i, float(str(e["start_time"])) + _DURACAO_ORFA_S),
            instrument=str(e["instrument"]),
        )
        for i, e in inicios.items()
        if instrument is None or e["instrument"] == instrument
    ]
    return sorted(notas, key=lambda n: (n.onset_s, n.pitch))


@dataclass(frozen=True, slots=True)
class MuscriptorTranscriber:
    """Áudio → notas, por subprocesso."""

    model: str = "small"
    device: str = "cpu"  # a estação não tem CUDA; ROCm não está no escopo
    binary: tuple[str, ...] = field(default=("uvx", "--python", "3.12", "muscriptor"))

    def _comando(self, audio: Path, saida: Path) -> list[str]:
        return [
            *self.binary, "transcribe", str(audio),
            "-m", self.model,
            "-d", self.device,
            "-f", "jsonl",
            "-o", str(saida),
            "--detect-tempo", "false",
        ]

    def transcribe(self, audio: Path, instrument: str | None = None) -> list[NoteEvent]:
        with tempfile.TemporaryDirectory() as tmp:
            saida = Path(tmp) / "notas.jsonl"
            subprocess.run(self._comando(audio, saida), check=True, capture_output=True)
            return parse_jsonl(saida.read_text(), instrument)
