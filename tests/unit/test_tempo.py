"""Estimativa de andamento — contra áudio real, nunca mock.

O ponto em teste é justamente o que um mock apagaria: o quanto o estimador acerta
num sinal de verdade (Regra 3). O material é o mesmo das fixtures sintéticas, cujo
andamento é conhecido porque nós o escrevemos no MIDI.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.sintetico import BPM, SOUNDFONT, renderizar
from thoth.services.tempo import dobrar_para_faixa, estimar_andamento

requer_soundfont = pytest.mark.skipif(not SOUNDFONT.exists(), reason="soundfont ausente")


@pytest.mark.parametrize(
    ("bruto", "esperado"),
    [
        (45.3, 90.6),   # erro de metade — o caso real do fixture `misto`
        (180.0, 90.0),  # erro de dobro
        (89.1, 89.1),   # já na faixa: não mexe
        (22.0, 88.0),   # duas dobras
    ],
)
def test_dobra_o_andamento_para_a_faixa_musical(bruto: float, esperado: float) -> None:
    assert dobrar_para_faixa(bruto) == pytest.approx(esperado, abs=0.1)


@requer_soundfont
@pytest.mark.parametrize("nome", ["escala", "walking", "groove16", "graves", "misto"])
def test_acerta_o_andamento_das_fixtures(nome: str, tmp_path: Path) -> None:
    """Todas foram geradas a 90 BPM: é ground truth escrito por nós, não opinião."""
    wav, _ = renderizar(nome, tmp_path)

    andamento = estimar_andamento(wav)

    assert andamento.bpm == pytest.approx(BPM, abs=4)


@requer_soundfont
def test_relata_desacordo_entre_os_dois_metodos(tmp_path: Path) -> None:
    """`groove16` é o caso conhecido: o segundo método lê 117 onde o primeiro lê 89."""
    wav, _ = renderizar("groove16", tmp_path)

    andamento = estimar_andamento(wav)

    assert andamento.bpm == pytest.approx(BPM, abs=4)
    assert not andamento.confiavel
    assert andamento.conferencia != pytest.approx(andamento.bpm, rel=0.05)


@requer_soundfont
def test_concorda_quando_o_pulso_e_claro(tmp_path: Path) -> None:
    wav, _ = renderizar("walking", tmp_path)

    assert estimar_andamento(wav).confiavel
