"""Sinaliza notas cuja fundamental não existe no áudio — provável erro de oitava.

Por que existe: a separação de fontes erra a oitava para baixo em material grave
e denso (Fase 0: 12 de 165 notas). Oitava errada vira corda e casa erradas na
tablatura, e nenhuma etapa posterior do pipeline detecta.

O discriminador é a fundamental **medida contra o próprio 2º harmônico**, não
contra o piso de ruído. Num arranjo denso o piso é alto e irregular — bumbo e
guitarra ocupam a mesma região —, e a versão com piso pegou só 3 das 12 notas
erradas conhecidas, criando 12 alarmes. A razão `f0 / 2·f0` é interna à nota e
imune a isso: se a nota for mesmo `p`, as duas parciais coexistem; se for
`p+12`, o que chamamos de `f0` é só o piso abaixo da fundamental real.

Limiar 0,40, calibrado nos dados reais de *Equus* (Fase 0): pega **12 de 12**
notas erradas conhecidas e sinaliza 11 de 127 notas concordantes (8,7%), das
quais 6 estão em `pitch <= 28` — registro em que a fundamental é fisicamente
fraca, então lá o alarme é esperado.

**Fora do Equus o limiar não se sustenta** (emenda do ADR-030): contra três tabs
alinhadas ao stem, alarma de 31 a 39% das notas que a tab confirma, e nenhum limiar de 0,2 a
1,0 separa. O aviso é diagnóstico da nota, não triagem.

A oitava acima é **ranqueada, não afirmada** (ADR-030): a mesma razão é medida para
`pitch + 12`, e a sugestão só sai quando ela explica o áudio melhor que a altura
transcrita. Quando nenhuma das duas se sustenta, o aviso sai sem alternativa — que é
a informação honesta, e não um palpite com cara de correção.

Isto **sinaliza para conferência**, não corrige: gravação com corte de graves
pode atenuar uma fundamental legítima, e o próprio B0 de um baixo real irradia
pouco em 30,9 Hz. A saída é para conferir contra tablatura de referência
(ADR-007), não uma correção automática — e, fora do Equus, não é curta (acima).
"""

from __future__ import annotations

import wave
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from thoth.domain.models import NoteEvent

#: Meio-tom para cada lado — tolera desafinação e vibrato sem varrer a nota vizinha.
_LARGURA = 2 ** (1 / 24)


@dataclass(frozen=True, slots=True)
class OctaveWarning:
    """Nota cuja fundamental não aparece no áudio, com a alternativa ranqueada."""

    event: NoteEvent
    suggested_pitch: int | None
    """`pitch + 12` quando a oitava acima explica o áudio melhor; `None` quando nenhuma
    das duas se sustenta — aí o aviso é diagnóstico puro (ADR-030)."""
    fundamental_ratio: float
    """Energia em `f0` dividida pela do 2º harmônico. Quanto menor, mais suspeita."""
    suggested_ratio: float
    """A mesma conta para `pitch + 12`, cuja fundamental é o 2º harmônico desta nota."""


def _frequencia(pitch: int) -> float:
    return 440.0 * 2 ** ((pitch - 69) / 12)


def _trecho_mono(w: wave.Wave_read, inicio: int, quadros: int) -> np.ndarray:
    """Só os quadros pedidos, em mono, `float64` em -1..1.

    Lê por posição em vez do arquivo inteiro: um stem de 16 min em `float64` são
    centenas de MB para analisar meio segundo de cada nota (ADR-029).
    """
    w.setpos(inicio)
    # `astype` não é redundante: o buffer vem `<i2` e a média inteira truncaria.
    amostras = np.frombuffer(w.readframes(quadros), dtype="<i2")
    canais = w.getnchannels()
    misturado = amostras.reshape(-1, canais).mean(axis=1) if canais > 1 else amostras
    return misturado.astype(np.float64) / 32768.0


def _pico_na_banda(espectro: np.ndarray, frequencias: np.ndarray, f: float) -> float:
    banda = (frequencias > f / _LARGURA) & (frequencias < f * _LARGURA)
    return float(espectro[banda].max()) if banda.any() else 0.0


def verificar_oitavas(
    wav: Path,
    notes: list[NoteEvent],
    *,
    janela_s: float = 0.6,
    limiar: float = 0.40,
) -> list[OctaveWarning]:
    """Devolve as notas cuja fundamental não se sustenta acima do piso de ruído.

    `janela_s` é o **teto** da janela: a análise para no `offset_s` da nota, para
    não medir o vizinho (ADR-029). O teto de 0,6 s dá ~1,7 Hz de resolução — o
    suficiente para separar 30,9 Hz de 61,7 Hz, as duas hipóteses do caso medido
    na Fase 0; nota de 0,2 s dá 5 Hz, que ainda separa as duas. Abaixo de 50 ms a
    função não opina. `limiar` é a razão `f0 / 2·f0` abaixo da qual a nota é
    suspeita; ver o módulo para a calibração.
    """
    if not notes:
        return []

    avisos = []
    with wave.open(str(wav)) as w:
        if w.getsampwidth() != 2:
            raise ValueError(f"esperado WAV PCM 16 bits, veio {w.getsampwidth() * 8} bits")
        taxa, total = w.getframerate(), w.getnframes()
        for nota in notes:
            inicio = int(nota.onset_s * taxa)
            # A janela para no fim da nota: 0,6 s fixos invadiam a nota seguinte, e a
            # fundamental do vizinho fazia a nota errada passar por certa (ADR-029).
            duracao = min(janela_s, max(0.0, nota.offset_s - nota.onset_s))
            quadros = min(int(duracao * taxa), max(0, total - inicio))
            if quadros < taxa // 20:  # menos de 50 ms: não dá resolução, não opina
                continue

            trecho = _trecho_mono(w, inicio, quadros)
            espectro = np.abs(np.fft.rfft(trecho * np.hanning(len(trecho))))
            frequencias = np.fft.rfftfreq(len(trecho), 1 / taxa)
            f0 = _frequencia(nota.pitch)
            fundamental = _pico_na_banda(espectro, frequencias, f0)
            segundo_harmonico = _pico_na_banda(espectro, frequencias, f0 * 2)
            quarto_harmonico = _pico_na_banda(espectro, frequencias, f0 * 4)

            razao = fundamental / segundo_harmonico if segundo_harmonico else float("inf")
            if razao >= limiar:
                continue
            # A mesma conta uma oitava acima: a fundamental de `pitch + 12` é o 2º
            # harmônico desta nota, e o 2º harmônico dela é o 4º desta. Ranquear em
            # vez de afirmar — e comparar as duas razões, não passar `limiar` de novo
            # numa população para a qual ele não foi calibrado (ADR-030).
            candidata = segundo_harmonico / quarto_harmonico if quarto_harmonico else float("inf")
            melhor = nota.pitch + 12 if candidata > razao else None
            avisos.append(OctaveWarning(nota, melhor, razao, candidata))
    return avisos
