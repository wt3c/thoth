"""O MuScriptor de verdade passando pelo cache em disco (ADR-052).

O teste unitário usa um contador no lugar do modelo; aqui o que se afirma é que a
saída real — notas e ataques, com os floats que o modelo dá — volta do JSON igual ao
que saiu do subprocesso, e que a volta não roda o modelo.
"""

from __future__ import annotations

import shutil
import time
from pathlib import Path

import pytest

from tests.sintetico import SOUNDFONT, renderizar
from thoth.adapters.transcription.muscriptor import MuscriptorTranscriber
from thoth.services.cache_transcricao import TranscritorEmCache, em_cache

pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(not SOUNDFONT.exists(), reason=f"soundfont ausente: {SOUNDFONT}"),
    pytest.mark.skipif(shutil.which("fluidsynth") is None, reason="fluidsynth ausente"),
]


def test_o_resultado_do_modelo_volta_do_disco_igual(tmp_path: Path) -> None:
    wav, _ = renderizar("escala", tmp_path)
    cache = em_cache(MuscriptorTranscriber(), tmp_path / "cache")
    assert isinstance(cache, TranscritorEmCache)

    inicio = time.perf_counter()
    primeira = cache.transcribe(wav)
    modelo_s = time.perf_counter() - inicio

    inicio = time.perf_counter()
    segunda = em_cache(MuscriptorTranscriber(), tmp_path / "cache").transcribe(wav)
    disco_s = time.perf_counter() - inicio
    print(f"modelo {modelo_s:.1f} s, disco {disco_s:.3f} s, {len(primeira.notas)} notas")

    assert primeira.notas
    assert segunda == primeira
    assert disco_s < 1.0
