"""A CLI precisa expor `fetch` como subcomando — o Typer colapsa quando só há um."""

from __future__ import annotations

import subprocess
from pathlib import Path

from typer.testing import CliRunner

from thoth.cli import app

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
