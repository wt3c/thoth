"""Verificador de oitava contra áudio real — o erro que atravessa até a tablatura.

Origem: Fase 0 mediu 12 notas (7% da linha) em que o stem do Demucs diz B0 e a
mix diz B1. Oitava errada é corda e casa erradas, e nenhuma etapa posterior
detecta. O discriminador é a **presença da fundamental**: um B0 real tem energia
em 30,9 Hz; um B1 confundido com B0 não tem, porque 61,7 Hz é a fundamental do
B1 e ao mesmo tempo o 2º harmônico do B0.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from thoth.domain.models import NoteEvent
from thoth.services.octave_check import verificar_oitavas

B0, B1 = 23, 35  # 30,87 Hz e 61,74 Hz


def _tom(destino: Path, parciais: tuple[float, ...], duracao: float = 1.5) -> Path:
    """Gera um WAV real somando parciais — nota de baixo tem harmônicos, não é seno puro."""
    expr = "+".join(f"0.3*sin(2*PI*{f}*t)/{i + 1}" for i, f in enumerate(parciais))
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
         "-i", f"aevalsrc='{expr}':s=44100:d={duracao}", "-ac", "2", str(destino)],
        check=True,
    )
    return destino


@pytest.fixture
def b0_real(tmp_path: Path) -> Path:
    """B0 de verdade: fundamental em 30,9 Hz e a série harmônica acima dela."""
    return _tom(tmp_path / "b0.wav", (30.87, 61.74, 92.61, 123.48))


@pytest.fixture
def b1_real(tmp_path: Path) -> Path:
    """B1 de verdade: nenhuma energia em 30,9 Hz — é o caso que o stem confunde."""
    return _tom(tmp_path / "b1.wav", (61.74, 123.48, 185.22))


def _nota(pitch: int) -> NoteEvent:
    return NoteEvent(pitch=pitch, onset_s=0.2, offset_s=1.2, instrument="electric_bass")


def test_nota_correta_no_grave_nao_gera_aviso(b0_real: Path) -> None:
    assert verificar_oitavas(b0_real, [_nota(B0)]) == []


def test_nota_correta_uma_oitava_acima_nao_gera_aviso(b1_real: Path) -> None:
    assert verificar_oitavas(b1_real, [_nota(B1)]) == []


def test_b1_transcrito_como_b0_e_sinalizado(b1_real: Path) -> None:
    """O caso medido na Fase 0: fundamental ausente, só o harmônico presente."""
    avisos = verificar_oitavas(b1_real, [_nota(B0)])

    assert len(avisos) == 1
    assert avisos[0].event.pitch == B0
    assert avisos[0].suggested_pitch == B1


def test_sem_notas_nao_gera_aviso(b1_real: Path) -> None:
    assert verificar_oitavas(b1_real, []) == []


def test_ignora_nota_fora_do_audio(b1_real: Path) -> None:
    """Nota depois do fim do arquivo não trava nem vira aviso falso."""
    tardia = NoteEvent(pitch=B0, onset_s=99.0, offset_s=99.5, instrument="electric_bass")

    assert verificar_oitavas(b1_real, [tardia]) == []


def test_fundamental_fraca_ainda_e_sinalizada(tmp_path: Path) -> None:
    """Grave contaminado: 30,9 Hz presente, mas a 20% do 2º harmônico — abaixo do limiar."""
    wav = _tom(tmp_path / "fraca.wav", (61.74, 123.48))
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
         "-i", "aevalsrc='0.06*sin(2*PI*30.87*t)+0.3*sin(2*PI*61.74*t)':s=44100:d=1.5",
         "-ac", "2", str(wav)],
        check=True,
    )

    assert [a.suggested_pitch for a in verificar_oitavas(wav, [_nota(B0)])] == [B1]


def test_fundamental_presente_nao_e_sinalizada(tmp_path: Path) -> None:
    """A mesma nota com a fundamental em 80% do 2º harmônico: acima do limiar, passa."""
    wav = tmp_path / "presente.wav"
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
         "-i", "aevalsrc='0.24*sin(2*PI*30.87*t)+0.3*sin(2*PI*61.74*t)':s=44100:d=1.5",
         "-ac", "2", str(wav)],
        check=True,
    )

    assert verificar_oitavas(wav, [_nota(B0)]) == []
