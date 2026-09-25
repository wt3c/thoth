"""Pipeline ponta a ponta.

Ingestão, tablatura, ritmo, verificação de oitava e exportadores são os reais —
só a separação e a transcrição entram dubladas, porque cada uma custa minutos de
CPU e já tem teste contra o binário real no seu próprio módulo (Regra 3). O
caminho completo com os dois de verdade está marcado `slow` no fim do arquivo.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from tests.sintetico import SOUNDFONT, renderizar
from thoth.domain.models import TUNING_BASS_5, AudioAsset, NoteEvent
from thoth.services.cache_notas import ler
from thoth.services.pipeline import ROTULOS_DE_BAIXO, transcrever


@dataclass(frozen=True, slots=True)
class SeparadorFalso:
    """Devolve o próprio áudio como stem de baixo, e silêncio como playback.

    A separação tem teste próprio. O `no_bass` precisa ser um arquivo **distinto**:
    apontá-lo para a entrada faria mix, baixo e sem-baixo saírem com os mesmos
    bytes, e o teste de cópia não distinguiria fiação correta de laço que grava o
    mix três vezes — a armadilha que o ADR-036 já pagou.
    """

    def separate(self, audio: Path, out_dir: Path) -> dict[str, Path]:
        out_dir.mkdir(parents=True, exist_ok=True)
        playback = out_dir / "no_bass.wav"
        dados, taxa = sf.read(str(audio))
        sf.write(str(playback), np.zeros_like(dados), taxa)
        return {"bass": audio, "no_bass": playback}


@dataclass(slots=True)
class EtapasVistas:
    """Dublê do `Progresso`: anota o nome de cada estágio na ordem em que chegou."""

    nomes: list[str] = field(default_factory=list)

    def inicia(self, etapa: str, detalhe: str = "") -> None:
        self.nomes.append(etapa)


@dataclass(frozen=True, slots=True)
class TranscritorFalso:
    notas: tuple[NoteEvent, ...]

    def transcribe(self, audio: Path, instrument: str | None = None) -> list[NoteEvent]:
        return [n for n in self.notas if instrument is None or n.instrument == instrument]


def _nota(pitch: int, onset: float, rotulo: str = "electric_bass") -> NoteEvent:
    return NoteEvent(pitch=pitch, onset_s=onset, offset_s=onset + 0.5, instrument=rotulo)


def _rodar(tmp_path: Path, notas: tuple[NoteEvent, ...], **kwargs: object):
    """Os dublês são default, não imposição: `kwargs` passa por cima de qualquer um."""
    wav, _ = renderizar("escala", tmp_path)
    argumentos: dict[str, object] = {
        "bpm": 90,
        "cache_dir": tmp_path / "cache",
        "separator": SeparadorFalso(),
        "transcriber": TranscritorFalso(notas),
    }
    return transcrever(str(wav), tmp_path / "out", **(argumentos | kwargs))  # type: ignore[arg-type]


requer_soundfont = pytest.mark.skipif(not SOUNDFONT.exists(), reason="soundfont ausente")


@requer_soundfont
def test_gera_os_dois_artefatos_nomeados_pelo_titulo(tmp_path: Path) -> None:
    resultado = _rodar(tmp_path, (_nota(36, 0.0), _nota(38, 0.7)))

    assert {"gp5", "musicxml"} <= set(resultado.artefatos)
    for formato in ("gp5", "musicxml"):
        caminho = resultado.artefatos[formato]
        assert caminho.exists() and caminho.stem == resultado.asset.title


@requer_soundfont
def test_o_mix_e_o_baixo_acompanham_a_partitura(tmp_path: Path) -> None:
    """Partitura sem o áudio ao lado obriga a procurar a música em outro lugar.

    Os dois vinham do cache, que é nomeado por hash da fonte: quem abrisse a pasta
    de saída via `.gp5` e `.musicxml` e mais nada que se pudesse ouvir (ADR-036).
    """
    resultado = _rodar(tmp_path, (_nota(36, 0.0), _nota(38, 0.7)))
    titulo = resultado.asset.title

    audios = {k: resultado.artefatos[k] for k in ("mix", "baixo")}
    assert [c.name for c in audios.values()] == [f"{titulo}.mix.wav", f"{titulo}.baixo.wav"]
    assert all(c.parent == resultado.artefatos["gp5"].parent for c in audios.values())
    # Cópia, não atalho: a pasta de saída tem que sobreviver à limpeza do cache.
    assert audios["mix"].read_bytes() == resultado.asset.wav.read_bytes()
    assert audios["baixo"].read_bytes() == resultado.stem.read_bytes()
    assert not any(c.is_symlink() for c in audios.values())


@requer_soundfont
def test_o_titulo_da_musica_entra_dentro_da_partitura(tmp_path: Path) -> None:
    """Nome de arquivo certo escondeu isto: dentro saía "Thoth" nas duas.

    O `asset.title` já alimentava `nome_de_arquivo`; faltava chegar aos
    exportadores, que ficavam no título default.
    """
    import guitarpro as gp
    from music21 import converter

    resultado = _rodar(tmp_path, (_nota(36, 0.0), _nota(38, 0.7)))
    titulo = resultado.asset.title

    assert gp.parse(str(resultado.artefatos["gp5"])).title == titulo
    xml = resultado.artefatos["musicxml"]
    assert f"<work-title>{titulo}</work-title>" in xml.read_text()
    assert converter.parse(str(xml)).metadata.bestTitle == titulo


@requer_soundfont
def test_descarta_o_que_nao_e_baixo_e_relata_os_rotulos(tmp_path: Path) -> None:
    """Rotular certo não impede vazamento (ADR-010): o filtro é nosso, e visível."""
    resultado = _rodar(tmp_path, (_nota(36, 0.0), _nota(72, 0.7, "acoustic_piano"), _nota(38, 1.4)))

    assert resultado.notas == 2
    assert resultado.rotulos == {"electric_bass": 2, "acoustic_piano": 1}


@requer_soundfont
def test_baixo_rotulado_como_outro_instrumento_e_readmitido(tmp_path: Path) -> None:
    """Longe de qualquer baixo, a linha com outro rótulo volta para a partitura."""
    baixo = tuple(_nota(40, t * 0.5) for t in range(8))
    guitarra = tuple(_nota(40, 10.0 + t * 0.5, "clean_electric_guitar") for t in range(20))

    resultado = _rodar(tmp_path, baixo + guitarra)

    assert resultado.notas == 8 + 20
    assert [t.rotulos for t in resultado.trechos_sem_baixo] == [{"clean_electric_guitar": 20}]


@requer_soundfont
def test_nota_simultanea_e_descartada_sem_derrubar_o_pipeline(tmp_path: Path) -> None:
    """A mais grave fica; a outra vai para o relatório, não para o silêncio."""
    resultado = _rodar(tmp_path, (_nota(43, 0.0), _nota(31, 0.0), _nota(38, 0.7)))

    assert resultado.notas == 2
    assert [n.pitch for n in resultado.descartadas] == [43]


@requer_soundfont
def test_sem_nota_de_baixo_falha_dizendo_o_que_veio(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="acoustic_piano"):
        _rodar(tmp_path, (_nota(72, 0.0, "acoustic_piano"),))


@requer_soundfont
def test_avisa_oitava_suspeita_contra_o_audio_real(tmp_path: Path) -> None:
    """A escala começa em C2 (36); afirmar C1 (24) acha só o 2º harmônico."""
    resultado = _rodar(tmp_path, (_nota(24, 0.0), _nota(38, 1.4)), tuning=TUNING_BASS_5)

    assert [a.event.pitch for a in resultado.avisos_de_oitava] == [24]


@requer_soundfont
def test_nota_fora_do_braco_nao_derruba_a_musica_inteira(tmp_path: Path) -> None:
    """Assinatura do erro de oitava do Demucs — custa a nota, não as duas horas."""
    resultado = _rodar(tmp_path, (_nota(24, 0.0), _nota(38, 0.7)))  # 24 < E1 de 4 cordas

    assert resultado.notas == 1
    assert [n.pitch for n in resultado.fora_do_braco] == [24]
    assert resultado.artefatos["gp5"].exists()


def test_rotulos_de_baixo_cobrem_os_tres_nomes_do_muscriptor() -> None:
    assert set(ROTULOS_DE_BAIXO) == {"electric_bass", "acoustic_bass", "contrabass"}


@pytest.mark.slow
@requer_soundfont
def test_caminho_completo_com_demucs_e_muscriptor_reais(tmp_path: Path) -> None:
    wav, _ = renderizar("escala", tmp_path)

    resultado = transcrever(str(wav), tmp_path / "out", bpm=90, cache_dir=tmp_path / "cache")

    assert resultado.notas > 10  # a escala tem 15 notas
    assert all(c.exists() for c in resultado.artefatos.values())
    # Com o Demucs real os três stems são arquivos distintos, e não o próprio mix
    # como no dublê: é aqui que se vê que não é a mesma cópia três vezes.
    bytes_de = {k: resultado.artefatos[k].read_bytes() for k in ("mix", "baixo", "sem-baixo")}
    assert len({*bytes_de.values()}) == 3, "mix, baixo e playback têm que diferir"


@requer_soundfont
def test_guarda_as_notas_no_cache_da_fonte(tmp_path: Path) -> None:
    """A transcrição custa minutos; jogar as notas fora obrigaria a pagar de novo."""
    resultado = _rodar(tmp_path, (_nota(36, 0.0), _nota(38, 0.7)))
    guardadas = ler(tmp_path / "cache" / resultado.asset.source_id / "notas.jsonl")

    # São as notas que entraram na tablatura, já sem as descartadas: é o que a
    # auralização precisa comparar com o original.
    assert [n.pitch for n in guardadas] == [36, 38]
    assert len(guardadas) == resultado.notas


# --- Desdobrar a faixa musical (ADR-024) --------------------------------------


def _semicolcheias_rapidas(bpm: float, quantas: int = 16) -> tuple[NoteEvent, ...]:
    """Ataques na semicolcheia de `bpm`: colidem em qualquer grade mais lenta."""
    passo = 60.0 / bpm / 4
    return tuple(_nota(36 + i % 5, i * passo) for i in range(quantas))


@requer_soundfont
def test_bpm_informado_nao_e_desdobrado(tmp_path: Path) -> None:
    """ADR-019: o número que você deu manda, mesmo colidindo. Só a fase é ajustada."""
    resultado = _rodar(tmp_path, _semicolcheias_rapidas(360.0))

    assert resultado.desdobrado is False
    assert resultado.bpm == 90


@requer_soundfont
def test_andamento_estimado_e_desdobrado_quando_as_notas_colidem(tmp_path: Path) -> None:
    """A fixture pulsa a 90; as notas, a 360. A grade de 90 colapsaria os ataques."""
    wav, _ = renderizar("escala", tmp_path)
    resultado = transcrever(
        str(wav),
        tmp_path / "out",
        bpm=None,
        cache_dir=tmp_path / "cache",
        separator=SeparadorFalso(),
        transcriber=TranscritorFalso(_semicolcheias_rapidas(360.0)),
    )

    assert resultado.desdobrado is True
    # O estimador lê 89 ou 90 neste render; o que importa é que ficou perto de 90.
    assert resultado.andamento is not None
    assert resultado.andamento.bpm == pytest.approx(90, abs=2)
    assert resultado.bpm >= 180
    # O que motivou o ADR-024: nenhuma nota perdida para colisão na grade.
    assert resultado.notas == 16


# --- BPM fora de faixa não chega à grade (ADR-025) ---------------------------


@pytest.mark.parametrize("bpm", [0, -120, 5, 1000])
def test_bpm_fora_de_faixa_e_erro_antes_de_qualquer_processamento(bpm: int, tmp_path: Path) -> None:
    """A CLI valida, mas quem usa o pipeline como biblioteca também merece o erro."""
    with pytest.raises(ValueError, match="BPM"):
        transcrever("x.mp3", tmp_path, bpm=bpm)


@dataclass(frozen=True, slots=True)
class FonteFalsa:
    """Áudio já em disco, sem ffmpeg nem yt-dlp: a ingestão tem teste próprio."""

    wav: Path

    def fetch(self, ref: str, cache_dir: Path) -> AudioAsset:
        self.vistos.append((ref, cache_dir))
        return AudioAsset(wav=self.wav, source_id="fonte-falsa", title="Título Injetado")

    #: `frozen` não impede mutar o conteúdo de uma lista; é onde o espião anota.
    vistos: list[tuple[str, Path]] = field(default_factory=list)


@requer_soundfont
def test_a_fonte_de_audio_entra_injetada_como_os_outros_estagios(tmp_path: Path) -> None:
    """Sem isto, todo teste do pipeline passava obrigatoriamente pela ingestão real."""
    wav, _ = renderizar("escala", tmp_path)
    fonte = FonteFalsa(wav)

    resultado = transcrever(
        "nem caminho nem URL",
        tmp_path / "out",
        bpm=90,
        cache_dir=tmp_path / "cache",
        source=fonte,
        separator=SeparadorFalso(),
        transcriber=TranscritorFalso((_nota(36, 0.0), _nota(38, 0.7))),
    )

    assert fonte.vistos == [("nem caminho nem URL", tmp_path / "cache")]
    assert resultado.asset.title == "Título Injetado"
    assert resultado.artefatos["gp5"].stem == "Título Injetado"


@requer_soundfont
def test_o_tom_informado_chega_a_armadura_da_partitura(tmp_path: Path) -> None:
    """Tom informado manda, como o `--bpm` manda sobre o andamento (ADR-019/031).

    A leitura é ancorada na pauta de notação: o arquivo traz uma armadura só, mas o
    `attributes` é da parte inteira e o music21 entrega uma cópia a cada pauta
    (ADR-035). Percorrer a partitura toda contaria duas e não diria nada de novo.
    """
    from music21 import converter, key

    resultado = _rodar(tmp_path, (_nota(34, 0.0), _nota(36, 0.7)), tom="f menor")

    assert resultado.tonalidade is not None
    assert resultado.tonalidade.armadura == -4 and resultado.tonalidade.margem is None
    partitura = converter.parse(str(resultado.artefatos["musicxml"])).parts[0]
    assert [k.sharps for k in partitura.recurse().getElementsByClass(key.KeySignature)] == [-4]
    assert "Bb" in [n.lyric for n in partitura.recurse().notes]


@requer_soundfont
def test_sem_tom_informado_o_pipeline_estima_e_relata(tmp_path: Path) -> None:
    """Estimar em silêncio é que não pode: o tom volta no `Resultado`."""
    resultado = _rodar(tmp_path, tuple(_nota(p, i * 0.7) for i, p in enumerate([29, 32, 34, 36])))

    assert resultado.tonalidade is not None
    assert resultado.tonalidade.margem is not None, "estimativa passa pela margem"


# --- Uma pasta por música, e todo áudio dentro dela (ADR-037) -----------------


@requer_soundfont
def test_cada_musica_ganha_a_propria_pasta(tmp_path: Path) -> None:
    """Oito músicas em `out/` plano são quarenta arquivos intercalados (ADR-037)."""
    resultado = _rodar(tmp_path, (_nota(36, 0.0), _nota(38, 0.7)))
    titulo = resultado.asset.title

    pasta = tmp_path / "out" / titulo
    assert pasta.is_dir()
    assert {c.parent for c in resultado.artefatos.values()} == {pasta}
    # O nome se repete de propósito: arquivo arrastado para fora da pasta continua
    # dizendo de que música ele é.
    assert all(c.name.startswith(titulo) for c in resultado.artefatos.values())


@requer_soundfont
def test_os_quatro_audios_saem_na_pasta_da_musica(tmp_path: Path) -> None:
    """Mix, baixo, playback e auralização — tudo que o pipeline produz de áudio.

    O playback (`no_bass`) o Demucs já entregava de graça e ficava só no cache; a
    auralização era comando à parte, e quem transcrevia não a tinha.
    """
    resultado = _rodar(tmp_path, (_nota(36, 0.0), _nota(38, 0.7)))
    titulo = resultado.asset.title
    audios = {k: resultado.artefatos[k] for k in ("mix", "baixo", "sem-baixo", "aural")}

    assert [c.name for c in audios.values()] == [
        f"{titulo}.mix.wav",
        f"{titulo}.baixo.wav",
        f"{titulo}.sem-baixo.wav",
        f"{titulo}.aural.wav",
    ]
    # Cópia, não atalho: a pasta de saída sobrevive à limpeza do cache.
    assert audios["mix"].read_bytes() == resultado.asset.wav.read_bytes()
    assert audios["baixo"].read_bytes() == resultado.stem.read_bytes()
    assert not any(c.is_symlink() for c in audios.values())
    # O dublê rende o playback em silêncio, então ele difere do mix. Os três
    # distintos entre si é o que o teste `slow` com o Demucs real afirma.
    assert audios["sem-baixo"].read_bytes() != audios["mix"].read_bytes()
    # Auralização é estéreo por definição: original num canal, transcrição no outro.
    assert sf.info(str(audios["aural"])).channels == 2


@requer_soundfont
def test_separacao_sem_playback_nao_impede_o_resto(tmp_path: Path) -> None:
    """`no_bass` é opcional no contrato do `Separator` — falta dele não é falha."""

    @dataclass(frozen=True, slots=True)
    class SoBaixo:
        def separate(self, audio: Path, out_dir: Path) -> dict[str, Path]:
            return {"bass": audio}

    resultado = _rodar(tmp_path, (_nota(36, 0.0), _nota(38, 0.7)), separator=SoBaixo())

    assert "sem-baixo" not in resultado.artefatos
    assert resultado.artefatos["mix"].exists()


@requer_soundfont
def test_auralizacao_que_falha_nao_derruba_a_corrida(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Soundfont é opcional; os minutos de CPU já gastos, não (ADR-014).

    O mock aqui é do cenário de erro, não do caminho felizardo — esse roda com o
    fluidsynth real nos testes acima (Regra 3).
    """
    from thoth.services import pipeline as modulo
    from thoth.services.auralizacao import AuralizacaoError

    def explodir(*args: object, **kwargs: object) -> Path:
        raise AuralizacaoError("soundfont ausente: /nao/existe.sf2")

    monkeypatch.setattr(modulo, "auralizar", explodir)
    resultado = _rodar(tmp_path, (_nota(36, 0.0), _nota(38, 0.7)))

    assert "aural" not in resultado.artefatos
    assert resultado.falha_na_auralizacao is not None
    assert "soundfont" in resultado.falha_na_auralizacao
    assert resultado.artefatos["gp5"].exists(), "a partitura não pode ir embora com o áudio"


# --- Os estágios relatados enquanto rodam (ADR-037) ---------------------------


@requer_soundfont
def test_relata_cada_estagio_na_ordem_em_que_roda(tmp_path: Path) -> None:
    """O pipeline anuncia; quem desenha é a CLI. Aqui o dublê só anota a ordem."""
    etapas = EtapasVistas()
    _rodar(tmp_path, (_nota(36, 0.0), _nota(38, 0.7)), progresso=etapas)

    assert etapas.nomes == [
        "obtendo o áudio",
        "separando o baixo",
        "transcrevendo as notas",
        "ajustando a grade rítmica",
        "conferindo as oitavas",
        "posicionando no braço",
        "exportando a partitura",
        "copiando os áudios",
        "auralizando",
    ]
    # `bpm=90` informado pula a estimativa; ela tem teste próprio, porque uma lista
    # só provaria nove dos dez estágios e passaria por completa.
    assert "estimando o andamento" not in etapas.nomes


@requer_soundfont
def test_o_estagio_da_estimativa_aparece_quando_nao_ha_bpm(tmp_path: Path) -> None:
    wav, _ = renderizar("escala", tmp_path)
    etapas = EtapasVistas()

    transcrever(
        str(wav),
        tmp_path / "out",
        bpm=None,
        cache_dir=tmp_path / "cache",
        separator=SeparadorFalso(),
        transcriber=TranscritorFalso((_nota(36, 0.0), _nota(38, 0.7))),
        progresso=etapas,
    )

    assert etapas.nomes[:3] == [
        "obtendo o áudio",
        "estimando o andamento",
        "separando o baixo",
    ]
