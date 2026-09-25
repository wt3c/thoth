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
from dataclasses import replace
from pathlib import Path

import httpx
import pytest

from tests.navegador.cdp import CHROMIUM, avaliar, sessao
from thoth.adapters.export.gp5 import Gp5Exporter, Gp5PercussaoExporter
from thoth.api.app import WEB_PADRAO, criar_app
from thoth.domain.instrumentos import PERFIS, TUNING_GUITARRA_6
from thoth.domain.models import (
    TUNING_BASS_4,
    TUNING_BASS_DROP_D,
    AcordeImpossivel,
    AudioAsset,
    EventoPercussivo,
    NoteEvent,
    TabNote,
)
from thoth.services.acordes import ViterbiAcordes
from thoth.services.fretboard import PADRAO
from thoth.services.octave_check import OctaveWarning
from thoth.services.pipeline import Resultado
from thoth.services.tonalidade import tom_de_texto

pytestmark = [
    pytest.mark.navegador,
    pytest.mark.skipif(CHROMIUM is None, reason="Chromium não instalado"),
    pytest.mark.skipif(
        not (WEB_PADRAO / "vendor" / "alphatab" / "alphaTab.min.mjs").exists(),
        reason="alphaTab não vendorizado (uv run python scripts/vendor_alphatab.py)",
    ),
]

BPM = 90

#: O que o executor recebeu, para conferir o que o formulário mandou. Limpo pela
#: fixture a cada teste.
RECEBIDOS: list[dict[str, object]] = []

#: O que o executor vai devolver como aviso de oitava. O teste enche antes de postar.
AVISOS: list[OctaveWarning] = []

#: Campos que o teste troca no `Resultado` devolvido. Limpo pela fixture.
TROCAS: dict[str, object] = {}


def _guitarra_real(out_dir: Path) -> Path:
    """GP5 de seis cordas com mi maior aberto e uma nota solta: o que a guitarra entrega."""
    rotulo = "clean_electric_guitar"
    notas = [NoteEvent(p, 0.0, 0.6, rotulo) for p in (40, 47, 52, 56, 59, 64)]
    notas.append(NoteEvent(45, 60 / BPM, 2 * 60 / BPM, rotulo))
    tab = list(ViterbiAcordes().posicionar(notas, TUNING_GUITARRA_6).tab)
    exportador = Gp5Exporter(
        bpm=BPM,
        faixa="Guitarra",
        programa_gm=PERFIS["guitarra-limpa"].programa_gm,
        acordes=True,
    )
    return exportador.export(tab, out_dir / "estudo.guitarra-limpa.gp5", TUNING_GUITARRA_6)


def _bateria_real(out_dir: Path) -> Path:
    """Faixa de percussão com bumbo e chimbal juntos e caixa: o que a bateria entrega."""
    ataques = [
        EventoPercussivo(i * 30 / BPM, p)
        for i in range(8)
        for p in ((36, 42) if i % 2 == 0 else (38,))
    ]
    return Gp5PercussaoExporter(bpm=BPM).exportar(ataques, out_dir / "estudo.bateria.gp5")


def _partitura_real(out_dir: Path, **kw: object) -> Resultado:
    """Executor de mentira, artefato de verdade: o alphaTab precisa de um GP5 legítimo."""
    RECEBIDOS.append(kw)
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
    if kw.get("instrumento", "baixo") == "baixo":
        artefato = Gp5Exporter(bpm=BPM).export(notas, out_dir / "estudo.gp5", TUNING_BASS_4)
    elif kw["instrumento"] == "bateria":
        artefato = _bateria_real(out_dir)
    else:
        artefato = _guitarra_real(out_dir)
    resultado = Resultado(
        asset=AudioAsset(
            wav=out_dir / "mix.wav", source_id="estudo", title="estudo", duration_s=3.0
        ),
        stem=out_dir / "bass.wav",
        artefatos={"gp5": artefato},
        notas=len(notas),
        bpm=BPM,
        rotulos={"electric_bass": len(notas)},
        descartadas=[],
        fora_do_braco=[],
        avisos_de_oitava=list(AVISOS),
        tonalidade=tom_de_texto(str(kw["tom"])) if kw.get("tom") else None,
        instrumento=str(kw.get("instrumento", "baixo")),
    )
    return replace(resultado, **TROCAS)  # type: ignore[arg-type]


@pytest.fixture
def servidor(tmp_path: Path) -> Iterator[str]:
    import uvicorn

    RECEBIDOS.clear()
    AVISOS.clear()
    TROCAS.clear()

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


def test_o_formulario_manda_afinacao_e_digitacao_por_nome(servidor: str) -> None:
    """O único caminho que exercita o JS do formulário (ADR-028).

    O teste acima posta o job por HTTP e passa por cima da página: um `Number()`
    sobre "drop-d" viraria `NaN`, o servidor devolveria 422 e a suíte inteira
    continuaria verde.
    """
    estado = avaliar(
        f"{servidor}/",
        """(async () => {
             document.getElementById('ref').value = 'x.wav';
             document.getElementById('afinacao').value = 'drop-d';
             document.getElementById('digitacao').value = 'experiente';
             document.getElementById('enviar').click();
             for (let i = 0; i < 100; i++) {
               const jobs = await (await fetch('/jobs')).json();
               if (jobs.length && jobs[0].status !== 'na fila') return jobs[0];
               await new Promise(r => setTimeout(r, 100));
             }
             return {status: 'nenhum job criado'};
           })()""",
        espera_s=6,
    )

    assert estado["status"] == "pronto", estado
    assert RECEBIDOS and RECEBIDOS[0]["tuning"] == TUNING_BASS_DROP_D
    assert RECEBIDOS[0]["instrumento"] == "baixo"
    assert RECEBIDOS[0]["assigner"].custos is PADRAO


def test_a_pagina_mostra_a_alternativa_do_aviso_de_oitava(servidor: str) -> None:
    """O número sozinho não diz o que conferir, e `sugestao` pode ser `null` (ADR-030)."""
    nota = NoteEvent(pitch=23, onset_s=1.25, offset_s=1.8, instrument="electric_bass")
    AVISOS.extend([OctaveWarning(nota, 35, 0.12, 3.0), OctaveWarning(nota, None, 0.33, 0.12)])

    ident = httpx.post(
        f"{servidor}/jobs", json={"ref": "x.wav", "bpm": BPM}, timeout=10
    ).json()["id"]
    estado = avaliar(
        f"{servidor}/?job={ident}",
        "({texto: document.getElementById('estado').innerText})",
        espera_s=10,
    )

    assert "23@1.25s → 35" in estado["texto"], estado
    assert "sem alternativa" in estado["texto"], estado


def test_o_formulario_manda_o_tom_e_a_pagina_relata_a_grafia(servidor: str) -> None:
    """Campo de tom e relato da grafia — o único caminho que exercita os dois (ADR-031)."""
    estado = avaliar(
        f"{servidor}/",
        """(async () => {
             document.getElementById('ref').value = 'x.wav';
             document.getElementById('tom').value = 'f menor';
             document.getElementById('enviar').click();
             for (let i = 0; i < 100; i++) {
               const jobs = await (await fetch('/jobs')).json();
               if (jobs.length && jobs[0].status === 'pronto') {
                 await new Promise(r => setTimeout(r, 300));
                 return {tom: jobs[0].tom, texto: document.getElementById('estado').innerText};
               }
               await new Promise(r => setTimeout(r, 100));
             }
             return {tom: null, texto: 'nenhum job pronto'};
           })()""",
        espera_s=8,
    )

    assert RECEBIDOS and RECEBIDOS[0]["tom"] == "f menor"
    assert estado["tom"] == {"nome": "f minor", "armadura": -4, "margem": None}
    assert "f minor" in estado["texto"], estado


def _pronto(servidor: str, corpo: dict[str, object]) -> str:
    ident = httpx.post(f"{servidor}/jobs", json=corpo, timeout=10).json()["id"]
    limite = time.time() + 30
    while time.time() < limite:
        if httpx.get(f"{servidor}/jobs/{ident}", timeout=5).json()["status"] == "pronto":
            return str(ident)
        time.sleep(0.3)
    pytest.fail("job não ficou pronto")


def test_o_formulario_de_guitarra_manda_o_instrumento_e_nao_a_afinacao(servidor: str) -> None:
    """A afinação da guitarra é a do perfil: mandá-la dá 422 (ADR-044)."""
    estado = avaliar(
        f"{servidor}/",
        """(async () => {
             document.getElementById('ref').value = 'x.wav';
             const escolha = document.getElementById('instrumento');
             escolha.value = 'guitarra-limpa';
             escolha.dispatchEvent(new Event('change'));
             const desabilitada = document.getElementById('afinacao').disabled;
             document.getElementById('enviar').click();
             for (let i = 0; i < 100; i++) {
               const jobs = await (await fetch('/jobs')).json();
               if (jobs.length && jobs[0].status !== 'na fila') {
                 return {status: jobs[0].status, desabilitada};
               }
               await new Promise(r => setTimeout(r, 100));
             }
             return {status: 'nenhum job criado', desabilitada,
                     texto: document.getElementById('estado').innerText};
           })()""",
        espera_s=6,
    )

    assert estado["status"] == "pronto", estado
    assert estado["desabilitada"] is True
    assert RECEBIDOS[0]["instrumento"] == "guitarra-limpa"
    assert RECEBIDOS[0]["tuning"] is None


def test_a_partitura_de_guitarra_com_acorde_aparece_na_tela(servidor: str) -> None:
    """Seis cordas e um beat de seis notas: o alphaTab só tinha visto o baixo."""
    ident = _pronto(servidor, {"ref": "x.wav", "bpm": BPM, "instrumento": "guitarra-limpa"})

    estado = avaliar(
        f"{servidor}/?job={ident}",
        "({svg: document.querySelectorAll('#tab svg').length,"
        " viva_por_ms: performance.now(),"
        " texto: document.getElementById('estado').innerText})",
        espera_s=15,
    )

    assert estado["viva_por_ms"] > 10_000, f"sessão curta demais para concluir nada: {estado}"
    assert estado["svg"] > 0, f"a partitura de guitarra não foi desenhada: {estado}"


def test_a_pagina_relata_as_tres_causas_de_nota_fora(servidor: str) -> None:
    acorde = (
        NoteEvent(40, 12.0, 12.4, "clean_electric_guitar"),
        NoteEvent(41, 12.06, 12.4, "clean_electric_guitar"),
    )
    TROCAS.update(
        erro_de_rotulo={"acoustic_guitar": 3},
        contaminacao={"acoustic_piano": 2},
        acordes_impossiveis=[AcordeImpossivel(acorde, "as duas só cabem na mesma corda")],
    )
    ident = _pronto(servidor, {"ref": "x.wav", "bpm": BPM, "instrumento": "guitarra-limpa"})

    texto = avaliar(
        f"{servidor}/?job={ident}", "document.getElementById('estado').innerText", espera_s=6
    )

    assert "erro de rótulo" in texto and "acoustic_guitar" in texto, texto
    assert "contaminação" in texto and "acoustic_piano" in texto, texto
    assert "40 41 @12s: as duas só cabem na mesma corda" in texto, texto


def test_job_sem_gp5_diz_por_que_nao_ha_partitura_na_tela(servidor: str) -> None:
    """O alphaTab só lê GP5; um alvo que só tem MusicXML é dito, não quebrado (ADR-044)."""
    ident = _pronto(servidor, {"ref": "x.wav", "bpm": BPM})
    job = httpx.get(f"{servidor}/jobs/{ident}", timeout=5).json()
    assert job["formatos"] == ["gp5"]
    TROCAS["artefatos"] = {}  # só para o próximo job
    ident = _pronto(servidor, {"ref": "y.wav", "bpm": BPM})

    estado = avaliar(
        f"{servidor}/?job={ident}",
        "({texto: document.getElementById('estado').innerText,"
        " oculto: document.getElementById('controles').classList.contains('oculto'),"
        " viva_por_ms: performance.now()})",
        espera_s=6,
    )

    assert estado["viva_por_ms"] > 5_000, estado
    assert "sem GP5" in estado["texto"], estado
    assert estado["oculto"] is True, estado


#: Injetado antes da página: toda ligação à saída de som ganha um analisador, e o volume
#: (RMS) de cada 100 ms fica em `window.__rms`. Só a API padrão do navegador, nada do
#: alphaTab — se ele mudar a forma de ligar o som, `saidas` fica em 0 e o teste diz.
OUVIDO = """
(() => {
  window.__rms = []; window.__saidas = 0;
  const ligar = AudioNode.prototype.connect;
  AudioNode.prototype.connect = function (alvo, ...resto) {
    if (alvo instanceof AudioDestinationNode) {
      const a = this.context.createAnalyser();
      ligar.call(this, a);
      window.__saidas += 1;
      const b = new Float32Array(a.fftSize);
      setInterval(() => {
        a.getFloatTimeDomainData(b);
        window.__rms.push(Math.sqrt(b.reduce((s, x) => s + x * x, 0) / b.length));
      }, 100);
    }
    return ligar.call(this, alvo, ...resto);
  };
})();
"""

#: Volume no último segundo e posição horizontal do cursor.
LEITURA = """(() => {
  const c = document.querySelector('.at-cursor-beat');
  const x = c && /translate\\(([-\\d.]+)px/.exec(c.style.transform);
  return {rms: Math.max(0, ...window.__rms.slice(-10)), saidas: window.__saidas,
          cursor_x: x ? Number(x[1]) : null};
})()"""


def test_tocar_faz_sair_som_e_andar_o_cursor_e_parar_cala(servidor: str) -> None:
    """O que antes era verificação manual: sai som? o cursor anda? — medido, não ouvido."""
    ident = httpx.post(
        f"{servidor}/jobs", json={"ref": "x.wav", "bpm": BPM}, timeout=10
    ).json()["id"]
    antes, _, tocando_1, tocando_2, _, parado = sessao(
        f"{servidor}/?job={ident}",
        [
            (12, LEITURA),
            (0, "document.getElementById('tocar').click()"),
            (1, LEITURA),
            (1, LEITURA),
            (0, "document.getElementById('parar').click()"),
            (1.5, LEITURA),
        ],
        script_inicial=OUVIDO,
    )
    print(f"antes {antes} · tocando {tocando_1} → {tocando_2} · parado {parado}")

    assert antes["rms"] == 0, f"som antes de tocar: {antes}"
    assert tocando_2["saidas"] > 0, "nada ligado à saída de som — o gancho não viu o player"
    assert tocando_2["rms"] > 0.01, f"tocando e sem som: {tocando_2}"
    assert tocando_1["cursor_x"] is not None, f"a página não tem cursor: {tocando_1}"
    assert tocando_2["cursor_x"] > tocando_1["cursor_x"], (
        f"o cursor não andou: {tocando_1} → {tocando_2}"
    )
    assert parado["rms"] < 0.001, f"parar não calou: {parado}"


def test_o_formulario_de_bateria_manda_o_instrumento_e_nao_a_afinacao(servidor: str) -> None:
    estado = avaliar(
        f"{servidor}/",
        """(async () => {
             document.getElementById('ref').value = 'x.wav';
             const escolha = document.getElementById('instrumento');
             escolha.value = 'bateria';
             escolha.dispatchEvent(new Event('change'));
             const desabilitada = document.getElementById('afinacao').disabled;
             document.getElementById('enviar').click();
             for (let i = 0; i < 100; i++) {
               const jobs = await (await fetch('/jobs')).json();
               if (jobs.length && jobs[0].status !== 'na fila') {
                 return {status: jobs[0].status, desabilitada};
               }
               await new Promise(r => setTimeout(r, 100));
             }
             return {status: 'nenhum job criado', desabilitada,
                     texto: document.getElementById('estado').innerText};
           })()""",
        espera_s=6,
    )

    assert estado["status"] == "pronto", estado
    assert estado["desabilitada"] is True
    assert RECEBIDOS[0]["instrumento"] == "bateria"
    assert RECEBIDOS[0]["tuning"] is None


def test_a_partitura_de_bateria_aparece_e_os_ataques_fora_sao_relatados(servidor: str) -> None:
    """Faixa de percussão no alphaTab, e cada causa de ataque fora na sua contagem."""
    TROCAS.update(
        ataques_descartados={
            "repetida no tique": [EventoPercussivo(1.0, 36), EventoPercussivo(2.0, 38)],
            "além de seis no tique": [EventoPercussivo(3.0, 57)],
        },
    )
    ident = _pronto(servidor, {"ref": "x.wav", "bpm": BPM, "instrumento": "bateria"})

    estado = avaliar(
        f"{servidor}/?job={ident}",
        "({svg: document.querySelectorAll('#tab svg').length,"
        " viva_por_ms: performance.now(),"
        " texto: document.getElementById('estado').innerText})",
        espera_s=15,
    )

    assert estado["viva_por_ms"] > 10_000, f"sessão curta demais para concluir nada: {estado}"
    assert estado["svg"] > 0, f"a partitura de bateria não foi desenhada: {estado}"
    assert "ataque(s) fora da partitura: 1 além de seis no tique, 2 repetida no tique" in (
        estado["texto"]
    ), estado
