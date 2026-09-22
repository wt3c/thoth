"""A CLI precisa expor `fetch` como subcomando — o Typer colapsa quando só há um."""

from __future__ import annotations

import subprocess
from pathlib import Path

from typer.testing import CliRunner

from thoth.cli import app
from thoth.domain.models import AudioAsset

runner = CliRunner()


def test_fetch_e_subcomando(tmp_path: Path) -> None:
    origem = tmp_path / "t.mp3"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=110:duration=1",
         "-ac", "2", "-loglevel", "error", str(origem)],
        check=True,
    )

    resultado = runner.invoke(app, ["fetch", str(origem), "--cache", str(tmp_path / "c")])

    assert resultado.exit_code == 0, resultado.output
    assert "mix.wav" in resultado.output


def test_transcribe_relata_descartes_e_avisos(tmp_path: Path, monkeypatch) -> None:
    """O relatório existe para o que o pipeline jogou fora — o silêncio é o risco."""
    from thoth.domain.models import NoteEvent
    from thoth.services import pipeline as modulo
    from thoth.services.pipeline import Resultado

    asset = AudioAsset(wav=tmp_path / "mix.wav", source_id="abc123", title="t", duration_s=1.0)
    nota = NoteEvent(pitch=43, onset_s=0.0, offset_s=0.5, instrument="electric_bass")
    monkeypatch.setattr(
        modulo, "transcrever",
        lambda *a, **k: Resultado(
            asset=asset, stem=tmp_path / "bass.wav",
            artefatos={"gp5": tmp_path / "abc123.gp5"}, notas=12,
            rotulos={"electric_bass": 13}, descartadas=[nota], fora_do_braco=[], bpm=90,
            avisos_de_oitava=[],
        ),
    )

    resultado = runner.invoke(app, ["transcribe", "x.mp3", "--out", str(tmp_path), "--bpm", "90"])

    assert resultado.exit_code == 0, resultado.output
    assert "12 notas" in resultado.output
    assert "1 descartada" in resultado.output
    assert "abc123.gp5" in resultado.output


def test_serve_monta_o_app_sem_subir_o_servidor(monkeypatch) -> None:
    """Checa a fiação até o uvicorn — subir servidor de verdade é teste de outro nível."""
    from thoth import cli

    recebido: dict[str, object] = {}
    monkeypatch.setattr(cli.uvicorn, "run", lambda app, **kw: recebido.update(kw, app=app))

    resultado = runner.invoke(app, ["serve", "--port", "9123"])

    assert resultado.exit_code == 0, resultado.output
    assert recebido["port"] == 9123
    assert recebido["app"].title == "Thoth"


def _wav(destino: Path, segundos: int = 2) -> Path:
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", f"sine=frequency=110:duration={segundos}",
         "-ac", "2", "-ar", "44100", "-loglevel", "error", str(destino)],
        check=True,
    )
    return destino


def test_auralizar_usa_as_notas_do_cache(tmp_path: Path) -> None:
    """Auralizar não pode recomeçar a transcrição: ela já foi paga uma vez."""
    from thoth.domain.models import NoteEvent
    from thoth.services.cache_notas import gravar

    origem = _wav(tmp_path / "t.wav")
    cache = tmp_path / "c"
    runner.invoke(app, ["fetch", str(origem), "--cache", str(cache)])
    fonte = next(p for p in cache.iterdir() if p.is_dir())
    gravar(
        [NoteEvent(pitch=40, onset_s=0.0, offset_s=0.8, instrument="electric_bass")],
        fonte / "notas.jsonl",
    )

    resultado = runner.invoke(
        app, ["auralizar", str(origem), "--cache", str(cache), "--out", str(tmp_path / "o")]
    )

    assert resultado.exit_code == 0, resultado.output
    assert (tmp_path / "o" / "t.aural.wav").exists()


def test_auralizar_sem_cache_orienta_a_transcrever(tmp_path: Path) -> None:
    """Erro mudo aqui pareceria bug do áudio; o recado tem que dizer o que fazer."""
    origem = _wav(tmp_path / "t.wav", segundos=1)

    resultado = runner.invoke(
        app, ["auralizar", str(origem), "--cache", str(tmp_path / "c"),
              "--out", str(tmp_path / "o")]
    )

    assert resultado.exit_code != 0
    assert "transcribe" in resultado.output
