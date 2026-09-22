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

Isto **sinaliza para conferência**, não corrige: gravação com corte de graves
pode atenuar uma fundamental legítima, e o próprio B0 de um baixo real irradia
pouco em 30,9 Hz. A saída é uma lista curta para a Camada 3 conferir contra
tablatura de referência (ADR-007), não uma correção automática.
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
    """Nota cuja fundamental não aparece no áudio, com a oitava sugerida."""

    event: NoteEvent
    suggested_pitch: int
    fundamental_ratio: float
    """Energia em `f0` dividida pela do 2º harmônico. Quanto menor, mais suspeita."""


def _frequencia(pitch: int) -> float:
    return 440.0 * 2 ** ((pitch - 69) / 12)


def _ler_mono(wav: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(wav)) as w:
        if w.getsampwidth() != 2:
            raise ValueError(f"esperado WAV PCM 16 bits, veio {w.getsampwidth() * 8} bits")
        quadros = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2")
        canais, taxa = w.getnchannels(), w.getframerate()
    amostras = quadros.reshape(-1, canais).mean(axis=1) if canais > 1 else quadros
    return amostras.astype(np.float64) / 32768.0, taxa


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

    `janela_s` de 0,6 s dá ~1,7 Hz de resolução — o suficiente para separar
    30,9 Hz de 61,7 Hz, as duas hipóteses do caso medido na Fase 0. `limiar` é a
    razão `f0 / 2·f0` abaixo da qual a nota é suspeita; ver o módulo para a
    calibração.
    """
    if not notes:
        return []

    sinal, taxa = _ler_mono(wav)
    avisos = []
    for nota in notes:
        inicio = int(nota.onset_s * taxa)
        trecho = sinal[inicio : inicio + int(janela_s * taxa)]
        if len(trecho) < taxa // 20:  # menos de 50 ms: não dá resolução, não opina
            continue

        espectro = np.abs(np.fft.rfft(trecho * np.hanning(len(trecho))))
        frequencias = np.fft.rfftfreq(len(trecho), 1 / taxa)
        f0 = _frequencia(nota.pitch)
        fundamental = _pico_na_banda(espectro, frequencias, f0)
        segundo_harmonico = _pico_na_banda(espectro, frequencias, f0 * 2)

        razao = fundamental / segundo_harmonico if segundo_harmonico else float("inf")
        if razao < limiar:
            avisos.append(OctaveWarning(nota, nota.pitch + 12, razao))
    return avisos
