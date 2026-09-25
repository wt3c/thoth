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
  bruta: um literal que não casa devolveria zero notas em silêncio. E readmitir,
  relatando, os trechos sem baixo (emenda do ADR-008): o rótulo depende de
  contexto, e o baixo chamado de guitarra no meio da música sairia do filtro.

Cada estágio se anuncia por `Progresso` antes de começar (ADR-037). Quem desenha é
a CLI: o pipeline não conhece terminal, cor nem barra de progresso.
"""

from __future__ import annotations

import shutil
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from thoth.adapters.export.gp5 import Gp5Exporter
from thoth.adapters.export.musicxml import MusicXmlExporter
from thoth.adapters.ingest import resolver_fonte
from thoth.adapters.separation import DemucsSeparator
from thoth.adapters.transcription.muscriptor import MuscriptorTranscriber
from thoth.domain.models import TUNING_BASS_4, AudioAsset, NoteEvent
from thoth.domain.ports import (
    AudioSource,
    Exporter,
    FretAssigner,
    Progresso,
    Separator,
    Transcriber,
)
from thoth.services.auralizacao import AuralizacaoError, auralizar
from thoth.services.cache_notas import gravar
from thoth.services.fretboard import ViterbiFretAssigner, cabe_no_braco
from thoth.services.nomes import nome_de_arquivo
from thoth.services.octave_check import OctaveWarning, verificar_oitavas
from thoth.services.rhythm import deslocar, monofonizar, recuo_de_fase
from thoth.services.rotulos import TrechoSemBaixo, readmitidas, trechos_sem_baixo
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
    #: Por que não saiu `.aural.wav`. A auralização depende de soundfont e de
    #: fluidsynth, e nenhum dos dois vale os minutos de CPU já gastos (ADR-037).
    falha_na_auralizacao: str | None = None
    #: Onde o stem seguiu tocando com rótulo de outro instrumento, longe de qualquer
    #: baixo — essas notas foram readmitidas como baixo (emenda do ADR-008).
    trechos_sem_baixo: list[TrechoSemBaixo] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class _Silencio:
    """`Progresso` que não relata nada — o default de quem usa como biblioteca."""

    def inicia(self, etapa: str, detalhe: str = "") -> None:
        return None


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
    progresso: Progresso | None = None,
) -> Resultado:
    """Caminho ou URL → uma pasta por música em `out_dir`, nomeada pelo título (ADR-037).

    Dentro dela, tudo com o nome da música: `.gp5`, `.musicxml` e os quatro áudios
    — `.mix.wav`, `.baixo.wav`, `.sem-baixo.wav` (o playback, que o Demucs já
    entregava de graça) e `.aural.wav`. Os três primeiros são cópias do cache, que
    é nomeado por hash da fonte: a pasta de saída é o que se abre e se move, e não
    pode depender de um diretório de hash continuar existindo (ADR-036/037).

    Áudio que falta não desce em silêncio: a auralização depende de ferramenta
    externa, e a falha dela volta em `falha_na_auralizacao` em vez de custar a
    corrida inteira (ADR-014).

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

    relator = progresso or _Silencio()
    separator = separator or DemucsSeparator()
    transcriber = transcriber or MuscriptorTranscriber()
    assigner = assigner or ViterbiFretAssigner()

    # `resolver_fonte` escolhe entre disco e YouTube pelo `ref`; `source` passa por
    # cima dessa escolha. Era o único estágio que não se deixava substituir, e sem
    # ele todo teste do pipeline arrastava ffmpeg ou rede.
    relator.inicia("obtendo o áudio", ref)
    asset = (source or resolver_fonte(ref)).fetch(ref, cache_dir)
    # Estimar pelo mix, não pelo stem: o pulso está na bateria, que a separação tira.
    andamento = None
    if bpm is None:
        relator.inicia("estimando o andamento", "do mix, onde está a bateria")
        andamento = estimar_andamento(asset.wav)
        bpm = andamento.bpm
    relator.inicia("separando o baixo", "Demucs, ~3x a duração do áudio em CPU")
    stems = separator.separate(asset.wav, cache_dir / "stems" / asset.source_id)
    stem = stems["bass"]

    relator.inicia("transcrevendo as notas", "MuScriptor, o outro estágio caro")
    todas = transcriber.transcribe(stem)
    rotulos = Counter(n.instrument for n in todas)
    baixo = [n for n in todas if n.instrument in ROTULOS_DE_BAIXO]
    outras = [n for n in todas if n.instrument not in ROTULOS_DE_BAIXO]
    sem_baixo = trechos_sem_baixo(baixo, outras)
    if not baixo:
        raise ValueError(
            f"nenhuma nota de baixo em {asset.title!r}: o transcritor devolveu "
            f"{dict(rotulos) or 'nada'}"
        )
    # Longe de qualquer baixo, a linha com outro rótulo é o baixo mal rotulado
    # (emenda do ADR-008). Perto dele, é vazamento ou duplicata e continua fora.
    baixo = sorted(baixo + readmitidas(outras, sem_baixo), key=lambda n: n.onset_s)

    no_braco = [n for n in baixo if cabe_no_braco(n.pitch, tuning)]

    fora = [n for n in baixo if not cabe_no_braco(n.pitch, tuning)]
    # O andamento estimado do mix é inteiro, e arredondar custa caro: 107,5 -> 108
    # acumulam 3,5 s em 756 s de música (ADR-021). As notas transcritas refinam o
    # número e, junto com ele, a fase da grade — os dois são acoplados, refinar só
    # um piora. `bpm` que você informou não é refinado, só ancorado: faixa=0.
    relator.inicia("ajustando a grade rítmica")
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
    relator.inicia("conferindo as oitavas", "sondando o stem no instante de cada nota")
    avisos = verificar_oitavas(stem, no_audio)
    # A transcrição custa minutos de CPU e morria com o processo: os artefatos
    # guardam só o tempo já quantizado. Isto guarda o tempo absoluto.
    # Só a partitura fica deslocada: o cache guarda o tempo do áudio, e a
    # auralização toca o MIDI contra o original — deslocar ali dessincronizaria.
    gravar(no_audio, cache_dir / asset.source_id / "notas.jsonl")
    relator.inicia("posicionando no braço")
    tabs = assigner.assign(mantidas, tuning)
    # O tom vem das notas que vão para a partitura, e a armadura só é escrita
    # quando a estimativa se sustenta: armadura errada imprime mais bequadro do
    # que armadura nenhuma (ADR-031). `tom` informado não passa por margem.
    tonalidade = tom_de_texto(tom) if tom else estimar_tom(mantidas)
    armadura = tonalidade.armadura if tonalidade else None
    exporters = exporters or {
        "gp5": Gp5Exporter(bpm=andamento_fino, armadura=armadura, titulo=asset.title),
        "musicxml": MusicXmlExporter(bpm=andamento_fino, armadura=armadura, titulo=asset.title),
    }

    relator.inicia("exportando a partitura", ", ".join(exporters))
    # Uma pasta por música, e o nome repetido dentro dela (ADR-037): oito músicas
    # em `out/` plano são quarenta arquivos intercalados, e o arquivo que sai da
    # pasta continua dizendo de que música é.
    nome = nome_de_arquivo(asset)
    pasta = out_dir / nome
    pasta.mkdir(parents=True, exist_ok=True)
    artefatos = {
        formato: exportador.export(tabs, pasta / f"{nome}.{formato}", tuning)
        for formato, exportador in exporters.items()
    }

    relator.inicia("copiando os áudios", "mix, baixo e playback")
    # Cópia, e não atalho para o cache: a pasta de saída é o que você abre e move,
    # e ela não pode depender de um diretório nomeado por hash continuar existindo.
    # `no_bass` é opcional no contrato do `Separator` — quem dubla a separação não
    # é obrigado a produzir playback para exercitar o resto.
    audios = [("mix", asset.wav), ("baixo", stem)]
    if (playback := stems.get("no_bass")) is not None:
        audios.append(("sem-baixo", playback))
    for chave, origem in audios:
        artefatos[chave] = Path(shutil.copy2(origem, pasta / f"{nome}.{chave}.wav"))

    relator.inicia("auralizando", "original num canal, transcrição no outro")
    # Depende de fluidsynth e de soundfont, e nenhum dos dois vale os minutos de
    # CPU já gastos: a falha vira relato (ADR-014). As notas são as do tempo do
    # áudio — a grade da partitura dessincronizaria a comparação.
    falha = None
    try:
        artefatos["aural"] = auralizar(asset.wav, no_audio, pasta / f"{nome}.aural.wav")
    except (AuralizacaoError, ValueError) as erro:
        falha = str(erro)
    return Resultado(
        falha_na_auralizacao=falha,
        trechos_sem_baixo=sem_baixo,
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
