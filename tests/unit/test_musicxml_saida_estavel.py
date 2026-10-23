"""Os três exportadores MusicXML produzem o mesmo arquivo de sempre.

Rede de segurança para mudança de desempenho no exportador: o hash do XML gerado
por entradas fixas, gravado com o código antes da mudança. Saem da conta só a data de
codificação e os ids de parte e instrumento, que o music21 sorteia a cada execução;
tudo o mais precisa sair byte a byte igual.
"""

from __future__ import annotations

import hashlib
import random
import re
from pathlib import Path

from thoth.adapters.export.musicxml import (
    MusicXmlExporter,
    MusicXmlPercussaoExporter,
    MusicXmlPianoExporter,
)
from thoth.domain.models import TUNING_BASS_4, EventoPercussivo, NoteEvent
from thoth.services.fretboard import ViterbiFretAssigner

BPM = 90


def _hash(arquivo: Path) -> str:
    xml = re.sub(r"<encoding-date>.*?</encoding-date>", "", arquivo.read_text())
    xml = re.sub(r'(id|part|instrument)="[PI][0-9a-f]{32}"', r'\1=""', xml)
    return hashlib.sha256(xml.encode()).hexdigest()[:16]


def _notas(sorteio: random.Random, faixa: tuple[int, int], rotulo: str) -> list[NoteEvent]:
    duracoes = [0.17, 0.33, 0.5, 0.67, 1.0, 1.33]
    notas, inicio = [], 0.0
    for _ in range(120):
        notas.append(
            NoteEvent(sorteio.randint(*faixa), inicio, inicio + sorteio.choice(duracoes), rotulo)
        )
        inicio += sorteio.choice(duracoes)
    return notas


def test_baixo_sai_igual(tmp_path: Path) -> None:
    tabs = ViterbiFretAssigner().assign(
        _notas(random.Random(1), (28, 60), "electric_bass"), TUNING_BASS_4
    )
    arquivo = MusicXmlExporter(bpm=BPM, titulo="Estável").export(
        tabs, tmp_path / "b.musicxml", TUNING_BASS_4
    )

    assert _hash(arquivo) == "5651cf38b8121062"


def test_bateria_sai_igual(tmp_path: Path) -> None:
    sorteio = random.Random(2)
    ataques = [
        EventoPercussivo(round(sorteio.randrange(256) / 6, 3), sorteio.choice([36, 38, 42, 46, 49]))
        for _ in range(200)
    ]
    arquivo = MusicXmlPercussaoExporter(bpm=BPM, titulo="Estável").exportar(
        ataques, tmp_path / "d.musicxml"
    )

    assert _hash(arquivo) == "67394d6cd29dd3f0"


def test_piano_sai_igual(tmp_path: Path) -> None:
    sorteio = random.Random(3)
    notas = _notas(sorteio, (40, 84), "acoustic_piano") + _notas(
        sorteio, (36, 72), "acoustic_piano"
    )
    arquivo = MusicXmlPianoExporter(bpm=BPM, titulo="Estável").exportar(
        notas, tmp_path / "p.musicxml"
    )

    assert _hash(arquivo) == "9ddb2f7c17a8867f"
