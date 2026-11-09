"""O mapa do braço num navegador de verdade: Worker, desbloqueio de áudio e relógio reais.

O Vitest prova o agendador com relógio falso e o Web Audio com `OfflineAudioContext`.
O que só aparece aqui: o `AudioContext` nasce no clique e não antes, o despertador é um
`Worker` de fato, e cada som é agendado no relógio de áudio um pouco à frente do agora —
a janela de 100 ms do ADR-057 — com os tempos exatamente espaçados, por mais que o
despertador atrase.

A instrumentação é só do teste: um script inicial embrulha `AudioContext`, `Worker` e
`AudioScheduledSourceNode.start` para registrar o que a página fez.
"""

from __future__ import annotations

import json
import socket
import statistics
import threading
import time
from collections.abc import Iterator
from itertools import pairwise
from pathlib import Path

import httpx
import pytest

from tests.navegador.cdp import CHROMIUM, sessao
from thoth.api.app import BRACO_PADRAO, criar_app

pytestmark = [
    pytest.mark.navegador,
    pytest.mark.skipif(CHROMIUM is None, reason="Chromium não instalado"),
    pytest.mark.skipif(
        not (BRACO_PADRAO / "index.html").exists(),
        reason="braço sem build (cd braco && npm ci && npm run build)",
    ),
]

INSTRUMENTACAO = """
window.__registro = { contextos: [], workers: 0, inicios: [] };
const ContextoOriginal = window.AudioContext;
window.AudioContext = class extends ContextoOriginal {
  constructor(...a) { super(...a); window.__registro.contextos.push(this); }
};
const WorkerOriginal = window.Worker;
window.Worker = class extends WorkerOriginal {
  constructor(...a) { super(...a); window.__registro.workers += 1; }
};
const startOriginal = AudioScheduledSourceNode.prototype.start;
AudioScheduledSourceNode.prototype.start = function (quando = 0, ...resto) {
  window.__registro.inicios.push({ quando, agora: this.context.currentTime });
  return startOriginal.call(this, quando, ...resto);
};
"""

ESTADO = """JSON.stringify({
  contextos: window.__registro.contextos.map((c) => c.state),
  workers: window.__registro.workers,
  inicios: window.__registro.inicios,
  notas: document.querySelectorAll('svg [data-destaque]').length,
  tonica: document.querySelector('.dica strong')?.textContent ?? null,
  aceso: [...document.querySelectorAll('.tempo')].findIndex((t) => t.classList.contains('aceso')),
  soando: document.querySelectorAll('[data-soando="true"]').length,
  busca: location.search,
})"""


def _clicar(seletor: str) -> str:
    return f"(document.querySelector({json.dumps(seletor)}).click(), {ESTADO})"


@pytest.fixture
def servidor(tmp_path: Path) -> Iterator[str]:
    import uvicorn

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        porta = int(s.getsockname()[1])
    app = criar_app(out_dir=tmp_path / "out", cache_dir=tmp_path / "cache")
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=porta, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{porta}"
    limite = time.time() + 20
    while time.time() < limite:
        try:
            httpx.get(f"{base}/braco/", timeout=1)
            break
        except httpx.HTTPError:
            time.sleep(0.2)
    else:
        pytest.fail("servidor de teste não subiu")
    yield base
    server.should_exit = True
    thread.join(timeout=10)


def test_metronomo_agenda_no_relogio_de_audio_a_partir_do_clique(servidor: str) -> None:
    # 120 BPM: um tempo a cada 0,5 s do relógio de áudio.
    antes, tocando = (
        json.loads(v)
        for v in sessao(
            f"{servidor}/braco/?bpm=120",
            [(2.0, ESTADO), (0.0, _clicar(".tocar"))],
            script_inicial=INSTRUMENTACAO,
        )[:2]
    )
    print("antes do clique:", antes["contextos"], antes["workers"])
    assert antes["contextos"] == [], "o AudioContext não pode nascer antes do gesto"
    assert antes["notas"] == 4 * 13

    # A sessão precisa durar para os cliques acontecerem; a segunda leitura é imediata,
    # então outra sessão mede o que soou em 3 s.
    depois = json.loads(
        sessao(
            f"{servidor}/braco/?bpm=120",
            [(1.5, "document.querySelector('.tocar').click()"), (3.0, ESTADO)],
            script_inicial=INSTRUMENTACAO,
        )[1]
    )
    assert tocando["contextos"] in ([], ["suspended"], ["running"])
    assert depois["contextos"] == ["running"]
    assert depois["workers"] == 1, "o despertador tem de ser um Worker"
    assert depois["aceso"] >= 0, "o indicador visual não andou"

    inicios = depois["inicios"]
    quandos = [i["quando"] for i in inicios]
    folgas = [i["quando"] - i["agora"] for i in inicios]
    intervalos = [b - a for a, b in pairwise(quandos)]
    print(
        f"{len(inicios)} cliques; folga {min(folgas):.4f} a {max(folgas):.4f} s;",
        f"intervalo {min(intervalos):.6f} a {max(intervalos):.6f} s",
    )
    assert len(inicios) >= 5
    # Agendado à frente, nunca no passado, e no máximo a janela mais um tique de atraso.
    assert min(folgas) >= 0
    assert max(folgas) <= 0.1 + 0.05 + 0.05
    # O espaçamento vem do relógio de áudio, não do despertador: exato.
    assert max(abs(d - 0.5) for d in intervalos) < 1e-6


def test_sequencia_soa_nos_pulsos_e_acende_no_braco(servidor: str) -> None:
    # Lá maior a 120 BPM, tônica pela URL (S8): oito notas, uma por tempo.
    url = f"{servidor}/braco/?modo=teoria&tonica=9&padrao=escala-maior&bpm=120"
    leituras = sessao(
        url,
        [
            (1.5, ESTADO),
            (
                0.0,
                "[...document.querySelectorAll('.painel button')]"
                ".find((b) => b.textContent.includes('Tocar sequência')).click()",
            ),
            (0.75, ESTADO),
            (0.5, ESTADO),
        ],
        script_inicial=INSTRUMENTACAO,
    )
    aberto, _, primeiro, segundo = (json.loads(v) if isinstance(v, str) else v for v in leituras)
    assert aberto["tonica"] == "A"
    assert "padrao=escala-maior" in aberto["busca"]
    assert primeiro["soando"] >= 1, "a nota da sequência não acendeu no braço"
    assert segundo["soando"] >= 1

    quandos = sorted({round(i["quando"], 6) for i in segundo["inicios"]})
    # Clique e nota caem no mesmo instante: cada tempo aparece uma vez no conjunto.
    intervalos = [b - a for a, b in pairwise(quandos)]
    print("instantes:", quandos)
    assert len(quandos) >= 2
    assert statistics.fmean(intervalos) == pytest.approx(0.5, abs=1e-6)


LAYOUT = """JSON.stringify({
  orientacao: document.querySelector('svg.braco').dataset.orientacao,
  transborda: document.documentElement.scrollWidth > window.innerWidth,
  larguraBraco: document.querySelector('svg.braco').getBoundingClientRect().width,
  alvos: [...document.querySelectorAll('.nota .alvo')].map((a) => {
    const r = a.getBoundingClientRect();
    return [r.width, r.height];
  }),
  barra: (() => {
    const b = document.querySelector('[aria-label="Metrônomo rápido"]');
    const r = b.getBoundingClientRect();
    return { visivel: getComputedStyle(b).display !== 'none', fundo: r.bottom, topo: r.top };
  })(),
  altura: window.innerHeight,
})"""


@pytest.mark.parametrize(
    ("tela", "orientacao", "barra"),
    [((390, 844), "vertical", True), ((844, 390), "horizontal", True),
     ((1280, 800), "horizontal", False)],
)
def test_layout_responsivo(
    servidor: str, tela: tuple[int, int], orientacao: str, barra: bool
) -> None:
    # O pior caso de largura: 7 cordas, 24 casas (ADR-063).
    url = f"{servidor}/braco/?casas=24&cordas=7&afinacao=baixo-7"
    estado = json.loads(sessao(url, [(1.5, LAYOUT)], tela=tela)[0])
    menor = min(min(w, h) for w, h in estado["alvos"])
    print(tela, estado["orientacao"], f"braço {estado['larguraBraco']:.0f} px;",
          f"menor alvo {menor:.0f} px;", "barra", estado["barra"])
    assert estado["orientacao"] == orientacao
    assert len(estado["alvos"]) == 7 * 25
    assert menor >= 44 - 0.01, "alvo de toque abaixo de 44 px"  # 43,9997: sub-pixel do layout
    assert estado["barra"]["visivel"] is barra
    if orientacao == "vertical":
        assert not estado["transborda"], "rolagem horizontal no celular em pé"
        assert estado["larguraBraco"] <= tela[0]
    if barra:
        assert estado["barra"]["fundo"] == pytest.approx(estado["altura"], abs=1)
