"""API de jobs.

O pipeline entra injetado: ele custa minutos de CPU e já tem teste próprio contra
Demucs e MuScriptor reais. O caminho com o pipeline de verdade está no fim, `slow`.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.sintetico import SOUNDFONT, renderizar
from thoth.api.app import criar_app
from thoth.domain.models import AudioAsset, NoteEvent
from thoth.services.pipeline import Resultado


def _resultado_falso(out_dir: Path, **_: object) -> Resultado:
    out_dir.mkdir(parents=True, exist_ok=True)
    artefato = out_dir / "abc.gp5"
    artefato.write_bytes(b"gp5 falso")
    descartada = NoteEvent(pitch=43, onset_s=1.5, offset_s=2.0, instrument="electric_bass")
    return Resultado(
        asset=AudioAsset(wav=out_dir / "mix.wav", source_id="abc", title="t", duration_s=9.0),
        stem=out_dir / "bass.wav",
        artefatos={"gp5": artefato},
        notas=15,
        rotulos={"electric_bass": 15},
        descartadas=[descartada],
        bpm=90,
        fora_do_braco=[],
        avisos_de_oitava=[],
    )


def _cliente(tmp_path: Path, executar=None) -> TestClient:
    return TestClient(
        criar_app(
            out_dir=tmp_path / "out",
            cache_dir=tmp_path / "cache",
            executar=executar or (lambda ref, out_dir, **kw: _resultado_falso(out_dir, **kw)),
        )
    )


def test_job_roda_e_relata_o_que_o_pipeline_descartou(tmp_path: Path) -> None:
    cliente = _cliente(tmp_path)

    criado = cliente.post("/jobs", json={"ref": "x.mp3", "bpm": 90})
    assert criado.status_code == 202, criado.text

    job = cliente.get(f"/jobs/{criado.json()['id']}").json()
    assert job["status"] == "pronto"
    assert job["notas"] == 15
    assert job["descartadas"] == 1
    assert job["formatos"] == ["gp5"]


def test_bpm_e_cordas_chegam_ao_pipeline(tmp_path: Path) -> None:
    """BPM errado produz leitura errada (ADR-013): não pode se perder no caminho."""
    recebido: dict[str, object] = {}

    def espiao(ref: str, out_dir: Path, **kw: object) -> Resultado:
        recebido.update(kw)
        return _resultado_falso(out_dir)

    cliente = _cliente(tmp_path, espiao)
    cliente.post("/jobs", json={"ref": "x.mp3", "bpm": 72, "cordas": 5})

    assert recebido["bpm"] == 72
    assert recebido["tuning"] == (23, 28, 33, 38, 43)


def test_artefato_volta_com_os_bytes_do_arquivo(tmp_path: Path) -> None:
    cliente = _cliente(tmp_path)
    ident = cliente.post("/jobs", json={"ref": "x.mp3"}).json()["id"]

    resposta = cliente.get(f"/jobs/{ident}/artifacts/gp5")

    assert resposta.status_code == 200
    assert resposta.content == b"gp5 falso"


def test_formato_que_o_job_nao_produziu_da_404(tmp_path: Path) -> None:
    cliente = _cliente(tmp_path)
    ident = cliente.post("/jobs", json={"ref": "x.mp3"}).json()["id"]

    resposta = cliente.get(f"/jobs/{ident}/artifacts/pdf")

    assert resposta.status_code == 404
    assert "gp5" in resposta.json()["detail"]  # diz o que existe


def test_job_desconhecido_da_404(tmp_path: Path) -> None:
    assert _cliente(tmp_path).get("/jobs/nao-existe").status_code == 404


def test_falha_do_pipeline_vira_estado_e_nao_500(tmp_path: Path) -> None:
    """O erro interessa ao usuário: 'nenhuma nota de baixo' é diagnóstico, não bug."""
    def explode(ref: str, out_dir: Path, **kw: object) -> Resultado:
        raise ValueError("nenhuma nota de baixo em 't'")

    cliente = _cliente(tmp_path, explode)
    ident = cliente.post("/jobs", json={"ref": "x.mp3"}).json()["id"]

    job = cliente.get(f"/jobs/{ident}").json()
    assert job["status"] == "erro"
    assert "nenhuma nota de baixo" in job["erro"]
    assert cliente.get(f"/jobs/{ident}/artifacts/gp5").status_code == 409


@pytest.mark.slow
@pytest.mark.skipif(not SOUNDFONT.exists(), reason="soundfont ausente")
def test_caminho_real_ate_o_arquivo_baixado(tmp_path: Path) -> None:
    wav, _ = renderizar("escala", tmp_path)
    cliente = TestClient(criar_app(out_dir=tmp_path / "out", cache_dir=tmp_path / "cache"))

    ident = cliente.post("/jobs", json={"ref": str(wav), "bpm": 90}).json()["id"]
    job = cliente.get(f"/jobs/{ident}").json()

    assert job["status"] == "pronto", job
    assert cliente.get(f"/jobs/{ident}/artifacts/musicxml").content.startswith(b"<?xml")


def test_raiz_serve_a_pagina_de_estudo(tmp_path: Path) -> None:
    resposta = _cliente(tmp_path).get("/")

    assert resposta.status_code == 200
    assert "alphaTab" in resposta.text


def test_sem_vendor_a_raiz_diz_o_comando_em_vez_de_quebrar(tmp_path: Path) -> None:
    """Página em branco não ensina nada; 503 com o comando ensina."""
    app = criar_app(out_dir=tmp_path, cache_dir=tmp_path, web_dir=tmp_path / "vazio")

    resposta = TestClient(app).get("/")

    assert resposta.status_code == 503
    assert "scripts/vendor_alphatab.py" in resposta.text


def test_bundle_do_alphatab_sai_como_javascript(tmp_path: Path) -> None:
    """`import` de módulo falha no navegador se o MIME não for de JavaScript."""
    resposta = _cliente(tmp_path).get("/vendor/alphatab/alphaTab.min.mjs")

    assert resposta.status_code == 200
    assert resposta.headers["content-type"].startswith("text/javascript")


def test_fonte_musical_sai_com_mime_de_fonte(tmp_path: Path) -> None:
    resposta = _cliente(tmp_path).get("/vendor/alphatab/font/Bravura.woff2")

    assert resposta.headers["content-type"] == "font/woff2"
