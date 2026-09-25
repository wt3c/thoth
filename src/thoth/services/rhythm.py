"""Segundos → tempo musical. O que os dois exportadores precisam compartilhar.

**O andamento chega pronto aqui.** Nenhum formato de partitura guarda segundos:
todos guardam compassos, tempos e figuras, então sem BPM não há arquivo. Quem o
resolve é `services/tempo.py` — informado por você, ele manda; ausente, é estimado
do mix e anunciado (ADR-019). Nos dois casos `ajustar` acerta a fase da grade
contra as notas transcritas antes de `alinhar`, e só refina o andamento junto
quando ele foi estimado — o BPM que você informou manda, a âncora ninguém
informou (ADR-021). Grade precisa ancorada no lugar errado erra mais que grade
grosseira alinhada por acaso: as duas contas são uma só.

O BPM que chega a `para_ticks` é fracionário de propósito. O arquivo guarda o
inteiro, porque GP5 e MusicXML só têm campo inteiro; quantizar no inteiro é o bug
que o ADR-021 corrige — 0,46% de erro vira segundos de deriva no fim da música.
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
    return deslocar(notes, recuo_de_fase(notes, bpm, fase))


def recuo_de_fase(notes: Sequence[NoteEvent], bpm: float, fase: float) -> float:
    """Quanto `alinhar` recua. Devolvido à parte para quem precisa desfazer o recuo."""
    if not fase or not notes:
        return 0.0
    grade = 60.0 / bpm / 4
    return fase if min(n.onset_s for n in notes) >= fase else fase - grade


def deslocar(notes: Sequence[NoteEvent], recuo: float) -> list[NoteEvent]:
    """Anda com as notas no tempo, ataque e término juntos."""
    if not recuo:
        return list(notes)
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


def unir_por_tique(notes: Sequence[NoteEvent], bpm: float) -> list[NoteEvent]:
    """Leva cada nota ao primeiro ataque do seu tique, término intacto.

    É o `monofonizar` da guitarra: o acorde é medido **na grade**, e é o tique que
    `acordes_em_ticks` recusa com corda repetida. Duas notas a 60 ms são dois acordes
    para uma janela de 50 ms e um tique só para a semicolcheia; unidas antes do
    posicionador, a digitação é decidida para o que o exportador vai escrever.
    """
    primeiro: dict[int, float] = {}
    for nota in sorted(notes, key=lambda n: n.onset_s):
        primeiro.setdefault(para_ticks(nota.onset_s, bpm), nota.onset_s)
    return [replace(n, onset_s=primeiro[para_ticks(n.onset_s, bpm)]) for n in notes]


def eventos(notes: Sequence[TabNote], bpm: float) -> list[tuple[int, int, TabNote]]:
    """`(início, duração, nota)` em ticks, sem sobreposição.

    A duração sai **inteira**, ainda que atravesse a barra: quem decide como
    representar a continuação é o exportador, com ligadura (ADR-022). Cortar
    aqui trocava legato por ataque curto seguido de pausa, e o exportador nunca
    chegava a ver o que deveria ligar.

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
        # A última nota não tem quem a corte: vale a duração que ela tem mesmo.
        fim = para_ticks(tab.event.offset_s, bpm)
        if i + 1 < len(inicios):
            fim = min(fim, inicios[i + 1])
        saida.append((inicio, max(GRADE, fim - inicio), tab))
    return saida


def acordes_em_ticks(
    notes: Sequence[TabNote], bpm: float
) -> list[tuple[int, int, tuple[TabNote, ...]]]:
    """`(início, duração, acorde)` em ticks: notas do mesmo tique viram um acorde.

    O par polifônico de `eventos`, para a guitarra (ADR-044). A simultaneidade é a
    da grade, não a do relógio: dois acordes posicionados separados podem cair no
    mesmo tique, e aí só se juntam se não disputarem corda. O acorde soa até a nota
    mais longa dele ou até o acorde seguinte, o que vier antes.
    """
    grupos: dict[int, list[TabNote]] = {}
    for tab in notes:
        grupos.setdefault(para_ticks(tab.event.onset_s, bpm), []).append(tab)
    for inicio, grupo in grupos.items():
        cordas = [t.string for t in grupo]
        if len(cordas) != len(set(cordas)):
            raise ValueError(
                f"duas notas na mesma corda no tique {inicio} "
                f"({grupo[0].event.onset_s:.2f}s): o acorde não é tocável"
            )

    inicios = sorted(grupos)
    saida = []
    for i, inicio in enumerate(inicios):
        acorde = tuple(sorted(grupos[inicio], key=lambda t: t.string))
        fim = max(para_ticks(t.event.offset_s, bpm) for t in acorde)
        if i + 1 < len(inicios):
            fim = min(fim, inicios[i + 1])
        saida.append((inicio, max(GRADE, fim - inicio), acorde))
    return saida
