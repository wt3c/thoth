"""Adaptadores de separação de fontes."""

from thoth.adapters.separation.demucs import (
    DemucsMultifaixaSeparator,
    DemucsSeparator,
    localizar_stems,
)

__all__ = ["DemucsMultifaixaSeparator", "DemucsSeparator", "localizar_stems"]
