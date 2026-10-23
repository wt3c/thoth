"""Os exportadores GP5 produzem o mesmo arquivo de sempre.

Rede de segurança para mudança de desempenho no exportador: o hash dos bytes
gravados a partir de entradas fixas, tirado com o código antes da mudança. O GP5
não tem data nem id sorteado, então nada sai da conta.
"""

from __future__ import annotations

import hashlib
import random
from pathlib import Path

from thoth.adapters.export.gp5 import Gp5Exporter, Gp5PercussaoExporter
from thoth.domain.models import TUNING_BASS_4, EventoPercussivo, NoteEvent
from thoth.services.fretboard import ViterbiFretAssigner


def _hash(arquivo: Path) -> str:
    return hashlib.sha256(arquivo.read_bytes()).hexdigest()[:16]


def test_baixo_sai_igual(tmp_path: Path) -> None:
    sorteio = random.Random(1)
    duracoes = [0.17, 0.33, 0.5, 0.67, 1.0, 1.33]
    notas, inicio = [], 0.0
    for _ in range(120):
        altura = sorteio.randint(28, 60)
        fim = inicio + sorteio.choice(duracoes)
        notas.append(NoteEvent(altura, inicio, fim, "electric_bass"))
        inicio += sorteio.choice(duracoes)
    tabs = ViterbiFretAssigner().assign(notas, TUNING_BASS_4)

    arquivo = Gp5Exporter(bpm=90, titulo="Estável").export(tabs, tmp_path / "b.gp5", TUNING_BASS_4)

    assert _hash(arquivo) == "57cebbab7be84036"


def test_bateria_sai_igual(tmp_path: Path) -> None:
    sorteio = random.Random(2)
    ataques = [
        EventoPercussivo(round(sorteio.randrange(256) / 6, 3), sorteio.choice([36, 38, 42, 46, 49]))
        for _ in range(200)
    ]

    arquivo = Gp5PercussaoExporter(bpm=90, titulo="Estável").exportar(ataques, tmp_path / "d.gp5")

    assert _hash(arquivo) == "75c4a562852d7a5c"
