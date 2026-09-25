"""Notas posicionadas → MusicXML, via music21.

Duas pautas na mesma parte (ADR-035): notação em cima, tablatura embaixo. Antes
daqui o arquivo era só notação, e corda e traste viajavam como indicações que
nenhum leitor desenhava — o MuseScore abria a partitura e a tablatura ficava
implícita no arquivo.

A clave é `Bass8vb` porque o baixo é instrumento transpositor: soa uma oitava
abaixo do escrito. Com clave de Fá comum, tudo sairia uma oitava acima. A guitarra
(`familia="guitarra"`, ADR-044) também soa uma oitava abaixo: clave de Sol 8vb, e
notas do mesmo tique saem como acorde nas duas pautas. O music21 10.5 só escreve
corda e traste na primeira nota de um acorde, então a digitação da guitarra é
escrita depois, no XML (`_com_digitacao`), como a afinação.

Ao contrário do GP5, aqui não decomponho figuras à mão — o `makeNotation` do
music21 resolve ligaduras e pausas a partir dos offsets.

A bateria (`MusicXmlPercussaoExporter`, ADR-044) é outra pauta: não afinada, clave
de percussão, cada peça GM numa posição e com uma cabeça (`MAPA_PERCUSSAO`, o
drumset padrão do MuseScore). Posição e cabeça não identificam a peça — a caixa
acústica e a eletrônica caem as duas em C5 —, e o music21 10.5 só escreve um
instrumento genérico por parte. O instrumento de cada peça, com o seu
`midi-unpitched`, é escrito depois, no XML (`_com_pecas`).

O piano (`MusicXmlPianoExporter`, ADR-044, M3) é um sistema de duas pautas sem
tablatura: clave de Sol do dó central para cima, de Fá abaixo, sem inferir a mão.
Mesmo tique e mesma duração formam acorde; duração sobreposta vai para outra voz,
até 4 (o limite do MuseScore). Cada voz é posta em compassos à parte e as vozes
se juntam por compasso, porque o `makeNotation` não separa vozes sozinho.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal
from xml.etree import ElementTree

from music21 import (
    articulations,
    beam,
    chord,
    clef,
    instrument,
    key,
    layout,
    metadata,
    meter,
    note,
    percussion,
    pitch,
    stream,
    tempo,
)

from thoth.domain.models import EventoPercussivo, NoteEvent, TabNote
from thoth.domain.ports import ExportadorDePercussao, ExportadorDePiano, Exporter
from thoth.services.notas import nome_da_nota
from thoth.services.rhythm import (
    COMPASSO,
    GRADE,
    PPQ,
    acordes_em_ticks,
    ataques_em_ticks,
    eventos,
    para_ticks,
)

#: `(início, duração, acorde)` em ticks; no baixo o acorde tem sempre uma nota.
Posicionadas = list[tuple[int, int, tuple[TabNote, ...]]]


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
    familia: Literal["baixo", "guitarra"] = "baixo"
    """O baixo segue monofônico, em `Bass8vb`; a guitarra empilha acordes em `Treble8vb`."""
    programa_gm: int = 33
    """Programa GM da guitarra, do perfil. O baixo continua como `ElectricBass`."""

    def export(self, notes: list[TabNote], out: Path, tuning: tuple[int, ...]) -> Path:
        if not notes:
            raise ValueError("sem notas para exportar")

        guitarra = self.familia == "guitarra"
        posicionadas: Posicionadas = (
            acordes_em_ticks(notes, self.bpm)
            if guitarra
            else [(ini, dur, (tab,)) for ini, dur, tab in eventos(notes, self.bpm)]
        )
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
        xml = _com_afinacao(out.read_text(), tuning)
        if guitarra:
            xml = _com_digitacao(xml, posicionadas, len(tuning))
        out.write_text(xml, encoding="utf-8")
        return out

    def _pauta(
        self,
        posicionadas: Posicionadas,
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
            if self.familia == "guitarra":
                parte.insert(0, instrument.instrumentFromMidiProgram(self.programa_gm))
                parte.insert(0, clef.Treble8vbClef())
            else:
                parte.insert(0, instrument.ElectricBass())
                parte.insert(0, clef.Bass8vbClef())
            parte.insert(0, tempo.MetronomeMark(number=round(self.bpm)))
            if self.armadura is not None:
                parte.insert(0, key.KeySignature(self.armadura))

        for inicio, duracao, acorde in posicionadas:
            if len(acorde) > 1:
                # Acorde não leva nome nem técnica aqui: seis nomes empilhados seriam
                # ruído, e a corda de cada nota entra no XML (`_com_digitacao`).
                c = chord.Chord([t.event.pitch for t in acorde], quarterLength=duracao / PPQ)
                parte.insert(inicio / PPQ, c)
                continue
            (tab,) = acorde
            n = note.Note(tab.event.pitch, quarterLength=duracao / PPQ)
            if tablatura and self.familia == "guitarra":
                pass  # a digitação entra no XML, igual à do acorde
            elif tablatura:
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

    Uma voz por vez: baixo e guitarra não têm vozes (ADR-014) e a camada é o
    compasso; no piano o music21 quebra os beams dentro de cada voz do mesmo jeito
    (ADR-044, M3), e cada voz é refeita sozinha.
    """
    for pauta in pronto.parts:
        pauta.makeBeams(inPlace=True)
        formula: meter.TimeSignature | None = None
        for compasso in pauta.getElementsByClass(stream.Measure):
            # Como o `makeBeams` acha a fórmula: a do compasso, senão a última vista.
            formula = compasso.timeSignature or formula
            if formula is None:
                continue
            for camada in list(compasso.voices) or [compasso]:
                if _beams_quebrados(camada):
                    _refazer_beams(camada, formula)
        pauta.streamStatus.beams = True


def _refazer_beams(camada: stream.Measure | stream.Voice, formula: meter.TimeSignature) -> None:
    """O `getBeams` do music21 um tempo por vez, sem grupo atravessando a fronteira."""
    elementos = list(camada.notesAndRests)
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


def _beams_quebrados(camada: stream.Measure | stream.Voice) -> bool:
    """A gramática do MusicXML sobre os beams do music21, por nível.

    `start` abre, `continue` e `stop` exigem aberto, `partial` (gancho) é isolado,
    e nada fica aberto no fim do compasso. É o mesmo autômato que os testes rodam
    sobre o XML escrito.
    """
    abertos: dict[int, bool] = {}
    for nota in camada.notes:
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


def _com_digitacao(xml: str, posicionadas: Posicionadas, cordas: int) -> str:
    """Escreve `<technical><string/><fret/>` em cada nota da pauta 2 (guitarra).

    O music21 10.5 põe a técnica só na primeira nota do acorde; as outras sairiam
    sem corda e o leitor escolheria uma por conta própria. Aqui o cursor do
    MusicXML é andado à mão (`duration`, `chord`, `backup`, `forward`), e cada
    nota — inclusive a continuação ligada — acha a sua pela altura dentro do
    acorde que soa naquele instante.
    """
    cabecalho = xml[: xml.index("<score-partwise")]
    raiz = ElementTree.fromstring(xml[len(cabecalho) :])
    divisoes = int(raiz.findtext(".//divisions") or 1)
    inicio_do_compasso = 0
    for compasso in raiz.iter("measure"):
        cursor = fim = anterior = inicio_do_compasso
        usadas: set[int] = set()
        for el in compasso:
            if el.tag == "backup":
                cursor -= int(el.findtext("duration") or 0)
            elif el.tag == "forward":
                cursor += int(el.findtext("duration") or 0)
            elif el.tag == "note":
                if el.find("chord") is None:
                    anterior = cursor
                    cursor += int(el.findtext("duration") or 0)
                    usadas = set()
                altura = el.find("pitch")
                if el.findtext("staff") == "2" and altura is not None:
                    tab = _tab_em(posicionadas, anterior * PPQ // divisoes, altura, usadas)
                    _anotar(el, cordas - tab.string, tab.fret)
            fim = max(fim, cursor)
        inicio_do_compasso = fim
    return cabecalho + ElementTree.tostring(raiz, encoding="unicode")


def _tab_em(
    posicionadas: Posicionadas, tique: int, altura: ElementTree.Element, usadas: set[int]
) -> TabNote:
    natural = pitch.Pitch(f"{altura.findtext('step')}{altura.findtext('octave')}").midi
    midi = natural + int(altura.findtext("alter") or 0)
    for inicio, duracao, acorde in posicionadas:
        if inicio <= tique < inicio + duracao:
            for tab in acorde:
                # Duas cordas na mesma altura (uníssono) ficam uma para cada nota.
                if tab.event.pitch == midi and id(tab) not in usadas:
                    usadas.add(id(tab))
                    return tab
    raise ValueError(f"nota {midi} no tique {tique} sem posição no braço")  # pragma: no cover


def _anotar(nota: ElementTree.Element, corda: int, traste: int) -> None:
    notacoes = nota.find("notations")
    if notacoes is None:
        notacoes = ElementTree.Element("notations")
        # `notations` vem antes de `lyric` e `play` na ordem do MusicXML.
        depois = [i for i, filho in enumerate(nota) if filho.tag in ("lyric", "play")]
        nota.insert(depois[0] if depois else len(nota), notacoes)
    tecnica = ElementTree.SubElement(notacoes, "technical")
    ElementTree.SubElement(tecnica, "string").text = str(corda)
    ElementTree.SubElement(tecnica, "fret").text = str(traste)


@dataclass(frozen=True, slots=True)
class PecaNaPauta:
    """Onde e como uma peça GM é desenhada na pauta de percussão."""

    nome: str
    altura: str
    """Posição na pauta, como altura de clave de Sol (`display-step`/`display-octave`)."""
    cabeca: str = "normal"
    """Cabeça MusicXML (`notehead`)."""


#: O drumset padrão do MuseScore 4 para o kit GM (35 a 59), lido de um arquivo importado:
#: linha e cabeça de cada peça. O prato chinês usa lá uma cabeça que o MusicXML não
#: tem; sai `x`, e o instrumento da nota desfaz a ambiguidade com o prato 2.
MAPA_PERCUSSAO: dict[int, PecaNaPauta] = {
    35: PecaNaPauta("Acoustic Bass Drum", "E4"),
    36: PecaNaPauta("Bass Drum 1", "F4"),
    37: PecaNaPauta("Side Stick", "C5", "x"),
    38: PecaNaPauta("Acoustic Snare", "C5"),
    39: PecaNaPauta("Hand Clap", "C5"),
    40: PecaNaPauta("Electric Snare", "C5"),
    41: PecaNaPauta("Low Floor Tom", "G4"),
    42: PecaNaPauta("Closed Hi-Hat", "G5", "x"),
    43: PecaNaPauta("High Floor Tom", "G4"),
    44: PecaNaPauta("Pedal Hi-Hat", "D4", "x"),
    45: PecaNaPauta("Low Tom", "A4"),
    46: PecaNaPauta("Open Hi-Hat", "G5", "circle-x"),
    47: PecaNaPauta("Low-Mid Tom", "B4"),
    48: PecaNaPauta("Hi-Mid Tom", "D5"),
    49: PecaNaPauta("Crash Cymbal 1", "A5", "x"),
    50: PecaNaPauta("High Tom", "E5"),
    51: PecaNaPauta("Ride Cymbal 1", "F5", "x"),
    52: PecaNaPauta("Chinese Cymbal", "B5", "x"),
    53: PecaNaPauta("Ride Bell", "F5", "diamond"),
    54: PecaNaPauta("Tambourine", "D5", "x"),
    55: PecaNaPauta("Splash Cymbal", "A5", "x"),
    56: PecaNaPauta("Cowbell", "F5"),
    57: PecaNaPauta("Crash Cymbal 2", "B5", "x"),
    58: PecaNaPauta("Vibraslap", "C5"),
    59: PecaNaPauta("Ride Cymbal 2", "D5", "x"),
}


@dataclass(frozen=True, slots=True)
class MusicXmlPercussaoExporter:
    """Implementa o `ExportadorDePercussao`: uma pauta, sem tablatura."""

    bpm: float = 120
    titulo: str = "Thoth"
    parte: str = "Bateria"

    def exportar(self, ataques: list[EventoPercussivo], out: Path) -> Path:
        if not ataques:
            raise ValueError("sem ataques para exportar")
        fora = sorted({a.peca_gm for a in ataques} - MAPA_PERCUSSAO.keys())
        if fora:
            raise ValueError(f"peça {fora[0]} fora do mapa de percussão")

        grupos, _ = ataques_em_ticks(ataques, self.bpm)
        pauta = stream.Part()
        pauta.partName = self.parte
        pauta.insert(0, instrument.Percussion())
        pauta.insert(0, clef.PercussionClef())
        pauta.insert(0, meter.TimeSignature("4/4"))
        pauta.insert(0, tempo.MetronomeMark(number=round(self.bpm)))
        for inicio, duracao, pecas in grupos:
            # Corta na barra: ligadura seria sustentação, e a bateria não a tem medida.
            figura = min(duracao, COMPASSO - inicio % COMPASSO) / PPQ
            notas = [_nao_afinada(p.peca_gm) for p in pecas]
            elemento = notas[0] if len(notas) == 1 else percussion.PercussionChord(notas)
            elemento.quarterLength = figura
            pauta.insert(inicio / PPQ, elemento)
        pauta.makeRests(fillGaps=True, inPlace=True)

        score = stream.Score()
        score.insert(0, pauta)
        score.insert(0, metadata.Metadata(title=self.titulo))
        out.parent.mkdir(parents=True, exist_ok=True)
        score.makeNotation().write("musicxml", fp=str(out))
        ordem = [p.peca_gm for _, _, pecas in grupos for p in pecas]
        out.write_text(_com_pecas(out.read_text(), ordem), encoding="utf-8")
        return out


def _nao_afinada(peca: int) -> note.Unpitched:
    na_pauta = MAPA_PERCUSSAO[peca]
    nota = note.Unpitched(displayName=na_pauta.altura)
    nota.notehead = na_pauta.cabeca
    return nota


def _com_pecas(xml: str, ordem: list[int]) -> str:
    """Um `score-instrument` por peça usada, e o `<instrument id>` de cada nota.

    As notas saem na ordem em que foram postas — grupo a grupo, peças por número
    GM —, sem ligadura que as duplicasse. A posição de cada uma é conferida contra
    a peça que recebe, e a contagem no fim: um desencontro vira erro, não arquivo
    com a peça trocada.
    """
    cabecalho = xml[: xml.index("<score-partwise")]
    raiz = ElementTree.fromstring(xml[len(cabecalho) :])
    parte = raiz.find("part-list/score-part")
    if parte is None:  # pragma: no cover — o music21 sempre escreve a parte
        raise ValueError("MusicXML sem <score-part>")
    for velho in parte.findall("score-instrument") + parte.findall("midi-instrument"):
        parte.remove(velho)
    # `score-instrument` logo depois do nome, `midi-instrument` no fim da parte.
    posicao = max(i for i, f in enumerate(parte) if f.tag.startswith("part-")) + 1
    for i, peca in enumerate(sorted(set(ordem))):
        ident = f"I{peca + 1}"
        instrumento = ElementTree.Element("score-instrument", id=ident)
        ElementTree.SubElement(instrumento, "instrument-name").text = MAPA_PERCUSSAO[peca].nome
        parte.insert(posicao + i, instrumento)
        midi = ElementTree.SubElement(parte, "midi-instrument", id=ident)
        ElementTree.SubElement(midi, "midi-channel").text = "10"
        ElementTree.SubElement(midi, "midi-unpitched").text = str(peca + 1)

    restantes = iter(ordem)
    for nota in raiz.iter("note"):
        exibida = nota.find("unpitched")
        if exibida is None:
            continue
        peca = next(restantes)
        altura = f"{exibida.findtext('display-step')}{exibida.findtext('display-octave')}"
        if altura != MAPA_PERCUSSAO[peca].altura:  # pragma: no cover — defesa
            raise ValueError(f"nota em {altura} para a peça {peca}")
        # `instrument` vem depois de `duration` e das `tie`, antes de `voice`/`type`.
        antes = [i for i, f in enumerate(nota) if f.tag in ("duration", "tie")]
        nota.insert(antes[-1] + 1, ElementTree.Element("instrument", id=f"I{peca + 1}"))
    if next(restantes, None) is not None:  # pragma: no cover — defesa
        raise ValueError("MusicXML com menos notas que ataques")
    return cabecalho + ElementTree.tostring(raiz, encoding="unicode")


#: Do dó central para cima, clave de Sol; abaixo, clave de Fá. Regra fixa: a partitura
#: não sabe que mão toca cada nota, e adivinhar seria inventar dedilhado (ADR-044).
DO_CENTRAL = 60

#: `(início, duração)` em ticks → alturas que soam juntas nesse trecho.
Acordes = dict[tuple[int, int], list[int]]


@dataclass(frozen=True, slots=True)
class MusicXmlPianoExporter:
    """Implementa o `ExportadorDePiano`: sistema de duas pautas, sem tablatura."""

    bpm: float = 120
    titulo: str = "Thoth"
    armadura: int | None = None
    """Armadura estimada, ou `None`, como no `MusicXmlExporter`."""

    def exportar(self, notas: list[NoteEvent], out: Path) -> Path:
        if not notas:
            raise ValueError("sem notas para exportar")

        acordes: tuple[Acordes, Acordes] = ({}, {})
        for n in notas:
            inicio = para_ticks(n.onset_s, self.bpm)
            duracao = max(GRADE, para_ticks(n.offset_s, self.bpm) - inicio)
            acordes[0 if n.pitch >= DO_CENTRAL else 1].setdefault(
                (inicio, duracao), []
            ).append(n.pitch)
        fim = max(i + d for pauta in acordes for i, d in pauta)
        fim = -(-fim // COMPASSO) * COMPASSO

        superior = self._pauta(acordes[0], clef.TrebleClef(), fim, primeira=True)
        inferior = self._pauta(acordes[1], clef.BassClef(), fim, primeira=False)
        score = stream.Score()
        score.insert(0, superior)
        score.insert(0, inferior)
        score.insert(0, layout.StaffGroup([superior, inferior], symbol="brace", barTogether=True))
        score.insert(0, metadata.Metadata(title=self.titulo))
        _consertar_beams(score)
        out.parent.mkdir(parents=True, exist_ok=True)
        score.write("musicxml", fp=str(out))
        return out

    def _pauta(
        self, acordes: Acordes, clave: clef.Clef, fim: int, *, primeira: bool
    ) -> stream.PartStaff:
        """Uma pauta já em compassos, com uma voz por camada de durações sobrepostas."""
        compassos_por_voz = [
            _em_compassos(voz, fim) for voz in _vozes(acordes)
        ] or [_em_compassos([], fim)]
        pauta = stream.PartStaff()
        for numero, grupo in enumerate(zip(*compassos_por_voz, strict=True), start=1):
            compasso = stream.Measure(number=numero)
            if numero == 1:
                if primeira:
                    compasso.insert(0, instrument.Piano())
                    compasso.insert(0, tempo.MetronomeMark(number=round(self.bpm)))
                compasso.insert(0, clave)
                if self.armadura is not None:
                    compasso.insert(0, key.KeySignature(self.armadura))
                compasso.insert(0, meter.TimeSignature("4/4"))
            if len(grupo) == 1:
                for el in grupo[0].notesAndRests:
                    compasso.insert(el.offset, el)
            else:
                for i, parcial in enumerate(grupo, start=1):
                    voz = stream.Voice(id=str(i))
                    for el in parcial.notesAndRests:
                        voz.insert(el.offset, el)
                    compasso.insert(0, voz)
            pauta.append(compasso)
        return pauta


#: O MuseScore tem 4 vozes por pauta e descarta a 5ª sem aviso (medido: 2 de 6 notas).
MAX_VOZES = 4


def _vozes(acordes: Acordes) -> list[list[tuple[int, int, list[int]]]]:
    """Cada acorde na primeira voz já livre no seu início; senão, voz nova, até 4.

    Mesmo tique com duração diferente não cabe num acorde MusicXML (as notas de um
    `<chord>` dividem a duração): a mais longa entra primeiro e a outra vai para a voz
    seguinte.

    Com as 4 ocupadas, a que libera primeiro é encurtada até o ataque novo; se ela
    ataca no mesmo tique, encurta até a duração do acorde novo e os dois se fundem
    (decisão do usuário). Altura e ataque nunca se perdem; duração só encolhe.
    """
    vozes: list[list[tuple[int, int, list[int]]]] = []
    for (inicio, duracao), alturas in sorted(acordes.items(), key=lambda x: (x[0][0], -x[0][1])):
        livre = next((v for v in vozes if v[-1][0] + v[-1][1] <= inicio), None)
        if livre is None and len(vozes) < MAX_VOZES:
            livre = []
            vozes.append(livre)
        if livre is None:
            livre = min(vozes, key=lambda v: v[-1][0] + v[-1][1])
            anterior, _, soando = livre[-1]
            if anterior == inicio:
                livre[-1] = (inicio, duracao, sorted(soando + alturas))
                continue
            livre[-1] = (anterior, inicio - anterior, soando)
        livre.append((inicio, duracao, sorted(alturas)))
    return vozes


def _em_compassos(voz: list[tuple[int, int, list[int]]], fim: int) -> list[stream.Measure]:
    """Uma voz inteira em compassos de 4/4, pausas nos buracos, ligadura na barra."""
    linha = stream.Part()
    linha.insert(0, meter.TimeSignature("4/4"))
    for inicio, duracao, alturas in voz:
        elemento: note.NotRest = (
            note.Note(alturas[0]) if len(alturas) == 1 else chord.Chord(alturas)
        )
        elemento.quarterLength = duracao / PPQ
        linha.insert(inicio / PPQ, elemento)
    linha.makeRests(fillGaps=True, refStreamOrTimeRange=[0, fim / PPQ], inPlace=True)
    medida = linha.makeMeasures()
    medida.makeTies(inPlace=True)
    return list(medida.getElementsByClass(stream.Measure))


if TYPE_CHECKING:  # pragma: no cover — trava a assinatura contra o Protocol
    _: Exporter = MusicXmlExporter()
    __: ExportadorDePercussao = MusicXmlPercussaoExporter()
    ___: ExportadorDePiano = MusicXmlPianoExporter()
