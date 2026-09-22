"""Notas posicionadas → arquivo GP5, via PyGuitarPro.

**O andamento é entrada, não estimativa.** O Thoth ainda não estima tempo (o
checkpoint do Beat This! está inacessível — ver C2 no `todo.md`), e o GP5 não
guarda segundos: ele guarda compassos, tempos e figuras. Sem BPM não há como
escrever o arquivo, então ele é parâmetro explícito em vez de um palpite
silencioso que sairia como tablatura errada.

Limitações assumidas desta primeira versão, todas visíveis na leitura:

- compasso fixo 4/4 e grade de semicolcheia;
- sem ligaduras: uma nota mais longa que a maior figura representável vira a
  figura mais longa que couber, e o resto vira pausa. O *ataque* — que é o que
  se lê numa tablatura — fica exato;
- linha monofônica (ADR-012): notas simultâneas são recusadas, não empilhadas.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import guitarpro as gp

from thoth.domain.models import TabNote
from thoth.domain.ports import Exporter
from thoth.services.notas import nome_da_nota
from thoth.services.rhythm import COMPASSO, GRADE, PPQ, eventos

BAIXO_GM = 33  # Electric Bass (finger)

assert gp.Duration.quarterTime // 4 == GRADE, "a grade tem que casar com o PPQ do GP5"

#: Figuras representáveis, da mais longa para a mais curta, com as pontuadas.
_FIGURAS = sorted(
    (
        (int(PPQ * 4 / valor * (1.5 if pontuada else 1.0)), valor, pontuada)
        for valor in (1, 2, 4, 8, 16)
        for pontuada in (False, True)
    ),
    reverse=True,
)


def _decompor(ticks: int) -> list[tuple[int, bool]]:
    """Maior figura que cabe, repetidamente. Nunca devolve lista vazia para `ticks > 0`."""
    figuras = []
    while ticks >= GRADE:
        for duracao, valor, pontuada in _FIGURAS:
            if duracao <= ticks:
                figuras.append((valor, pontuada))
                ticks -= duracao
                break
        else:  # pragma: no cover — GRADE é a menor figura, então sempre há uma
            break
    return figuras


@dataclass(frozen=True, slots=True)
class Gp5Exporter:
    """Implementa o `Exporter`. Round-trip verificado contra o próprio PyGuitarPro."""

    bpm: int = 120
    titulo: str = "Thoth"

    def export(self, notes: list[TabNote], out: Path, tuning: tuple[int, ...]) -> Path:
        if not notes:
            raise ValueError("sem notas para exportar")

        song = gp.Song(title=self.titulo, tempo=self.bpm)
        song.tracks.clear()
        track = gp.Track(song, number=1, name="Baixo")
        # O GP numera as cordas da mais aguda para a mais grave; nós, o contrário.
        track.strings = [gp.GuitarString(i + 1, v) for i, v in enumerate(reversed(tuning))]
        track.channel.instrument = BAIXO_GM
        track.measures.clear()  # o construtor já cria um compasso a partir dos headers
        song.tracks.append(track)

        marcados = eventos(notes, self.bpm)
        total = (marcados[-1][0] + marcados[-1][1] - 1) // COMPASSO + 1
        cursor = 0
        for numero in range(total):
            while numero >= len(song.measureHeaders):
                song.addMeasureHeader(gp.MeasureHeader(number=len(song.measureHeaders) + 1))
            medida = gp.Measure(track, song.measureHeaders[numero])
            voz = gp.Voice(medida)
            fim_do_compasso = (numero + 1) * COMPASSO

            for inicio, duracao, tab in marcados:
                if not numero * COMPASSO <= inicio < fim_do_compasso:
                    continue
                for valor, pontuada in _decompor(inicio - cursor):
                    voz.beats.append(self._pausa(voz, valor, pontuada))
                figuras = _decompor(duracao)
                valor, pontuada = figuras[0]
                voz.beats.append(self._nota(voz, tab, len(tuning), valor, pontuada))
                for valor, pontuada in figuras[1:]:
                    voz.beats.append(self._pausa(voz, valor, pontuada))
                cursor = inicio + duracao

            for valor, pontuada in _decompor(fim_do_compasso - cursor):
                voz.beats.append(self._pausa(voz, valor, pontuada))
            cursor = fim_do_compasso

            medida.voices = [voz, *(gp.Voice(medida) for _ in range(3))]
            track.measures.append(medida)

        out.parent.mkdir(parents=True, exist_ok=True)
        gp.write(song, str(out))
        return out

    @staticmethod
    def _pausa(voz: gp.Voice, valor: int, pontuada: bool) -> gp.Beat:
        beat = gp.Beat(voz, duration=gp.Duration(value=valor, isDotted=pontuada))
        beat.status = gp.BeatStatus.rest
        return beat

    @staticmethod
    def _nota(voz: gp.Voice, tab: TabNote, cordas: int, valor: int, pontuada: bool) -> gp.Beat:
        beat = gp.Beat(voz, duration=gp.Duration(value=valor, isDotted=pontuada))
        beat.notes.append(gp.Note(beat, value=tab.fret, string=cordas - tab.string, velocity=95))
        # Sem isto o beat sai `empty` (o default do PyGuitarPro): o leitor trata beat
        # vazio como duração zero, e todos os beats do compasso colapsam num só.
        beat.status = gp.BeatStatus.normal
        beat.text = nome_da_nota(tab.event.pitch)
        return beat


if TYPE_CHECKING:  # pragma: no cover — trava a assinatura contra o Protocol
    _: Exporter = Gp5Exporter()
