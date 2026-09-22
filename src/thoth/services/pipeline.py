"""Áudio → artefatos. A única função que conhece a ordem dos estágios.

Sem fila, sem estado, sem retentativa: é uso pessoal, uma música por vez. A Fase
5 embrulha isto num `POST /jobs`; não há motivo para antecipar o embrulho.

Três restrições medidas, embutidas aqui porque é aqui que elas se aplicam:

- **Separar sempre**, antes de transcrever (ADR-010) — o teclado vaza para
  dentro do canal do baixo mesmo quando o modelo o rotula corretamente.
- **Transcrever o stem inteiro, de uma vez** (emenda do ADR-008) — o rótulo do
  instrumento depende de contexto; 2,9 s de baixo viram `acoustic_piano`.
- **Nota fora do braço é descartada, não fatal** — é a assinatura do erro de
  oitava do Demucs (ADR-010: B0 onde a mix diz B1), e uma nota errada não pode
  custar os 16 minutos de processamento da música inteira.
- **Filtrar por conjunto de rótulos, nunca por literal**, e relatar a contagem
  bruta: um literal que não casa devolveria zero notas em silêncio.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from thoth.adapters.export.gp5 import Gp5Exporter
from thoth.adapters.export.musicxml import MusicXmlExporter
from thoth.adapters.ingest import resolver_fonte
from thoth.adapters.separation import DemucsSeparator
from thoth.adapters.transcription.muscriptor import MuscriptorTranscriber
from thoth.domain.models import TUNING_BASS_4, AudioAsset, NoteEvent
from thoth.domain.ports import Exporter, FretAssigner, Separator, Transcriber
from thoth.services.fretboard import ViterbiFretAssigner, cabe_no_braco
from thoth.services.nomes import nome_de_arquivo
from thoth.services.octave_check import OctaveWarning, verificar_oitavas
from thoth.services.rhythm import monofonizar

#: Os três nomes que o MuScriptor usa para baixo (`list-instruments`, v0.3.0).
ROTULOS_DE_BAIXO = frozenset({"electric_bass", "acoustic_bass", "contrabass"})


@dataclass(frozen=True, slots=True)
class Resultado:
    """O que o pipeline produziu e o que ele preferiu não esconder."""

    asset: AudioAsset
    stem: Path
    artefatos: dict[str, Path]
    notas: int
    rotulos: dict[str, int]
    descartadas: list[NoteEvent]
    fora_do_braco: list[NoteEvent]
    avisos_de_oitava: list[OctaveWarning]


def transcrever(
    ref: str,
    out_dir: Path,
    *,
    bpm: int,
    tuning: tuple[int, ...] = TUNING_BASS_4,
    cache_dir: Path = Path("cache"),
    separator: Separator | None = None,
    transcriber: Transcriber | None = None,
    assigner: FretAssigner | None = None,
    exporters: dict[str, Exporter] | None = None,
) -> Resultado:
    """Caminho ou URL → `.gp5` e `.musicxml` em `out_dir`, nomeados pelo título (ADR-017).

    `bpm` é entrada, não estimativa (ADR-013): nenhum formato de partitura guarda
    segundos, e o Thoth ainda não estima andamento.
    """
    separator = separator or DemucsSeparator()
    transcriber = transcriber or MuscriptorTranscriber()
    assigner = assigner or ViterbiFretAssigner()
    exporters = exporters or {
        "gp5": Gp5Exporter(bpm=bpm),
        "musicxml": MusicXmlExporter(bpm=bpm),
    }

    asset = resolver_fonte(ref).fetch(ref, cache_dir)
    stem = separator.separate(asset.wav, cache_dir / "stems" / asset.source_id)["bass"]

    todas = transcriber.transcribe(stem)
    rotulos = Counter(n.instrument for n in todas)
    baixo = [n for n in todas if n.instrument in ROTULOS_DE_BAIXO]
    if not baixo:
        raise ValueError(
            f"nenhuma nota de baixo em {asset.title!r}: o transcritor devolveu "
            f"{dict(rotulos) or 'nada'}"
        )

    no_braco = [n for n in baixo if cabe_no_braco(n.pitch, tuning)]
    fora = [n for n in baixo if not cabe_no_braco(n.pitch, tuning)]
    mantidas, simultaneas = monofonizar(no_braco, bpm)
    descartadas = sorted(simultaneas + fora, key=lambda n: n.onset_s)
    avisos = verificar_oitavas(stem, mantidas)
    tabs = assigner.assign(mantidas, tuning)

    out_dir.mkdir(parents=True, exist_ok=True)
    artefatos = {
        formato: exportador.export(tabs, out_dir / f"{nome_de_arquivo(asset)}.{formato}", tuning)
        for formato, exportador in exporters.items()
    }
    return Resultado(
        asset=asset,
        stem=stem,
        artefatos=artefatos,
        notas=len(mantidas),
        rotulos=dict(rotulos),
        descartadas=descartadas,
        fora_do_braco=fora,
        avisos_de_oitava=avisos,
    )
