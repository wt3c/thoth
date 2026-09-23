"""Tonalidade da linha → como escrever o acidente (ADR-031).

Sem tonalidade o acidente é ambíguo: a tecla preta entre lá e si é tanto A# quanto
Bb, e o Thoth fixava o sustenido (ADR-018). Em tom bemol isso está errado em toda
nota alterada — e o acervo tem: de sete músicas medidas, duas estimam fá menor e
uma ré menor, com 5,2% a 76,1% das notas carregando acidente.

A estimativa vem do music21 (Krumhansl sobre as alturas da linha, ponderadas pela
duração). Ela erra, e errar aqui é **pior que não opinar**: armadura errada obriga
o bequadro em quase toda nota. Medido numa linha de 12 notas em mi menor: 7
acidentes impressos com a armadura certa, 9 sem armadura nenhuma, 11 com a
armadura errada de quatro bemóis.

Daí a margem. O que decide a grafia não é o nome do tom, é o **sinal** da armadura:
mi menor e sol maior escrevem igual, então empate entre relativas é inofensivo. A
margem é contra a melhor interpretação de sinal oposto, e abaixo dela o Thoth fica
com o que já fazia — sustenidos, sem armadura.
"""

from __future__ import annotations

from dataclasses import dataclass

from music21 import key, note, stream

from thoth.domain.models import NoteEvent

#: Margem mínima contra a melhor interpretação de sinal oposto. Medida no acervo
#: (sete músicas): 0,000 · 0,095 · 0,327 · 0,403 · 0,511 · 0,620 · 0,774. O zero é
#: um empate exato (fá menor contra dó maior), e é o caso que esta margem existe para
#: recusar; o vizinho mais próximo dele está quase dez vezes acima.
MARGEM_MINIMA = 0.05

#: Teto de notas na análise. É um histograma ponderado: música longa satura muito
#: antes disso, e foi com este corte que o acervo foi medido.
LIMITE_DE_NOTAS = 2000

_MODOS = {"maior": "major", "menor": "minor"}


@dataclass(frozen=True, slots=True)
class Tonalidade:
    """O tom e o quanto se pode apostar nele."""

    nome: str
    sharps: int
    margem: float | None
    """Distância até a melhor interpretação de sinal oposto. `None` quando o tom
    veio de você — aí não há o que ranquear."""

    @property
    def confiavel(self) -> bool:
        return self.margem is None or self.margem > MARGEM_MINIMA

    @property
    def bemois(self) -> bool:
        """Se a grafia usa bemol. Tom duvidoso mantém o sustenido de sempre."""
        return self.confiavel and self.sharps < 0

    @property
    def armadura(self) -> int | None:
        """A armadura a escrever, ou `None` — que é o que a partitura tem hoje."""
        return self.sharps if self.confiavel else None


def estimar_tom(notas: list[NoteEvent]) -> Tonalidade | None:
    """Estima o tom da linha. Sem notas não há o que estimar — `None`, não dó maior."""
    if not notas:
        return None

    linha: stream.Stream[note.Note] = stream.Stream()
    for evento in notas[:LIMITE_DE_NOTAS]:
        alvo = note.Note(evento.pitch)
        # A análise é ponderada pela duração, que é tempo até a próxima nota e não
        # sustentação real (ADR-033): o peso é o do *espaço* que a nota ocupa na
        # frase, não o do som que ela prolonga. Serve igual para ranquear tom, e foi
        # assim que o ADR-031 mediu as sete músicas. Piso de semicolcheia para nota
        # sem duração útil.
        alvo.quarterLength = max(0.25, round(evento.duration_s * 2) / 2)
        linha.append(alvo)

    estimado = linha.analyze("key")
    bemol = estimado.sharps < 0
    oposta = next(
        (a for a in estimado.alternateInterpretations if (a.sharps < 0) != bemol), None
    )
    # Sem nenhuma interpretação de sinal oposto, nada contradiz a grafia: 2,0 é o
    # tamanho da faixa inteira da correlação (-1 a 1), ou seja, margem máxima.
    margem = (
        estimado.correlationCoefficient - oposta.correlationCoefficient if oposta else 2.0
    )
    return Tonalidade(nome=str(estimado), sharps=int(estimado.sharps), margem=float(margem))


def tom_de_texto(texto: str) -> Tonalidade:
    """`"Bb maior"`, `"f menor"` → `Tonalidade`. Tom informado não passa por margem.

    Texto que não é tom é `ValueError`, nunca dó maior calado — o mesmo princípio
    do catálogo de afinações (ADR-025).
    """
    partes = texto.split()
    if len(partes) != 2 or partes[1].lower() not in _MODOS:
        raise ValueError(f"{texto!r} não é um tom; use 'Bb maior' ou 'f menor'")

    # music21 escreve bemol com hífen: Bb vira B-. O 'b' da tônica é o único que
    # pode virar hífen; 'B' maiúsculo é a nota si.
    tonica = partes[0][:1].upper() + partes[0][1:].replace("b", "-")
    try:
        lido = key.Key(tonica, _MODOS[partes[1].lower()])
    except Exception as erro:  # music21 levanta tipos próprios em cada camada
        raise ValueError(f"{texto!r} não é um tom: {erro}") from erro
    return Tonalidade(nome=str(lido), sharps=int(lido.sharps), margem=None)
