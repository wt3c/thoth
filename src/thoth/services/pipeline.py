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

import shutil
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from thoth.adapters.export.gp5 import Gp5Exporter
from thoth.adapters.export.musicxml import MusicXmlExporter
from thoth.adapters.ingest import resolver_fonte
from thoth.adapters.separation import DemucsSeparator
from thoth.adapters.transcription.muscriptor import MuscriptorTranscriber
from thoth.domain.models import TUNING_BASS_4, AudioAsset, NoteEvent
from thoth.domain.ports import AudioSource, Exporter, FretAssigner, Separator, Transcriber
from thoth.services.cache_notas import gravar
from thoth.services.fretboard import ViterbiFretAssigner, cabe_no_braco
from thoth.services.nomes import nome_de_arquivo
from thoth.services.octave_check import OctaveWarning, verificar_oitavas
from thoth.services.rhythm import deslocar, monofonizar, recuo_de_fase
from thoth.services.tempo import (
    BPM_MAXIMO,
    BPM_MINIMO,
    Andamento,
    ajustar,
    desdobrar,
    estimar_andamento,
)
from thoth.services.tonalidade import Tonalidade, estimar_tom, tom_de_texto

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
    bpm: float
    #: Preenchido só quando o andamento foi estimado — `None` quando veio de você.
    andamento: Andamento | None = None
    #: A dobra para a faixa musical foi desfeita pelas notas (ADR-024). Sempre
    #: `False` no `--bpm` informado, que não passa por essa correção.
    desdobrado: bool = False
    #: O tom, informado ou estimado (ADR-031). `margem is None` distingue os dois.
    tonalidade: Tonalidade | None = None


def transcrever(
    ref: str,
    out_dir: Path,
    *,
    bpm: int | None = None,
    tom: str | None = None,
    tuning: tuple[int, ...] = TUNING_BASS_4,
    cache_dir: Path = Path("cache"),
    source: AudioSource | None = None,
    separator: Separator | None = None,
    transcriber: Transcriber | None = None,
    assigner: FretAssigner | None = None,
    exporters: dict[str, Exporter] | None = None,
) -> Resultado:
    """Caminho ou URL → partitura e áudio em `out_dir`, nomeados pelo título (ADR-017).

    Saem quatro arquivos: `.gp5`, `.musicxml`, `.mix.wav` e `.baixo.wav`. Os dois
    áudios são cópias do cache, que é nomeado por hash da fonte — sem elas a pasta
    de saída não tem nada que se possa ouvir ao lado da partitura (ADR-036).

    `bpm` informado manda sempre. Sem ele, o andamento é estimado do mix e vem
    relatado no `Resultado` (ADR-019) — estimar em silêncio é que não pode.
    """
    # Antes de qualquer minuto de CPU, e antes de qualquer conta: `bpm=0` fazia
    # `para_ticks` devolver zero para toda nota, a música inteira colapsava num
    # tick e o relatório culpava polifonia (ADR-025).
    if bpm is not None and not BPM_MINIMO <= bpm <= BPM_MAXIMO:
        raise ValueError(f"BPM fora de faixa: {bpm} não está entre {BPM_MINIMO} e {BPM_MAXIMO}")

    # Tom ilegível é erro de uso: recusar aqui, antes do download e dos minutos de
    # CPU, e não depois de tudo pronto na hora de exportar.
    if tom is not None:
        tom_de_texto(tom)

    separator = separator or DemucsSeparator()
    transcriber = transcriber or MuscriptorTranscriber()
    assigner = assigner or ViterbiFretAssigner()

    # `resolver_fonte` escolhe entre disco e YouTube pelo `ref`; `source` passa por
    # cima dessa escolha. Era o único estágio que não se deixava substituir, e sem
    # ele todo teste do pipeline arrastava ffmpeg ou rede.
    asset = (source or resolver_fonte(ref)).fetch(ref, cache_dir)
    # Estimar pelo mix, não pelo stem: o pulso está na bateria, que a separação tira.
    andamento = None
    if bpm is None:
        andamento = estimar_andamento(asset.wav)
        bpm = andamento.bpm
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
    # O andamento estimado do mix é inteiro, e arredondar custa caro: 107,5 -> 108
    # acumulam 3,5 s em 756 s de música (ADR-021). As notas transcritas refinam o
    # número e, junto com ele, a fase da grade — os dois são acoplados, refinar só
    # um piora. `bpm` que você informou não é refinado, só ancorado: faixa=0.
    onsets = [n.onset_s for n in no_braco]
    # `dobrar_para_faixa` decidiu antes de existir nota alguma. Agora existem, e
    # grade grosseira pela metade colapsa ataques distintos no mesmo tick (ADR-024).
    # O `--bpm` que você informou não passa por aqui: ele manda (ADR-019).
    base = desdobrar(onsets, bpm) if andamento else float(bpm)
    andamento_fino, fase = ajustar(onsets, base, faixa=None if andamento else 0.0)
    # Deslocar ANTES de monofonizar: `monofonizar` deduplica ticks e `eventos`
    # recusa ticks repetidos, e as duas contas precisam ser a mesma grade. Feitas
    # em fases diferentes, um par aprovado por uma colapsa na outra.
    recuo = recuo_de_fase(no_braco, andamento_fino, fase)
    mantidas, simultaneas = monofonizar(deslocar(no_braco, recuo), andamento_fino)
    # Tudo que é medido contra o áudio ou relatado a você volta ao tempo do
    # áudio: `verificar_oitavas` sonda o stem no instante da nota, e `fora` nunca
    # foi deslocada. Só a partitura vive na grade.
    no_audio = deslocar(mantidas, -recuo)
    descartadas = sorted(deslocar(simultaneas, -recuo) + fora, key=lambda n: n.onset_s)
    avisos = verificar_oitavas(stem, no_audio)
    # A transcrição custa minutos de CPU e morria com o processo: os artefatos
    # guardam só o tempo já quantizado. Isto guarda o tempo absoluto.
    # Só a partitura fica deslocada: o cache guarda o tempo do áudio, e a
    # auralização toca o MIDI contra o original — deslocar ali dessincronizaria.
    gravar(no_audio, cache_dir / asset.source_id / "notas.jsonl")
    tabs = assigner.assign(mantidas, tuning)
    # O tom vem das notas que vão para a partitura, e a armadura só é escrita
    # quando a estimativa se sustenta: armadura errada imprime mais bequadro do
    # que armadura nenhuma (ADR-031). `tom` informado não passa por margem.
    tonalidade = tom_de_texto(tom) if tom else estimar_tom(mantidas)
    armadura = tonalidade.armadura if tonalidade else None
    exporters = exporters or {
        "gp5": Gp5Exporter(bpm=andamento_fino, armadura=armadura, titulo=asset.title),
        "musicxml": MusicXmlExporter(
            bpm=andamento_fino, armadura=armadura, titulo=asset.title
        ),
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    nome = nome_de_arquivo(asset)
    artefatos = {
        formato: exportador.export(tabs, out_dir / f"{nome}.{formato}", tuning)
        for formato, exportador in exporters.items()
    }
    # Cópia, e não atalho para o cache: a pasta de saída é o que você abre e move,
    # e ela não pode depender de um diretório nomeado por hash continuar existindo.
    for chave, origem in (("mix", asset.wav), ("baixo", stem)):
        artefatos[chave] = Path(shutil.copy2(origem, out_dir / f"{nome}.{chave}.wav"))
    return Resultado(
        bpm=andamento_fino,
        tonalidade=tonalidade,
        andamento=andamento,
        desdobrado=base != float(bpm),
        asset=asset,
        stem=stem,
        artefatos=artefatos,
        notas=len(mantidas),
        rotulos=dict(rotulos),
        descartadas=descartadas,
        fora_do_braco=fora,
        avisos_de_oitava=avisos,
    )
