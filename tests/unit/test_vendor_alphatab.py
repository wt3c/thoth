"""O que foi vendorizado tem de bastar sozinho — sem CDN e sem 404 no console."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.vendor_alphatab import _IMPORT_RELATIVO, DESTINO, ENTRADA

pytestmark = pytest.mark.skipif(
    not (DESTINO / "alphaTab.min.mjs").exists(),
    reason="alphaTab ausente: uv run python scripts/vendor_alphatab.py",
)


def test_todo_import_relativo_aponta_para_arquivo_existente() -> None:
    """A entrada tem 4 KB e é só fachada: sem `core`, a página abre em branco."""
    faltando = [
        (modulo.name, alvo)
        for modulo in DESTINO.rglob("*.mjs")
        for alvo in _IMPORT_RELATIVO.findall(modulo.read_text("utf-8", "ignore"))
        if not (modulo.parent / alvo).exists()
    ]

    assert faltando == []


def test_a_entrada_vendorizada_e_a_que_a_pagina_importa() -> None:
    pagina = (Path(__file__).resolve().parents[2] / "web" / "index.html").read_text()

    assert f"vendor/alphatab/{Path(ENTRADA).name}" in pagina


def test_fonte_e_soundfont_estao_onde_a_pagina_os_configura() -> None:
    """Nenhum `import` alcança esses dois — eles entram por caminho, em runtime."""
    assert (DESTINO / "font" / "Bravura.woff2").exists()
    assert (DESTINO / "soundfont" / "sonivox.sf3").exists()
