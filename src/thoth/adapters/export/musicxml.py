"""Notas posicionadas → MusicXML, via music21.

Partitura, não tablatura: serve para ler no MuseScore e para quem lê música
escrita. Corda e traste viajam junto como indicações, então a informação da
tablatura não se perde no caminho.

A clave é `Bass8vb` porque o baixo é instrumento transpositor: soa uma oitava
abaixo do escrito. Com clave de Fá comum, tudo sairia uma oitava acima.

Ao contrário do GP5, aqui não decomponho figuras à mão — o `makeNotation` do
music21 resolve ligaduras e pausas a partir dos offsets.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from music21 import (
    articulations,
    clef,
    instrument,
    key,
    metadata,
    meter,
    note,
    stream,
    tempo,
)

from thoth.domain.models import TabNote
from thoth.domain.ports import Exporter
from thoth.services.notas import nome_da_nota
from thoth.services.rhythm import PPQ, eventos


@dataclass(frozen=True, slots=True)
class MusicXmlExporter:
    """Implementa o `Exporter`. Round-trip verificado contra o próprio music21."""

    bpm: float = 120
    titulo: str = "Thoth"
    """Título impresso na partitura. O default é marca d'água de quem não informou:
    quem transcreve uma música tem o nome dela, e o pipeline passa o do `AudioAsset`."""
    armadura: int | None = None
    """Armadura estimada, ou `None` — que é o que a partitura tinha até o ADR-031.
    Armadura errada é pior que armadura nenhuma, então quem estima decide antes."""

    def export(self, notes: list[TabNote], out: Path, tuning: tuple[int, ...]) -> Path:
        if not notes:
            raise ValueError("sem notas para exportar")

        parte = stream.Part()
        parte.insert(0, instrument.ElectricBass())
        parte.insert(0, clef.Bass8vbClef())
        parte.insert(0, meter.TimeSignature("4/4"))
        if self.armadura is not None:
            parte.insert(0, key.KeySignature(self.armadura))
        parte.insert(0, tempo.MetronomeMark(number=round(self.bpm)))

        for inicio, duracao, tab in eventos(notes, self.bpm):
            n = note.Note(tab.event.pitch, quarterLength=duracao / PPQ)
            n.lyric = nome_da_nota(tab.event.pitch, bemois=(self.armadura or 0) < 0)
            n.articulations = [
                # MusicXML numera as cordas como o GP: 1 = mais aguda.
                articulations.StringIndication(len(tuning) - tab.string),
                articulations.FretIndication(tab.fret),
            ]
            parte.insert(inicio / PPQ, n)

        score = stream.Score()
        score.insert(0, parte)
        # Sem `Metadata` explícita o music21 imprime a partitura anônima. Era o que
        # acontecia: o nome da música chegava ao nome do arquivo e não ao papel.
        score.insert(0, metadata.Metadata(title=self.titulo))
        pronto = score.makeNotation()

        out.parent.mkdir(parents=True, exist_ok=True)
        pronto.write("musicxml", fp=str(out))
        return out


if TYPE_CHECKING:  # pragma: no cover — trava a assinatura contra o Protocol
    _: Exporter = MusicXmlExporter()
