"""models.lock.toml — pesos somem e mudam; o lock é o que detecta os dois.

Não é paranoia: o checkpoint do Beat This! já ficou inalcançável durante a
Fase 0, e os pesos do MuScriptor são CC BY-NC 4.0 em repositório de terceiro,
com licença aceita por repositório. Se um dia o `model.safetensors` for
republicado com outro conteúdo, a transcrição muda em silêncio.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from thoth.services.model_lock import IntegridadeError, carregar_lock, conferir

LOCK = """\
[muscriptor-small]
repo = "MuScriptor/muscriptor-small"
revision = "8c127f603b807520fa465c838e9bfee8a91ada4e"
licenca = "CC BY-NC 4.0"

[[muscriptor-small.arquivos]]
path = "config.json"
sha256 = "3008fc481e4a1cd978e337eb3759260c270892204db5039235ac939e1f42aeb2"
bytes = 124
"""


@pytest.fixture
def lock_path(tmp_path: Path) -> Path:
    destino = tmp_path / "models.lock.toml"
    destino.write_text(LOCK)
    return destino


@pytest.fixture
def arquivo(tmp_path: Path) -> Path:
    conteudo = tmp_path / "peso.bin"
    conteudo.write_bytes(b"pesos de mentira")
    return conteudo


def test_le_o_lock(lock_path: Path) -> None:
    modelos = carregar_lock(lock_path)

    assert list(modelos) == ["muscriptor-small"]
    modelo = modelos["muscriptor-small"]
    assert modelo.repo == "MuScriptor/muscriptor-small"
    assert modelo.revision.startswith("8c127f")
    assert [a.path for a in modelo.arquivos] == ["config.json"]


def test_confere_arquivo_intacto(arquivo: Path) -> None:
    from thoth.services.model_lock import ArquivoTravado

    esperado = ArquivoTravado(
        path="peso.bin",
        sha256=hashlib.sha256(arquivo.read_bytes()).hexdigest(),
        bytes=arquivo.stat().st_size,
    )

    conferir(arquivo, esperado)  # não levanta


def test_conteudo_trocado_e_detectado(arquivo: Path) -> None:
    from thoth.services.model_lock import ArquivoTravado

    esperado = ArquivoTravado(path="peso.bin", sha256="0" * 64, bytes=arquivo.stat().st_size)

    with pytest.raises(IntegridadeError, match="sha256"):
        conferir(arquivo, esperado)


def test_tamanho_diferente_falha_sem_precisar_ler_tudo(arquivo: Path) -> None:
    """Download truncado se detecta pelo tamanho, sem hashear 1,2 GB."""
    from thoth.services.model_lock import ArquivoTravado

    esperado = ArquivoTravado(path="peso.bin", sha256="0" * 64, bytes=999_999)

    with pytest.raises(IntegridadeError, match="bytes"):
        conferir(arquivo, esperado)


def test_arquivo_ausente_e_erro_claro(tmp_path: Path) -> None:
    from thoth.services.model_lock import ArquivoTravado

    esperado = ArquivoTravado(path="sumiu.bin", sha256="0" * 64, bytes=1)

    with pytest.raises(IntegridadeError, match="não encontrado"):
        conferir(tmp_path / "sumiu.bin", esperado)


#: Raiz do repositório, para o teste não depender do diretório de execução.
RAIZ = Path(__file__).resolve().parents[2]


@pytest.mark.slow
def test_lock_do_projeto_bate_com_os_pesos_da_estacao() -> None:
    """Contra os pesos reais no cache do HuggingFace — o lock só vale se for verdade.

    `slow` porque hasheia 1,6 GB; roda antes de confiar em qualquer medição de
    qualidade, já que modelo trocado invalida todo o portão de regressão.
    """
    from thoth.services.model_lock import caminho_no_cache

    modelos = carregar_lock(RAIZ / "models.lock.toml")
    assert modelos, "o lock do projeto está vazio"

    conferidos = 0
    for modelo in modelos.values():
        for esperado in modelo.arquivos:
            alvo = caminho_no_cache(modelo, esperado)
            if alvo is None:
                pytest.skip(f"{modelo.repo} não está no cache desta estação")
            conferir(alvo, esperado)
            conferidos += 1
    assert conferidos
