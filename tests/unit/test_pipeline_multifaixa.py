"""Contrato do modo multifaixa: partitura ampla, áudio focado no baixo."""

from __future__ import annotations

import shutil
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

import guitarpro as gp
import numpy as np
import soundfile as sf

from thoth.domain.models import TUNING_BASS_5, AudioAsset, NoteEvent, Transcricao
from thoth.services.pipeline import transcrever


@dataclass(frozen=True, slots=True)
class FonteLocal:
    asset: AudioAsset

    def fetch(self, ref: str, cache_dir: Path) -> AudioAsset:
        return self.asset


@dataclass(frozen=True, slots=True)
class SeparadorDeTodasAsFamilias:
    def separate(self, audio: Path, out_dir: Path) -> dict[str, Path]:
        out_dir.mkdir(parents=True, exist_ok=True)
        caminhos: dict[str, Path] = {}
        for nome in ("bass", "other", "drums", "no_bass"):
            destino = out_dir / f"{nome}.wav"
            shutil.copy2(audio, destino)
            caminhos[nome] = destino
        return caminhos


@dataclass(frozen=True, slots=True)
class TranscritorPorStem:
    def transcribe(self, audio: Path) -> Transcricao:
        if audio.stem == "bass":
            return Transcricao.do_muscriptor([
                NoteEvent(36, 0.0, 0.45, "electric_bass"),
                NoteEvent(38, 0.5, 0.95, "electric_bass"),
            ])
        if audio.stem == "other":
            return Transcricao.do_muscriptor([
                NoteEvent(52, 0.0, 0.45, "clean_electric_guitar"),
                NoteEvent(53, 0.5, 0.95, "distorted_electric_guitar"),
                NoteEvent(55, 1.0, 1.45, "acoustic_guitar"),
            ])
        return Transcricao.do_muscriptor([
            NoteEvent(36, 0.0, 0.1, "drums"),
            NoteEvent(42, 0.5, 0.6, "drums"),
        ])


def test_todos_combina_partes_e_entrega_somente_wavs_de_baixo(tmp_path: Path) -> None:
    wav = tmp_path / "musica.wav"
    sf.write(wav, np.zeros(88_200, dtype=np.float32), 44_100)
    asset = AudioAsset(wav=wav, source_id="multifaixa", title="Música", duration_s=2.0)

    resultado = transcrever(
        str(wav),
        tmp_path / "out",
        bpm=120,
        instrumento="todos",
        tuning=TUNING_BASS_5,
        cache_dir=tmp_path / "cache",
        source=FonteLocal(asset),
        separator=SeparadorDeTodasAsFamilias(),
        transcriber=TranscritorPorStem(),
        _gerar_auralizacao=False,
    )

    musica = gp.parse(str(resultado.artefatos["gp5"]))
    xml = ET.parse(resultado.artefatos["musicxml"]).getroot()
    assert [faixa.name for faixa in musica.tracks] == [
        "Baixo",
        "Guitarra limpa",
        "Guitarra distorcida",
        "Guitarra acústica",
        "Bateria",
    ]
    assert [parte.text for parte in xml.iter("part-name")] == [
        "Baixo", "Guitarra limpa", "Guitarra distorcida", "Guitarra acústica", "Bateria"
    ]
    assert len(musica.tracks[0].strings) == 5
    assert resultado.instrumento == "todos"
    assert resultado.notas == 7
    assert {chave for chave in resultado.artefatos if chave not in {"gp5", "musicxml"}} <= {
        "mix",
        "baixo",
        "sem-baixo",
        "aural",
    }
    wavs = list(resultado.artefatos["gp5"].parent.glob("*.wav"))
    assert {caminho.name for caminho in wavs} <= {
        "Música.mix.wav",
        "Música.baixo.wav",
        "Música.sem-baixo.wav",
        "Música.aural.wav",
    }


@dataclass(frozen=True, slots=True)
class TranscritorForaDeFase:
    """Grade a 50 ms do zero; a guitarra entra antes da fase, o baixo depois dela."""

    def transcribe(self, audio: Path) -> Transcricao:
        if audio.stem == "bass":
            return Transcricao.do_muscriptor([
                NoteEvent(36, 0.55 + 0.5 * k, 0.9 + 0.5 * k, "electric_bass") for k in range(8)
            ])
        if audio.stem == "other":
            return Transcricao.do_muscriptor([
                NoteEvent(52, 0.03, 0.4, "clean_electric_guitar"),
                *(
                    NoteEvent(52, 1.05 + 0.5 * k, 1.4 + 0.5 * k, "clean_electric_guitar")
                    for k in range(7)
                ),
            ])
        return Transcricao.do_muscriptor([])


def _inicios_com_nota(faixa: gp.Track) -> set[int]:
    return {
        beat.start
        for compasso in faixa.measures
        for voz in compasso.voices
        for beat in voz.beats
        if beat.notes
    }


def test_o_mesmo_instante_do_audio_cai_no_mesmo_tique_em_toda_faixa(tmp_path: Path) -> None:
    """Cada parte recuava pela própria fase: a guitarra saía uma semicolcheia atrás."""
    wav = tmp_path / "musica.wav"
    sf.write(wav, np.zeros(88_200, dtype=np.float32), 44_100)
    asset = AudioAsset(wav=wav, source_id="fase", title="Música", duration_s=2.0)

    resultado = transcrever(
        str(wav),
        tmp_path / "out",
        bpm=120,
        instrumento="todos",
        cache_dir=tmp_path / "cache",
        source=FonteLocal(asset),
        separator=SeparadorDeTodasAsFamilias(),
        transcriber=TranscritorForaDeFase(),
        _gerar_auralizacao=False,
    )

    baixo, guitarra = gp.parse(str(resultado.artefatos["gp5"])).tracks[:2]
    assert guitarra.name == "Guitarra limpa"
    # 1,05 s … 4,05 s: sete instantes tocados pelas duas partes.
    assert len(_inicios_com_nota(baixo) & _inicios_com_nota(guitarra)) == 7


def test_o_baixo_da_multifaixa_e_o_mesmo_do_modo_baixo(tmp_path: Path) -> None:
    """A grade comum é a do baixo: acrescentar faixas não pode mover a linha dele."""
    wav = tmp_path / "musica.wav"
    sf.write(wav, np.zeros(88_200, dtype=np.float32), 44_100)
    asset = AudioAsset(wav=wav, source_id="fase", title="Música", duration_s=2.0)

    def rodar(instrumento: str) -> gp.Track:
        resultado = transcrever(
            str(wav),
            tmp_path / instrumento,
            bpm=120,
            instrumento=instrumento,
            cache_dir=tmp_path / "cache",
            source=FonteLocal(asset),
            separator=SeparadorDeTodasAsFamilias(),
            transcriber=TranscritorForaDeFase(),
            _gerar_auralizacao=False,
        )
        return gp.parse(str(resultado.artefatos["gp5"])).tracks[0]

    solo, na_multifaixa = rodar("baixo"), rodar("todos")
    assert _inicios_com_nota(na_multifaixa) == _inicios_com_nota(solo)


@dataclass(frozen=True, slots=True)
class TranscritorDeBateriaForaDoMapa:
    """A bateria tem ataques, mas nenhum que a partitura de percussão represente."""

    def transcribe(self, audio: Path) -> Transcricao:
        if audio.stem == "drums":
            return Transcricao.do_muscriptor([
                NoteEvent(90, 0.5 * k, 0.5 * k + 0.1, "drums") for k in range(4)
            ])
        return TranscritorPorStem().transcribe(audio)


def test_parte_sem_nada_exportavel_fica_ausente_em_vez_de_derrubar_a_musica(
    tmp_path: Path,
) -> None:
    wav = tmp_path / "musica.wav"
    sf.write(wav, np.zeros(88_200, dtype=np.float32), 44_100)
    asset = AudioAsset(wav=wav, source_id="vazia", title="Música", duration_s=2.0)

    resultado = transcrever(
        str(wav),
        tmp_path / "out",
        bpm=120,
        instrumento="todos",
        cache_dir=tmp_path / "cache",
        source=FonteLocal(asset),
        separator=SeparadorDeTodasAsFamilias(),
        transcriber=TranscritorDeBateriaForaDoMapa(),
        _gerar_auralizacao=False,
    )

    assert resultado.partes_ausentes == ["bateria"]
    assert "Bateria" not in [f.name for f in gp.parse(str(resultado.artefatos["gp5"])).tracks]


@dataclass(frozen=True, slots=True)
class TranscritorComDescartes:
    """Um ataque fora do mapa de percussão, que a parte relata e a multifaixa perdia."""

    def transcribe(self, audio: Path) -> Transcricao:
        if audio.stem == "drums":
            return Transcricao.do_muscriptor([
                NoteEvent(36, 0.0, 0.1, "drums"),
                NoteEvent(90, 0.5, 0.6, "drums"),
            ])
        return TranscritorPorStem().transcribe(audio)


def test_a_multifaixa_relata_o_que_cada_parte_relatou_e_conta_cada_stem_uma_vez(
    tmp_path: Path,
) -> None:
    wav = tmp_path / "musica.wav"
    sf.write(wav, np.zeros(88_200, dtype=np.float32), 44_100)
    asset = AudioAsset(wav=wav, source_id="relato", title="Música", duration_s=2.0)

    resultado = transcrever(
        str(wav),
        tmp_path / "out",
        bpm=120,
        instrumento="todos",
        cache_dir=tmp_path / "cache",
        source=FonteLocal(asset),
        separator=SeparadorDeTodasAsFamilias(),
        transcriber=TranscritorComDescartes(),
        _gerar_auralizacao=False,
    )

    # As três guitarras leem o mesmo `other`: o histograma dele entra uma vez, não três.
    assert resultado.rotulos == {
        "electric_bass": 2,
        "clean_electric_guitar": 1,
        "distorted_electric_guitar": 1,
        "acoustic_guitar": 1,
        "drums": 2,
    }
    assert {m: len(a) for m, a in resultado.ataques_descartados.items()} == {
        "fora do mapa de percussão": 1
    }
