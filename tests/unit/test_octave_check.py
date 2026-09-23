"""Verificador de oitava contra áudio real — o erro que atravessa até a tablatura.

Origem: Fase 0 mediu 12 notas (7% da linha) em que o stem do Demucs diz B0 e a
mix diz B1. Oitava errada é corda e casa erradas, e nenhuma etapa posterior
detecta. O discriminador é a **presença da fundamental**: um B0 real tem energia
em 30,9 Hz; um B1 confundido com B0 não tem, porque 61,7 Hz é a fundamental do
B1 e ao mesmo tempo o 2º harmônico do B0.
"""

from __future__ import annotations

import subprocess
import tracemalloc
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


def test_a_janela_para_no_fim_da_nota(tmp_path: Path) -> None:
    """Nota curta seguida de um grave forte: a janela fixa de 0,6 s pegava o vizinho.

    A nota dura 0,3 s e é um B1 (sem nada em 30,9 Hz). Depois dela entra um
    30,9 Hz forte, que não é dela. Com a janela fixa, a fundamental "aparecia" e o
    B1 transcrito como B0 passava calado — o defeito que o aviso existe para pegar.
    """
    wav = tmp_path / "vizinha.wav"
    expr = (
        "(0.3*sin(2*PI*61.74*t)+0.15*sin(2*PI*123.48*t))*between(t,0,0.3)"
        "+0.6*sin(2*PI*30.87*t)*gt(t,0.32)"
    )
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
         "-i", f"aevalsrc='{expr}':s=44100:d=1.5", "-ac", "2", str(wav)],
        check=True,
    )
    curta = NoteEvent(pitch=B0, onset_s=0.0, offset_s=0.3, instrument="electric_bass")

    assert [a.suggested_pitch for a in verificar_oitavas(wav, [curta])] == [B1]


def test_nao_le_o_stem_inteiro_na_memoria(tmp_path: Path) -> None:
    """Uma música de 16 min custaria centenas de MB para analisar meio segundo.

    O pico medido é o que sobra depois de descontar a janela analisada (~0,2 MB
    para 0,5 s em float64); o arquivo inteiro aqui já daria 16 MB.
    """
    wav = _tom(tmp_path / "longo.wav", (61.74, 123.48), duracao=30.0)
    tardia = NoteEvent(pitch=B0, onset_s=29.0, offset_s=29.5, instrument="electric_bass")

    tracemalloc.start()
    try:
        avisos = verificar_oitavas(wav, [tardia])
        _, pico = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()

    assert [a.suggested_pitch for a in avisos] == [B1], "a análise tem que continuar valendo"
    assert pico < 2_000_000, f"pico de {pico / 1e6:.1f} MB para meio segundo de áudio"


def test_sem_alternativa_melhor_o_aviso_nao_sugere_oitava(tmp_path: Path) -> None:
    """Fundamental fraca **e** oitava acima pior: é diagnóstico, não sugestão (ADR-030).

    `pitch + 12` deixa de ser afirmado e passa a ser ranqueado pelo mesmo
    discriminador. Aqui a hipótese original mede ~0,33 (abaixo do limiar, avisa) e
    a candidata mede ~0,12 — pior. Sugerir a troca seria trocar uma altura
    duvidosa por outra ainda menos sustentada.
    """
    wav = tmp_path / "nenhuma.wav"
    expr = "0.02*sin(2*PI*30.87*t)+0.06*sin(2*PI*61.74*t)+0.5*sin(2*PI*123.48*t)"
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
         "-i", f"aevalsrc='{expr}':s=44100:d=1.5", "-ac", "2", str(wav)],
        check=True,
    )

    avisos = verificar_oitavas(wav, [_nota(B0)])

    assert len(avisos) == 1, "a nota continua suspeita: a fundamental não se sustenta"
    medido = f"razao={avisos[0].fundamental_ratio:.2f} candidata={avisos[0].suggested_ratio:.2f}"
    assert avisos[0].suggested_pitch is None, medido
    assert avisos[0].suggested_ratio < avisos[0].fundamental_ratio, medido


def test_a_sugestao_vem_com_a_razao_que_a_sustenta(b1_real: Path) -> None:
    """Expor só a altura devolveria o mesmo palpite cego de antes (ADR-030)."""
    aviso = verificar_oitavas(b1_real, [_nota(B0)])[0]

    assert aviso.suggested_pitch == B1
    assert aviso.suggested_ratio > aviso.fundamental_ratio
