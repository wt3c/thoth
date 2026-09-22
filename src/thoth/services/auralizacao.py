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
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

import pretty_midi

from thoth.domain.models import NoteEvent

BAIXO_GM = 33  # Electric Bass (finger)
SOUNDFONT = Path("/usr/share/soundfonts/FluidR3_GM.sf2")
TAXA = 44_100


class AuralizacaoError(RuntimeError):
    """Falta uma ferramenta externa ou ela falhou."""


def _midi(notas: list[NoteEvent], destino: Path) -> Path:
    """As notas já estão em tempo absoluto, então o andamento do MIDI é irrelevante."""
    pm = pretty_midi.PrettyMIDI()
    instrumento = pretty_midi.Instrument(program=BAIXO_GM)
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
        subprocess.run(
            ["fluidsynth", "-ni", "-q", "-F", str(destino), "-r", str(TAXA),
             str(SOUNDFONT), str(mid)],
            check=True, capture_output=True,
        )
    except FileNotFoundError as erro:  # pragma: no cover — depende do SO
        raise AuralizacaoError("fluidsynth não encontrado") from erro
    return destino


def auralizar(original: Path, notas: list[NoteEvent], destino: Path) -> Path:
    """WAV estéreo: original à esquerda, transcrição à direita.

    Ambos os canais são reduzidos a mono antes de ir cada um para o seu lado — o
    original costuma ser estéreo, e misturar os dois lados dele no canal esquerdo
    preserva tudo que se precisa ouvir para comparar.
    """
    if not notas:
        raise ValueError("sem notas para auralizar")

    destino.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        rendido = _renderizar(_midi(notas, Path(tmp) / "notas.mid"), Path(tmp) / "notas.wav")
        # `apad` + `shortest` iguala o canal curto ao longo sem cortar nenhum dos dois.
        filtro = (
            f"[0:a]pan=mono|c0=.5*c0+.5*c1,aresample={TAXA}[esq];"
            f"[1:a]pan=mono|c0=c0,aresample={TAXA},apad[dir];"
            "[esq][dir]join=inputs=2:channel_layout=stereo[saida]"
        )
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", str(original), "-i", str(rendido),
             "-filter_complex", filtro, "-map", "[saida]", "-shortest", str(destino)],
            check=True,
        )
    return destino
