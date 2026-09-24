"""Fixtures sintéticas de baixo com ground truth conhecido.

Nasceram na Fase 0 (Camada 1 do ADR-006) e viraram teste de regressão. O áudio
**não** é versionado (ADR-005): é regerado a cada execução a partir do MIDI, que
é a própria referência.

Duas exigências descobertas medindo, não supondo:

- **Soundfont, não onda sintética.** Seno ou triangular fazem o MuScriptor
  devolver zero notas — material fora da distribuição de treino.
- **Normalizar o pico.** O fluidsynth rende a -36 dB de média; nesse nível o
  modelo erra por volume e a medição culpa o modelo pelo motivo errado.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pretty_midi

BAIXO = 33  # GM: Electric Bass (finger)
PIANO = 0  # GM: Acoustic Grand — intruso do teste de vazamento
BPM = 90
TEMPO = 60.0 / BPM
SOUNDFONT = Path("/usr/share/soundfonts/FluidR3_GM.sf2")


def _sequencia(alturas: list[int], passo: float) -> list[tuple[int, float, float]]:
    return [(p, i * passo, passo) for i, p in enumerate(alturas)]


def _midi(
    notas: list[tuple[int, float, float]], extra: pretty_midi.Instrument | None = None
) -> pretty_midi.PrettyMIDI:
    pm = pretty_midi.PrettyMIDI(initial_tempo=BPM)
    inst = pretty_midi.Instrument(program=BAIXO)
    for pitch, inicio, dur in notas:
        inst.notes.append(
            pretty_midi.Note(velocity=100, pitch=pitch, start=inicio, end=inicio + dur * 0.9)
        )
    pm.instruments.append(inst)
    if extra is not None:
        pm.instruments.append(extra)
    return pm


def _com_piano() -> pretty_midi.PrettyMIDI:
    """Baixo + piano no registro médio: mede vazamento de conteúdo alheio."""
    piano = pretty_midi.Instrument(program=PIANO)
    acordes = [(60, 64, 67), (62, 65, 69), (59, 62, 67), (60, 64, 67)] * 2
    for i, acorde in enumerate(acordes):
        for altura in acorde:
            piano.notes.append(
                pretty_midi.Note(
                    velocity=80, pitch=altura,
                    start=i * TEMPO * 2, end=i * TEMPO * 2 + TEMPO * 1.8,
                )
            )
    return _midi(_sequencia([36, 43, 38, 45, 31, 38, 36, 43] * 2, TEMPO), extra=piano)


#: Cada fixture sonda uma propriedade diferente; nenhuma é decorativa.
FIXTURES = {
    # Caso mais simples possível — escala de dó maior em semínimas.
    "escala": _midi(
        _sequencia([36, 38, 40, 41, 43, 45, 47, 48, 47, 45, 43, 41, 40, 38, 36], TEMPO)
    ),
    # Walking bass sobre II-V-I.
    "walking": _midi(_sequencia([38, 41, 43, 45, 31, 35, 38, 40, 36, 40, 43, 45, 36, 33, 31, 36],
                                TEMPO)),
    # Semicolcheias — estressa resolução temporal de onset.
    "groove16": _midi(_sequencia([36, 36, 43, 36, 38, 36, 43, 41, 36, 36, 43, 36, 41, 40, 38, 36]
                                 * 2, TEMPO / 4)),
    # Região grave de 5 cordas (B0..E1) — o caso que não pode ser clampado.
    "graves": _midi(_sequencia([23, 24, 26, 28, 26, 24, 23, 25, 27, 23], TEMPO)),
    # Saltos de oitava — sonda específica de erro de oitava.
    "oitavas": _midi(_sequencia([36, 48, 36, 48, 31, 43, 31, 43, 33, 45, 33, 45], TEMPO)),
    # Baixo + piano: quanto do piano entra no canal do baixo.
    "misto": _com_piano(),
}


def _pico_dbfs(wav: Path) -> float:
    saida = subprocess.run(
        ["ffmpeg", "-nostdin", "-i", str(wav), "-af", "volumedetect", "-f", "null", "-"],
        capture_output=True, text=True, check=True,
    ).stderr
    achado = re.search(r"max_volume: (-?[\d.]+) dB", saida)
    if achado is None:
        raise RuntimeError(f"ffmpeg não reportou max_volume para {wav}")
    return float(achado.group(1))


def renderizar(nome: str, destino: Path) -> tuple[Path, pretty_midi.PrettyMIDI]:
    """Devolve o WAV normalizado a -1 dBFS de pico e o MIDI que é sua referência."""
    midi = FIXTURES[nome]
    mid = destino / f"{nome}.mid"
    bruto = destino / f"{nome}.bruto.wav"
    wav = destino / f"{nome}.wav"
    midi.write(str(mid))
    subprocess.run(
        ["fluidsynth", "-ni", "-q", "-F", str(bruto), "-r", "44100", str(SOUNDFONT), str(mid)],
        check=True, capture_output=True,
    )
    ganho = -1.0 - _pico_dbfs(bruto)
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(bruto),
         "-af", f"volume={ganho:.2f}dB", str(wav)],
        check=True,
    )
    return wav, midi
