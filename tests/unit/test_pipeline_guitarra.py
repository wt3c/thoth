"""Pipeline com `instrumento` de guitarra (ADR-044, M4).

Os mesmos dublês do `test_pipeline.py`: separação e transcrição custam minutos de CPU
e têm teste próprio contra o binário real; o resto — ritmo, posicionamento de acordes,
exportadores e cópia dos áudios — é o de verdade. O ponta a ponta com Demucs e
MuScriptor reais está marcado `slow` no fim.

O caminho do baixo é guardado pelo `test_pipeline.py`, que roda sem `instrumento`.
Aqui o que se afirma é o que a guitarra muda: rótulos separados por perfil, acorde
num beat só e nada do baixo sobrescrito na mesma pasta.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import guitarpro as gp
import numpy as np
import pytest
import soundfile as sf

from tests.sintetico import BPM as BPM_FIXTURE
from tests.sintetico import SOUNDFONT, renderizar
from tests.sintetico_multi import FIXTURES_MULTI, referencia, renderizar_multi
from thoth.domain.models import AudioAsset, NoteEvent
from thoth.services.cache_notas import ler
from thoth.services.evaluation import avaliar_polifonico
from thoth.services.pipeline import transcrever

LIMPA = "clean_electric_guitar"
MI_MAIOR = (40, 47, 52, 56, 59, 64)

requer_soundfont = pytest.mark.skipif(not SOUNDFONT.exists(), reason="soundfont ausente")


@dataclass(frozen=True, slots=True)
class SeparadorFalso:
    """Os quatro stems que as duas famílias usam, cada um um arquivo distinto.

    Arquivos distintos pela mesma razão do dublê do baixo (ADR-036): com os mesmos
    bytes, o teste de cópia não distinguiria a fiação certa da errada.
    """

    def separate(self, audio: Path, out_dir: Path) -> dict[str, Path]:
        out_dir.mkdir(parents=True, exist_ok=True)
        dados, taxa = sf.read(str(audio))
        stems = {}
        for i, nome in enumerate(("no_bass", "other", "no_other")):
            stems[nome] = out_dir / f"{nome}.wav"
            sf.write(str(stems[nome]), dados * (0.1 * i), taxa)
        return {"bass": audio, **stems}


@dataclass(frozen=True, slots=True)
class TranscritorFalso:
    notas: tuple[NoteEvent, ...]

    def transcribe(self, audio: Path, instrument: str | None = None) -> list[NoteEvent]:
        return list(self.notas)


@dataclass(frozen=True, slots=True)
class FonteQueNaoPodeSerChamada:
    def fetch(self, ref: str, cache_dir: Path) -> AudioAsset:
        raise AssertionError("buscou o áudio antes de recusar o pedido")


def _nota(pitch: int, onset: float, rotulo: str = LIMPA, dur: float = 0.5) -> NoteEvent:
    return NoteEvent(pitch=pitch, onset_s=onset, offset_s=onset + dur, instrument=rotulo)


def _acorde(pitches: tuple[int, ...], onset: float, rotulo: str = LIMPA) -> list[NoteEvent]:
    return [_nota(p, onset, rotulo) for p in pitches]


def _rodar(tmp_path: Path, notas: list[NoteEvent], **kwargs: object):
    wav, _ = renderizar("escala", tmp_path)
    argumentos: dict[str, object] = {
        "bpm": 90,
        "cache_dir": tmp_path / "cache",
        "separator": SeparadorFalso(),
        "transcriber": TranscritorFalso(tuple(notas)),
        "instrumento": "guitarra-limpa",
    }
    return transcrever(str(wav), tmp_path / "out", **(argumentos | kwargs))  # type: ignore[arg-type]


def _beats(caminho: Path) -> list[gp.Beat]:
    song = gp.parse(str(caminho))
    return [b for m in song.tracks[0].measures for b in m.voices[0].beats if b.notes]


@requer_soundfont
def test_so_o_rotulo_do_perfil_entra_e_o_acorde_sai_num_beat(tmp_path: Path) -> None:
    """Os outros rótulos de guitarra não se fundem na parte: viram erro de rótulo."""
    notas = [
        *_acorde(MI_MAIOR, 0.0),
        _nota(45, 0.7),
        _nota(50, 1.4, "distorted_electric_guitar"),
        _nota(55, 2.0, "acoustic_guitar"),
        _nota(60, 2.5, "acoustic_piano"),
        _nota(36, 3.0, "electric_bass"),
    ]

    r = _rodar(tmp_path, notas)

    assert [len(b.notes) for b in _beats(r.artefatos["gp5"])] == [6, 1]
    assert r.notas == 7
    assert r.erro_de_rotulo == {"distorted_electric_guitar": 1, "acoustic_guitar": 1}
    assert r.contaminacao == {"acoustic_piano": 1, "electric_bass": 1}
    assert r.acordes_impossiveis == []
    assert r.instrumento == "guitarra-limpa"


@requer_soundfont
def test_dois_grupos_no_mesmo_tique_viram_acorde_impossivel_e_nao_derrubam(
    tmp_path: Path,
) -> None:
    """A 60 ms, são dois acordes para o posicionador e o mesmo tique para a grade.

    Nas duas, E2 e F2 só existem na corda mais grave: sem unir pelo tique, as duas
    notas saíam posicionadas e o GP5 recusava a corda repetida depois dos minutos de
    CPU (ADR-014).
    """
    notas = [_nota(40, 0.0), _nota(41, 0.06), _nota(45, 0.7)]

    r = _rodar(tmp_path, notas)

    (impossivel,) = r.acordes_impossiveis
    assert sorted(n.pitch for n in impossivel.notas) == [40, 41]
    assert r.notas == 1
    assert [len(b.notes) for b in _beats(r.artefatos["gp5"])] == [1]


@requer_soundfont
def test_a_guitarra_nao_sobrescreve_nada_do_baixo(tmp_path: Path) -> None:
    """Mesma música, mesma pasta: o baixo segue com o nome de sempre (M5)."""
    notas = [_nota(36, 0.0, "electric_bass"), _nota(38, 0.7, "electric_bass")]
    notas += [*_acorde(MI_MAIOR, 0.0), _nota(45, 0.7)]
    baixo = _rodar(tmp_path, notas, instrumento="baixo")
    antes = {k: c.read_bytes() for k, c in baixo.artefatos.items()}
    cache_baixo = tmp_path / "cache" / baixo.asset.source_id / "notas.jsonl"
    notas_do_baixo = cache_baixo.read_bytes()

    guitarra = _rodar(tmp_path, notas)

    assert {k: c.read_bytes() for k, c in baixo.artefatos.items()} == antes
    assert cache_baixo.read_bytes() == notas_do_baixo
    titulo = guitarra.asset.title
    assert guitarra.artefatos["gp5"].name == f"{titulo}.guitarra-limpa.gp5"
    assert guitarra.artefatos["musicxml"].name == f"{titulo}.guitarra-limpa.musicxml"
    cache = tmp_path / "cache" / guitarra.asset.source_id / "notas.guitarra-limpa.jsonl"
    assert len(ler(cache)) == 7


@requer_soundfont
def test_stem_e_playback_da_guitarra_saem_como_outros(tmp_path: Path) -> None:
    r = _rodar(tmp_path, [*_acorde(MI_MAIOR, 0.0)])

    titulo = r.asset.title
    assert r.artefatos["outros"].name == f"{titulo}.outros.wav"
    assert r.artefatos["sem-outros"].name == f"{titulo}.sem-outros.wav"
    stems = tmp_path / "cache" / "stems" / r.asset.source_id
    assert r.artefatos["outros"].read_bytes() == (stems / "other.wav").read_bytes()
    assert r.artefatos["sem-outros"].read_bytes() == (stems / "no_other.wav").read_bytes()
    assert "baixo" not in r.artefatos
    assert r.artefatos["aural"].name == f"{titulo}.guitarra-limpa.aural.wav"


@requer_soundfont
def test_a_faixa_leva_o_programa_do_perfil(tmp_path: Path) -> None:
    distorcida = _acorde(MI_MAIOR, 0.0, "distorted_electric_guitar")

    r = _rodar(tmp_path, distorcida, instrumento="guitarra-distorcida")

    faixa = gp.parse(str(r.artefatos["gp5"])).tracks[0]
    assert faixa.channel.instrument == 30
    assert len(faixa.strings) == 6


@requer_soundfont
def test_sem_nota_do_perfil_e_erro_que_diz_os_rotulos(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="distorted_electric_guitar"):
        _rodar(tmp_path, [_nota(50, 0.0, "distorted_electric_guitar")])


@requer_soundfont
def test_acordes_nao_enganam_o_desdobramento_do_andamento(tmp_path: Path) -> None:
    """Seis notas no mesmo tique não são ataques colapsados pela grade (ADR-024).

    Contadas uma a uma, cada acorde seria cinco colisões e o andamento estimado
    dobraria à toa; contado pelo primeiro ataque, os acordes a 0,5 s não colidem.
    """
    notas = [n for i in range(10) for n in _acorde(MI_MAIOR, i * 0.5)]

    r = _rodar(tmp_path, notas, bpm=None)

    assert r.andamento is not None
    assert not r.desdobrado


@pytest.mark.parametrize("instrumento", ["piano-acustico", "ukulele"])
def test_perfil_sem_exportador_e_recusado_antes_do_download(
    tmp_path: Path, instrumento: str
) -> None:
    with pytest.raises(ValueError, match=instrumento):
        transcrever(
            "x.mp3",
            tmp_path,
            bpm=90,
            instrumento=instrumento,
            source=FonteQueNaoPodeSerChamada(),
        )


def test_o_duble_devolve_stems_distintos(tmp_path: Path) -> None:
    """Guarda do próprio dublê: bytes iguais esconderiam fiação trocada."""
    wav = tmp_path / "x.wav"
    sf.write(str(wav), np.ones(4410) * 0.5, 44100)

    stems = SeparadorFalso().separate(wav, tmp_path / "s")

    assert len({p.read_bytes() for p in stems.values()}) == 4


#: Nota F1 medido em 2026-09-25 pelo pipeline inteiro (`small`, `htdemucs_ft`): o mesmo
#: 0,990 do stem cru no `test_multi_instrumento.py` — posicionar e exportar não perderam
#: nota. A folga é a da separação, que não se repete entre rodadas (ADR-044).
F1_MEDIDO_MIX = 0.990
#: A mesma do `test_multi_instrumento.py`: um evento de folga em 34 (emenda do ADR-044).
FOLGA_DEMUCS = 0.03


@pytest.mark.slow
@requer_soundfont
def test_caminho_completo_de_guitarra_com_demucs_e_muscriptor_reais(tmp_path: Path) -> None:
    """A fixture `-mix` (guitarra limpa com baixo e piano) pelo pipeline inteiro.

    O que se afirma é a estrutura: acordes de verdade no GP5, stem `other` distinto
    do mix, nada do baixo gerado. O F1 sai impresso ao lado do piso.
    """
    wav = renderizar_multi("guitarra-limpa-mix", tmp_path)

    r = transcrever(
        str(wav),
        tmp_path / "out",
        bpm=BPM_FIXTURE,
        cache_dir=tmp_path / "cache",
        instrumento="guitarra-limpa",
    )

    ref = referencia(FIXTURES_MULTI["guitarra-limpa-mix"])
    guardadas = ler(tmp_path / "cache" / r.asset.source_id / "notas.guitarra-limpa.jsonl")
    s = avaliar_polifonico(ref.notas, guardadas)
    piso = F1_MEDIDO_MIX - FOLGA_DEMUCS
    tamanhos = [len(b.notes) for b in _beats(r.artefatos["gp5"])]
    print(
        f"\nMEDIDO pipeline guitarra-limpa-mix: nota F1 {s.nota.f1:.3f} "
        f"ataque F1 {s.ataque.f1:.3f} ref={s.n_ref} est={s.n_est} notas={r.notas} "
        f"erro_de_rotulo={r.erro_de_rotulo} contaminacao={r.contaminacao} "
        f"impossiveis={len(r.acordes_impossiveis)} beats={tamanhos} "
        f"piso={piso:.3f} margem={s.nota.f1 - piso:+.3f}"
    )

    assert s.nota.f1 >= piso, f"regrediu: {s.nota.f1} < {piso}"

    assert max(tamanhos) >= 5, "nenhum acorde grande chegou ao GP5 num beat só"
    assert {"gp5", "musicxml", "mix", "outros", "sem-outros"} <= set(r.artefatos)
    assert not {"baixo", "sem-baixo"} & set(r.artefatos)
    bytes_de = {k: r.artefatos[k].read_bytes() for k in ("mix", "outros", "sem-outros")}
    assert len({*bytes_de.values()}) == 3, "mix, outros e sem-outros têm que diferir"
