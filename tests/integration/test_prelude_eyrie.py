"""O buraco do prelude forcing, contra o modelo real, no trecho de *Eyrie* onde ele apareceu.

Com o forcing, o MuScriptor 0.3.0 devolve vazio para todo bloco a partir de ~50 s deste
trecho (557 s na música), com o baixo soando. A segunda passada sem o forcing precisa
preencher o buraco (emenda do ADR-008, 2026-09-25).

O arquivo é o stem de baixo de *Ne Obliviscaris - Eyrie* (YouTube `_RMax1LS3pM`) a partir de
520 s. Fica fora do repositório (áudio de terceiro, ADR-005); sem ele, `skip`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from thoth.adapters.transcription.muscriptor import MuscriptorTranscriber

TRECHO = Path.home() / "thoth-fase0" / "eyrie_stem_520s.wav"

#: O buraco, em segundos deste trecho: 557 a 671 s na música.
BURACO = (37.0, 151.0)
#: Medido em 2026-09-25: 382 notas no buraco pelo `transcribe`, 0 só com o forcing. O piso
#: fica bem abaixo: o teste prova que o buraco se preenche, a qualidade é outro assunto.
NOTAS_NO_BURACO_MINIMO = 200

pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(not TRECHO.exists(), reason=f"trecho de Eyrie ausente em {TRECHO}"),
]


def _no_buraco(onsets: list[float]) -> int:
    return sum(BURACO[0] <= t < BURACO[1] for t in onsets)


def test_o_forcing_ainda_emudece_este_trecho() -> None:
    """Sem isto, o teste de baixo passaria mesmo que o buraco tivesse sumido sozinho."""
    notas = MuscriptorTranscriber()._passada(TRECHO, prelude=True)

    medidas = _no_buraco([n.onset_s for n in notas])
    print(f"com o forcing: {medidas} notas no buraco")
    assert medidas == 0


def test_segunda_passada_preenche_o_buraco() -> None:
    notas = MuscriptorTranscriber().transcribe(TRECHO)

    medidas = _no_buraco([n.onset_s for n in notas])
    print(f"transcribe: {medidas} notas no buraco (piso {NOTAS_NO_BURACO_MINIMO})")
    assert medidas >= NOTAS_NO_BURACO_MINIMO
