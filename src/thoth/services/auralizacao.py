"""Original num ouvido, transcrição no outro (Fase 0, Camada 2 do ADR-006).

É o teste de qualidade que não precisa de tab humana nem de treino musical: se a
transcrição descola do original, qualquer pessoa ouve em dez segundos. Números de
F1 dizem quanto se errou; a auralização diz *onde*.

Duas escolhas que parecem detalhe e não são:

- **Soundfont, não onda sintética.** Um seno em E1 (41 Hz) é quase inaudível em
  caixa de notebook. O baixo GM traz harmônicos, e é por eles que se reconhece a
  altura no meio da música.
- **Mesmo comprimento do original.** O canal da transcrição é esticado com
  silêncio até o fim: truncar esconderia justamente o trecho final, onde o erro
  de andamento mais acumula.
- **Mesma energia nos dois canais.** Sem isso a comparação vira teste de volume:
  a transcrição saía até 23 dB abaixo do original, e a música de baixo mais alto
  na mixagem soava "melhor transcrita" por ser mais audível.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pretty_midi
import soundfile as sf

from thoth.domain.models import NoteEvent
from thoth.processos import ErroDeProcesso, rodar

BAIXO_GM = 33  # Electric Bass (finger)
SOUNDFONT = Path("/usr/share/soundfonts/FluidR3_GM.sf2")
TAXA = 44_100


class AuralizacaoError(RuntimeError):
    """Falta uma ferramenta externa ou ela falhou."""


def _midi(notas: list[NoteEvent], destino: Path, programa: int = BAIXO_GM) -> Path:
    """As notas já estão em tempo absoluto, então o andamento do MIDI é irrelevante."""
    pm = pretty_midi.PrettyMIDI()
    instrumento = pretty_midi.Instrument(program=programa)
    instrumento.notes.extend(
        pretty_midi.Note(velocity=100, pitch=n.pitch, start=n.onset_s, end=n.offset_s)
        for n in notas
    )
    pm.instruments.append(instrumento)
    pm.write(str(destino))
    return destino


def _renderizar(mid: Path, destino: Path) -> Path:
    if not SOUNDFONT.exists():
        raise AuralizacaoError(f"soundfont ausente: {SOUNDFONT}")
    try:
        rodar(
            ["fluidsynth", "-ni", "-q", "-F", str(destino), "-r", str(TAXA),
             str(SOUNDFONT), str(mid)]
        )
    except FileNotFoundError as erro:  # pragma: no cover — depende do SO
        raise AuralizacaoError("fluidsynth não encontrado") from erro
    except ErroDeProcesso as erro:
        raise AuralizacaoError(str(erro)) from erro
    return destino


def _duracao(caminho: Path) -> float:
    info = sf.info(str(caminho))
    return float(info.frames) / float(info.samplerate)


def _para_mono(canais: int) -> str:
    """Média dos canais escrita à mão — a mesma conta que `_energia` faz.

    `aformat=channel_layouts=stereo` parece inócuo numa entrada mono e não é: o
    upmix do ffmpeg preserva energia dividindo cada canal por √2, e esses 3 dB
    somem do canal do original sem aparecer em lugar nenhum (medido: 0,0884 →
    0,0625). Sem ele, `pan` sozinho tem ganho unitário e coincide com a medição.
    """
    pesos = "+".join(f"{1 / canais:.6f}*c{c}" for c in range(canais))
    return f"pan=mono|c0={pesos}"


def _energia(caminho: Path, janela_s: float) -> tuple[float, float]:
    """RMS e pico do arquivo reduzido a mono, dentro da janela que vai ser escrita.

    A janela é a duração do original, que é o que o `-shortest` deixa passar.
    Medir o arquivo inteiro contaria a cauda do soundfont — quatro segundos onde
    saem dois — e o ganho sairia alto na mesma proporção. Pelo mesmo motivo a
    média divide pela janela, não pelo que foi lido: o silêncio que o `apad`
    completa entra no canal e puxa a energia dele para baixo.

    Em blocos porque o original é a música inteira: 12 minutos em float64 não
    precisam caber na memória só para se medir a média de um quadrado.
    """
    info = sf.info(str(caminho))
    alvo = round(janela_s * float(info.samplerate))
    if alvo <= 0:
        return 0.0, 0.0
    soma, pico = 0.0, 0.0
    for bloco in sf.blocks(
        str(caminho), blocksize=1 << 20, dtype="float64", always_2d=True, frames=alvo
    ):
        mono = bloco.mean(axis=1)
        soma += float((mono**2).sum())
        pico = max(pico, float(np.abs(mono).max(initial=0.0)))
    return (soma / alvo) ** 0.5, pico


def _ganhos(original: Path, rendido: Path) -> tuple[float, float]:
    """Fatores para os dois canais: mesma energia, sem estourar.

    A transcrição sobe até a energia do original — e não o contrário, que deixaria
    tudo no volume baixíssimo do soundfont. Se subir fizer o pico passar de 1, os
    **dois** canais descem na mesma proporção: o que precisa ser preservado é a
    razão entre eles, não o nível absoluto.
    """
    janela = _duracao(original)
    rms_esq, pico_esq = _energia(original, janela)
    rms_dir, pico_dir = _energia(rendido, janela)
    if not rms_dir or not rms_esq:
        return 1.0, 1.0
    ganho = rms_esq / rms_dir
    pico = max(pico_esq, pico_dir * ganho)
    escala = 0.99 / pico if pico > 0.99 else 1.0
    return escala, ganho * escala


def auralizar(
    original: Path, notas: list[NoteEvent], destino: Path, programa: int = BAIXO_GM
) -> Path:
    """WAV estéreo: original à esquerda, transcrição à direita.

    Ambos os canais são reduzidos a mono antes de ir cada um para o seu lado — o
    original costuma ser estéreo, e misturar os dois lados dele no canal esquerdo
    preserva tudo que se precisa ouvir para comparar.
    """
    if not notas:
        raise ValueError("sem notas para auralizar")

    destino.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        mid = _midi(notas, Path(tmp) / "notas.mid", programa)
        rendido = _renderizar(mid, Path(tmp) / "notas.wav")
        g_esq, g_dir = _ganhos(original, rendido)
        # `apad` + `shortest` iguala o canal curto ao longo sem cortar nenhum dos dois.
        filtro = (
            f"[0:a]{_para_mono(sf.info(str(original)).channels)},"
            f"aresample={TAXA},volume={g_esq:.6f}[esq];"
            f"[1:a]{_para_mono(sf.info(str(rendido)).channels)},"
            f"aresample={TAXA},apad,volume={g_dir:.6f}[dir];"
            "[esq][dir]join=inputs=2:channel_layout=stereo[saida]"
        )
        try:
            rodar(
                ["ffmpeg", "-y", "-loglevel", "error", "-i", str(original), "-i", str(rendido),
                 "-filter_complex", filtro, "-map", "[saida]", "-shortest", str(destino)]
            )
        except ErroDeProcesso as erro:
            raise AuralizacaoError(str(erro)) from erro
    return destino
