"""Calibração do aviso de oitava travada nos dados reais de *Equus* (Fase 0).

A janela do ADR-029 derrubou a detecção de 12 para 2 das 12 notas erradas conhecidas
sem nenhum teste perceber: a calibração só existia como número no ADR-030. Este teste
refaz a conta da Fase 0 — mesmos arquivos, mesmo pareamento — e trava o resultado.

Os arquivos ficam fora do repositório (áudio de terceiro, ADR-005); sem eles, `skip`.
O rótulo vem da concordância entre duas transcrições da Fase 0: a do stem e a da mix.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np
import pretty_midi
import pytest

from thoth.domain.models import NoteEvent
from thoth.services.octave_check import verificar_oitavas

FASE0 = Path.home() / "thoth-fase0"
ARQUIVOS = [FASE0 / "neo_STEM.wav", FASE0 / "neo_STEM.mid", FASE0 / "neo_MIX.mid"]

#: Medido com a janela de piso 0,3 s (emenda do ADR-029): 8 de 12 e 4 de 127, sem folga —
#: áudio, MIDI e código são fixos, a conta é determinística.
PEGA_MINIMO = 8
ALARME_MAXIMO = 4

pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(
        not all(a.exists() for a in ARQUIVOS), reason=f"arquivos da Fase 0 ausentes em {FASE0}"
    ),
]


def _notas_de_baixo(mid: Path) -> list[tuple[float, float, int]]:
    """Programas 32 a 39 do General MIDI, fora da percussão."""
    return [
        (n.start, n.end, n.pitch)
        for ins in pretty_midi.PrettyMIDI(str(mid)).instruments
        if 32 <= ins.program <= 39 and not ins.is_drum
        for n in ins.notes
    ]


def _rotular() -> tuple[list[NoteEvent], np.ndarray]:
    """Nota do stem com ataque a até 50 ms de uma da mix: concorda, ou B0 onde a mix diz B1."""
    mix = _notas_de_baixo(FASE0 / "neo_MIX.mid")
    ataques_mix = np.array([m[0] for m in mix])
    alturas_mix = np.array([m[2] for m in mix])
    eventos, errada = [], []
    for inicio, fim, altura in _notas_de_baixo(FASE0 / "neo_STEM.mid"):
        perto = alturas_mix[np.abs(ataques_mix - inicio) <= 0.05]
        if altura in perto:
            errada.append(False)
        elif altura == 23 and 35 in perto:
            errada.append(True)
        else:
            continue
        eventos.append(NoteEvent(altura, inicio, fim, "electric_bass"))
    return eventos, np.array(errada)


def test_aviso_de_oitava_no_equus(tmp_path: Path) -> None:
    # Canal esquerdo, como na Fase 0.
    stem = tmp_path / "stem_L.wav"
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(ARQUIVOS[0]),
         "-af", "pan=mono|c0=c0", "-c:a", "pcm_s16le", str(stem)],
        check=True,
    )
    eventos, errada = _rotular()
    assert (int((~errada).sum()), int(errada.sum())) == (127, 12), "pareamento da Fase 0 mudou"

    avisadas = {(a.event.onset_s, a.event.pitch) for a in verificar_oitavas(stem, eventos)}
    avisou = np.array([(e.onset_s, e.pitch) in avisadas for e in eventos])
    pega, alarme = int(avisou[errada].sum()), int(avisou[~errada].sum())

    print(f"pega {pega}/12 (piso {PEGA_MINIMO}) · alarme {alarme}/127 (teto {ALARME_MAXIMO})")
    assert pega >= PEGA_MINIMO
    assert alarme <= ALARME_MAXIMO
