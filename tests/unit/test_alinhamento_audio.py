"""Tab levada ao tempo do stem por DTW sobre croma, sem olhar a transcrição (ADR-042)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf

from thoth.domain.models import NoteEvent
from thoth.services.alinhamento_audio import HOP, SR, alinhar_ao_stem

HOP_S = HOP / SR


def _tab(n: int = 150, semente: int = 0) -> list[NoteEvent]:
    """Linha irregular, alturas sorteadas: sem isso qualquer encaixe serve."""
    gera = np.random.default_rng(semente)
    ataques = 0.5 + np.cumsum(gera.choice([0.25, 0.5, 0.75], size=n))
    alturas = gera.integers(28, 48, size=n)
    return [
        NoteEvent(int(p), float(t), float(t) + 0.2, "electric_bass")
        for t, p in zip(ataques, alturas, strict=True)
    ]


def _stem(caminho: Path, notas: list[NoteEvent], duracao_s: float) -> Path:
    """Fundamental e dois harmônicos por nota: o croma só precisa da classe de altura."""
    t = np.arange(int(duracao_s * SR)) / SR
    y = np.zeros_like(t)
    for n in notas:
        f = 440.0 * 2 ** ((n.pitch - 69) / 12)
        trecho = (t >= n.onset_s) & (t < n.offset_s)
        fase = t[trecho] - n.onset_s
        envelope = np.exp(-fase * 4)
        y[trecho] += sum(np.sin(2 * np.pi * k * f * fase) / k for k in (1, 2, 3)) * envelope
    sf.write(caminho, 0.3 * y / np.abs(y).max(), SR)
    return caminho


def test_recupera_escala_e_deslocamento_da_gravacao(tmp_path: Path) -> None:
    ref = _tab()
    tocada = [
        NoteEvent(n.pitch, n.onset_s * 0.95 + 1.5, n.offset_s * 0.95 + 1.5, n.instrument)
        for n in ref
    ]
    stem = _stem(tmp_path / "bass.wav", tocada, tocada[-1].offset_s + 2.0)

    alinhada = alinhar_ao_stem(ref, stem)

    erros = np.abs([a.onset_s - t.onset_s for a, t in zip(alinhada, tocada, strict=True)])
    print(f"erro mediano {np.median(erros):.3f} s · p90 {np.percentile(erros, 90):.3f} s")
    assert np.median(erros) < HOP_S
    assert [a.pitch for a in alinhada] == [n.pitch for n in ref]


def test_trecho_mais_lento_no_meio_e_acompanhado(tmp_path: Path) -> None:
    """O que a escala global do ADR-041 não faz: a banda desacelera só num trecho."""
    ref = _tab()
    meio = ref[len(ref) // 2].onset_s

    def tempo(t: float) -> float:
        return t if t < meio else meio + (t - meio) * 1.1

    tocada = [
        NoteEvent(n.pitch, tempo(n.onset_s), tempo(n.onset_s) + 0.2, n.instrument) for n in ref
    ]
    stem = _stem(tmp_path / "bass.wav", tocada, tocada[-1].offset_s + 1.0)

    alinhada = alinhar_ao_stem(ref, stem)

    erros = np.abs([a.onset_s - t.onset_s for a, t in zip(alinhada, tocada, strict=True)])
    print(f"erro mediano {np.median(erros):.3f} s")
    assert np.median(erros) < HOP_S
