"""Sessão de navegador controlada em tempo real, via Chrome DevTools Protocol.

Motivo de existir: `--virtual-time-budget` e `--screenshot` deixam o Chromium sair
antes do trabalho assíncrono da página terminar, e o resultado é indistinguível de
uma página quebrada. Aqui a espera é de relógio, e `viva_por_ms` é a prova de que a
sessão durou o que se pediu — sem isso nenhuma asserção sobre a página vale.
"""

from __future__ import annotations

import json
import shutil
import socket
import subprocess
import tempfile
import time
import urllib.request
from contextlib import suppress
from typing import Any

CHROMIUM = (
    shutil.which("chromium")
    or shutil.which("chromium-browser")
    or shutil.which("google-chrome-stable")
)


def _porta_livre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def avaliar(url: str, expressao: str, *, espera_s: float = 15.0) -> Any:
    """Abre `url`, deixa a página viver `espera_s` de relógio e avalia `expressao`."""
    if CHROMIUM is None:
        raise RuntimeError("chromium não encontrado")
    from websockets.sync.client import connect

    perfil = tempfile.mkdtemp(prefix="thoth-cdp-")
    porta = _porta_livre()
    proc = subprocess.Popen(
        [CHROMIUM, "--headless", "--disable-gpu", "--no-sandbox",
         f"--remote-debugging-port={porta}", f"--user-data-dir={perfil}", "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        alvo = _esperar_alvo(porta)
        with connect(alvo["webSocketDebuggerUrl"], max_size=None) as ws:
            _enviar(ws, 1, "Page.enable")
            _enviar(ws, 2, "Page.navigate", url=url)
            time.sleep(espera_s)
            _enviar(ws, 3, "Runtime.evaluate", expression=expressao,
                    returnByValue=True, awaitPromise=True)
            limite = time.time() + 30
            while time.time() < limite:
                msg = json.loads(ws.recv(timeout=max(1.0, limite - time.time())))
                if msg.get("id") == 3:
                    resultado = msg.get("result", {}).get("result", {})
                    if "value" not in resultado:
                        raise RuntimeError(f"avaliação falhou: {msg}")
                    return resultado["value"]
            raise TimeoutError("navegador não respondeu à avaliação")
    finally:
        proc.terminate()
        with suppress(subprocess.TimeoutExpired):
            proc.wait(timeout=10)
        shutil.rmtree(perfil, ignore_errors=True)


def _esperar_alvo(porta: int) -> dict[str, Any]:
    for _ in range(80):
        with suppress(Exception):
            alvos = json.load(urllib.request.urlopen(f"http://127.0.0.1:{porta}/json/list"))
            paginas = [
                a for a in alvos
                if a.get("type") == "page" and a.get("webSocketDebuggerUrl")
            ]
            if paginas:
                return dict(paginas[0])
        time.sleep(0.25)
    raise RuntimeError("Chromium não expôs um alvo de página")


def _enviar(ws: Any, ident: int, metodo: str, **params: Any) -> None:
    ws.send(json.dumps({"id": ident, "method": metodo, "params": params}))
