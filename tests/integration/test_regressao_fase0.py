"""Portão de regressão: as fixtures da Fase 0, travadas nos números medidos.

Vale **apenas para o modelo `small`** na revisão fixada em `models.lock.toml`
(ADR-009): os pisos abaixo são medição daquele checkpoint, não meta de
qualidade. Trocar de modelo exige remedir, não afrouxar o piso.

O portão cobre a cadeia inteira — geração da fixture, MuScriptor e o avaliador —
porque um avaliador quebrado produz decisão errada com a mesma facilidade com
que um transcritor quebrado produz tablatura errada.
"""

from __future__ import annotations

import shutil
from collections import Counter
from pathlib import Path

import pytest

from tests.sintetico import SOUNDFONT, renderizar
from thoth.adapters.transcription.muscriptor import MuscriptorTranscriber
from thoth.services.evaluation import avaliar, notas_do_midi
from thoth.services.model_lock import caminho_no_cache, carregar_lock, conferir

RAIZ = Path(__file__).resolve().parents[2]

#: Sem folga: a renderização é byte-idêntica entre execuções (verificado por
#: SHA-256) e o MuScriptor está pregado em `muscriptor@0.3.0` sobre um
#: checkpoint conferido por hash. Uma folga uniforme seria enganosa de todo
#: jeito — 0,03 absorve uma nota perdida em `groove16` (32 notas) e nenhuma em
#: `graves` (10).
FOLGA = 0.0

#: (fixture, onset F1, nota F1) — condição livre, `small`, tolerância 50 ms.
BASELINE = [
    ("escala", 1.000, 0.968),
    ("graves", 1.000, 1.000),
    ("groove16", 1.000, 1.000),
    ("oitavas", 1.000, 1.000),
    ("walking", 0.938, 0.968),
    # Baixo + piano sem separação: o vazamento do piano é o próprio fenômeno
    # medido, e por isso o piso de nota F1 aqui é baixo de propósito.
    ("misto", 0.938, 0.682),
]

pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(not SOUNDFONT.exists(), reason=f"soundfont ausente: {SOUNDFONT}"),
    pytest.mark.skipif(shutil.which("fluidsynth") is None, reason="fluidsynth ausente"),
]


@pytest.fixture(scope="module")
def pesos_conferidos() -> None:
    """Os pisos descrevem um checkpoint específico; medir outro não significa nada."""
    modelo = carregar_lock(RAIZ / "models.lock.toml")["muscriptor-small"]
    for arquivo in modelo.arquivos:
        caminho = caminho_no_cache(modelo, arquivo)
        if caminho is None:
            pytest.skip("muscriptor-small ainda não está no cache do HuggingFace")
        conferir(caminho, arquivo)


@pytest.mark.parametrize(("nome", "piso_onset", "piso_nota"), BASELINE)
@pytest.mark.usefixtures("pesos_conferidos")
def test_fixture_nao_regrediu(
    nome: str, piso_onset: float, piso_nota: float, tmp_path: Path
) -> None:
    wav, _ = renderizar(nome, tmp_path)
    referencia = notas_do_midi(tmp_path / f"{nome}.mid")
    todas = MuscriptorTranscriber(model="small").transcribe(wav)
    estimativa = [n for n in todas if n.instrument == "electric_bass"]

    # Sem isto, um rótulo diferente (ADR-008: o MuScriptor já chamou baixo de
    # `acoustic_piano` em áudio curto) esvazia o filtro e o portão reporta
    # colapso total de qualidade em vez do que de fato mudou.
    assert estimativa, f"{nome}: nenhuma nota electric_bass; rótulos: {
        Counter(n.instrument for n in todas)}"

    resultado = avaliar(referencia, estimativa)

    assert resultado.onset_f1 >= piso_onset - FOLGA, f"{nome}: onset F1 {resultado}"
    assert resultado.note_f1 >= piso_nota - FOLGA, f"{nome}: nota F1 {resultado}"
