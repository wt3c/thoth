"""Nome de arquivo derivado do título da fonte.

Função pura, sem I/O: mock aqui não esconde nada (Regra 3). O que ela precisa
provar é que nenhum título real do YouTube produz um caminho inválido.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from thoth.domain.models import AudioAsset
from thoth.services.nomes import nome_de_arquivo


def _ativo(title: str, source_id: str = "yt_abc123") -> AudioAsset:
    return AudioAsset(wav=Path("mix.wav"), source_id=source_id, title=title)


def test_mantem_o_titulo_legivel_com_acentos() -> None:
    assert nome_de_arquivo(_ativo("SOU EU - Fabiana Anastácio")) == "SOU EU - Fabiana Anastácio"


def test_troca_barra_e_dois_pontos_por_hifen() -> None:
    """Título real do cache: a barra criaria diretório e o artefato se perderia."""
    nome = nome_de_arquivo(
        _ativo("Feel Like Makin' Love - Toshiki Soejima : Live & Recording 2022 / Neo-Soul Guitar")
    )

    assert "/" not in nome and ":" not in nome
    assert nome == (
        "Feel Like Makin' Love - Toshiki Soejima - Live & Recording 2022 - Neo-Soul Guitar"
    )


@pytest.mark.parametrize("hostil", ["\\", "*", "?", '"', "<", ">", "|", "\0", "\n"])
def test_remove_todo_caractere_hostil(hostil: str) -> None:
    assert hostil not in nome_de_arquivo(_ativo(f"antes{hostil}depois"))


def test_nao_deixa_ponto_nem_espaco_nas_pontas() -> None:
    """Ponto inicial esconde o arquivo; ponto ou espaço final quebra no Windows."""
    assert nome_de_arquivo(_ativo("  .Equus. ")) == "Equus"


def test_trunca_titulo_longo() -> None:
    nome = nome_de_arquivo(_ativo("Ré " * 200))

    assert len(nome) <= 120
    assert len(nome.encode()) < 255 - len(".musicxml")


def test_cai_no_source_id_quando_nada_sobra() -> None:
    """Sem isto o artefato viraria `.gp5` — um arquivo oculto sem nome."""
    assert nome_de_arquivo(_ativo("///", source_id="yt_QTOyeFQgZKk")) == "yt_QTOyeFQgZKk"


def test_arquivo_local_usa_o_nome_do_arquivo() -> None:
    """LocalSource põe o stem do caminho em `title` — nada a traduzir aqui."""
    assert nome_de_arquivo(_ativo("walking", source_id="9aa6eda3591aa060")) == "walking"
