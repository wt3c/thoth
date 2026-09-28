"""Separação vocal auditável, sem inferir notas, vozes ou letra (ADR-048)."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from thoth.adapters.ingest import resolver_fonte
from thoth.adapters.separation import DemucsSeparator
from thoth.domain.models import AudioAsset
from thoth.domain.ports import AudioSource, Separator
from thoth.services.nomes import nome_de_arquivo


@dataclass(frozen=True, slots=True)
class ResultadoVocais:
    """Áudios para estudar e auditar a separação vocal."""

    asset: AudioAsset
    stem: Path
    artefatos: dict[str, Path]


def separar(
    ref: str,
    out_dir: Path,
    *,
    cache_dir: Path = Path("cache"),
    source: AudioSource | None = None,
    separator: Separator | None = None,
) -> ResultadoVocais:
    """Entrega mix, stem vocal e playback sem vocal numa pasta da música.

    `vocals` é o nome da fonte agregada do Demucs. O resultado não afirma que ela
    contém só a voz principal nem que separa harmonias, dobragens ou técnicas.
    """
    fonte = source or resolver_fonte(ref)
    asset = fonte.fetch(ref, cache_dir)
    separador = separator or DemucsSeparator(stem="vocals")
    stems = separador.separate(asset.wav, cache_dir / "stems" / asset.source_id)
    try:
        vocal = stems["vocals"]
        sem_vocal = stems["no_vocals"]
    except KeyError as erro:
        raise FileNotFoundError(f"separação vocal incompleta: ausente {erro.args[0]!r}") from erro

    nome = nome_de_arquivo(asset)
    pasta = out_dir / nome
    pasta.mkdir(parents=True, exist_ok=True)
    origens = {
        "mix": asset.wav,
        "vocais": vocal,
        "sem-vocais": sem_vocal,
    }
    artefatos = {
        chave: Path(shutil.copy2(origem, pasta / f"{nome}.{chave}.wav"))
        for chave, origem in origens.items()
    }
    return ResultadoVocais(asset=asset, stem=artefatos["vocais"], artefatos=artefatos)
