"""API de jobs.

O pipeline entra injetado: ele custa minutos de CPU e já tem teste próprio contra
Demucs e MuScriptor reais. O caminho com o pipeline de verdade está no fim, `slow`.
"""

from __future__ import annotations

import threading
import time
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.sintetico import SOUNDFONT, renderizar
from thoth.api.app import (
    LIMITE_DE_JOBS,
    TERMINADOS,
    Job,
    Pedido,
    _afinacao,
    criar_app,
    descartar_antigos,
)
from thoth.domain.models import (
    TUNING_BASS_4,
    TUNING_BASS_DROP_D,
    AcordeImpossivel,
    AudioAsset,
    NoteEvent,
)
from thoth.domain.reproducao import ReproducaoExterna
from thoth.services.acordes import ViterbiAcordes
from thoth.services.fretboard import PADRAO
from thoth.services.octave_check import OctaveWarning
from thoth.services.pipeline import Resultado
from thoth.services.tonalidade import Tonalidade


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


class _Local(TestClient):
    """Fala com o servidor pelo host da página; o `testserver` do Starlette é recusado."""

    def __init__(self, app, **kwargs):  # type: ignore[no-untyped-def]
        super().__init__(app, base_url="http://127.0.0.1:8000", **kwargs)


class _ClienteQueEspera(_Local):
    """O job roda no trabalhador, fora da requisição: o `POST /jobs` volta antes dele.

    Quem testa o que o job produziu espera ele terminar; quem testa a fila em si usa
    o `TestClient` cru.
    """

    def post(self, url, *args, **kwargs):  # type: ignore[no-untyped-def, override]
        resposta = super().post(url, *args, **kwargs)
        if url == "/jobs" and resposta.status_code == 202:
            limite = time.monotonic() + 600
            while self.get(f"/jobs/{resposta.json()['id']}").json()["status"] not in TERMINADOS:
                assert time.monotonic() < limite, "o job não terminou"
                time.sleep(0.005)
        return resposta


def _app(tmp_path: Path, executar=None):  # type: ignore[no-untyped-def]
    return criar_app(
        out_dir=tmp_path / "out",
        cache_dir=tmp_path / "cache",
        executar=executar or (lambda ref, out_dir, **kw: _resultado_falso(out_dir, **kw)),
    )


def _cliente(tmp_path: Path, executar=None) -> TestClient:
    return _ClienteQueEspera(_app(tmp_path, executar))


def test_job_roda_e_relata_o_que_o_pipeline_descartou(tmp_path: Path) -> None:
    cliente = _cliente(tmp_path)

    criado = cliente.post("/jobs", json={"ref": "x.mp3", "bpm": 90})
    assert criado.status_code == 202, criado.text

    job = cliente.get(f"/jobs/{criado.json()['id']}").json()
    assert job["status"] == "pronto"
    assert job["notas"] == 15
    assert job["descartadas"] == 1
    assert job["formatos"] == ["gp5"]
    assert job["trechos_sem_baixo"] == []


def test_lista_players_mpris_sem_dependencia_de_player_instalado(tmp_path: Path) -> None:
    class LeitorFalso:
        async def listar(self) -> list[ReproducaoExterna]:
            return [
                ReproducaoExterna(
                    nome="org.mpris.MediaPlayer2.vlc",
                    identidade="VLC media player",
                    estado="Playing",
                    posicao_s=12.5,
                    duracao_s=180.0,
                    titulo="Música de teste",
                    artista="Banda",
                    album="Álbum",
                    url="file:///tmp/musica.flac",
                )
            ]

    cliente = _Local(
        criar_app(
            out_dir=tmp_path / "out",
            cache_dir=tmp_path / "cache",
            leitor_reproducao=LeitorFalso(),
        )
    )

    resposta = cliente.get("/playback/players")

    assert resposta.status_code == 200
    assert resposta.json() == [
        {
            "nome": "org.mpris.MediaPlayer2.vlc",
            "identidade": "VLC media player",
            "estado": "Playing",
            "posicao_s": 12.5,
            "duracao_s": 180.0,
            "titulo": "Música de teste",
            "artista": "Banda",
            "album": "Álbum",
        }
    ]


def test_lista_players_mpris_vazia_quando_nao_ha_player(tmp_path: Path) -> None:
    class LeitorVazio:
        async def listar(self) -> list[ReproducaoExterna]:
            return []

    cliente = _Local(
        criar_app(
            out_dir=tmp_path / "out",
            cache_dir=tmp_path / "cache",
            leitor_reproducao=LeitorVazio(),
        )
    )

    assert cliente.get("/playback/players").json() == []


def test_job_relata_trecho_sem_baixo(tmp_path: Path) -> None:
    from thoth.services.rotulos import TrechoSemBaixo

    trecho = TrechoSemBaixo(516.5, 654.88, {"clean_electric_guitar": 621})
    cliente = _cliente(
        tmp_path,
        lambda ref, out_dir, **kw: replace(_resultado_falso(out_dir), trechos_sem_baixo=[trecho]),
    )

    criado = cliente.post("/jobs", json={"ref": "x.mp3", "bpm": 90})
    job = cliente.get(f"/jobs/{criado.json()['id']}").json()

    assert job["trechos_sem_baixo"] == [
        {"inicio_s": 516.5, "fim_s": 654.88, "rotulos": {"clean_electric_guitar": 621}}
    ]


def test_bpm_afinacao_e_digitacao_chegam_ao_pipeline(tmp_path: Path) -> None:
    """BPM errado produz leitura errada (ADR-013): não pode se perder no caminho.

    Drop D é o caso que a contagem de cordas não conseguia pedir (ADR-028): tem
    quatro cordas como a afinação padrão, e nenhuma delas afinada igual.
    """
    recebido: dict[str, object] = {}

    def espiao(ref: str, out_dir: Path, **kw: object) -> Resultado:
        recebido.update(kw)
        return _resultado_falso(out_dir)

    cliente = _cliente(tmp_path, espiao)
    resposta = cliente.post(
        "/jobs",
        json={"ref": "x.mp3", "bpm": 72, "afinacao": "drop-d", "digitacao": "experiente"},
    )

    assert resposta.status_code == 202, resposta.text
    assert recebido["bpm"] == 72
    assert recebido["tuning"] == TUNING_BASS_DROP_D
    assert recebido["assigner"].custos is PADRAO  # type: ignore[union-attr]


def test_afinacao_desconhecida_e_recusada_na_entrada(tmp_path: Path) -> None:
    resposta = _cliente(tmp_path).post("/jobs", json={"ref": "x.mp3", "afinacao": "7"})

    assert resposta.status_code == 422


def test_instrumento_de_guitarra_chega_ao_pipeline_com_a_afinacao_do_perfil(
    tmp_path: Path,
) -> None:
    """`tuning=None`: a afinação da guitarra vem do perfil, não da lista do baixo."""
    recebido: dict[str, object] = {}

    def espiao(ref: str, out_dir: Path, **kw: object) -> Resultado:
        recebido.update(kw)
        return _resultado_falso(out_dir)

    resposta = _cliente(tmp_path, espiao).post(
        "/jobs", json={"ref": "x.mp3", "instrumento": "guitarra-limpa"}
    )

    assert resposta.status_code == 202, resposta.text
    assert recebido["instrumento"] == "guitarra-limpa"
    assert recebido["tuning"] is None
    assert isinstance(recebido["atribuidor_de_acordes"], ViterbiAcordes)


def test_sem_instrumento_o_pedido_e_de_baixo_na_afinacao_padrao(tmp_path: Path) -> None:
    recebido: dict[str, object] = {}

    def espiao(ref: str, out_dir: Path, **kw: object) -> Resultado:
        recebido.update(kw)
        return _resultado_falso(out_dir)

    _cliente(tmp_path, espiao).post("/jobs", json={"ref": "x.mp3"})

    assert recebido["instrumento"] == "baixo"
    assert recebido["tuning"] == TUNING_BASS_4


def test_pedido_todos_nao_aplica_afinacao_especifica() -> None:
    pedido = Pedido(ref="x.mp3", instrumento="todos")

    assert pedido.instrumento == "todos"
    assert _afinacao(pedido) is None


@pytest.mark.parametrize(
    "corpo",
    [
        {"instrumento": "piano-acustico"},
        {"instrumento": "violino"},
        {"instrumento": "bateria", "afinacao": "5"},
        {"instrumento": "guitarra-limpa", "afinacao": "drop-d"},
    ],
)
def test_instrumento_sem_exportador_ou_afinacao_de_baixo_na_guitarra_sao_recusados(
    tmp_path: Path, corpo: dict[str, str]
) -> None:
    resposta = _cliente(tmp_path).post("/jobs", json={"ref": "x.mp3", **corpo})

    assert resposta.status_code == 422, resposta.text


def test_job_de_guitarra_relata_as_tres_causas_de_nota_fora(tmp_path: Path) -> None:
    acorde = (
        NoteEvent(40, 12.0, 12.4, "clean_electric_guitar"),
        NoteEvent(41, 12.06, 12.4, "clean_electric_guitar"),
    )
    impossivel = AcordeImpossivel(acorde, "duas notas só cabem na mesma corda")
    cliente = _cliente(
        tmp_path,
        lambda ref, out_dir, **kw: replace(
            _resultado_falso(out_dir),
            instrumento="guitarra-limpa",
            erro_de_rotulo={"acoustic_guitar": 3},
            contaminacao={"acoustic_piano": 2},
            acordes_impossiveis=[impossivel],
        ),
    )

    criado = cliente.post("/jobs", json={"ref": "x.mp3", "instrumento": "guitarra-limpa"})
    job = cliente.get(f"/jobs/{criado.json()['id']}").json()

    assert job["instrumento"] == "guitarra-limpa"
    assert job["erro_de_rotulo"] == {"acoustic_guitar": 3}
    assert job["contaminacao"] == {"acoustic_piano": 2}
    assert job["acordes_impossiveis"] == [
        {"onset_s": 12.0, "alturas": [40, 41], "motivo": "duas notas só cabem na mesma corda"}
    ]


def test_job_de_bateria_relata_os_ataques_fora_por_motivo(tmp_path: Path) -> None:
    from thoth.domain.models import EventoPercussivo

    recebido: dict[str, object] = {}

    def executar(ref: str, out_dir: Path, **kw: object) -> Resultado:
        recebido.update(kw)
        return replace(
            _resultado_falso(out_dir),
            instrumento="bateria",
            ataques_descartados={"além de seis no tique": [EventoPercussivo(4.0, 57)]},
        )

    cliente = _cliente(tmp_path, executar)

    criado = cliente.post("/jobs", json={"ref": "x.mp3", "instrumento": "bateria"})
    job = cliente.get(f"/jobs/{criado.json()['id']}").json()

    assert criado.status_code == 202, criado.text
    assert recebido["instrumento"] == "bateria"
    assert recebido["tuning"] is None
    assert job["ataques_descartados"] == {"além de seis no tique": 1}


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
    cliente = _ClienteQueEspera(criar_app(out_dir=tmp_path / "out", cache_dir=tmp_path / "cache"))

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

    resposta = _Local(app).get("/")

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


def test_um_job_espera_o_outro_em_vez_de_dividir_os_arquivos(tmp_path: Path) -> None:
    """Dois pipelines ao mesmo tempo escrevem no mesmo lugar (ADR-027).

    O cache de separação encena em `<modelo>.parcial` e o exportador nomeia pelo
    título (ADR-017): o segundo job apagaria o encenado do primeiro debaixo dele.
    """
    liberar, dentro_de_a, dentro_de_b = (threading.Event() for _ in range(3))

    def executar(ref: str, out_dir: Path, **kw: object) -> Resultado:
        (dentro_de_a if ref == "a.mp3" else dentro_de_b).set()
        assert liberar.wait(10), "o teste travou esperando liberação"
        return _resultado_falso(out_dir)

    cliente = _cliente(tmp_path, executar)
    jobs = [
        threading.Thread(target=cliente.post, args=("/jobs",), kwargs={"json": {"ref": ref}})
        for ref in ("a.mp3", "b.mp3")
    ]
    jobs[0].start()
    assert dentro_de_a.wait(10), "o primeiro job não chegou a rodar"
    jobs[1].start()

    assert not dentro_de_b.wait(0.5), "o segundo job entrou no pipeline com o primeiro dentro"
    b = next(j for j in cliente.get("/jobs").json() if j["ref"] == "b.mp3")
    assert b["status"] == "na fila"

    liberar.set()
    for job in jobs:
        job.join(10)
    assert [j["status"] for j in cliente.get("/jobs").json()] == ["pronto", "pronto"]


def test_o_historico_de_jobs_para_de_crescer(tmp_path: Path) -> None:
    """Processo de longa vida com dict sem teto é vazamento de memória (ADR-027)."""
    cliente = _cliente(tmp_path)

    ids = [
        cliente.post("/jobs", json={"ref": f"{i}.mp3"}).json()["id"]
        for i in range(LIMITE_DE_JOBS + 5)
    ]

    lista = cliente.get("/jobs").json()
    assert [j["id"] for j in lista] == ids[5:], "deviam sobrar os mais novos"
    assert cliente.get(f"/jobs/{ids[0]}").status_code == 404


def test_job_que_ainda_nao_terminou_nunca_e_descartado() -> None:
    """Descartar o que está rodando perderia o resultado de minutos de CPU."""
    pedido = Pedido(ref="x.mp3")
    jobs = {
        "vivo": Job(id="vivo", pedido=pedido, status="rodando"),
        "fila": Job(id="fila", pedido=pedido, status="na fila"),
        **{f"velho{i}": Job(id=f"velho{i}", pedido=pedido, status="pronto") for i in range(3)},
    }

    descartar_antigos(jobs, limite=3)

    assert list(jobs) == ["vivo", "fila", "velho2"]


def test_o_aviso_de_oitava_sai_com_a_alternativa_e_a_razao(tmp_path: Path) -> None:
    """Pitch e instante não dizem o que conferir; a alternativa ranqueada diz (ADR-030).

    A razão da candidata é `inf` quando não há 4º harmônico no trecho — comum em
    material esparso. `Infinity` é JSON inválido: `JSON.parse` da página recusa o
    corpo inteiro, e nada que use `.json()` do Python percebe, porque o `json` da
    biblioteca padrão aceita.
    """
    nota = NoteEvent(pitch=23, onset_s=1.25, offset_s=1.8, instrument="electric_bass")

    def executar(ref: str, out_dir: Path, **kw: object) -> Resultado:
        return replace(
            _resultado_falso(out_dir, **kw),
            avisos_de_oitava=[
                OctaveWarning(nota, 35, 0.12, float("inf")),
                OctaveWarning(nota, None, 0.33, 0.12),
            ],
        )

    cliente = _cliente(tmp_path, executar)
    ident = cliente.post("/jobs", json={"ref": "x.mp3", "bpm": 90}).json()["id"]
    resposta = cliente.get(f"/jobs/{ident}")

    assert "Infinity" not in resposta.text, "corpo que o JSON.parse da página recusa"
    primeiro, segundo = resposta.json()["avisos_de_oitava"]
    assert primeiro == {
        "pitch": 23,
        "onset_s": 1.25,
        "sugestao": 35,
        "razao": 0.12,
        "razao_sugerida": None,
    }
    assert segundo["sugestao"] is None and segundo["razao_sugerida"] == 0.12


def test_o_tom_chega_ao_pipeline_e_volta_no_resumo(tmp_path: Path) -> None:
    """Tom informado manda (ADR-031); o `_resumo` diz qual foi e com que margem."""
    recebido: dict[str, object] = {}

    def executar(ref: str, out_dir: Path, **kw: object) -> Resultado:
        recebido.update(kw)
        return replace(_resultado_falso(out_dir, **kw), tonalidade=Tonalidade("f minor", -4, None))

    cliente = _cliente(tmp_path, executar)
    criado = cliente.post("/jobs", json={"ref": "x.mp3", "bpm": 90, "tom": "f menor"})
    assert criado.status_code == 202, criado.text

    job = cliente.get(f"/jobs/{criado.json()['id']}").json()
    assert recebido["tom"] == "f menor"
    assert job["tom"] == {"nome": "f minor", "armadura": -4, "margem": None}


def test_tom_ilegivel_e_recusado_na_entrada(tmp_path: Path) -> None:
    resposta = _cliente(tmp_path).post("/jobs", json={"ref": "x.mp3", "tom": "H menor"})

    assert resposta.status_code == 422, resposta.text


def test_upload_de_audio_devolve_ref_que_o_job_aceita(tmp_path: Path) -> None:
    """O navegador não revela o caminho: o áudio sobe e vira `ref` local (ADR-051)."""
    recebido: dict[str, object] = {}

    def executar(ref: str, out_dir: Path, **kw: object) -> Resultado:
        recebido["ref"] = ref
        return _resultado_falso(out_dir)

    cliente = _cliente(tmp_path, executar)
    enviado = cliente.post("/uploads", params={"nome": "Minha Música.mp3"}, content=b"ID3 bytes")

    assert enviado.status_code == 201, enviado.text
    ref = Path(enviado.json()["ref"])
    assert ref.name == "Minha Música.mp3"  # o nome vira o título da partitura
    assert ref.read_bytes() == b"ID3 bytes"
    assert ref.is_relative_to(tmp_path / "cache" / "uploads")
    cliente.post("/jobs", json={"ref": str(ref)})
    assert recebido["ref"] == str(ref)


def test_mesmo_audio_reenviado_cai_no_mesmo_lugar(tmp_path: Path) -> None:
    cliente = _cliente(tmp_path)

    um = cliente.post("/uploads", params={"nome": "a.wav"}, content=b"RIFF x").json()["ref"]
    dois = cliente.post("/uploads", params={"nome": "a.wav"}, content=b"RIFF x").json()["ref"]
    outro = cliente.post("/uploads", params={"nome": "a.wav"}, content=b"RIFF y").json()["ref"]

    assert um == dois
    assert outro != um


@pytest.mark.parametrize("nome", ["Minha Música.wav", "mix.wav"])
def test_wav_real_enviado_e_ingerido_com_o_nome_do_arquivo(tmp_path: Path, nome: str) -> None:
    """O caminho de verdade: o upload passa pelo `LocalFileSource` com ffmpeg e ffprobe.

    `mix.wav` é o nome técnico do cache, e um upload com esse nome não pode ser
    confundido com ele: o título continua sendo o que você enviou.
    """
    from tests.unit.test_cli import _wav
    from thoth.adapters.ingest.local_source import LocalFileSource

    wav = _wav(tmp_path / "origem.wav", segundos=1)
    enviado = _cliente(tmp_path).post("/uploads", params={"nome": nome}, content=wav.read_bytes())
    assert enviado.status_code == 201, enviado.text

    ativo = LocalFileSource().fetch(enviado.json()["ref"], tmp_path / "cache")

    assert ativo.title == Path(nome).stem
    assert ativo.duration_s == pytest.approx(1.0, abs=0.1)
    assert ativo.wav.is_file()


@pytest.mark.parametrize("nome", ["tab.gp5", "partitura.musicxml", "script.sh", "sem_extensao", ""])
def test_upload_recusa_o_que_nao_e_audio(tmp_path: Path, nome: str) -> None:
    """Partitura abre no navegador, não sobe: só áudio vira transcrição."""
    resposta = _cliente(tmp_path).post("/uploads", params={"nome": nome}, content=b"x")

    assert resposta.status_code == 422, resposta.text


def test_upload_ignora_diretorio_no_nome(tmp_path: Path) -> None:
    cliente = _cliente(tmp_path)

    ref = Path(
        cliente.post("/uploads", params={"nome": "../../fora.mp3"}, content=b"x").json()["ref"]
    )

    assert ref.name == "fora.mp3"
    assert ref.is_relative_to(tmp_path / "cache" / "uploads")


def test_upload_vazio_e_recusado(tmp_path: Path) -> None:
    resposta = _cliente(tmp_path).post("/uploads", params={"nome": "a.mp3"}, content=b"")

    assert resposta.status_code == 422, resposta.text


def test_upload_acima_do_teto_e_recusado_sem_deixar_nada_no_cache(tmp_path: Path) -> None:
    """O corpo inteiro ia para a memória antes de qualquer verificação."""
    cliente = _Local(
        criar_app(out_dir=tmp_path / "out", cache_dir=tmp_path / "cache", teto_de_upload=8)
    )

    resposta = cliente.post("/uploads", params={"nome": "a.wav"}, content=b"RIFF" * 3)

    assert resposta.status_code == 413, resposta.text
    uploads = tmp_path / "cache" / "uploads"
    assert not uploads.exists() or not any(uploads.rglob("*"))


def test_upload_no_teto_passa(tmp_path: Path) -> None:
    cliente = _Local(
        criar_app(out_dir=tmp_path / "out", cache_dir=tmp_path / "cache", teto_de_upload=8)
    )

    resposta = cliente.post("/uploads", params={"nome": "a.wav"}, content=b"RIFF1234")

    assert resposta.status_code == 201, resposta.text
    assert Path(resposta.json()["ref"]).read_bytes() == b"RIFF1234"


def test_jobs_rodam_em_ordem_de_chegada_sem_prender_a_requisicao(tmp_path: Path) -> None:
    """Cada job esperava a trava numa thread do pool, e a trava não tem ordem (ADR-027)."""
    liberar = threading.Event()
    ordem: list[str] = []

    def executar(ref: str, out_dir: Path, **kw: object) -> Resultado:
        if not ordem:
            # O primeiro segura o trabalhador até os outros três estarem na fila.
            assert liberar.wait(timeout=5), "a requisição esperou o job terminar"
        ordem.append(ref)
        return _resultado_falso(out_dir)

    cliente = _Local(_app(tmp_path, executar))
    ids = [cliente.post("/jobs", json={"ref": f"{n}.mp3"}).json()["id"] for n in "abcd"]
    liberar.set()

    limite = time.monotonic() + 5
    while time.monotonic() < limite:
        if all(cliente.get(f"/jobs/{i}").json()["status"] == "pronto" for i in ids):
            break
        time.sleep(0.01)
    assert ordem == ["a.mp3", "b.mp3", "c.mp3", "d.mp3"]


@pytest.mark.parametrize(
    "ref",
    [
        "https://exemplo.com/watch?v=QTOyeFQgZKk",
        "http://127.0.0.1:9000/interno",
        "/etc/passwd",
        "~/.ssh/id_ed25519",
        "",
    ],
)
def test_ref_que_nao_e_youtube_nem_audio_e_recusado_na_entrada(tmp_path: Path, ref: str) -> None:
    """O `ref` decide o que o servidor lê do disco e de onde o yt-dlp baixa."""
    resposta = _cliente(tmp_path).post("/jobs", json={"ref": ref})

    assert resposta.status_code == 422, resposta.text


@pytest.mark.parametrize("ref", ["https://youtu.be/QTOyeFQgZKk", "~/Música/baixo.MP3"])
def test_ref_do_youtube_ou_de_audio_local_e_aceito(tmp_path: Path, ref: str) -> None:
    assert _cliente(tmp_path).post("/jobs", json={"ref": ref}).status_code == 202


def test_host_estranho_e_recusado(tmp_path: Path) -> None:
    """DNS rebinding: uma página de fora resolvendo o próprio domínio para 127.0.0.1."""
    cliente = TestClient(_app(tmp_path), base_url="http://ataque.exemplo")

    assert cliente.get("/jobs").status_code == 400


def test_host_informado_ao_servidor_e_aceito(tmp_path: Path) -> None:
    app = criar_app(out_dir=tmp_path / "out", cache_dir=tmp_path / "c", hosts=("pandora.lan",))

    assert TestClient(app, base_url="http://pandora.lan:8000").get("/jobs").status_code == 200
