"""O mapa do braço servido pelo Thoth em `/braco/` (ADR-056)."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from thoth.api.app import WEB_PADRAO, criar_app


class _Local(TestClient):
    def __init__(self, app, **kwargs):  # type: ignore[no-untyped-def]
        super().__init__(app, base_url="http://127.0.0.1:8000", **kwargs)


def _build_falso(raiz: Path) -> Path:
    """O formato do `vite build`: `index.html` e os módulos em `assets/`."""
    (raiz / "assets").mkdir(parents=True)
    (raiz / "index.html").write_text("<!doctype html><title>braço</title>", encoding="utf-8")
    (raiz / "assets" / "index-abc.js").write_text("export {}", encoding="utf-8")
    (raiz / "assets" / "index-abc.css").write_text("body{}", encoding="utf-8")
    return raiz


def _app(tmp_path: Path, *, web_dir: Path = WEB_PADRAO, braco_dir: Path):  # type: ignore[no-untyped-def]
    return criar_app(out_dir=tmp_path, cache_dir=tmp_path, web_dir=web_dir, braco_dir=braco_dir)


def test_sem_build_o_braco_diz_o_comando_em_vez_de_quebrar(tmp_path: Path) -> None:
    resposta = _Local(_app(tmp_path, braco_dir=tmp_path / "sem-build")).get("/braco/")

    assert resposta.status_code == 503
    assert "npm run build" in resposta.text


def test_braco_sai_antes_da_raiz_quando_o_alphatab_existe(tmp_path: Path) -> None:
    """O `/` do alphaTab é catch-all: montado depois, o `/braco` sumiria atrás dele."""
    assert (WEB_PADRAO / "vendor" / "alphatab" / "alphaTab.min.mjs").exists()
    cliente = _Local(_app(tmp_path, braco_dir=_build_falso(tmp_path / "dist")))

    pagina = cliente.get("/braco/")
    modulo = cliente.get("/braco/assets/index-abc.js")
    estilo = cliente.get("/braco/assets/index-abc.css")

    assert pagina.status_code == 200
    assert "braço" in pagina.text
    assert modulo.headers["content-type"].startswith("text/javascript")
    assert estilo.headers["content-type"].startswith("text/css")
    assert cliente.get("/").status_code == 200


def test_braco_nao_depende_do_alphatab(tmp_path: Path) -> None:
    cliente = _Local(
        _app(tmp_path, web_dir=tmp_path / "sem-web", braco_dir=_build_falso(tmp_path / "dist"))
    )

    assert cliente.get("/braco/").status_code == 200
    assert cliente.get("/").status_code == 503


def test_braco_sem_barra_leva_ao_braco(tmp_path: Path) -> None:
    cliente = _Local(_app(tmp_path, braco_dir=_build_falso(tmp_path / "dist")))

    resposta = cliente.get("/braco")

    assert resposta.status_code == 200
    assert str(resposta.url).endswith("/braco/")
