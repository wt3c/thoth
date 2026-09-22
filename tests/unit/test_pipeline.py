"""Pipeline ponta a ponta.

Ingestão, tablatura, ritmo, verificação de oitava e exportadores são os reais —
só a separação e a transcrição entram dubladas, porque cada uma custa minutos de
CPU e já tem teste contra o binário real no seu próprio módulo (Regra 3). O
caminho completo com os dois de verdade está marcado `slow` no fim do arquivo.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from tests.sintetico import SOUNDFONT, renderizar
from thoth.domain.models import TUNING_BASS_5, NoteEvent
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
def test_gera_os_dois_artefatos_nomeados_pelo_source_id(tmp_path: Path) -> None:
    resultado = _rodar(tmp_path, (_nota(36, 0.0), _nota(38, 0.7)))

    assert set(resultado.artefatos) == {"gp5", "musicxml"}
    for caminho in resultado.artefatos.values():
        assert caminho.exists() and caminho.stem == resultado.asset.source_id


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
