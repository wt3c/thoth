"""Segundos → tempo musical. O que os dois exportadores precisam compartilhar.

**O andamento é entrada, não estimativa.** O Thoth ainda não estima tempo (o
checkpoint do Beat This! está inacessível — C2 no `todo.md`), e nenhum formato de
partitura guarda segundos: todos guardam compassos, tempos e figuras. Sem BPM não
há arquivo, então ele é parâmetro explícito em vez de palpite silencioso — um BPM
errado não quebra nada, produz uma leitura errada, que é pior.
"""

from __future__ import annotations

from collections.abc import Sequence
from itertools import pairwise

from thoth.domain.models import TabNote

PPQ = 960  # ticks por semínima (convenção do GP5)
GRADE = PPQ // 4  # semicolcheia: a menor figura que a grade reconhece
COMPASSO = PPQ * 4  # 4/4


def para_ticks(segundos: float, bpm: int) -> int:
    """Quantiza para a grade de semicolcheia."""
    return round(segundos * bpm / 60 * PPQ / GRADE) * GRADE


def eventos(notes: Sequence[TabNote], bpm: int) -> list[tuple[int, int, TabNote]]:
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
