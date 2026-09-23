"""O que a separação compra, medido contra ground truth (Camada 1 do ADR-006).

O portão do `test_regressao_fase0.py` mede o **transcritor sozinho**: renderiza a
fixture e entrega o WAV direto ao MuScriptor. É a medição certa para detectar
regressão de modelo, e é a medição errada para decidir sobre o ADR-010 — que
manda separar antes de transcrever.

A diferença só aparece numa fixture. Cinco das seis são baixo solo saído de MIDI
limpo: rodar Demucs nelas responde *"atrapalha?"*, não *"ajuda?"*. O `misto` é o
único com conteúdo alheio — piano no registro médio, exatamente o vazamento que o
ADR-010 cita — e é o único ponto onde o ganho é mensurável em vez de argumentado.

Este teste é caro (Demucs + MuScriptor em CPU) e roda uma fixture só, de
propósito.
"""

from __future__ import annotations

import shutil
from collections import Counter
from pathlib import Path

import pytest

from tests.sintetico import SOUNDFONT, renderizar
from thoth.adapters.separation import DemucsSeparator
from thoth.adapters.transcription.muscriptor import MuscriptorTranscriber
from thoth.domain.models import NoteEvent
from thoth.services.evaluation import Scores, avaliar, notas_do_midi

#: Medido em `test_regressao_fase0.py`, `small`, sem separação. Não é piso: é a
#: referência do que a separação compra. Se a separação cair abaixo disto, quem
#: está errado é o ADR-010 — e o lugar de descobrir isso é aqui.
SEM_SEPARACAO_NOTA_F1 = 0.682
SEM_SEPARACAO_ONSET_F1 = 0.938
#: O piso de verdade: o valor que a separação **mediu** (ADR-010, emenda de
#: 2026-09-23). Com 0,682 no lugar, o portão passava com a separação perdendo
#: quatro notas de dezesseis e não dizia nada.
#:
#: Exato, sem folga, porque o F1 aqui é discreto: 16 notas de referência fazem a
#: menor diferença possível valer ~0,03. Não existe flutuação menor que isso para
#: uma folga absorver — o que houver é nota ganha ou perdida, e é para saber disso
#: que o portão existe.
COM_SEPARACAO_NOTA_F1 = 0.968

pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(not SOUNDFONT.exists(), reason=f"soundfont ausente: {SOUNDFONT}"),
    pytest.mark.skipif(shutil.which("fluidsynth") is None, reason="fluidsynth ausente"),
]


def _transcrever(wav: Path) -> list[NoteEvent]:
    todas = MuscriptorTranscriber(model="small").transcribe(wav)
    baixo = [n for n in todas if n.instrument == "electric_bass"]
    assert baixo, f"nenhuma nota electric_bass; rótulos: {Counter(n.instrument for n in todas)}"
    return baixo


def test_separar_antes_de_transcrever_nao_piora_o_misto(tmp_path: Path) -> None:
    """A afirmação do ADR-010 virada em número, sobre a única fixture que a testa."""
    wav, _ = renderizar("misto", tmp_path)
    referencia = notas_do_midi(tmp_path / "misto.mid")

    stem = DemucsSeparator().separate(wav, tmp_path / "stems")["bass"]
    com: Scores = avaliar(referencia, _transcrever(stem))

    print(f"\nmisto com separação: onset {com.onset_f1} nota {com.note_f1} "
          f"(piso {COM_SEPARACAO_NOTA_F1}; sem separação: onset {SEM_SEPARACAO_ONSET_F1} "
          f"nota {SEM_SEPARACAO_NOTA_F1}) ref={com.n_ref} est={com.n_est} "
          f"margem={com.note_f1 - COM_SEPARACAO_NOTA_F1:+.3f}")

    assert com.note_f1 >= SEM_SEPARACAO_NOTA_F1, (
        f"separar piorou o misto: {com.note_f1} < {SEM_SEPARACAO_NOTA_F1} — "
        "o ADR-010 precisa ser reaberto, não o piso afrouxado"
    )
    assert com.note_f1 >= COM_SEPARACAO_NOTA_F1, (
        f"a separação regrediu: {com.note_f1} < {COM_SEPARACAO_NOTA_F1} medido no "
        "ADR-010. Ainda é melhor que não separar, e é justamente por isso que o "
        "piso de 0,682 deixava passar"
    )
    assert com.onset_f1 >= SEM_SEPARACAO_ONSET_F1
