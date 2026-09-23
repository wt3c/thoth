"""O `stderr` da ferramenta externa é a única pista que existe (ADR-026).

Tudo aqui roda contra `sh` de verdade: o que está em teste é o que o
`subprocess` faz com a saída de erro, e um mock do `subprocess` testaria a minha
suposição sobre isso em vez do fato.
"""

from __future__ import annotations

import pytest

from thoth.processos import ErroDeProcesso, rodar


def test_devolve_o_stdout() -> None:
    assert rodar(["sh", "-c", "echo oi"]) == "oi\n"


def test_falha_traz_o_stderr_na_mensagem() -> None:
    """`CalledProcessError` diz só 'exit status 3' — o motivo ficava no chão."""
    with pytest.raises(ErroDeProcesso, match="boom") as erro:
        rodar(["sh", "-c", "echo boom >&2; exit 3"])

    assert "3" in str(erro.value)
    assert "sh" in str(erro.value)


def test_stderr_gigante_e_cortado_pelo_fim() -> None:
    """O fim é onde a ferramenta diz o que falhou; o começo é banner."""
    with pytest.raises(ErroDeProcesso, match="ultima") as erro:
        rodar(["sh", "-c", "yes banner | head -c 20000 >&2; echo ultima >&2; exit 1"])

    assert len(str(erro.value)) < 1500


def test_comando_inexistente_continua_sendo_filenotfound() -> None:
    """Quem trata 'ferramenta não instalada' depende disto (auralização)."""
    with pytest.raises(FileNotFoundError):
        rodar(["nao_existe_esse_binario_aqui"])


def test_timeout_e_erro_de_processo() -> None:
    with pytest.raises(ErroDeProcesso, match="excedeu"):
        rodar(["sleep", "5"], timeout=0.2)
