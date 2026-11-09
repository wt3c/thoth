"""Digitação aprendida nas tabs humanas de `samples/`, só para baixo de 4 cordas (ADR-055).

Perceptron estruturado com média sobre o mesmo Viterbi do `experiente`: em vez de
pesos escolhidos à mão (ADR-050), o caminho humano de cada frase de treino puxa os
pesos para si. As features não dependem da afinação: casa e região da casa, corda
solta, cordas atravessadas, deslocamento da mão em faixas e deslocamento rápido.

A mão segue o ADR-032 com alcance zero: é a última casa pisada, e corda solta não
a move.

Validado deixando uma tab de fora: as três de 4 cordas ganharam de 0,08 a 0,10;
as de 5 e 6 cordas, do mesmo baixista, perderam. Por isso, fora de 4 cordas, a
digitação fica com a `reserva` (o `experiente`). _Você_ e _Fear of the Dark_ nunca
entram no treino: são os testes.
"""

from __future__ import annotations

import hashlib
import json
import random
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from thoth.domain.models import NoteEvent, TabNote
from thoth.domain.ports import FretAssigner
from thoth.services.fretboard import PADRAO, AlturaImpossivelError, ViterbiFretAssigner, _posicoes

if TYPE_CHECKING:
    from thoth.services.tab_referencia import Referencia

#: Mesmo estado do `ViterbiFretAssigner` com alcance zero: corda, casa, mão.
_Estado = tuple[int, int, int | None]

#: Pesos travados, com a identidade das tabs que os produziram.
MODELO = Path(__file__).with_name("digitacao_aprendida.json")

#: As tabs que só medem. Nunca entram em `treinar`.
ACEITACAO = "catedral-voce_build.gp5"
TESTE_LIMPO = "Iron Maiden - Fear Of The Dark.gp5"

CORDAS = 4
EPOCAS = 10
FRASE = 32
FRASES_POR_MUSICA = 40
#: Abaixo disso entre duas notas, o deslocamento da mão pesa a mais.
CURTO_S = 0.25


@dataclass(frozen=True, slots=True)
class Modelo:
    pesos: dict[str, float]
    treino: dict[str, str]
    """Nome da tab → sha256 do arquivo."""


def carregar_modelo(caminho: Path = MODELO) -> Modelo:
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    return Modelo(pesos=dados["pesos"], treino=dados["treino"])


def sha256(caminho: Path) -> str:
    return hashlib.sha256(caminho.read_bytes()).hexdigest()


def _faixa(valor: float, cortes: tuple[int, ...]) -> int:
    return next(i for i, corte in enumerate(cortes) if valor <= corte)


def caracteristicas(anterior: _Estado | None, atual: _Estado, dt: float) -> dict[str, float]:
    """Features de chegar em `atual` vindo de `anterior` (`None` na primeira nota)."""
    corda, casa, mao = atual
    f = {"casa": casa / 12, "solta": float(casa == 0)}
    if casa:
        f[f"regiao{_faixa(casa, (4, 9, 14, 99))}"] = 1.0
    if anterior is not None:
        c0, k0, m0 = anterior
        dc = abs(corda - c0)
        f["dcorda"] = dc
        f[f"dcorda_f{min(dc, 3)}"] = 1.0
        if k0 == 0 and casa == 0:
            f["solta_solta"] = 1.0
        if m0 is not None and mao is not None:
            dm = abs(mao - m0)
            f["dmao"] = dm
            f[f"dmao_f{_faixa(dm, (0, 2, 4, 7, 99))}"] = 1.0
            if dt < CURTO_S:
                f["dmao_curto"] = dm
    return f


def _pontua(pesos: Mapping[str, float], f: Mapping[str, float]) -> float:
    return sum(pesos.get(k, 0.0) * v for k, v in f.items())


def _estado(posicao: tuple[int, int], mao: int | None) -> _Estado:
    corda, casa = posicao
    return (corda, casa, casa if casa else mao)


def _viterbi(
    pesos: Mapping[str, float], notas: list[NoteEvent], afinacao: tuple[int, ...], max_fret: int
) -> list[_Estado]:
    """Caminho de maior pontuação; `notas` já em ordem de onset."""
    opcoes = []
    for nota in notas:
        posicoes = _posicoes(nota.pitch, afinacao, max_fret)
        if not posicoes:
            raise AlturaImpossivelError(
                f"pitch {nota.pitch} em {nota.onset_s:.2f}s não cabe na afinação "
                f"{afinacao} até o traste {max_fret}"
            )
        opcoes.append(posicoes)
    valor = {
        s: _pontua(pesos, caracteristicas(None, s, 0.0))
        for s in (_estado(p, None) for p in opcoes[0])
    }
    camadas: list[dict[_Estado, _Estado]] = []
    for i in range(1, len(notas)):
        dt = notas[i].onset_s - notas[i - 1].onset_s
        novo: dict[_Estado, float] = {}
        de: dict[_Estado, _Estado] = {}
        for p in opcoes[i]:
            for s0, v0 in valor.items():
                s = _estado(p, s0[2])
                v = v0 + _pontua(pesos, caracteristicas(s0, s, dt))
                if s not in novo or v > novo[s]:
                    novo[s], de[s] = v, s0
        camadas.append(de)
        valor = novo
    s = max(valor, key=valor.__getitem__)
    caminho = [s]
    for de in reversed(camadas):
        s = de[s]
        caminho.append(s)
    return caminho[::-1]


@dataclass(frozen=True, slots=True)
class DigitacaoAprendida:
    """Implementa o `FretAssigner`. Fora de 4 cordas, delega à `reserva`."""

    pesos: Mapping[str, float]
    reserva: FretAssigner = field(default_factory=lambda: ViterbiFretAssigner(custos=PADRAO))

    def assign(
        self, notes: list[NoteEvent], tuning: tuple[int, ...], max_fret: int = 24
    ) -> list[TabNote]:
        if len(tuning) != CORDAS:
            return self.reserva.assign(notes, tuning, max_fret)
        if not notes:
            return []
        notes = sorted(notes, key=lambda n: (n.onset_s, n.pitch))
        caminho = _viterbi(self.pesos, notes, tuning, max_fret)
        return [
            TabNote(event=nota, string=s[0], fret=s[1])
            for nota, s in zip(notes, caminho, strict=True)
        ]


def _caminho_humano(tablatura: list[TabNote]) -> list[_Estado]:
    caminho: list[_Estado] = []
    mao = None
    for t in tablatura:
        mao = t.fret if t.fret else mao
        caminho.append((t.string, t.fret, mao))
    return caminho


def _soma(caminho: list[_Estado], notas: list[NoteEvent]) -> dict[str, float]:
    total: dict[str, float] = {}
    for i, s in enumerate(caminho):
        anterior = caminho[i - 1] if i else None
        dt = notas[i].onset_s - notas[i - 1].onset_s if i else 0.0
        for k, v in caracteristicas(anterior, s, dt).items():
            total[k] = total.get(k, 0.0) + v
    return total


def treinar(tabs: Mapping[str, Referencia], semente: int = 0) -> dict[str, float]:
    """Perceptron com média; o mesmo número de frases por música a cada época.

    Parte do `experiente` (ADR-050), com sinal de pontuação.
    """
    if ACEITACAO in tabs or TESTE_LIMPO in tabs:
        raise ValueError("tab de teste no treino")
    rng = random.Random(semente)
    pesos = {
        "casa": -PADRAO.traste_alto * 12,
        "dmao": -PADRAO.deslocamento,
        "dcorda": -PADRAO.troca_corda,
    }
    soma: dict[str, float] = {}
    n = 0
    frases = {
        nome: [
            (r.notas[i : i + FRASE], r.tablatura[i : i + FRASE], r.afinacao)
            for i in range(0, len(r.notas) - 1, FRASE)
        ]
        for nome, r in tabs.items()
    }
    for _ in range(EPOCAS):
        lote = [rng.choice(fs) for fs in frases.values() for _ in range(FRASES_POR_MUSICA)]
        rng.shuffle(lote)
        for notas, tablatura, afinacao in lote:
            ouro = _caminho_humano(tablatura)
            previsto = _viterbi(pesos, notas, afinacao, 24)
            if [s[:2] for s in previsto] != [s[:2] for s in ouro]:
                fo, fp = _soma(ouro, notas), _soma(previsto, notas)
                for k in fo.keys() | fp.keys():
                    pesos[k] = pesos.get(k, 0.0) + fo.get(k, 0.0) - fp.get(k, 0.0)
            n += 1
            for k, v in pesos.items():
                soma[k] = soma.get(k, 0.0) + v
    return {k: v / n for k, v in soma.items()}


if TYPE_CHECKING:  # pragma: no cover — trava a assinatura contra o Protocol
    _: FretAssigner = DigitacaoAprendida({})
