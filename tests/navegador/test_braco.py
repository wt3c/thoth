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
    [
        ((390, 844), "vertical", True),
        ((844, 390), "horizontal", True),
        ((1280, 800), "horizontal", False),
    ],
)
def test_layout_responsivo(
    servidor: str, tela: tuple[int, int], orientacao: str, barra: bool
) -> None:
    # O pior caso de largura: 7 cordas, 24 casas (ADR-063).
    url = f"{servidor}/braco/?casas=24&cordas=7&afinacao=baixo-7"
    estado = json.loads(sessao(url, [(1.5, LAYOUT)], tela=tela)[0])
    menor = min(min(w, h) for w, h in estado["alvos"])
    print(
        tela,
        estado["orientacao"],
        f"braço {estado['larguraBraco']:.0f} px;",
        f"menor alvo {menor:.0f} px;",
        "barra",
        estado["barra"],
    )
    assert estado["orientacao"] == orientacao
    assert len(estado["alvos"]) == 7 * 25
    assert menor >= 44 - 0.01, "alvo de toque abaixo de 44 px"  # 43,9997: sub-pixel do layout
    assert estado["barra"]["visivel"] is barra
    if orientacao == "vertical":
        assert not estado["transborda"], "rolagem horizontal no celular em pé"
        assert estado["larguraBraco"] <= tela[0]
    if barra:
        assert estado["barra"]["fundo"] == pytest.approx(estado["altura"], abs=1)


SOANDO = """JSON.stringify({
  lugares: [...document.querySelectorAll('[data-soando="true"]')]
    .map((n) => `${n.dataset.nota} ${n.dataset.corda}-${n.dataset.casa}`),
  inicios: window.__registro.inicios,
  botao: document.querySelector('[data-acao="tocar-notas"]').textContent.trim(),
})"""


def test_notas_acesas_soam_no_metronomo_da_grave_a_aguda(servidor: str) -> None:
    # E e A acesas nas 12 casas do baixo de 4 cordas: dez posições, uma por tempo a 120 BPM.
    # A1 aparece em duas (corda E casa 5, corda A solta) e cada uma tem o seu tempo.
    url = f"{servidor}/braco/?filtro=49&bpm=120"
    leituras = sessao(
        url,
        [
            (1.5, "document.querySelector('[data-acao=\"tocar-notas\"]').click()"),
            (0.75, SOANDO),
            (0.5, SOANDO),
            (0.5, SOANDO),
            (0.0, "document.querySelector('[data-acao=\"tocar-notas\"]').click()"),
            (0.3, SOANDO),
            (1.0, SOANDO),
        ],
        script_inicial=INSTRUMENTACAO,
    )
    *tocando, _, parado, depois = (json.loads(v) if isinstance(v, str) else v for v in leituras[1:])
    # "Parar notas" para também o metrônomo: nada mais é agendado e nada acende.
    print("sons agendados ao parar e 1 s depois:", len(parado["inicios"]), len(depois["inicios"]))
    assert len(depois["inicios"]) == len(parado["inicios"]), "o metrônomo continuou tocando"
    assert depois["lugares"] == []
    estados = tocando
    acesas = [e["lugares"] for e in estados]
    print("acesas por leitura:", acesas)
    assert estados[0]["botao"] == "Parar notas"
    assert all(len(n) == 1 for n in acesas), "uma posição por vez, nunca um conjunto"
    assert all(n[0].split()[0] in {"E", "A"} for n in acesas), "só E ou A acendem"
    assert len({n[0] for n in acesas}) == len(acesas), "cada tempo acende outra posição"

    quandos = sorted({round(i["quando"], 6) for i in estados[-1]["inicios"]})
    intervalos = [b - a for a, b in pairwise(quandos)]
    print("instantes:", quandos)
    assert len(quandos) >= 3
    assert statistics.fmean(intervalos) == pytest.approx(0.5, abs=1e-6)


def test_o_site_abre_com_o_braco_limpo(servidor: str) -> None:
    estado = json.loads(
        sessao(
            f"{servidor}/braco/",
            [
                (
                    1.5,
                    """JSON.stringify({
  posicoes: document.querySelectorAll('svg.braco .nota').length,
  marcadores: document.querySelectorAll('svg.braco .marcador').length,
  limpar: document.querySelector('[data-acao="limpar"]')?.textContent.trim() ?? null,
})""",
                )
            ],
        )[0]
    )
    print("braço ao abrir:", estado)
    assert estado == {"posicoes": 4 * 13, "marcadores": 0, "limpar": "Limpar"}


LEGENDA = """JSON.stringify({
  sinais: [...document.querySelectorAll('.legenda [data-sinal]')].map((i) => i.dataset.sinal),
  topoLegenda: document.querySelector('.legenda')?.getBoundingClientRect().top ?? null,
  fimBraco: document.querySelector('svg.braco').getBoundingClientRect().bottom,
  transborda: document.documentElement.scrollWidth > innerWidth,
})"""


@pytest.mark.parametrize("tela", [(390, 844), (1280, 800)])
def test_legenda_das_oitavas_fica_logo_abaixo_do_braco(
    servidor: str, tela: tuple[int, int]
) -> None:
    estado = json.loads(sessao(f"{servidor}/braco/", [(1.5, LEGENDA)], tela=tela)[0])
    print(tela, "legenda:", estado)
    # O sinal de menos é o da etiqueta no braço (U+2212), não o hífen.
    assert estado["sinais"] == ["referencia", "+1", "+2", "\u22121", "="]
    assert estado["topoLegenda"] >= estado["fimBraco"]
    assert not estado["transborda"]


GUIA = """(() => {
  for (const d of document.querySelectorAll('#como-usar details')) d.open = true
  return JSON.stringify({
    link: document.querySelector('header a[href="#como-usar"]')?.textContent.trim() ?? null,
    blocos: document.querySelectorAll('#como-usar details').length,
    abaixoDosPaineis: document.querySelector('#como-usar')?.getBoundingClientRect().top
      >= document.querySelector('.paineis').getBoundingClientRect().bottom,
    transborda: document.documentElement.scrollWidth > innerWidth,
  })
})()"""


@pytest.mark.parametrize("tela", [(390, 844), (1280, 800)])
def test_guia_de_uso_abre_pelo_link_do_cabecalho_sem_transbordar(
    servidor: str, tela: tuple[int, int]
) -> None:
    estado = json.loads(sessao(f"{servidor}/braco/", [(1.5, GUIA)], tela=tela)[0])
    print(tela, "guia:", estado)
    assert estado == {
        "link": "Como usar",
        "blocos": 9,
        "abaixoDosPaineis": True,
        "transborda": False,
    }


OITAVAS = """JSON.stringify({
  referencia: [...document.querySelectorAll('[data-referencia="true"]')]
    .map((n) => `${n.dataset.corda}-${n.dataset.casa}`),
  etiquetas: Object.fromEntries([...document.querySelectorAll('.nota')]
    .filter((n) => n.querySelector('.oitava'))
    .map((n) => [`${n.dataset.corda}-${n.dataset.casa}`, n.querySelector('.oitava').textContent])),
})"""


def test_nota_tocada_sinaliza_as_oitavas_das_outras(servidor: str) -> None:
    # Baixo E A D G, 12 casas: o C da corda A, casa 3 (C2) é tocado e vira a referência.
    url = f"{servidor}/braco/"
    leituras = sessao(
        url,
        [
            (
                1.5,
                'document.querySelector(\'[data-corda="1"][data-casa="3"]\').dispatchEvent('
                "new MouseEvent('click', { bubbles: true }))",
            ),
            (0.3, OITAVAS),
        ],
    )
    estado = json.loads(leituras[1])
    print("referência:", estado["referencia"], "etiquetas:", estado["etiquetas"])
    assert estado["referencia"] == ["1-3"]
    # Corda E casa 8: o mesmo C2. Corda D casa 10 e corda G casa 5: C3, uma oitava acima.
    assert estado["etiquetas"] == {"0-8": "=", "2-10": "+1", "3-5": "+1"}
