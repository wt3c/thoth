"""Notas posicionadas → arquivo GP5, via PyGuitarPro.

**O andamento chega decidido de fora.** O GP5 não guarda segundos: guarda
compassos, tempos e figuras. O `--bpm` que você informar manda; sem ele, o
pipeline estima do mix e avisa em vez de palpitar em silêncio (ADR-019). O que
chega aqui já passou pelo refino conjunto de andamento e fase (ADR-021).

Limitações assumidas desta primeira versão, todas visíveis na leitura:

- compasso fixo 4/4, grade de semicolcheia e um único andamento para a música
  inteira — o campo de BPM do arquivo é inteiro, então ele sai arredondado
  enquanto a quantização usa o fracionário (ADR-021);
- linha monofônica (ADR-012): notas simultâneas são recusadas, não empilhadas —
  salvo com `acordes=True` (guitarra, ADR-044), em que notas do mesmo tique viram
  um beat com uma nota por corda. Acorde não recebe nome no beat.

A bateria sai por `Gp5PercussaoExporter`, com contrato próprio (ADR-044): faixa de
percussão nativa, peças do mesmo tique num beat e nenhuma ligadura.

A sustentação é escrita com ligadura (ADR-022): a duração que não cabe numa
figura só — ou que atravessa a barra — vira beats `NoteType.tie` encadeados. Não
é enfeite: antes disso o resto virava **pausa**, e uma nota de 1,5 semínima era
lida como 0,5.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import guitarpro as gp

from thoth.domain.models import EventoPercussivo, TabNote
from thoth.domain.ports import ExportadorDePercussao, Exporter
from thoth.services.notas import nome_da_nota
from thoth.services.rhythm import (
    COMPASSO,
    GRADE,
    PPQ,
    acordes_em_ticks,
    ataques_em_ticks,
    eventos,
)

BAIXO_GM = 33  # Electric Bass (finger)
#: Canal 10 do GM, 0-indexado: o canal que os sintetizadores tocam como bateria.
CANAL_PERCUSSAO = 9
#: Uma peça por corda no beat; seis é o que o Guitar Pro cria para faixa de bateria.
CORDAS_PERCUSSAO = 6

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


def _fatiar_na_barra(inicio: int, duracao: int) -> list[tuple[int, int]]:
    """Parte o evento nos limites de compasso. Cada fatia cabe num compasso só.

    O GP5 guarda beats dentro de compassos: um beat que atravessa a barra não
    tem onde existir. A continuação vira outro beat, ligado ao anterior.
    """
    fatias = []
    while duracao > 0:
        ate_a_barra = COMPASSO * (inicio // COMPASSO + 1) - inicio
        cabe = min(duracao, ate_a_barra)
        fatias.append((inicio, cabe))
        inicio += cabe
        duracao -= cabe
    return fatias


@dataclass(frozen=True, slots=True)
class Gp5Exporter:
    """Implementa o `Exporter`. Round-trip verificado contra o próprio PyGuitarPro."""

    bpm: float = 120
    titulo: str = "Thoth"
    armadura: int | None = None
    """Armadura estimada. O GP5 do Thoth não a escreve na pauta — ela só decide se o
    nome do beat sai com bemol ou com sustenido (ADR-031)."""
    faixa: str = "Baixo"
    programa_gm: int = BAIXO_GM
    acordes: bool = False
    """Empilha notas do mesmo tique num beat (guitarra). Desligado, o baixo segue
    recusando simultaneidade: lá ela é defeito da transcrição, não música."""

    def export(self, notes: list[TabNote], out: Path, tuning: tuple[int, ...]) -> Path:
        if not notes:
            raise ValueError("sem notas para exportar")

        # O GP5 só guarda andamento inteiro no cabeçalho, mas a quantização usa o
        # fracionário: as posições ficam certas e só a reprodução corre ~0,5%
        # fora. O inverso — quantizar no inteiro — desloca as notas (ADR-021).
        song = gp.Song(title=self.titulo, tempo=round(self.bpm))
        song.tracks.clear()
        track = gp.Track(song, number=1, name=self.faixa)
        # O GP numera as cordas da mais aguda para a mais grave; nós, o contrário.
        track.strings = [gp.GuitarString(i + 1, v) for i, v in enumerate(reversed(tuning))]
        track.channel.instrument = self.programa_gm
        track.measures.clear()  # o construtor já cria um compasso a partir dos headers
        song.tracks.append(track)

        # `(início, duração, nota, continuação)` — a continuação é o que sai ligado
        # ao beat anterior em vez de reatacar a corda.
        agrupados = (
            acordes_em_ticks(notes, self.bpm)
            if self.acordes
            else [(ini, dur, (tab,)) for ini, dur, tab in eventos(notes, self.bpm)]
        )
        marcados = [
            (ini, dur, acorde, i > 0)
            for inicio, duracao, acorde in agrupados
            for i, (ini, dur) in enumerate(_fatiar_na_barra(inicio, duracao))
        ]
        total = (marcados[-1][0] + marcados[-1][1] - 1) // COMPASSO + 1
        cursor = 0
        for numero in range(total):
            while numero >= len(song.measureHeaders):
                song.addMeasureHeader(gp.MeasureHeader(number=len(song.measureHeaders) + 1))
            medida = gp.Measure(track, song.measureHeaders[numero])
            voz = gp.Voice(medida)
            fim_do_compasso = (numero + 1) * COMPASSO

            for inicio, duracao, acorde, continuacao in marcados:
                if not numero * COMPASSO <= inicio < fim_do_compasso:
                    continue
                for valor, pontuada in _decompor(inicio - cursor):
                    voz.beats.append(self._pausa(voz, valor, pontuada))
                # Só a primeira figura da primeira fatia é ataque; o resto da
                # duração é a mesma nota continuando, então sai ligada.
                for i, (valor, pontuada) in enumerate(_decompor(duracao)):
                    ligada = continuacao or i > 0
                    voz.beats.append(
                        self._nota(voz, acorde, len(tuning), valor, pontuada, ligada)
                    )
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

    def _nota(
        self, voz: gp.Voice, acorde: tuple[TabNote, ...], cordas: int, valor: int,
        pontuada: bool, ligada: bool = False,
    ) -> gp.Beat:
        beat = gp.Beat(voz, duration=gp.Duration(value=valor, isDotted=pontuada))
        for tab in acorde:
            beat.notes.append(
                gp.Note(
                    beat,
                    value=tab.fret,
                    string=cordas - tab.string,
                    velocity=95,
                    type=gp.NoteType.tie if ligada else gp.NoteType.normal,
                )
            )
        # Sem isto o beat sai `empty` (o default do PyGuitarPro): o leitor trata beat
        # vazio como duração zero, e todos os beats do compasso colapsam num só.
        beat.status = gp.BeatStatus.normal
        # O nome vai só no ataque de nota solta: repeti-lo na ligadura sugeriria
        # outra nota, e seis nomes empilhados num acorde seriam ruído.
        beat.text = (
            None
            if ligada or len(acorde) > 1
            else nome_da_nota(acorde[0].event.pitch, bemois=(self.armadura or 0) < 0)
        )
        return beat


@dataclass(frozen=True, slots=True)
class Gp5PercussaoExporter:
    """Implementa o `ExportadorDePercussao`: faixa de bateria, uma peça por corda.

    O `value` da nota é o número GM da peça, e a corda só existe para várias peças
    caberem no mesmo beat. A duração vem de `ataques_em_ticks`, que já é gráfica; a
    parte que atravessaria a barra vira pausa, nunca ligadura — ligar diria que a
    peça soa através da barra, e isso ninguém mediu. A mesma peça repetida no tique
    sai uma vez; quem relata a repetida é o pipeline.
    """

    bpm: float = 120
    titulo: str = "Thoth"
    faixa: str = "Bateria"

    def exportar(self, ataques: list[EventoPercussivo], out: Path) -> Path:
        if not ataques:
            raise ValueError("sem ataques para exportar")
        grupos, _ = ataques_em_ticks(ataques, self.bpm)
        for inicio, _, grupo in grupos:
            if len(grupo) > CORDAS_PERCUSSAO:
                raise ValueError(
                    f"{len(grupo)} peças no tique {inicio} "
                    f"({grupo[0].instante_s:.2f}s): a faixa tem {CORDAS_PERCUSSAO} cordas"
                )

        song = gp.Song(title=self.titulo, tempo=round(self.bpm))
        song.tracks.clear()
        track = gp.Track(song, number=1, name=self.faixa, isPercussionTrack=True)
        track.strings = [gp.GuitarString(i + 1, 0) for i in range(CORDAS_PERCUSSAO)]
        track.channel.channel = track.channel.effectChannel = CANAL_PERCUSSAO
        track.measures.clear()
        song.tracks.append(track)

        # Só a fatia até a barra é figura; o resto do espaço é pausa.
        cortados = [(inicio, _fatiar_na_barra(inicio, dur)[0][1], g) for inicio, dur, g in grupos]
        total = (cortados[-1][0] + cortados[-1][1] - 1) // COMPASSO + 1
        cursor = 0
        for numero in range(total):
            while numero >= len(song.measureHeaders):
                song.addMeasureHeader(gp.MeasureHeader(number=len(song.measureHeaders) + 1))
            medida = gp.Measure(track, song.measureHeaders[numero])
            voz = gp.Voice(medida)
            fim_do_compasso = (numero + 1) * COMPASSO
            for inicio, duracao, grupo in cortados:
                if not numero * COMPASSO <= inicio < fim_do_compasso:
                    continue
                for valor, pontuada in _decompor(inicio - cursor):
                    voz.beats.append(Gp5Exporter._pausa(voz, valor, pontuada))
                (valor, pontuada), *resto = _decompor(duracao)
                voz.beats.append(self._ataque(voz, grupo, valor, pontuada))
                for valor, pontuada in resto:
                    voz.beats.append(Gp5Exporter._pausa(voz, valor, pontuada))
                cursor = inicio + duracao
            for valor, pontuada in _decompor(fim_do_compasso - cursor):
                voz.beats.append(Gp5Exporter._pausa(voz, valor, pontuada))
            cursor = fim_do_compasso
            medida.voices = [voz, *(gp.Voice(medida) for _ in range(3))]
            track.measures.append(medida)

        out.parent.mkdir(parents=True, exist_ok=True)
        gp.write(song, str(out))
        return out

    @staticmethod
    def _ataque(
        voz: gp.Voice, grupo: tuple[EventoPercussivo, ...], valor: int, pontuada: bool
    ) -> gp.Beat:
        beat = gp.Beat(voz, duration=gp.Duration(value=valor, isDotted=pontuada))
        for corda, ataque in enumerate(grupo, start=1):
            # `gp.Note` nasce `NoteType.rest`: sem o tipo, a peça volta como pausa.
            beat.notes.append(
                gp.Note(
                    beat, value=ataque.peca_gm, string=corda, velocity=95,
                    type=gp.NoteType.normal,
                )
            )
        # O mesmo `empty` do exportador de cordas: sem isto o compasso colapsa.
        beat.status = gp.BeatStatus.normal
        return beat


if TYPE_CHECKING:  # pragma: no cover — trava a assinatura contra o Protocol
    _: Exporter = Gp5Exporter()
    __: ExportadorDePercussao = Gp5PercussaoExporter()
