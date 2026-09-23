"""Estimativa de andamento — contra áudio real, nunca mock.

O ponto em teste é justamente o que um mock apagaria: o quanto o estimador acerta
num sinal de verdade (Regra 3). O material é o mesmo das fixtures sintéticas, cujo
andamento é conhecido porque nós o escrevemos no MIDI.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.sintetico import BPM, SOUNDFONT, renderizar
from thoth.services.tempo import ajustar, dobrar_para_faixa, estimar_andamento, residuo

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


# --- Ajuste conjunto de andamento e fase (ADR-021) ---------------------------


def _onsets(bpm: float, fase: float, passos: list[int]) -> list[float]:
    """Onsets exatos numa grade de semicolcheia — o caso que o ajuste tem que recuperar."""
    grade = 60.0 / bpm / 4
    return [fase + p * grade for p in passos]


def test_recupera_andamento_fracionario_e_fase() -> None:
    """107,5 BPM é o caso do Equus: arredondar para 108 custa 3,5s de deriva em 756s."""
    onsets = _onsets(107.5, 0.137, list(range(0, 400, 2)))

    bpm, fase = ajustar(onsets, 108)

    assert bpm == pytest.approx(107.5, abs=0.05)
    # 2 ms é meio passo da busca de fase, e fica bem abaixo dos 3-10 ms de erro de
    # onset do próprio transcritor (medido nas fixtures): refinar mais não compra nada.
    assert residuo(onsets, bpm, fase) < 0.002


def test_nao_mexe_no_que_ja_esta_certo() -> None:
    """Fixtures são 90 BPM exatos ancorados em zero: o ajuste tem que ser inócuo."""
    onsets = _onsets(90.0, 0.0, list(range(0, 64)))

    bpm, fase = ajustar(onsets, 90)

    assert bpm == pytest.approx(90.0, abs=0.05)
    assert residuo(onsets, bpm, fase) < 0.002


def test_nao_foge_da_estimativa_do_audio() -> None:
    """O mix é a âncora: notas ruins não podem arrastar o andamento para o dobro."""
    onsets = _onsets(180.0, 0.0, list(range(0, 200)))

    bpm, _ = ajustar(onsets, 90)

    assert 90 * 0.97 <= bpm <= 90 * 1.03


def test_recusa_material_curto_demais() -> None:
    """Com poucas notas qualquer grade serve: devolver a estimativa original."""
    bpm, fase = ajustar([0.0, 0.5], 120)

    assert (bpm, fase) == (120.0, 0.0)
