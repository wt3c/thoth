"""Fixtures sintéticas de bateria, piano e guitarra (ADR-044), com referência conhecida.

Mesma regra do `tests/sintetico.py`: o MIDI é a referência, o áudio é regerado a
cada execução e nunca entra no repositório. O instrumento-alvo fica sempre no
índice 0; na versão `-mix`, baixo e um terceiro instrumento entram como distratores.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pretty_midi

from tests.sintetico import BAIXO, BPM, PIANO, TEMPO, renderizar_midi
from thoth.domain.instrumentos import PERFIS
from thoth.domain.models import EventoPercussivo, NoteEvent, Transcricao

#: Peças GM: bumbo, caixa, chimbal fechado, tons grave/médio/agudo, prato de ataque.
BUMBO, CAIXA, CHIMBAL, TOM_GRAVE, TOM_MEDIO, TOM_AGUDO, PRATO = 36, 38, 42, 45, 48, 50, 49
#: Os seis tons do GM, do surdo grave ao tom agudo.
TONS = (41, 43, 45, 47, 48, 50)

Evento = tuple[tuple[int, ...], float, float]  # alturas simultâneas, início, duração


@dataclass(frozen=True)
class FixtureMulti:
    perfil: str
    midi: pretty_midi.PrettyMIDI


def _instrumento(
    programa: int, eventos: list[Evento], *, bateria: bool = False, velocidade: int = 100
) -> pretty_midi.Instrument:
    inst = pretty_midi.Instrument(program=programa, is_drum=bateria)
    for alturas, inicio, dur in eventos:
        for altura in alturas:
            inst.notes.append(
                pretty_midi.Note(
                    velocity=velocidade,
                    pitch=altura,
                    start=inicio,
                    end=inicio + dur * 0.9,
                )
            )
    return inst


def _em_semiminimas(sequencia: list[tuple[int, ...]], passo: float = TEMPO) -> list[Evento]:
    return [(alturas, i * passo, passo) for i, alturas in enumerate(sequencia)]


def _bateria() -> list[Evento]:
    """Quatro compassos em colcheias; o último é virada nos tons. Ataques simultâneos."""
    eventos: list[Evento] = []
    colcheia = TEMPO / 2
    for compasso in range(4):
        for i in range(8):
            t = (compasso * 8 + i) * colcheia
            if compasso == 3 and i >= 4:
                pecas: tuple[int, ...] = ((TOM_AGUDO,), (TOM_MEDIO,), (TOM_GRAVE,), (BUMBO,))[i - 4]
            else:
                pecas = (CHIMBAL,)
                if i in (0, 4):
                    pecas += (BUMBO,)
                if i in (2, 6):
                    pecas += (CAIXA,)
                if i == 0 and compasso % 2 == 0:
                    pecas += (PRATO,)
            eventos.append((pecas, t, 0.1 / 0.9))
    return eventos


def _piano() -> list[Evento]:
    """Duas mãos, inversões e nota repetida, com A0 no início e C8 no fim."""
    acordes = [
        (36, 60, 64, 67),
        (36, 64, 67, 72),
        (41, 60, 65, 69),
        (41, 65, 69, 72),
        (43, 59, 62, 67),
        (43, 62, 67, 71),
        (36, 60, 64, 67),
        (36, 60, 64, 67),
    ]
    extremos = [((21,), 0.0, TEMPO * 2)]
    corpo = [(a, TEMPO * 2 + i * TEMPO * 2, TEMPO * 2) for i, a in enumerate(acordes)]
    fim = TEMPO * 2 * (len(acordes) + 1)
    return [*extremos, *corpo, ((108,), fim, TEMPO * 2)]


def _guitarra() -> list[Evento]:
    """Nota simples, díade e acordes de três a seis notas, todos na afinação padrão."""
    return _em_semiminimas(
        [
            (40,),
            (43,),
            (45,),
            (47,),
            (40, 47),
            (45, 52),
            (47, 54),
            (50, 57),
            (52, 55, 59),
            (45, 52, 57, 61, 64),
            (40, 47, 52, 56, 59, 64),  # mi maior aberto, seis cordas
            (43, 47, 50, 55, 59, 67),  # sol maior aberto, seis cordas
            (45, 52, 57, 61, 64),
            (40, 47, 52, 56, 59, 64),
            (50, 57, 62, 66),
            (40, 47, 52, 55, 59, 64),
        ]
    )


def _baixo_distrator() -> pretty_midi.Instrument:
    return _instrumento(BAIXO, _em_semiminimas([(n,) for n in [28, 35, 33, 31] * 4]))


def _piano_distrator() -> pretty_midi.Instrument:
    return _instrumento(
        PIANO, [((60, 64, 67), i * TEMPO * 4, TEMPO * 4) for i in range(4)], velocidade=70
    )


def _tons() -> list[Evento]:
    """Oito voltas pelos seis tons em colcheias, um por vez. Cada volta gira a ordem e
    alterna o sentido, para nenhum tom ter sempre o mesmo vizinho (emenda do ADR-044)."""
    sequencia: list[tuple[int, ...]] = []
    for volta in range(8):
        ordem = TONS[volta % len(TONS) :] + TONS[: volta % len(TONS)]
        sequencia += [(t,) for t in (ordem[::-1] if volta % 2 else ordem)]
    return [(pecas, t, 0.1 / 0.9) for pecas, t, _ in _em_semiminimas(sequencia, TEMPO / 2)]


def _bateria_distratora() -> pretty_midi.Instrument:
    return _instrumento(0, _bateria(), bateria=True, velocidade=80)


def _fixture(perfil: str, *, mix: bool) -> FixtureMulti:
    p = PERFIS[perfil]
    if p.familia == "bateria":
        alvo = _instrumento(0, _bateria(), bateria=True)
        distratores = [_baixo_distrator(), _piano_distrator()]
    else:
        eventos = _piano() if p.familia == "piano" else _guitarra()
        alvo = _instrumento(p.programa_gm, eventos)
        distratores = [_baixo_distrator(), _bateria_distratora()]
    midi = pretty_midi.PrettyMIDI(initial_tempo=BPM)
    midi.instruments.append(alvo)
    if mix:
        midi.instruments.extend(distratores)
    return FixtureMulti(perfil, midi)


FIXTURES_MULTI: dict[str, FixtureMulti] = {
    f"{perfil}-{condicao}": _fixture(perfil, mix=condicao == "mix")
    for perfil in PERFIS
    if perfil != "baixo"
    for condicao in ("isolada", "mix")
}
#: Só tons, sem distrator: a fixture geral tem três ataques deles, pouco para ver a troca.
FIXTURES_MULTI["bateria-tons"] = FixtureMulti("bateria", pretty_midi.PrettyMIDI(initial_tempo=BPM))
FIXTURES_MULTI["bateria-tons"].midi.instruments.append(_instrumento(0, _tons(), bateria=True))

#: Os extremos do teclado longe das bordas do áudio, entre dós centrais de âncora: a
#: fixture geral põe A0 no instante zero e C8 no fim, onde o modelo já perde ataques.
EXTREMOS_PIANO = ((60,), (21,), (60,), (108,), (60,), (21, 108), (60,))
for _perfil in ("piano-acustico", "piano-eletrico"):
    FIXTURES_MULTI[f"{_perfil}-extremos"] = FixtureMulti(
        _perfil, pretty_midi.PrettyMIDI(initial_tempo=BPM)
    )
    FIXTURES_MULTI[f"{_perfil}-extremos"].midi.instruments.append(
        _instrumento(PERFIS[_perfil].programa_gm, _em_semiminimas(list(EXTREMOS_PIANO), TEMPO * 2))
    )


def referencia(fixture: FixtureMulti) -> Transcricao:
    """O instrumento-alvo como o Thoth espera recebê-lo do transcritor."""
    alvo = fixture.midi.instruments[0]
    if alvo.is_drum:
        return Transcricao(
            notas=(), ataques=tuple(EventoPercussivo(n.start, n.pitch) for n in alvo.notes)
        )
    (rotulo,) = PERFIS[fixture.perfil].rotulos
    return Transcricao(
        notas=tuple(NoteEvent(n.pitch, n.start, n.end, rotulo) for n in alvo.notes), ataques=()
    )


def renderizar_multi(nome: str, destino: Path) -> Path:
    return renderizar_midi(FIXTURES_MULTI[nome].midi, nome, destino)
