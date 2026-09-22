"""Baixa o alphaTab para `web/vendor/`. Uma vez por estação, não a cada execução.

O alphaTab é servido **daqui**, não de CDN (ADR-006): a ferramenta de estudo tem
de funcionar sem internet, e um CDN transforma cada sessão de estudo num pedido a
um terceiro.

O `.tgz` não é versionado (ADR-005, mesma regra dos pesos e do áudio): 4,5 MB de
dist de terceiro não entram no repositório. O que fica versionado é a
**identidade** dele — versão e SHA-256 aqui embaixo —, do mesmo jeito que o
`models.lock.toml` guarda a identidade dos pesos sem guardar os pesos.

    uv run python scripts/vendor_alphatab.py
"""

from __future__ import annotations

import hashlib
import re
import subprocess
import tarfile
import tempfile
from pathlib import Path

VERSAO = "1.8.4"
SHA256 = "70b2c77abc9698a055d90a11d77308b6b41247936476e969d85770e3d4db4602"
DESTINO = Path(__file__).resolve().parents[1] / "web" / "vendor" / "alphatab"

#: Ponto de entrada; o resto dos módulos sai dos `import` dele, não de palpite.
ENTRADA = "dist/alphaTab.min.mjs"

#: O que nenhum `import` alcança: a fonte musical e o soundfont são carregados em
#: tempo de execução, por caminho, pelas configurações do próprio alphaTab.
ATIVOS = (
    "dist/font/Bravura.woff2",
    "dist/font/Bravura.woff",
    "dist/font/Bravura.otf",
    "dist/soundfont/sonivox.sf3",
    "dist/soundfont/LICENSE",
)

#: `from "./x.mjs"` e `import("./x.mjs")` — só o que é relativo ao pacote.
_IMPORT_RELATIVO = re.compile(r"""["'](\./[^"']+\.m?js)["']""")


def _conferir(tgz: Path) -> None:
    digest = hashlib.sha256(tgz.read_bytes()).hexdigest()
    if digest != SHA256:
        raise SystemExit(f"SHA-256 do alphaTab {VERSAO} não confere: {digest}")


def _ler(arquivo: tarfile.TarFile, nome: str) -> bytes:
    fonte = arquivo.extractfile(f"package/{nome}")
    if fonte is None:
        raise SystemExit(f"{nome} não existe no pacote do alphaTab {VERSAO}")
    return fonte.read()


def _extrair(arquivo: tarfile.TarFile, nome: str, destino: Path) -> None:
    alvo = destino / Path(nome).relative_to("dist")
    alvo.parent.mkdir(parents=True, exist_ok=True)
    alvo.write_bytes(_ler(arquivo, nome))


def modulos(arquivo: tarfile.TarFile, entrada: str = ENTRADA) -> list[str]:
    """Fecho transitivo dos `import` relativos, a partir da entrada.

    Lista fixa não serve, e isso foi medido: `alphaTab.min.mjs` tem 4 KB e é só
    uma fachada que importa `core`, `worker` e `worklet`. Vendorizar só a entrada
    rende página em branco e 404 no console do navegador — que nenhum teste de
    servidor pega, porque o servidor responde 200 para o que existe. Seguir os
    `import` não depende de eu adivinhar a lista certa.
    """
    pendentes, vistos = [entrada], []
    while pendentes:
        atual = pendentes.pop()
        if atual in vistos:
            continue
        vistos.append(atual)
        base = Path(atual).parent
        texto = _ler(arquivo, atual).decode("utf-8", "ignore")
        pendentes += [str(base / alvo) for alvo in _IMPORT_RELATIVO.findall(texto)]
    return sorted(vistos)


def baixar(destino: Path = DESTINO) -> Path:
    """Extrai os arquivos necessários; devolve o diretório de destino."""
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(
            ["npm", "pack", f"@coderline/alphatab@{VERSAO}"],
            cwd=tmp, check=True, capture_output=True,
        )
        tgz = next(Path(tmp).glob("*.tgz"))
        _conferir(tgz)

        destino.mkdir(parents=True, exist_ok=True)
        with tarfile.open(tgz) as arquivo:
            for nome in [*modulos(arquivo), *ATIVOS]:
                _extrair(arquivo, nome, destino)
    return destino


if __name__ == "__main__":
    print(f"alphaTab {VERSAO} em {baixar()}")
