"""Pipeline ponta a ponta.

Ingestão, tablatura, ritmo, verificação de oitava e exportadores são os reais —
só a separação e a transcrição entram dubladas, porque cada uma custa minutos de
CPU e já tem teste contra o binário real no seu próprio módulo (Regra 3). O
caminho completo com os dois de verdade está marcado `slow` no fim do arquivo.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pytest

from tests.sintetico import SOUNDFONT, renderizar
from thoth.domain.models import TUNING_BASS_5, AudioAsset, NoteEvent
from thoth.services.cache_notas import ler
from thoth.services.pipeline import ROTULOS_DE_BAIXO, transcrever


@dataclass(frozen=True, slots=True)
class SeparadorFalso:
    """Devolve o próprio áudio como stem: a separação tem teste próprio."""

    def separate(self, audio: Path, out_dir: Path) -> dict[str, Path]:
        return {"bass": audio}


@dataclass(frozen=True, slots=True)
class TranscritorFalso:
    notas: tuple[NoteEvent, ...]

    def transcribe(self, audio: Path, instrument: str | None = None) -> list[NoteEvent]:
        return [n for n in self.notas if instrument is None or n.instrument == instrument]


def _nota(pitch: int, onset: float, rotulo: str = "electric_bass") -> NoteEvent:
    return NoteEvent(pitch=pitch, onset_s=onset, offset_s=onset + 0.5, instrument=rotulo)


def _rodar(tmp_path: Path, notas: tuple[NoteEvent, ...], **kwargs: object):
    wav, _ = renderizar("escala", tmp_path)
    return transcrever(
        str(wav),
        tmp_path / "out",
        bpm=90,
        cache_dir=tmp_path / "cache",
        separator=SeparadorFalso(),
        transcriber=TranscritorFalso(notas),
        **kwargs,  # type: ignore[arg-type]
    )


requer_soundfont = pytest.mark.skipif(not SOUNDFONT.exists(), reason="soundfont ausente")


@requer_soundfont
def test_gera_os_dois_artefatos_nomeados_pelo_titulo(tmp_path: Path) -> None:
    resultado = _rodar(tmp_path, (_nota(36, 0.0), _nota(38, 0.7)))

    assert set(resultado.artefatos) == {"gp5", "musicxml"}
    for caminho in resultado.artefatos.values():
        assert caminho.exists() and caminho.stem == resultado.asset.title


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
    resultado = _rodar(
        tmp_path, (_nota(36, 0.0), _nota(72, 0.7, "acoustic_piano"), _nota(38, 1.4))
    )

    assert resultado.notas == 2
    assert resultado.rotulos == {"electric_bass": 2, "acoustic_piano": 1}


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
        str(wav), tmp_path / "out", bpm=None, cache_dir=tmp_path / "cache",
        separator=SeparadorFalso(), transcriber=TranscritorFalso(_semicolcheias_rapidas(360.0)),
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
def test_bpm_fora_de_faixa_e_erro_antes_de_qualquer_processamento(
    bpm: int, tmp_path: Path
) -> None:
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
