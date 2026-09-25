"""Separação de fontes pelo Demucs, atrás do `Protocol Separator`.

Etapa fixa do pipeline desde o ADR-010: o MuScriptor rotula o teclado
corretamente e ainda assim vaza parte dele para dentro do canal do baixo. Só
remover o instrumento do áudio resolve — nenhuma flag do transcritor resolve.

Por subprocesso via `uvx`, como o transcritor, e pelo mesmo motivo: o demucs
arrasta torch. O `--with "numpy<2"` não é preferência — o demucs declara mal as
dependências e quebra com `ModuleNotFoundError: numpy` sem ele. A versão vai pregada
(`demucs@4.1.0`), como a do transcritor: sem ela o `uvx` pega a mais nova do dia e os
stems — e o cache e as medições do ADR-010 feitos sobre eles — mudam sem aviso.
Pelo mesmo motivo a versão entra na chave do cache, ao lado do modelo (emenda do
ADR-026): trocar o pin não reaproveita calado o stem da versão anterior.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from thoth.arquivos import diretorio_atomico
from thoth.domain.ports import Separator
from thoth.processos import rodar

#: O que o `htdemucs` sabe separar. Piano e guitarra saem em `other` (ADR-044).
STEMS_DO_HTDEMUCS = frozenset({"bass", "drums", "other", "vocals"})


def localizar_stems(out_dir: Path, stem: str = "bass") -> dict[str, Path]:
    """Acha os stems por varredura sob `out_dir`, não reconstruindo o caminho.

    O demucs aninha a saída em `<out>/<modelo>/<nome do arquivo>/`, e o nome do
    arquivo aqui é o `source_id` — um SHA-256. Procurar o arquivo é mais barato e
    mais honesto do que remontar essa convenção.

    **Quem chama decide o escopo.** `separate` passa `<out>/<modelo>/<versão>`,
    porque stem de outro modelo ou de outra versão não é cache deste (ADR-026): a
    diferença entre dois separadores é exatamente o que o ADR-010 mede.
    """
    encontrados = {
        caminho.stem: caminho
        for nome in (f"{stem}.wav", f"no_{stem}.wav")
        for caminho in out_dir.rglob(nome)
    }
    if stem not in encontrados:
        raise FileNotFoundError(f"nenhum {stem}.wav sob {out_dir}")
    return encontrados


@dataclass(frozen=True, slots=True)
class DemucsSeparator:
    """Mix → um stem e o resto (`--two-stems`). Baixo por padrão; o perfil escolhe outro."""

    stem: str = "bass"
    model: str = "htdemucs_ft"
    device: str = "cpu"  # mesma razão do transcritor: a estação não tem CUDA
    versao: str = "4.1.0"
    # Só para teste: troca o programa inteiro, mas a versão continua na chave do cache.
    binary: tuple[str, ...] | None = None

    def __post_init__(self) -> None:
        if self.stem not in STEMS_DO_HTDEMUCS:
            raise ValueError(
                f"stem {self.stem!r} não existe no demucs; há {sorted(STEMS_DO_HTDEMUCS)}"
            )

    def _escopo(self, out_dir: Path) -> Path:
        """Onde fica o cache deste stem. Irmãos, nunca aninhados: `diretorio_atomico`
        apaga o destino inteiro antes de promover, e levaria o stem vizinho junto.

        O baixo fica em `<modelo>/<versão>`, o caminho de antes do ADR-044, para não
        invalidar os stems já em cache; os outros ganham o nome do stem ao lado.
        """
        base = out_dir / self.model
        return base / (self.versao if self.stem == "bass" else f"{self.versao}-{self.stem}")

    def _comando(self, audio: Path, out_dir: Path) -> list[str]:
        programa = self.binary or ("uvx", "--with", "numpy<2", f"demucs@{self.versao}")
        return [
            *programa,
            "-n", self.model,
            "-d", self.device,
            "--two-stems", self.stem,
            "-o", str(out_dir),
            str(audio),
        ]

    def separate(self, audio: Path, out_dir: Path) -> dict[str, Path]:
        """Separa, ou devolve o que já está separado — a conta é de ~88s por 30s."""
        out_dir.mkdir(parents=True, exist_ok=True)
        # O cache pertence ao modelo *e* à versão que o produziram: sem a versão, um
        # stem de outro demucs passaria por este (emenda do ADR-026).
        meu = self._escopo(out_dir)
        try:
            return localizar_stems(meu, self.stem)
        except FileNotFoundError:
            pass
        # Atômico (ADR-026): o demucs escreve `no_bass.wav` antes de `bass.wav`, e
        # morrer entre os dois deixava meio stem de pé no cache.
        with diretorio_atomico(meu) as parcial:
            rodar(self._comando(audio, parcial))
            # O demucs aninha por modelo. O diretório promovido é o de dentro, para
            # que o resultado não fique em `<out>/<modelo>/<versão>/<modelo>/`.
            # Ausente quando o demucs termina sem produzir nada: quem reclama disso
            # com mensagem boa é `localizar_stems`, logo abaixo.
            produzido = parcial / self.model
            if produzido.is_dir():
                for item in produzido.iterdir():
                    item.rename(parcial / item.name)
                produzido.rmdir()
        return localizar_stems(meu, self.stem)


if TYPE_CHECKING:  # pragma: no cover — trava a assinatura contra o Protocol
    _: Separator = DemucsSeparator()
