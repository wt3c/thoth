"""O comparativo lê GP5 reais sem mudar os arquivos humanos ou gerados."""

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from scripts.avaliar_corpus_ritmico import avaliar_corpus
from thoth.adapters.export.gp5 import Gp5Exporter
from thoth.domain.models import TUNING_BASS_4, NoteEvent
from thoth.services.fretboard import ViterbiFretAssigner


def _gravar(destino: Path, bpm: float) -> None:
    notas = [
        NoteEvent(p, i * 60 / bpm, (i + 0.5) * 60 / bpm, "electric_bass")
        for i, p in enumerate([36, 38, 40])
    ]
    tabs = ViterbiFretAssigner().assign(notas, TUNING_BASS_4)
    Gp5Exporter(bpm=bpm).export(tabs, destino, TUNING_BASS_4)


def test_corpus_detecta_velocidade_errada_sem_mudar_as_notas(tmp_path: Path) -> None:
    ref, gerada = tmp_path / "humana.gp5", tmp_path / "gerada.gp5"
    _gravar(ref, 96)
    _gravar(gerada, 192)
    hashes = [hashlib.sha256(p.read_bytes()).hexdigest() for p in (ref, gerada)]
    manifesto = tmp_path / "corpus.json"
    manifesto.write_text(
        json.dumps(
            {
                "casos": [
                    {
                        "nome": "Exemplo",
                        "referencia": ref.name,
                        "gerada": gerada.name,
                    }
                ]
            }
        )
    )

    resultado = avaliar_corpus(manifesto, tmp_path, tmp_path / "resultado")

    assert resultado[0]["metricas"]["velocidade_relativa"] == pytest.approx(2)
    assert resultado[0]["metricas"]["alturas_divergentes"] == 0
    assert resultado[0]["metricas"]["intervalos_corretos"] == 2
    assert resultado[0]["metricas"]["digitacoes_comparaveis"] == 3
    assert resultado[0]["boletim"] == {
        "andamento": 0,
        "figuras": 1,
        "posicao_no_pulso": 1,
        "altura": 1,
        "digitacao": 1,
    }
    assert (tmp_path / "resultado" / "metricas.json").is_file()
    assert [hashlib.sha256(p.read_bytes()).hexdigest() for p in (ref, gerada)] == hashes


def test_manifesto_vazio_nao_e_avaliacao_valida(tmp_path: Path) -> None:
    manifesto = tmp_path / "corpus.json"
    manifesto.write_text('{"casos": []}')

    with pytest.raises(ValueError, match="casos"):
        avaliar_corpus(manifesto, tmp_path, tmp_path / "resultado")


def test_arquivo_ausente_nao_e_omitido_silenciosamente(tmp_path: Path) -> None:
    manifesto = tmp_path / "corpus.json"
    manifesto.write_text(
        json.dumps(
            {
                "casos": [
                    {
                        "nome": "Ausente",
                        "referencia": "falta.gp5",
                        "gerada": "outra.gp5",
                    }
                ]
            }
        )
    )

    with pytest.raises(FileNotFoundError):
        avaliar_corpus(manifesto, tmp_path, tmp_path / "resultado")


@pytest.mark.slow
@pytest.mark.skipif(shutil.which("mscore") is None, reason="MuseScore ausente")
def test_comparativo_midi_real_pode_ser_gravado_em_json(tmp_path: Path) -> None:
    _gravar(tmp_path / "humana.gp5", 96)
    _gravar(tmp_path / "gerada.gp5", 192)
    manifesto = tmp_path / "corpus.json"
    manifesto.write_text(json.dumps({"casos": [{
        "nome": "MIDI", "referencia": "humana.gp5", "gerada": "gerada.gp5",
    }]}))

    resultados = avaliar_corpus(manifesto, tmp_path, tmp_path / "saida", reproduzir=True)

    assert "erro_reproducao" not in resultados[0]
    assert resultados[0]["reproducao"]["metricas"]["velocidade_relativa"] == pytest.approx(2)
