"""Separação de fontes pelo Demucs, atrás do `Protocol Separator`.

Etapa fixa do pipeline desde o ADR-010: o MuScriptor rotula o teclado
corretamente e ainda assim vaza parte dele para dentro do canal do baixo. Só
remover o instrumento do áudio resolve — nenhuma flag do transcritor resolve.

Por subprocesso via `uvx`, como o transcritor, e pelo mesmo motivo: o demucs
arrasta torch. O `--with "numpy<2"` não é preferência — o demucs declara mal as
dependências e quebra com `ModuleNotFoundError: numpy` sem ele. A versão vai pregada
(`demucs@4.1.0`), como a do transcritor: sem ela o `uvx` pega a mais nova do dia e os
stems — e o cache e as medições do ADR-010 feitos sobre eles — mudam sem aviso.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from thoth.arquivos import diretorio_atomico
from thoth.domain.ports import Separator
from thoth.processos import rodar


def localizar_stems(out_dir: Path) -> dict[str, Path]:
    """Acha os stems por varredura sob `out_dir`, não reconstruindo o caminho.

    O demucs aninha a saída em `<out>/<modelo>/<nome do arquivo>/`, e o nome do
    arquivo aqui é o `source_id` — um SHA-256. Procurar o arquivo é mais barato e
    mais honesto do que remontar essa convenção.

    **Quem chama decide o escopo.** `separate` passa `<out>/<modelo>`, porque
    stem de outro modelo não é cache deste (ADR-026): a diferença entre dois
    separadores é exatamente o que o ADR-010 mede.
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
    binary: tuple[str, ...] = field(default=("uvx", "--with", "numpy<2", "demucs@4.1.0"))

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
        # O demucs já escreve sob `<out>/<modelo>/`; procurar aí em vez de em
        # `<out>` é o que faz o cache pertencer ao modelo que o produziu.
        meu = out_dir / self.model
        try:
            return localizar_stems(meu)
        except FileNotFoundError:
            pass
        # Atômico (ADR-026): o demucs escreve `no_bass.wav` antes de `bass.wav`, e
        # morrer entre os dois deixava meio stem de pé no cache.
        with diretorio_atomico(meu) as parcial:
            rodar(self._comando(audio, parcial))
            # O demucs aninha por modelo. O diretório promovido é o de dentro, para
            # que o resultado não fique em `<out>/<modelo>/<modelo>/`.
            # Ausente quando o demucs termina sem produzir nada: quem reclama disso
            # com mensagem boa é `localizar_stems`, logo abaixo.
            produzido = parcial / self.model
            if produzido.is_dir():
                for item in produzido.iterdir():
                    item.rename(parcial / item.name)
                produzido.rmdir()
        return localizar_stems(meu)


if TYPE_CHECKING:  # pragma: no cover — trava a assinatura contra o Protocol
    _: Separator = DemucsSeparator()
