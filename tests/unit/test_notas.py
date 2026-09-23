"""Altura MIDI → nome da nota. Função pura, sem I/O."""

from __future__ import annotations

import pytest

from thoth.services.notas import nome_da_nota


@pytest.mark.parametrize(
    ("pitch", "nome"),
    [
        (28, "E"),   # 4ª corda solta do baixo de 4
        (23, "B"),   # 5ª corda solta do baixo de 5
        (33, "A"),
        (34, "A#"),  # sem armadura de clave, acidente sai sempre sustenido
        (36, "C"),
        (48, "C"),   # a oitava não entra no nome: só a classe de altura
    ],
)
def test_nomeia_a_classe_de_altura(pitch: int, nome: str) -> None:
    assert nome_da_nota(pitch) == nome


def test_ignora_a_oitava() -> None:
    assert len({nome_da_nota(p) for p in range(24, 36)}) == 12
    assert all(nome_da_nota(p) == nome_da_nota(p + 12) for p in range(24, 60))


@pytest.mark.parametrize(
    ("pitch", "nome"),
    [(34, "Bb"), (35, "B"), (32, "Ab"), (30, "Gb"), (29, "F"), (37, "Db")],
)
def test_em_tom_bemol_o_acidente_e_bemol(pitch: int, nome: str) -> None:
    """Fá menor escrito com G# é o defeito que o ADR-031 corrige."""
    assert nome_da_nota(pitch, bemois=True) == nome


def test_bemol_tambem_ignora_a_oitava() -> None:
    """A mesma invariante do modo de sempre: doze nomes, um por classe."""
    assert len({nome_da_nota(p, bemois=True) for p in range(24, 36)}) == 12
