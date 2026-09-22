"""Separação de fontes pelo Demucs, atrás do `Protocol Separator`.

Etapa fixa do pipeline desde o ADR-010: o MuScriptor rotula o teclado
corretamente e ainda assim vaza parte dele para dentro do canal do baixo. Só
remover o instrumento do áudio resolve — nenhuma flag do transcritor resolve.

Por subprocesso via `uvx`, como o transcritor, e pelo mesmo motivo: o demucs
arrasta torch. O `--with "numpy<2"` não é preferência — o demucs declara mal as
dependências e quebra com `ModuleNotFoundError: numpy` sem ele.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from thoth.domain.ports import Separator


def localizar_stems(out_dir: Path) -> dict[str, Path]:
    """Acha os stems por varredura, não reconstruindo o caminho.

    O demucs aninha a saída em `<out>/<modelo>/<nome do arquivo>/`, e o nome do
    arquivo aqui é o `source_id` — um SHA-256. Procurar é mais barato e mais
    honesto do que remontar essa convenção.
    """
    encontrados = {
        caminho.stem: caminho
        for nome in ("bass.wav", "no_bass.wav")
        for caminho in out_dir.rglob(nome)
    }
    if "bass" not in encontrados:
        raise FileNotFoundError(f"nenhum bass.wav sob {out_dir}")
    return encontrados


@dataclass(frozen=True, slots=True)
class DemucsSeparator:
    """Mix → stem de baixo."""

    model: str = "htdemucs_ft"
    device: str = "cpu"  # mesma razão do transcritor: a estação não tem CUDA
    binary: tuple[str, ...] = field(default=("uvx", "--with", "numpy<2", "demucs"))

    def _comando(self, audio: Path, out_dir: Path) -> list[str]:
        return [
            *self.binary,
            "-n", self.model,
            "-d", self.device,
            "--two-stems", "bass",
            "-o", str(out_dir),
            str(audio),
        ]

    def separate(self, audio: Path, out_dir: Path) -> dict[str, Path]:
        """Separa, ou devolve o que já está separado — a conta é de ~88s por 30s."""
        out_dir.mkdir(parents=True, exist_ok=True)
        try:
            return localizar_stems(out_dir)
        except FileNotFoundError:
            subprocess.run(self._comando(audio, out_dir), check=True, capture_output=True)
        return localizar_stems(out_dir)


if TYPE_CHECKING:  # pragma: no cover — trava a assinatura contra o Protocol
    _: Separator = DemucsSeparator()
