"""Pipeline com `instrumento="bateria"` (ADR-044, M2).

Os mesmos dublês do `test_pipeline_guitarra.py`: separação e transcrição custam minutos
de CPU e têm teste próprio contra o binário real; o resto — grade, quantização dos
ataques, os dois exportadores de percussão e a cópia dos áudios — é o de verdade. O
ponta a ponta com Demucs e MuScriptor reais está marcado `slow` no fim.

A bateria não tem afinação nem tablatura: o que se afirma aqui é a faixa de percussão
nos dois formatos, os ataques que ficam fora relatados por motivo, e nada do baixo
gerado ou sobrescrito na mesma pasta.
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
from thoth.domain.instrumentos import PERFIS
from thoth.domain.models import ROTULO_BATERIA, EventoPercussivo, NoteEvent
from thoth.services.cache_notas import ler
from thoth.services.evaluation import avaliar_bateria
from thoth.services.pipeline import transcrever, transcritor_padrao

requer_soundfont = pytest.mark.skipif(not SOUNDFONT.exists(), reason="soundfont ausente")

#: Semicolcheia a 90 BPM: todo ataque dos testes cai num múltiplo dela, e a grade não
#: tem motivo para mover nenhum de tique.
SEMI = 60 / 90 / 4


@dataclass(frozen=True, slots=True)
class SeparadorFalso:
    """`drums` e `no_drums` em arquivos distintos do mix, pela razão do ADR-036."""

    def separate(self, audio: Path, out_dir: Path) -> dict[str, Path]:
        out_dir.mkdir(parents=True, exist_ok=True)
        dados, taxa = sf.read(str(audio))
        stems = {}
        for i, nome in enumerate(("drums", "no_drums"), start=1):
            stems[nome] = out_dir / f"{nome}.wav"
            sf.write(str(stems[nome]), dados * (0.3 * i), taxa)
        return stems


@dataclass(frozen=True, slots=True)
class TranscritorFalso:
    notas: tuple[NoteEvent, ...]

    def transcribe(self, audio: Path, instrument: str | None = None) -> list[NoteEvent]:
        return list(self.notas)


def _ataque(peca: int, onset: float, rotulo: str = ROTULO_BATERIA) -> NoteEvent:
    """O MuScriptor fecha a nota de bateria 10 ms depois do ataque."""
    return NoteEvent(pitch=peca, onset_s=onset, offset_s=onset + 0.01, instrument=rotulo)


def _rodar(tmp_path: Path, notas: list[NoteEvent], **kwargs: object):
    wav, _ = renderizar("escala", tmp_path)
    argumentos: dict[str, object] = {
        "bpm": 90,
        "cache_dir": tmp_path / "cache",
        "separator": SeparadorFalso(),
        "transcriber": TranscritorFalso(tuple(notas)),
        "instrumento": "bateria",
    }
    return transcrever(str(wav), tmp_path / "out", **(argumentos | kwargs))  # type: ignore[arg-type]


def _groove() -> list[NoteEvent]:
    """Bumbo e chimbal juntos, caixa, e um baixo que vazou para o stem."""
    return [
        _ataque(36, 0.0),
        _ataque(42, 0.0),
        _ataque(38, 3 * SEMI),
        _ataque(36, 6 * SEMI),
        _ataque(40, 9 * SEMI, "electric_bass"),
    ]


def _beats(caminho: Path) -> list[gp.Beat]:
    song = gp.parse(str(caminho))
    return [b for m in song.tracks[0].measures for b in m.voices[0].beats if b.notes]


@requer_soundfont
def test_os_dois_formatos_saem_como_percussao_e_sem_tablatura(tmp_path: Path) -> None:
    r = _rodar(tmp_path, _groove())

    gp5, musicxml = r.artefatos["gp5"], r.artefatos["musicxml"]
    assert gp5.name.endswith(".bateria.gp5") and musicxml.name.endswith(".bateria.musicxml")
    assert gp.parse(str(gp5)).tracks[0].isPercussionTrack
    assert [sorted(n.value for n in b.notes) for b in _beats(gp5)] == [[36, 42], [38], [36]]
    xml = musicxml.read_text()
    assert "<sign>percussion</sign>" in xml
    assert "<staff-details" not in xml, "tablatura na partitura de bateria"
    assert r.notas == 4
    assert r.instrumento == "bateria"
    assert r.contaminacao == {"electric_bass": 1}
    assert r.tonalidade is None, "bateria não tem tom"


@requer_soundfont
def test_a_bateria_nao_gera_nem_sobrescreve_nada_do_baixo(tmp_path: Path) -> None:
    r = _rodar(tmp_path, _groove())

    nomes = {c.name for c in r.artefatos.values()}
    pasta = r.artefatos["gp5"].parent
    assert not any(n.endswith((".baixo.wav", ".sem-baixo.wav")) for n in nomes)
    assert not (pasta / f"{pasta.name}.gp5").exists()
    assert r.artefatos["aural"].name.endswith(".bateria.aural.wav")


@requer_soundfont
def test_stem_e_playback_da_bateria_saem_com_o_nome_dela(tmp_path: Path) -> None:
    r = _rodar(tmp_path, _groove())

    assert r.artefatos["bateria"].name.endswith(".bateria.wav")
    assert r.artefatos["sem-bateria"].name.endswith(".sem-bateria.wav")
    assert r.artefatos["bateria"].read_bytes() == r.stem.read_bytes()
    assert r.artefatos["bateria"].read_bytes() != r.artefatos["sem-bateria"].read_bytes()


@requer_soundfont
def test_repetida_fora_do_mapa_e_alem_de_seis_sao_relatadas_sem_derrubar(
    tmp_path: Path,
) -> None:
    """Cada causa na sua coluna e no tempo do áudio; a partitura sai com o resto."""
    sete = (35, 36, 38, 42, 46, 49, 51)
    notas = [
        _ataque(36, 0.0),
        _ataque(36, 0.02),
        _ataque(81, 6 * SEMI),
        *(_ataque(p, 12 * SEMI) for p in sete),
    ]

    r = _rodar(tmp_path, notas)

    relato = {
        motivo: [(round(a.instante_s, 3), a.peca_gm) for a in ataques]
        for motivo, ataques in r.ataques_descartados.items()
    }
    assert relato == {
        "repetida no tique": [(0.02, 36)],
        "fora do mapa de percussão": [(round(6 * SEMI, 3), 81)],
        "além de seis no tique": [(round(12 * SEMI, 3), 51)],
    }
    assert [sorted(n.value for n in b.notes) for b in _beats(r.artefatos["gp5"])] == [
        [36],
        [35, 36, 38, 42, 46, 49],
    ]
    assert r.notas == 7


@requer_soundfont
def test_o_cache_guarda_os_ataques_mantidos_no_tempo_do_audio(tmp_path: Path) -> None:
    r = _rodar(tmp_path, _groove())

    guardadas = ler(tmp_path / "cache" / r.asset.source_id / "notas.bateria.jsonl")

    assert [(round(n.onset_s, 3), n.pitch, n.instrument) for n in guardadas] == [
        (0.0, 36, ROTULO_BATERIA),
        (0.0, 42, ROTULO_BATERIA),
        (round(3 * SEMI, 3), 38, ROTULO_BATERIA),
        (round(6 * SEMI, 3), 36, ROTULO_BATERIA),
    ]
    assert not (tmp_path / "cache" / r.asset.source_id / "notas.jsonl").exists()


def test_sem_ataque_de_bateria_e_erro_que_diz_os_rotulos(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="electric_bass"):
        _rodar(tmp_path, [_ataque(40, 0.0, "electric_bass")])


@requer_soundfont
def test_pecas_simultaneas_nao_enganam_o_desdobramento_do_andamento(tmp_path: Path) -> None:
    """Bumbo, caixa e prato no mesmo instante são um ataque para a grade (ADR-024)."""
    notas = [_ataque(p, i * 0.5) for i in range(10) for p in (36, 38, 49)]

    r = _rodar(tmp_path, notas, bpm=None)

    assert r.andamento is not None
    assert not r.desdobrado


def test_o_transcritor_padrao_so_poe_silencio_na_frente_da_bateria() -> None:
    """0,1 s levanta a bateria de 0,529 para 0,901 e troca o rótulo dos outros (ADR-045)."""
    assert transcritor_padrao(PERFIS["bateria"]).silencio_inicial_s == 0.1
    for nome in ("baixo", "guitarra-limpa", "guitarra-acustica"):
        assert transcritor_padrao(PERFIS[nome]).silencio_inicial_s == 0.0


def test_o_duble_devolve_stems_distintos_do_mix(tmp_path: Path) -> None:
    wav = tmp_path / "x.wav"
    sf.write(str(wav), np.ones(4410) * 0.5, 44100)

    stems = SeparadorFalso().separate(wav, tmp_path / "s")

    assert len({p.read_bytes() for p in (wav, *stems.values())}) == 3


#: F1 micro medido em 2026-09-25 no stem cru (`test_multi_instrumento.py`, `mix-stem`).
#: O pipeline mede sobre os ataques do cache, depois da grade e dos descartes.
F1_MEDIDO_MIX_STEM = 0.901
#: A mesma do `test_multi_instrumento.py`: um evento de folga (emenda do ADR-044).
FOLGA_DEMUCS = 0.03


@pytest.mark.slow
@requer_soundfont
def test_caminho_completo_de_bateria_com_demucs_e_muscriptor_reais(tmp_path: Path) -> None:
    """A fixture `bateria-mix` pelo pipeline inteiro, com o transcritor padrão.

    O que se afirma é a estrutura — faixa de percussão, stem `drums` distinto do mix,
    nada do baixo gerado. O F1 sai impresso ao lado do piso.
    """
    wav = renderizar_multi("bateria-mix", tmp_path)

    r = transcrever(
        str(wav),
        tmp_path / "out",
        bpm=BPM_FIXTURE,
        cache_dir=tmp_path / "cache",
        instrumento="bateria",
    )

    ref = referencia(FIXTURES_MULTI["bateria-mix"])
    guardadas = ler(tmp_path / "cache" / r.asset.source_id / "notas.bateria.jsonl")
    b = avaliar_bateria(ref.ataques, [EventoPercussivo(n.onset_s, n.pitch) for n in guardadas])
    piso = F1_MEDIDO_MIX_STEM - FOLGA_DEMUCS
    descartes = {m: len(a) for m, a in r.ataques_descartados.items()}
    print(
        f"\nMEDIDO pipeline bateria-mix: micro F1 {b.micro.f1:.3f} macro {b.macro_f1:.3f} "
        f"ref={b.n_ref} est={b.n_est} notas={r.notas} contaminacao={r.contaminacao} "
        f"descartes={descartes} piso={piso:.3f} margem={b.micro.f1 - piso:+.3f}"
    )

    assert b.micro.f1 >= piso, f"regrediu: {b.micro.f1} < {piso}"
    assert gp.parse(str(r.artefatos["gp5"])).tracks[0].isPercussionTrack
    assert {"gp5", "musicxml", "mix", "bateria", "sem-bateria", "aural"} <= set(r.artefatos)
    assert not {"baixo", "sem-baixo"} & set(r.artefatos)
    bytes_de = {k: r.artefatos[k].read_bytes() for k in ("mix", "bateria", "sem-bateria")}
    assert len({*bytes_de.values()}) == 3, "mix, bateria e sem-bateria têm que diferir"

