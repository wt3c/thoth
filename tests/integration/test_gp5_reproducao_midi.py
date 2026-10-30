"""GP5 → MuseScore real → MIDI: o arquivo precisa tocar no tempo declarado."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pretty_midi
import pytest

from tests.integration.test_quantizacao_ponta_a_ponta import BPM, LINHA, _referencia
from thoth.adapters.export.gp5 import Gp5Exporter
from thoth.domain.models import TUNING_BASS_4
from thoth.services.fretboard import ViterbiFretAssigner
from thoth.services.rhythm import COMPASSO
from thoth.services.tab_referencia import ler_tab

pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(shutil.which("mscore") is None, reason="MuseScore ausente"),
]


@pytest.mark.parametrize("trocar_andamento", [False, True])
def test_midi_do_gp5_preserva_ataques_pausas_ligaduras_e_andamento(
    tmp_path: Path,
    trocar_andamento: bool,
) -> None:
    """Reutiliza a fixture canônica, sem reescrever suas treze notas de memória."""
    tabs = ViterbiFretAssigner().assign(_referencia(), TUNING_BASS_4)
    marcas = ((2 * COMPASSO, 80.0),) if trocar_andamento else ()
    gp5 = Gp5Exporter(bpm=BPM, marcas=marcas).export(
        tabs, tmp_path / "reproducao.gp5", TUNING_BASS_4
    )
    midi = tmp_path / "reproducao.mid"
    subprocess.run(
        ["mscore", str(gp5), "-o", str(midi)],
        check=True,
        capture_output=True,
        timeout=90,
        env=os.environ | {"QT_QPA_PLATFORM": "offscreen"},
    )
    song = pretty_midi.PrettyMIDI(str(midi))
    instrumentos = [i for i in song.instruments if i.notes]
    assert len(instrumentos) == 1
    notas = sorted(instrumentos[0].notes, key=lambda n: (n.start, n.pitch))
    referencia = ler_tab(gp5).notas

    assert [n.pitch for n in notas] == [p for p, _, _ in LINHA]
    assert [n.start for n in notas] == pytest.approx([n.onset_s for n in referencia], abs=0.001)
    # A pausa entre as notas 6 e 7 não pode sumir na reprodução.
    assert notas[7].start - notas[6].end > 0.5
    # Cada sustentação que cruza barra deve continuar soando depois dela.
    for i in (4, 7, 10):
        limite = referencia[i].offset_s - 0.15
        assert notas[i].end > limite
    tempos, bpms = song.get_tempo_changes()
    assert list(bpms) == pytest.approx([BPM, 80.0] if trocar_andamento else [BPM])
    assert list(tempos) == pytest.approx([0.0, 5.0] if trocar_andamento else [0.0])
