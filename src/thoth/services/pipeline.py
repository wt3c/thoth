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

A guitarra (ADR-044) segue a mesma ordem, com três diferenças, todas medidas:

- **Notas do mesmo tique viram um acorde antes do posicionamento**
  (`unir_por_tique`). Dois grupos a 60 ms são dois acordes para o `ViterbiAcordes`
  e o mesmo tique para a grade. Sem a união, o exportador recusava a corda repetida
  depois dos minutos de CPU.
- **O andamento é medido pelo primeiro ataque de cada acorde**. Contando as seis
  notas, cada acorde valia cinco colisões e o desdobramento do ADR-024 dobrava o
  andamento sem motivo.
- **Sem readmissão, monofonização nem conferência de oitava**: as três pressupõem
  uma nota por vez. Os outros rótulos de guitarra e as outras famílias presentes no
  stem são relatados em separado, nunca fundidos na parte.

A bateria (ADR-044, M2) não tem altura nem braço: sai do stem `drums` como ataques,
em faixa de percussão, com a grade medida pelo primeiro ataque de cada grupo, como a
guitarra. O que a partitura não comporta — a mesma peça duas vezes no tique, peça fora
do mapa de percussão, mais de seis peças juntas — é relatado por motivo, não fatal.

Cada estágio se anuncia por `Progresso` antes de começar (ADR-037). Quem desenha é
a CLI: o pipeline não conhece terminal, cor nem barra de progresso.
"""

from __future__ import annotations

import shutil
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from thoth.adapters.export.gp5 import CORDAS_PERCUSSAO, Gp5Exporter, Gp5PercussaoExporter
from thoth.adapters.export.musicxml import (
    MAPA_PERCUSSAO,
    MusicXmlExporter,
    MusicXmlPercussaoExporter,
)
from thoth.adapters.ingest import resolver_fonte
from thoth.adapters.separation import DemucsSeparator
from thoth.adapters.transcription.muscriptor import MuscriptorTranscriber
from thoth.domain.instrumentos import PERFIS, PerfilInstrumento
from thoth.domain.models import (
    AcordeImpossivel,
    AudioAsset,
    EventoPercussivo,
    NoteEvent,
    TabNote,
)
from thoth.domain.ports import (
    AtribuidorDeAcordes,
    AudioSource,
    ExportadorDePercussao,
    Exporter,
    FretAssigner,
    Progresso,
    Separator,
    Transcriber,
)
from thoth.services.acordes import ViterbiAcordes, inicios_de_acorde
from thoth.services.auralizacao import AuralizacaoError, auralizar
from thoth.services.cache_notas import gravar
from thoth.services.fretboard import ViterbiFretAssigner, cabe_no_braco
from thoth.services.nomes import nome_de_arquivo
from thoth.services.octave_check import OctaveWarning, verificar_oitavas
from thoth.services.rhythm import (
    ataques_em_ticks,
    deslocar,
    monofonizar,
    recuo_de_fase,
    unir_por_tique,
)
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

#: Os perfis que chegam à partitura, com a afinação padrão de cada um — a bateria, sem
#: nenhuma. O piano ainda não tem exportador (ADR-044): recusá-lo antes do download é o
#: que evita minutos de CPU que terminariam sem arquivo.
INSTRUMENTOS: dict[str, tuple[int, ...]] = {
    nome: p.afinacao or ()
    for nome, p in PERFIS.items()
    if p.familia == "bateria" or (p.familia in ("baixo", "guitarra") and p.afinacao)
}

#: O stem do Demucs no nome do áudio copiado. `other` não é "guitarra": é tudo que
#: não é voz, bateria nem baixo, e as três guitarras e os pianos saem nele juntos.
_STEM_EM_PORTUGUES = {"bass": "baixo", "other": "outros", "drums": "bateria"}

#: Silêncio na frente do stem da bateria (ADR-045): levanta o F1 de 0,529 para 0,901 e,
#: nos outros perfis, troca o rótulo — por isso só aqui.
SILENCIO_BATERIA_S = 0.1


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
    instrumento: str = "baixo"
    #: Notas no stem com rótulo de **outro perfil da mesma família** — a guitarra
    #: limpa chamada de distorcida. Ficam fora da parte: somadas, duas guitarras
    #: viram um acorde impossível (ADR-044).
    erro_de_rotulo: dict[str, int] = field(default_factory=dict)
    #: Notas de outra família no stem — o piano e o baixo que vazaram para o `other`.
    contaminacao: dict[str, int] = field(default_factory=dict)
    #: Acordes sem digitação, relatados inteiros no tempo do áudio (ADR-014).
    acordes_impossiveis: list[AcordeImpossivel] = field(default_factory=list)
    #: Ataques de bateria fora da partitura, por motivo e no tempo do áudio: a mesma
    #: peça repetida no tique, peça fora do mapa de percussão, além de seis no tique.
    ataques_descartados: dict[str, list[EventoPercussivo]] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class _Silencio:
    """`Progresso` que não relata nada — o default de quem usa como biblioteca."""

    def inicia(self, etapa: str, detalhe: str = "") -> None:
        return None


@dataclass(frozen=True, slots=True)
class _Parte:
    """O que cada família entrega ao trecho comum: partitura, notas e relato.

    `mantidas` e `tabs` vivem na grade; `no_audio` volta ao tempo do áudio, que é o
    que o cache guarda e a auralização toca.
    """

    tabs: list[TabNote]
    mantidas: list[NoteEvent]
    no_audio: list[NoteEvent]
    bpm: float
    base: float
    descartadas: list[NoteEvent] = field(default_factory=list)
    fora: list[NoteEvent] = field(default_factory=list)
    avisos: list[OctaveWarning] = field(default_factory=list)
    sem_baixo: list[TrechoSemBaixo] = field(default_factory=list)
    erro_de_rotulo: dict[str, int] = field(default_factory=dict)
    contaminacao: dict[str, int] = field(default_factory=dict)
    impossiveis: list[AcordeImpossivel] = field(default_factory=list)
    #: Só da bateria: os ataques da partitura, na grade, e os que ficaram fora dela.
    ataques: list[EventoPercussivo] = field(default_factory=list)
    ataques_descartados: dict[str, list[EventoPercussivo]] = field(default_factory=dict)


def transcritor_padrao(perfil: PerfilInstrumento) -> MuscriptorTranscriber:
    """O MuScriptor de sempre; na bateria, com o silêncio na frente (ADR-045)."""
    if perfil.familia == "bateria":
        return MuscriptorTranscriber(silencio_inicial_s=SILENCIO_BATERIA_S)
    return MuscriptorTranscriber()


def transcrever(
    ref: str,
    out_dir: Path,
    *,
    bpm: int | None = None,
    tom: str | None = None,
    tuning: tuple[int, ...] | None = None,
    instrumento: str = "baixo",
    cache_dir: Path = Path("cache"),
    source: AudioSource | None = None,
    separator: Separator | None = None,
    transcriber: Transcriber | None = None,
    assigner: FretAssigner | None = None,
    atribuidor_de_acordes: AtribuidorDeAcordes | None = None,
    exporters: dict[str, Exporter] | None = None,
    progresso: Progresso | None = None,
) -> Resultado:
    """Caminho ou URL → uma pasta por música em `out_dir`, nomeada pelo título (ADR-037).

    Dentro dela, tudo com o nome da música: `.gp5`, `.musicxml` e os quatro áudios
    — `.mix.wav`, `.baixo.wav`, `.sem-baixo.wav` (o playback, que o Demucs já
    entregava de graça) e `.aural.wav`. Os três primeiros são cópias do cache, que
    é nomeado por hash da fonte: a pasta de saída é o que se abre e se move, e não
    pode depender de um diretório de hash continuar existindo (ADR-036/037).

    `instrumento` escolhe o perfil (ADR-044); `baixo` é o padrão e o caminho de
    sempre. Uma guitarra sai do stem `other`, com o perfil no nome da partitura, da
    auralização e do cache de notas — `.guitarra-limpa.gp5` ao lado do `.gp5` do
    baixo, sem sobrescrevê-lo —, e o stem e o playback como `.outros.wav` e
    `.sem-outros.wav`. A bateria sai do stem `drums`, sem tablatura: `.bateria.gp5` e
    `.bateria.musicxml` em faixa de percussão, e `.bateria.wav` e `.sem-bateria.wav`.
    Os `exporters` injetados valem só para as cordas.

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

    if instrumento not in INSTRUMENTOS:
        raise ValueError(
            f"instrumento {instrumento!r} não tem partitura; há {', '.join(INSTRUMENTOS)}"
        )
    perfil = PERFIS[instrumento]
    tuning = tuning or INSTRUMENTOS[instrumento]
    guitarra = perfil.familia == "guitarra"
    bateria = perfil.familia == "bateria"

    relator = progresso or _Silencio()
    separator = separator or DemucsSeparator(stem=perfil.stem)
    transcriber = transcriber or transcritor_padrao(perfil)

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
    relator.inicia(
        "separando o baixo" if perfil.familia == "baixo" else f"separando o stem {perfil.stem}",
        "Demucs, ~3x a duração do áudio em CPU",
    )
    stems = separator.separate(asset.wav, cache_dir / "stems" / asset.source_id)
    stem = stems[perfil.stem]

    relator.inicia("transcrevendo as notas", "MuScriptor, o outro estágio caro")
    todas = transcriber.transcribe(stem)
    rotulos = Counter(n.instrument for n in todas)
    # O perfil entra no nome de tudo que não é do baixo: a guitarra da mesma música
    # cai na mesma pasta, e o baixo tem que continuar byte a byte onde estava (M5).
    sufixo = "" if perfil.familia == "baixo" else f".{instrumento}"
    cache_de_notas = cache_dir / asset.source_id / f"notas{sufixo}.jsonl"
    if bateria:
        parte = _parte_de_bateria(todas, perfil, asset, bpm, andamento, relator, cache_de_notas)
    elif guitarra:
        parte = _parte_de_guitarra(
            todas, perfil, asset, bpm, andamento, tuning,
            atribuidor_de_acordes or ViterbiAcordes(), relator, cache_de_notas,
        )
    else:
        parte = _parte_de_baixo(
            todas, stem, asset, bpm, andamento, tuning,
            assigner or ViterbiFretAssigner(), relator, cache_de_notas,
        )

    # O tom vem das notas que vão para a partitura, e a armadura só é escrita
    # quando a estimativa se sustenta: armadura errada imprime mais bequadro do
    # que armadura nenhuma (ADR-031). `tom` informado não passa por margem.
    # A bateria não tem tom: nem estimado, nem informado.
    tonalidade = None if bateria else tom_de_texto(tom) if tom else estimar_tom(parte.mantidas)
    armadura = tonalidade.armadura if tonalidade else None
    if exporters is None and guitarra:
        exporters = {
            "gp5": Gp5Exporter(
                bpm=parte.bpm, armadura=armadura, titulo=asset.title, faixa="Guitarra",
                programa_gm=perfil.programa_gm, acordes=True,
            ),
            "musicxml": MusicXmlExporter(
                bpm=parte.bpm, armadura=armadura, titulo=asset.title, familia="guitarra",
                programa_gm=perfil.programa_gm,
            ),
        }
    exporters = exporters or {
        "gp5": Gp5Exporter(bpm=parte.bpm, armadura=armadura, titulo=asset.title),
        "musicxml": MusicXmlExporter(bpm=parte.bpm, armadura=armadura, titulo=asset.title),
    }

    # Uma pasta por música, e o nome repetido dentro dela (ADR-037): oito músicas
    # em `out/` plano são quarenta arquivos intercalados, e o arquivo que sai da
    # pasta continua dizendo de que música é.
    nome = nome_de_arquivo(asset)
    pasta = out_dir / nome
    pasta.mkdir(parents=True, exist_ok=True)
    if bateria:
        relator.inicia("exportando a partitura", "gp5, musicxml")
        percussao: dict[str, ExportadorDePercussao] = {
            "gp5": Gp5PercussaoExporter(bpm=parte.bpm, titulo=asset.title),
            "musicxml": MusicXmlPercussaoExporter(bpm=parte.bpm, titulo=asset.title),
        }
        artefatos = {
            formato: exportador.exportar(parte.ataques, pasta / f"{nome}{sufixo}.{formato}")
            for formato, exportador in percussao.items()
        }
    else:
        relator.inicia("exportando a partitura", ", ".join(exporters))
        artefatos = {
            formato: exportador.export(parte.tabs, pasta / f"{nome}{sufixo}.{formato}", tuning)
            for formato, exportador in exporters.items()
        }

    do_stem = _STEM_EM_PORTUGUES[perfil.stem]
    relator.inicia("copiando os áudios", f"mix, {do_stem} e playback")
    # Cópia, e não atalho para o cache: a pasta de saída é o que você abre e move,
    # e ela não pode depender de um diretório nomeado por hash continuar existindo.
    # O playback é opcional no contrato do `Separator` — quem dubla a separação não
    # é obrigado a produzi-lo para exercitar o resto.
    audios = [("mix", asset.wav), (do_stem, stem)]
    if (playback := stems.get(f"no_{perfil.stem}")) is not None:
        audios.append((f"sem-{do_stem}", playback))
    for chave, origem in audios:
        artefatos[chave] = Path(shutil.copy2(origem, pasta / f"{nome}.{chave}.wav"))

    relator.inicia("auralizando", "original num canal, transcrição no outro")
    # Depende de fluidsynth e de soundfont, e nenhum dos dois vale os minutos de
    # CPU já gastos: a falha vira relato (ADR-014). As notas são as do tempo do
    # áudio — a grade da partitura dessincronizaria a comparação.
    falha = None
    try:
        artefatos["aural"] = auralizar(
            asset.wav, parte.no_audio, pasta / f"{nome}{sufixo}.aural.wav",
            programa=perfil.programa_gm, percussao=bateria,
        )
    except (AuralizacaoError, ValueError) as erro:
        falha = str(erro)
    return Resultado(
        falha_na_auralizacao=falha,
        trechos_sem_baixo=parte.sem_baixo,
        bpm=parte.bpm,
        tonalidade=tonalidade,
        andamento=andamento,
        desdobrado=parte.base != float(bpm),
        asset=asset,
        stem=stem,
        artefatos=artefatos,
        notas=len(parte.ataques) if bateria else len(parte.mantidas),
        rotulos=dict(rotulos),
        descartadas=parte.descartadas,
        fora_do_braco=parte.fora,
        avisos_de_oitava=parte.avisos,
        instrumento=instrumento,
        erro_de_rotulo=parte.erro_de_rotulo,
        contaminacao=parte.contaminacao,
        acordes_impossiveis=parte.impossiveis,
        ataques_descartados=parte.ataques_descartados,
    )


def _parte_de_baixo(
    todas: list[NoteEvent],
    stem: Path,
    asset: AudioAsset,
    bpm: float,
    andamento: Andamento | None,
    tuning: tuple[int, ...],
    assigner: FretAssigner,
    relator: Progresso,
    cache_de_notas: Path,
) -> _Parte:
    """Linha monofônica: filtro de rótulos com readmissão, uma nota por tique."""
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
    gravar(no_audio, cache_de_notas)
    relator.inicia("posicionando no braço")
    return _Parte(
        tabs=assigner.assign(mantidas, tuning),
        mantidas=mantidas,
        no_audio=no_audio,
        bpm=andamento_fino,
        base=base,
        descartadas=descartadas,
        fora=fora,
        avisos=avisos,
        sem_baixo=sem_baixo,
    )


def _parte_de_guitarra(
    todas: list[NoteEvent],
    perfil: PerfilInstrumento,
    asset: AudioAsset,
    bpm: float,
    andamento: Andamento | None,
    tuning: tuple[int, ...],
    atribuidor: AtribuidorDeAcordes,
    relator: Progresso,
    cache_de_notas: Path,
) -> _Parte:
    """Acordes do perfil: nada de readmissão, monofonização nem conferência de oitava.

    A readmissão existe porque o baixo é o único instrumento do stem `bass`; no
    `other` há guitarras e pianos juntos, e o que não tem o rótulo do perfil é outro
    instrumento. A conferência de oitava sonda a fundamental de **uma** nota no stem,
    o que um acorde não tem. O que fica de fora é contado, por rótulo, em duas
    colunas: outra guitarra (erro de rótulo) e outra família (contaminação).
    """
    do_perfil = [n for n in todas if n.instrument in perfil.rotulos]
    if not do_perfil:
        raise ValueError(
            f"nenhuma nota com {sorted(perfil.rotulos)} em {asset.title!r}: o transcritor "
            f"devolveu {dict(Counter(n.instrument for n in todas)) or 'nada'}"
        )
    da_familia = frozenset().union(
        *(p.rotulos for p in PERFIS.values() if p.familia == perfil.familia)
    )
    erro_de_rotulo = Counter(
        n.instrument for n in todas if n.instrument in da_familia - perfil.rotulos
    )
    contaminacao = Counter(n.instrument for n in todas if n.instrument not in da_familia)

    relator.inicia("ajustando a grade rítmica")
    # Um ataque por acorde: seis notas simultâneas contadas uma a uma parecem cinco
    # colisões, e o desdobramento dobraria o andamento à toa (ADR-024).
    onsets = inicios_de_acorde(do_perfil)
    base = desdobrar(onsets, bpm) if andamento else float(bpm)
    andamento_fino, fase = ajustar(onsets, base, faixa=None if andamento else 0.0)
    recuo = recuo_de_fase(do_perfil, andamento_fino, fase)
    # Unir pelo tique ANTES de posicionar, pela mesma razão de deslocar antes de
    # monofonizar no baixo: a janela do posicionador e a grade do exportador têm
    # que ver o mesmo acorde, senão dois acordes no mesmo tique dividem uma corda e
    # o GP5 os recusa depois dos minutos de CPU.
    na_grade = unir_por_tique(deslocar(do_perfil, recuo), andamento_fino)
    relator.inicia("posicionando no braço")
    posicionamento = atribuidor.posicionar(na_grade, tuning)
    mantidas = [t.event for t in posicionamento.tab]
    # O cache e a auralização levam o acorde no primeiro ataque do seu tique: a
    # diferença para o áudio é menor que uma semicolcheia, que a grade não distingue.
    no_audio = deslocar(mantidas, -recuo)
    gravar(no_audio, cache_de_notas)
    return _Parte(
        tabs=list(posicionamento.tab),
        mantidas=mantidas,
        no_audio=no_audio,
        bpm=andamento_fino,
        base=base,
        erro_de_rotulo=dict(erro_de_rotulo),
        contaminacao=dict(contaminacao),
        impossiveis=[
            AcordeImpossivel(tuple(deslocar(a.notas, -recuo)), a.motivo)
            for a in posicionamento.impossiveis
        ],
    )


def _parte_de_bateria(
    todas: list[NoteEvent],
    perfil: PerfilInstrumento,
    asset: AudioAsset,
    bpm: float,
    andamento: Andamento | None,
    relator: Progresso,
    cache_de_notas: Path,
) -> _Parte:
    """Ataques do stem `drums`: grade como a da guitarra, descartes por motivo.

    A grade se mede pelo primeiro ataque de cada grupo, pela razão da guitarra: bumbo e
    prato juntos seriam uma colisão e o desdobramento dobraria o andamento (ADR-024).
    O que a partitura não comporta fica fora, relatado, e a música segue (ADR-014).
    """
    do_perfil = [n for n in todas if n.instrument in perfil.rotulos]
    if not do_perfil:
        raise ValueError(
            f"nenhum ataque com {sorted(perfil.rotulos)} em {asset.title!r}: o transcritor "
            f"devolveu {dict(Counter(n.instrument for n in todas)) or 'nada'}"
        )
    contaminacao = Counter(n.instrument for n in todas if n.instrument not in perfil.rotulos)

    relator.inicia("ajustando a grade rítmica")
    onsets = inicios_de_acorde(do_perfil)
    base = desdobrar(onsets, bpm) if andamento else float(bpm)
    andamento_fino, fase = ajustar(onsets, base, faixa=None if andamento else 0.0)
    recuo = recuo_de_fase(do_perfil, andamento_fino, fase)

    na_grade = deslocar(do_perfil, recuo)
    no_mapa = [n for n in na_grade if n.pitch in MAPA_PERCUSSAO]
    ataques = [EventoPercussivo(n.onset_s, n.pitch) for n in no_mapa]
    # Pela identidade, não pela igualdade: a repetida no tique pode ser igual à mantida,
    # e o cache precisa da nota que de fato foi para a partitura.
    nota_de = {id(a): n for a, n in zip(ataques, no_mapa, strict=True)}
    grupos, repetidas = ataques_em_ticks(ataques, andamento_fino)
    # Mais peças que cordas na faixa: ficam as de número GM mais baixo, que no mapa são
    # bumbo e caixa — as que sustentam o compasso — antes de pratos e percussão de mão.
    mantidos = [a for _, _, grupo in grupos for a in grupo[:CORDAS_PERCUSSAO]]
    alem = [a for _, _, grupo in grupos for a in grupo[CORDAS_PERCUSSAO:]]
    fora_do_mapa = [
        EventoPercussivo(n.onset_s, n.pitch) for n in na_grade if n.pitch not in MAPA_PERCUSSAO
    ]

    def no_audio(lista: list[EventoPercussivo]) -> list[EventoPercussivo]:
        return [EventoPercussivo(a.instante_s - recuo, a.peca_gm) for a in lista]

    descartados = {
        motivo: no_audio(lista)
        for motivo, lista in (
            ("repetida no tique", repetidas),
            ("fora do mapa de percussão", fora_do_mapa),
            ("além de seis no tique", alem),
        )
        if lista
    }
    notas_no_audio = sorted(
        deslocar([nota_de[id(a)] for a in mantidos], -recuo), key=lambda n: (n.onset_s, n.pitch)
    )
    gravar(notas_no_audio, cache_de_notas)
    return _Parte(
        tabs=[],
        mantidas=[],
        no_audio=notas_no_audio,
        bpm=andamento_fino,
        base=base,
        contaminacao=dict(contaminacao),
        ataques=mantidos,
        ataques_descartados=descartados,
    )
