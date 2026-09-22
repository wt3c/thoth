"""A página de estudo renderiza a partitura de verdade, num navegador de verdade.

Nenhum teste de servidor pega o bug que motivou este arquivo: o alphaTab respondia
`renderFinished`, criava a superfície e os blocos com as alturas certas — e deixava
todos vazios, porque o `scrollElement` apontava para o próprio container e o lazy
loading concluía que nada estava visível. A única evidência que distingue os dois
mundos é a contagem de `<svg>` dentro de `#tab`.
"""

from __future__ import annotations

import socket
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest

from tests.navegador.cdp import CHROMIUM, avaliar
from thoth.adapters.export.gp5 import Gp5Exporter
from thoth.api.app import WEB_PADRAO, criar_app
from thoth.domain.models import TUNING_BASS_4, AudioAsset, NoteEvent, TabNote
from thoth.services.pipeline import Resultado

pytestmark = [
    pytest.mark.navegador,
    pytest.mark.skipif(CHROMIUM is None, reason="Chromium não instalado"),
    pytest.mark.skipif(
        not (WEB_PADRAO / "vendor" / "alphatab" / "alphaTab.min.mjs").exists(),
        reason="alphaTab não vendorizado (uv run python scripts/vendor_alphatab.py)",
    ),
]

BPM = 90


def _partitura_real(out_dir: Path, **_: object) -> Resultado:
    """Executor de mentira, artefato de verdade: o alphaTab precisa de um GP5 legítimo."""
    out_dir.mkdir(parents=True, exist_ok=True)
    notas = [
        TabNote(
            event=NoteEvent(pitch=p, onset_s=i * 60 / BPM, offset_s=(i + 1) * 60 / BPM,
                            instrument="electric_bass"),
            string=s,
            fret=f,
        )
        for i, (p, s, f) in enumerate([(28, 0, 0), (33, 1, 0), (38, 2, 0), (40, 2, 2)])
    ]
    artefato = Gp5Exporter(bpm=BPM).export(notas, out_dir / "estudo.gp5", TUNING_BASS_4)
    return Resultado(
        asset=AudioAsset(
            wav=out_dir / "mix.wav", source_id="estudo", title="estudo", duration_s=3.0
        ),
        stem=out_dir / "bass.wav",
        artefatos={"gp5": artefato},
        notas=len(notas),
        rotulos={"electric_bass": len(notas)},
        descartadas=[],
        fora_do_braco=[],
        avisos_de_oitava=[],
    )


@pytest.fixture
def servidor(tmp_path: Path) -> Iterator[str]:
    import uvicorn

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        porta = int(s.getsockname()[1])

    app = criar_app(
        out_dir=tmp_path / "out",
        cache_dir=tmp_path / "cache",
        executar=lambda ref, out_dir, **kw: _partitura_real(out_dir, **kw),
    )
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=porta, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{porta}"
    limite = time.time() + 20
    while time.time() < limite:
        try:
            httpx.get(f"{base}/", timeout=1)
            break
        except httpx.HTTPError:
            time.sleep(0.2)
    else:
        pytest.fail("servidor de teste não subiu")
    yield base
    server.should_exit = True
    thread.join(timeout=10)


def test_a_partitura_aparece_na_tela(servidor: str) -> None:
    criado = httpx.post(f"{servidor}/jobs", json={"ref": "x.wav", "bpm": BPM}, timeout=10)
    assert criado.status_code == 202, criado.text
    ident = criado.json()["id"]

    limite = time.time() + 30
    while time.time() < limite:
        if httpx.get(f"{servidor}/jobs/{ident}", timeout=5).json()["status"] == "pronto":
            break
        time.sleep(0.3)
    else:
        pytest.fail("job não ficou pronto")

    estado = avaliar(
        f"{servidor}/?job={ident}",
        "({svg: document.querySelectorAll('#tab svg').length,"
        " viva_por_ms: performance.now()})",
        espera_s=15,
    )
    assert estado["viva_por_ms"] > 10_000, f"sessão curta demais para concluir nada: {estado}"
    assert estado["svg"] > 0, f"a superfície existe mas nenhum SVG foi desenhado: {estado}"


def test_job_inexistente_nao_deixa_a_pagina_girando(servidor: str) -> None:
    estado = avaliar(
        f"{servidor}/?job=naoexiste123",
        "({estado: document.getElementById('estado').innerText})",
        espera_s=6,
    )
    assert "não encontrado" in estado["estado"]
