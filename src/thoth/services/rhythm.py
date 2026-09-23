"""Segundos → tempo musical. O que os dois exportadores precisam compartilhar.

**O andamento é entrada, não estimativa.** O Thoth ainda não estima tempo (o
checkpoint do Beat This! está inacessível — C2 no `todo.md`), e nenhum formato de
partitura guarda segundos: todos guardam compassos, tempos e figuras. Sem BPM não
há arquivo, então ele é parâmetro explícito em vez de palpite silencioso — um BPM
errado não quebra nada, produz uma leitura errada, que é pior.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from itertools import pairwise

from thoth.domain.models import NoteEvent, TabNote

PPQ = 960  # ticks por semínima (convenção do GP5)
GRADE = PPQ // 4  # semicolcheia: a menor figura que a grade reconhece
COMPASSO = PPQ * 4  # 4/4


def alinhar(notes: Sequence[NoteEvent], bpm: float, fase: float) -> list[NoteEvent]:
    """Desloca as notas para que a grade caia sobre elas, e não ao lado.

    `para_ticks` ancora a grade em `t=0`, e nenhuma gravação começa no tempo 1
    exato. Deslocar as notas é o caminho mais simples: preserva a aritmética da
    grade e produz o mesmo resultado que ancorar a grade na fase.

    O deslocamento é por uma grade inteira quando adiantar levaria antes do zero —
    `fase` e `fase - grade` descrevem o mesmo retículo, e tempo negativo nenhum
    formato de partitura representa.
    """
    if not fase:
        return list(notes)
    grade = 60.0 / bpm / 4
    recuo = fase if min(n.onset_s for n in notes) >= fase else fase - grade
    return [replace(n, onset_s=n.onset_s - recuo, offset_s=n.offset_s - recuo) for n in notes]


def para_ticks(segundos: float, bpm: float) -> int:
    """Quantiza para a grade de semicolcheia."""
    return round(segundos * bpm / 60 * PPQ / GRADE) * GRADE


def monofonizar(
    notes: Sequence[NoteEvent], bpm: float
) -> tuple[list[NoteEvent], list[NoteEvent]]:
    """Reduz cada grupo simultâneo à nota mais grave; devolve `(mantidas, descartadas)`.

    A colisão é medida **na grade**, não no relógio: duas notas a 20 ms de
    distância são eventos distintos no áudio e o mesmo tick de semicolcheia, e é
    o tick que `eventos` recusa. Filtrar por onset cru deixaria o erro passar
    para o exportador.

    A escolha da mais grave é do domínio: num acorde de baixo quem sustenta a
    harmonia é a fundamental, e o resto costuma ser vazamento de outro
    instrumento ou harmônico mal decodificado (ADR-014). Nada é descartado em
    silêncio — a lista de descartes é devolvida para quem chamou relatar.
    """
    melhor: dict[int, NoteEvent] = {}
    descartadas: list[NoteEvent] = []
    for nota in sorted(notes, key=lambda n: n.onset_s):
        tick = para_ticks(nota.onset_s, bpm)
        anterior = melhor.get(tick)
        if anterior is None or nota.pitch < anterior.pitch:
            melhor[tick] = nota
            if anterior is not None:
                descartadas.append(anterior)
        else:
            descartadas.append(nota)

    return sorted(melhor.values(), key=lambda n: n.onset_s), descartadas


def eventos(notes: Sequence[TabNote], bpm: float) -> list[tuple[int, int, TabNote]]:
    """`(início, duração, nota)` em ticks, sem sobreposição e sem cruzar a barra.

    Recusa notas simultâneas: a tablatura é monofônica (ADR-012) e empilhá-las
    produziria posição impossível de tocar.
    """
    ordenadas = sorted(notes, key=lambda t: t.event.onset_s)
    inicios = [para_ticks(t.event.onset_s, bpm) for t in ordenadas]
    for (anterior, _), (seguinte, tab) in pairwise(list(zip(inicios, ordenadas, strict=True))):
        if anterior == seguinte:
            raise ValueError(
                f"notas simultâneas em {tab.event.onset_s:.2f}s: a tablatura é "
                "monofônica e empilhá-las produziria posição impossível"
            )

    saida = []
    for i, (inicio, tab) in enumerate(zip(inicios, ordenadas, strict=True)):
        proxima = inicios[i + 1] if i + 1 < len(inicios) else COMPASSO * (inicio // COMPASSO + 1)
        ate_a_barra = COMPASSO * (inicio // COMPASSO + 1)
        fim = min(para_ticks(tab.event.offset_s, bpm), proxima, ate_a_barra)
        saida.append((inicio, max(GRADE, fim - inicio), tab))
    return saida
