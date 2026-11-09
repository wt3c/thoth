"""Separação de fontes pelo Demucs, atrás do `Protocol Separator`.

Etapa fixa do pipeline desde o ADR-010: o MuScriptor rotula o teclado
corretamente e ainda assim vaza parte dele para dentro do canal do baixo. Só
remover o instrumento do áudio resolve — nenhuma flag do transcritor resolve.

Por subprocesso via `uvx`, como o transcritor, e pelo mesmo motivo: o demucs
arrasta torch. O `--with "numpy<2"` não é preferência — o demucs declara mal as
dependências e quebra com `ModuleNotFoundError: numpy` sem ele. A versão vai pregada
(`demucs@4.1.0`), como a do transcritor: sem ela o `uvx` pega a mais nova do dia e os
stems — e o cache e as medições do ADR-010 feitos sobre eles — mudam sem aviso.
Pelo mesmo motivo a versão e a configuração entram na chave do cache, ao lado do
modelo (ADR-026). O separador de um stem desliga os deslocamentos aleatórios com
`--shifts 0`: a medição de 2026-10-23 reproduziu o WAV byte a byte. O escopo novo
não reaproveita stems produzidos com o deslocamento aleatório padrão.
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

#: Comando e cache leem a mesma configuração; nunca aceitar stem do default antigo.
_DESLOCAMENTOS = 0


def localizar_stems(out_dir: Path, stem: str = "bass") -> dict[str, Path]:
    """Acha os stems por varredura sob `out_dir`, não reconstruindo o caminho.

    O demucs aninha a saída em `<out>/<modelo>/<nome do arquivo>/`, e o nome do
    arquivo aqui é `mix` — o `source_id` já está em `out_dir`. Procurar o arquivo é
    mais barato e mais honesto do que remontar essa convenção.

    **Quem chama decide o escopo.** `separate` passa o modelo, a versão e a
    configuração, porque stem de outro separador não é cache deste (ADR-026): a
    diferença entre dois separadores é exatamente o que o ADR-010 mede. Quem lê o
    cache fora do pipeline (o `comparar`) usa `DemucsSeparator().escopo` pelo mesmo
    motivo.
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

    def escopo(self, out_dir: Path) -> Path:
        """Onde fica o cache deste stem. Irmãos, nunca aninhados: `diretorio_atomico`
        apaga o destino inteiro antes de promover, e levaria o stem vizinho junto.

        O baixo fica em `<modelo>/<versão>-shifts0`; os outros ganham o nome do
        stem ao lado. O cache anterior, com deslocamento aleatório, é preservado,
        mas não reutilizado (emenda de 2026-10-23 do ADR-026).
        """
        base = out_dir / self.model
        configuracao = f"{self.versao}-shifts{_DESLOCAMENTOS}"
        return base / (configuracao if self.stem == "bass" else f"{configuracao}-{self.stem}")

    def _comando(self, audio: Path, out_dir: Path) -> list[str]:
        programa = self.binary or ("uvx", "--with", "numpy<2", f"demucs@{self.versao}")
        return [
            *programa,
            "-n", self.model,
            "-d", self.device,
            "--two-stems", self.stem,
            "-o", str(out_dir),
            "--shifts", str(_DESLOCAMENTOS),
            str(audio),
        ]

    def separate(self, audio: Path, out_dir: Path) -> dict[str, Path]:
        """Separa, ou devolve o que já está separado — a conta é de ~88s por 30s."""
        out_dir.mkdir(parents=True, exist_ok=True)
        # O cache pertence ao modelo, à versão e à configuração que o produziram
        # (ADR-026): o default aleatório anterior não é este separador.
        meu = self.escopo(out_dir)
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


@dataclass(frozen=True, slots=True)
class DemucsMultifaixaSeparator:
    """Mix → todos os stems numa execução, para a partitura multifaixa."""

    model: str = "htdemucs_ft"
    device: str = "cpu"
    versao: str = "4.1.0"
    binary: tuple[str, ...] | None = None

    def _escopo(self, out_dir: Path) -> Path:
        return out_dir / self.model / f"{self.versao}-multifaixa"

    def _comando(self, audio: Path, out_dir: Path) -> list[str]:
        programa = self.binary or ("uvx", "--with", "numpy<2", f"demucs@{self.versao}")
        return [
            *programa,
            "-n", self.model,
            "-d", self.device,
            "-o", str(out_dir),
            str(audio),
        ]

    def _localizar(self, escopo: Path) -> dict[str, Path]:
        encontrados = {
            caminho.stem: caminho
            for stem in STEMS_DO_HTDEMUCS
            for caminho in escopo.rglob(f"{stem}.wav")
        }
        ausentes = STEMS_DO_HTDEMUCS.difference(encontrados)
        if ausentes:
            raise FileNotFoundError(f"stems ausentes sob {escopo}: {sorted(ausentes)}")
        return encontrados

    def separate(self, audio: Path, out_dir: Path) -> dict[str, Path]:
        """Separa as quatro fontes uma vez e compartilha o resultado entre perfis."""
        out_dir.mkdir(parents=True, exist_ok=True)
        meu = self._escopo(out_dir)
        try:
            return self._localizar(meu)
        except FileNotFoundError:
            pass
        with diretorio_atomico(meu) as parcial:
            rodar(self._comando(audio, parcial))
            produzido = parcial / self.model
            if produzido.is_dir():
                for item in produzido.iterdir():
                    item.rename(parcial / item.name)
                produzido.rmdir()
        return self._localizar(meu)


if TYPE_CHECKING:  # pragma: no cover — trava a assinatura contra o Protocol
    _separador: Separator = DemucsSeparator()
    _separador_multifaixa: Separator = DemucsMultifaixaSeparator()
