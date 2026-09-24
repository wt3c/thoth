"""Tab `.gp5` humana → notas em segundos, como referência externa (Camada 3, ADR-041).

A tab chega por download manual do usuário (ADR-007): o Thoth só lê o arquivo local.
O que ela guarda é partitura — compassos, figuras, andamento —, e a comparação com a
transcrição precisa de segundos. A conversão tem três armadilhas, todas medidas na
primeira tab lida:

- **o andamento pode estar em qualquer faixa.** Em *Fear Is The Key* as seis mudanças
  estão na bateria, e ler só a faixa do baixo deixava a música 36 s mais longa. Toda
  faixa contribui para um mapa só, na posição exata do beat — a mudança do compasso 76
  está na última semicolcheia, não no começo;
- **a ordem de execução não é a ordem do arquivo.** Repetição toca o trecho de novo, e
  final alternativo só toca na passada marcada. Limites: cada final ocupa **um**
  compasso, e D.S./coda não são seguidos — nenhuma das tabs lidas até aqui usa isso;
- **ligadura é continuação, não ataque.** Ela estende a nota anterior da mesma corda;
  contá-la como nota nova inventaria ataques que ninguém tocou. Nota morta não tem
  altura e fica fora.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import guitarpro as gp

from thoth.domain.models import NoteEvent

PPQ = gp.Duration.quarterTime
#: C3, a corda mais aguda do baixo de seis cordas. A da guitarra é E4 (64).
MAIS_AGUDA_DO_BAIXO = 48


@dataclass(frozen=True, slots=True)
class Referencia:
    faixa: str
    notas: list[NoteEvent]


def ler_tab(caminho: Path, faixa: int | None = None) -> Referencia:
    """Lê a faixa de baixo; `faixa` (1 = primeira) força uma quando a escolha é ambígua."""
    song = gp.parse(str(caminho))
    track = _faixa(song, faixa, caminho.name)
    return Referencia(track.name, _notas(song, track))


def _faixa(song: gp.Song, faixa: int | None, nome: str) -> gp.Track:
    faixas = ", ".join(f"{i}: {t.name}" for i, t in enumerate(song.tracks, start=1))
    if faixa is not None:
        if not 1 <= faixa <= len(song.tracks):
            raise ValueError(f"{nome} não tem a faixa {faixa}; há {faixas}")
        return song.tracks[faixa - 1]
    baixos = [
        t
        for t in song.tracks
        if not t.isPercussionTrack and max(c.value for c in t.strings) <= MAIS_AGUDA_DO_BAIXO
    ]
    if len(baixos) == 1:
        return baixos[0]
    motivo = "nenhuma faixa de baixo" if not baixos else f"{len(baixos)} faixas de baixo"
    raise ValueError(f"{motivo} em {nome}; escolha com --faixa entre {faixas}")


def _andamentos(song: gp.Song) -> dict[int, list[tuple[int, int]]]:
    """Mudanças de andamento de **todas** as faixas: compasso → [(posição, bpm)]."""
    mudancas: dict[int, dict[int, int]] = defaultdict(dict)
    for track in song.tracks:
        for indice, medida in enumerate(track.measures):
            for voz in medida.voices:
                for beat in voz.beats:
                    mix = beat.effect.mixTableChange
                    if mix is not None and mix.tempo is not None:
                        posicao = beat.start - medida.header.start
                        mudancas[indice][posicao] = mix.tempo.value
    return {i: sorted(m.items()) for i, m in mudancas.items()}


def _ordem(headers: list[gp.MeasureHeader]) -> list[int]:
    """Índices dos compassos na ordem em que são tocados."""
    ordem: list[int] = []
    i = inicio = passada = 0
    while i < len(headers):
        h = headers[i]
        if h.isRepeatOpen and i != inicio:
            inicio, passada = i, 0
        if h.repeatAlternative and not (h.repeatAlternative >> passada) & 1:
            i += 1
            continue
        ordem.append(i)
        if h.repeatClose > 0:
            if passada < h.repeatClose:
                passada += 1
                i = inicio
                continue
            inicio, passada = i + 1, 0
        i += 1
    return ordem


def _segundos(posicao: int, trechos: list[tuple[int, int]]) -> float:
    """Segundos desde o início do compasso até `posicao` (ticks), atravessando mudanças."""
    total = 0.0
    for (inicio, bpm), (fim, _) in zip(trechos, [*trechos[1:], (posicao, 0)], strict=True):
        if posicao <= inicio:
            break
        total += (min(posicao, fim) - inicio) / PPQ * 60 / bpm
    return total


def _notas(song: gp.Song, track: gp.Track) -> list[NoteEvent]:
    andamentos = _andamentos(song)
    bpm = song.tempo
    relogio = 0.0
    notas: list[NoteEvent] = []
    soando: dict[int, int] = {}  # corda → índice da nota em `notas`
    for indice in _ordem(song.measureHeaders):
        medida = track.measures[indice]
        trechos = [(0, bpm), *andamentos.get(indice, [])]
        for voz in medida.voices:
            for beat in voz.beats:
                posicao = beat.start - medida.header.start
                inicio = relogio + _segundos(posicao, trechos)
                fim = relogio + _segundos(posicao + beat.duration.time, trechos)
                for nota in beat.notes:
                    if nota.type == gp.NoteType.tie and nota.string in soando:
                        anterior = notas[soando[nota.string]]
                        notas[soando[nota.string]] = NoteEvent(
                            anterior.pitch, anterior.onset_s, fim, anterior.instrument
                        )
                    elif nota.type == gp.NoteType.normal:
                        altura = track.strings[nota.string - 1].value + nota.value
                        soando[nota.string] = len(notas)
                        notas.append(NoteEvent(altura, inicio, fim, "electric_bass"))
        relogio += _segundos(medida.header.length, trechos)
        bpm = trechos[-1][1]
    return sorted(notas, key=lambda n: (n.onset_s, n.pitch))
