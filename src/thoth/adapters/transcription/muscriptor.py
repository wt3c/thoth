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
- **Segunda passada sem prelude forcing, só onde a primeira emudeceu** (emenda do
  ADR-008, 2026-09-25): cada bloco de 5 s começa forçado pelas notas abertas do
  anterior, e em *Eyrie* isso travou o modelo em vazio de 557 a 671 s com o baixo
  soando. O mesmo trecho sem o forcing sai transcrito. Desligar sempre custaria a
  qualidade na fronteira dos blocos (rótulo trocado) nas 13 de 14 músicas sem buraco.
"""

from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import soundfile as sf

from thoth.domain.models import NoteEvent
from thoth.domain.ports import Transcriber
from thoth.processos import rodar

#: Duração atribuída a nota cujo evento `end` não veio (truncamento no fim do áudio).
_DURACAO_ORFA_S = 0.1

#: "Soando" é o segundo a menos de 12 dB da mediana dos segundos não silenciosos.
#: Medido em 14 músicas: só o buraco de *Eyrie* (114 s) passa dos dois critérios.
_ABAIXO_DA_MEDIANA_DB = 12.0
_SILENCIO_DB = -60.0
#: Segundo sem ataque a até 2 s dele. Pausa de música dura menos que o mínimo.
_VIZINHANCA_S = 2
_BURACO_MINIMO_S = 10


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


def trechos_sem_nota(energia_db: list[float], onsets: list[float]) -> list[tuple[int, int]]:
    """Trechos `[início, fim)` em segundos onde o stem soa e o modelo não deu nota alguma.

    `energia_db` é a energia de cada segundo do stem; `onsets`, os ataques de
    **todos** os rótulos: nota com rótulo de outro instrumento não é buraco do
    modelo, é assunto do filtro (ADR-008).
    """
    energia = np.asarray(energia_db, dtype=float)
    audiveis = energia[energia > _SILENCIO_DB]
    if not len(audiveis):
        return []
    soando = energia > np.median(audiveis) - _ABAIXO_DA_MEDIANA_DB
    com_ataque = np.zeros(len(energia), dtype=bool)
    for t in onsets:
        if 0 <= t < len(energia):
            com_ataque[int(t)] = True
    janela = np.ones(2 * _VIZINHANCA_S + 1)
    perto = np.convolve(com_ataque, janela, mode="same") > 0
    buraco = soando & ~perto

    trechos: list[tuple[int, int]] = []
    inicio: int | None = None
    for i, vazio in enumerate([*buraco, False]):
        if vazio and inicio is None:
            inicio = i
        elif not vazio and inicio is not None:
            if i - inicio >= _BURACO_MINIMO_S:
                trechos.append((inicio, i))
            inicio = None
    return trechos


def _energia_por_segundo(audio: Path) -> list[float]:
    y, taxa = sf.read(audio, always_2d=True)
    mono = y.mean(axis=1)
    return [
        float(20 * np.log10(np.sqrt(np.mean(mono[i : i + taxa] ** 2)) + 1e-9))
        for i in range(0, len(mono) - taxa + 1, taxa)
    ]


@dataclass(frozen=True, slots=True)
class MuscriptorTranscriber:
    """Áudio → notas, por subprocesso."""

    model: str = "small"
    device: str = "cpu"  # a estação não tem CUDA; ROCm não está no escopo
    binary: tuple[str, ...] = field(default=("uvx", "--python", "3.12", "muscriptor@0.3.0"))

    def _comando(self, audio: Path, saida: Path, *, prelude: bool = True) -> list[str]:
        return [
            *self.binary, "transcribe", str(audio),
            "-m", self.model,
            "-d", self.device,
            "-f", "jsonl",
            "-o", str(saida),
            "--detect-tempo", "false",
            *([] if prelude else ["--no-prelude-forcing"]),
        ]

    def _passada(self, audio: Path, *, prelude: bool) -> list[NoteEvent]:
        with tempfile.TemporaryDirectory() as tmp:
            saida = Path(tmp) / "notas.jsonl"
            rodar(self._comando(audio, saida, prelude=prelude))
            return parse_jsonl(saida.read_text())

    def transcribe(self, audio: Path, instrument: str | None = None) -> list[NoteEvent]:
        notas = self._passada(audio, prelude=True)
        buracos = trechos_sem_nota(_energia_por_segundo(audio), [n.onset_s for n in notas])
        if buracos:
            # Stem inteiro de novo, sem fatiar: o rótulo depende de contexto (ADR-008).
            # A vizinhança atrasa o início e adianta o fim de cada buraco; sem
            # devolvê-la, os 2 s de cada borda não viriam de passada nenhuma.
            def no_buraco(n: NoteEvent) -> bool:
                return any(
                    a - _VIZINHANCA_S <= n.onset_s < b + _VIZINHANCA_S for a, b in buracos
                )

            segunda = self._passada(audio, prelude=False)
            notas = [n for n in notas if not no_buraco(n)] + [n for n in segunda if no_buraco(n)]
        return sorted(
            (n for n in notas if instrument is None or n.instrument == instrument),
            key=lambda n: (n.onset_s, n.pitch),
        )


if TYPE_CHECKING:  # pragma: no cover — trava a assinatura contra o Protocol
    _: Transcriber = MuscriptorTranscriber()
