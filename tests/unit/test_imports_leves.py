"""Importar um módulo não arrasta dependência pesada que ele não usa.

Cada processo do `pytest -n auto` e cada `thoth <comando>` pagava ~1,6 s de import:
o `acordes` puxava o `mir_eval` inteiro por uma constante, e a CLI carregava
FastAPI e uvicorn mesmo sem `serve`. Em subprocesso, porque o `sys.modules` do
próprio pytest já tem de tudo.
"""

from __future__ import annotations

import subprocess
import sys


def _carregados(modulo: str) -> set[str]:
    codigo = f"import sys, {modulo}; print(' '.join(sys.modules))"
    saida = subprocess.run(
        [sys.executable, "-c", codigo], capture_output=True, text=True, check=True
    ).stdout
    return {nome.split(".")[0] for nome in saida.split()}


def test_acordes_nao_carrega_o_avaliador() -> None:
    assert "mir_eval" not in _carregados("thoth.services.acordes")


def test_cli_so_carrega_o_servidor_no_serve() -> None:
    assert {"fastapi", "uvicorn"}.isdisjoint(_carregados("thoth.cli"))


def test_janela_de_acorde_e_a_tolerancia_do_avaliador() -> None:
    """A constante mudou de casa, não de valor: os dois lados seguem amarrados."""
    from thoth.services.acordes import JANELA_ACORDE_S
    from thoth.services.evaluation import TOLERANCIA_S

    assert JANELA_ACORDE_S == TOLERANCIA_S
