"""Notas posicionadas → MusicXML, via music21.

Duas pautas na mesma parte (ADR-035): notação em cima, tablatura embaixo. Antes
daqui o arquivo era só notação, e corda e traste viajavam como indicações que
nenhum leitor desenhava — o MuseScore abria a partitura e a tablatura ficava
implícita no arquivo.

A clave é `Bass8vb` porque o baixo é instrumento transpositor: soa uma oitava
abaixo do escrito. Com clave de Fá comum, tudo sairia uma oitava acima.

Ao contrário do GP5, aqui não decomponho figuras à mão — o `makeNotation` do
music21 resolve ligaduras e pausas a partir dos offsets.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from music21 import (
    articulations,
    beam,
    clef,
    instrument,
    key,
    layout,
    metadata,
    meter,
    note,
    pitch,
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

        posicionadas = list(eventos(notes, self.bpm))
        partitura = self._pauta(posicionadas, tuning, tablatura=False)
        tablatura = self._pauta(posicionadas, tuning, tablatura=True)

        score = stream.Score()
        score.insert(0, partitura)
        score.insert(0, tablatura)
        score.insert(
            0, layout.StaffGroup([partitura, tablatura], symbol="bracket", barTogether=True)
        )
        # Sem `Metadata` explícita o music21 imprime a partitura anônima. Era o que
        # acontecia: o nome da música chegava ao nome do arquivo e não ao papel.
        score.insert(0, metadata.Metadata(title=self.titulo))
        pronto = score.makeNotation()
        _consertar_beams(pronto)

        out.parent.mkdir(parents=True, exist_ok=True)
        pronto.write("musicxml", fp=str(out))
        out.write_text(_com_afinacao(out.read_text(), tuning), encoding="utf-8")
        return out

    def _pauta(
        self,
        posicionadas: list[tuple[int, int, TabNote]],
        tuning: tuple[int, ...],
        *,
        tablatura: bool,
    ) -> stream.PartStaff:
        """Uma das duas pautas. As alturas são as mesmas; muda o que se lê nelas."""
        parte = stream.PartStaff()
        parte.insert(0, meter.TimeSignature("4/4"))
        if tablatura:
            parte.insert(0, clef.TabClef())
            # O music21 10.5 não emite `staff-details`; quem escreve é `_com_afinacao`.
            parte.insert(0, layout.StaffLayout(staffLines=len(tuning)))
        else:
            parte.insert(0, instrument.ElectricBass())
            parte.insert(0, clef.Bass8vbClef())
            parte.insert(0, tempo.MetronomeMark(number=round(self.bpm)))
            if self.armadura is not None:
                parte.insert(0, key.KeySignature(self.armadura))

        for inicio, duracao, tab in posicionadas:
            n = note.Note(tab.event.pitch, quarterLength=duracao / PPQ)
            if tablatura:
                n.articulations = [
                    # MusicXML numera as cordas como o GP: 1 = mais aguda.
                    articulations.StringIndication(len(tuning) - tab.string),
                    articulations.FretIndication(tab.fret),
                ]
            else:
                # O nome só na partitura: na tablatura ele repete o traste ao lado.
                n.lyric = nome_da_nota(tab.event.pitch, bemois=(self.armadura or 0) < 0)
            parte.insert(inicio / PPQ, n)
        # As pausas antes do `makeNotation`, e não depois: ele beameia o que vê, e
        # com o stream cheio de buracos duas notas a meio compasso de distância se
        # veem como vizinhas e saem no mesmo grupo — `end` sem `begin` no nível 2,
        # arquivo mal-formado (ADR-038). Com as pausas na mão, o music21 acerta.
        parte.makeRests(fillGaps=True, inPlace=True)
        return parte


def _consertar_beams(pronto: stream.Score) -> None:
    """Refaz, por semínima, o beaming dos compassos que o music21 escreveu quebrado.

    Forma (B) do ADR-038: com nota cruzando a fronteira de tempo, o music21 10.5
    às vezes escreve `end` sem `begin` — arquivo mal-formado, calado. Só o compasso
    quebrado é refeito (ADR-039): nos que saem certos ele junta, por exemplo,
    colcheia e colcheia pontuada que atravessa o tempo, e isso é notação legítima
    que um beaming por tempo trocaria por duas bandeirolas.

    O refeito é o próprio `getBeams` do music21, chamado um tempo por vez, e
    nenhum grupo atravessa a fronteira. A nota que cruza fica no tempo em que
    começa; sozinha nele, sai com bandeirola. O `getBeams` supõe que a lista
    começa no `measureStartOffset`: o trecho que abre no meio do tempo (depois
    de uma nota que veio cruzando) passa o offset da própria primeira nota, não
    o do tempo — do contrário o nível 2 sai desalinhado.

    O `makeBeams` roda aqui, e não no `write`: o exportador de MusicXML refaz os
    beams de toda pauta que não esteja marcada como beameada, e refaria por cima
    do conserto. Rodá-lo antes e marcar a pauta é o que faz o arquivo sair com o
    que foi examinado.

    Sem vozes: a pauta é monofônica por construção (ADR-014).
    """
    for pauta in pronto.parts:
        pauta.makeBeams(inPlace=True)
        formula: meter.TimeSignature | None = None
        for compasso in pauta.getElementsByClass(stream.Measure):
            # Como o `makeBeams` acha a fórmula: a do compasso, senão a última vista.
            formula = compasso.timeSignature or formula
            if formula is None or not _beams_quebrados(compasso):
                continue
            elementos = list(compasso.notesAndRests)
            for tempo_ in range(int(formula.barDuration.quarterLength)):
                trecho = [e for e in elementos if tempo_ <= e.offset < tempo_ + 1]
                if not trecho:
                    continue
                # Cópias: o `getBeams` só lê durações, mas não mexer no `activeSite`
                # das notas da partitura custa uma linha.
                novos = formula.getBeams(
                    deepcopy(trecho), measureStartOffset=trecho[0].offset
                )
                for elemento, beams in zip(trecho, novos, strict=True):
                    if isinstance(elemento, note.NotRest):
                        elemento.beams = beams or beam.Beams()
        pauta.streamStatus.beams = True


def _beams_quebrados(compasso: stream.Measure) -> bool:
    """A gramática do MusicXML sobre os beams do music21, por nível.

    `start` abre, `continue` e `stop` exigem aberto, `partial` (gancho) é isolado,
    e nada fica aberto no fim do compasso. É o mesmo autômato que os testes rodam
    sobre o XML escrito.
    """
    abertos: dict[int, bool] = {}
    for nota in compasso.notes:
        for b in nota.beams:
            if b.type == "start":
                if abertos.get(b.number):
                    return True
                abertos[b.number] = True
            elif b.type in ("continue", "stop"):
                if not abertos.get(b.number):
                    return True
                abertos[b.number] = b.type == "continue"
    return any(abertos.values())


def _com_afinacao(xml: str, tuning: tuple[int, ...]) -> str:
    """Escreve `staff-details` da pauta 2 — quantas linhas e como estão afinadas.

    Sem isto o leitor não sabe o que fazer com os trastes: o MuseScore cai na
    afinação default e desenha as notas nas cordas erradas.

    A linha 1 é a de BAIXO da tablatura, logo a corda mais grave — a ordem do
    nosso `tuning`. Invertê-la gera arquivo que abre sem erro e mostra outra coisa.
    """
    cordas = []
    for linha, midi in enumerate(tuning, start=1):
        altura = pitch.Pitch(midi)
        alteracao = (
            f"\n            <tuning-alter>{int(altura.alter)}</tuning-alter>"
            if altura.alter
            else ""
        )
        cordas.append(
            f'          <staff-tuning line="{linha}">\n'
            f"            <tuning-step>{altura.step}</tuning-step>{alteracao}\n"
            f"            <tuning-octave>{altura.octave}</tuning-octave>\n"
            f"          </staff-tuning>"
        )
    detalhes = (
        '        <staff-details number="2">\n'
        f"          <staff-lines>{len(tuning)}</staff-lines>\n"
        + "\n".join(cordas)
        + "\n        </staff-details>\n"
    )
    # No MusicXML `staff-details` vem depois dos `clef`, que o music21 põe por
    # último. O primeiro `</attributes>` é o do compasso 1, onde a pauta se define.
    fecha = "      </attributes>"
    if fecha not in xml:  # pragma: no cover — o music21 sempre abre com attributes
        raise ValueError("MusicXML sem bloco <attributes>")
    return xml.replace(fecha, detalhes + fecha, 1)


if TYPE_CHECKING:  # pragma: no cover — trava a assinatura contra o Protocol
    _: Exporter = MusicXmlExporter()
