"""Persistência das notas transcritas — arquivo real, nunca mock.

O ponto do cache é sobreviver ao processo: mock provaria que serializo do jeito
que imagino, que é exatamente a suposição em teste.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from thoth.domain.models import NoteEvent
from thoth.services.cache_notas import gravar, ler

NOTAS = [
    NoteEvent(pitch=28, onset_s=0.0, offset_s=0.5, instrument="electric_bass"),
    NoteEvent(pitch=35, onset_s=0.5, offset_s=1.25, instrument="acoustic_bass"),
]


def test_round_trip_preserva_as_notas(tmp_path: Path) -> None:
    alvo = gravar(NOTAS, tmp_path / "notas.jsonl")

    assert alvo.exists()
    assert ler(alvo) == NOTAS


def test_cria_o_diretorio_que_falta(tmp_path: Path) -> None:
    """O cache da fonte pode não existir quando a transcrição termina."""
    alvo = gravar(NOTAS, tmp_path / "fundo" / "do" / "poco" / "notas.jsonl")

    assert ler(alvo) == NOTAS


def test_uma_linha_por_nota(tmp_path: Path) -> None:
    """JSONL, não JSON: arquivo de 3 mil notas tem que ser legível linha a linha."""
    alvo = gravar(NOTAS, tmp_path / "notas.jsonl")

    assert len(alvo.read_text().strip().splitlines()) == len(NOTAS)


def test_arquivo_ausente_e_erro_claro(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        ler(tmp_path / "nao-existe.jsonl")


def test_falha_no_meio_da_escrita_nao_estraga_o_cache_anterior(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Disco cheio no meio do `write_text` trunca o arquivo, e truncado é o pior
    estado possível: o cache aceita, e as notas do fim somem sem aviso (ADR-026)."""
    destino = tmp_path / "notas.jsonl"
    gravar([NoteEvent(pitch=40, onset_s=0.0, offset_s=0.5, instrument="electric_bass")], destino)
    antes = destino.read_text()

    def morre_no_meio(self: Path, texto: str, *args: object, **kwargs: object) -> int:
        self.write_bytes(texto[: len(texto) // 2].encode())
        raise OSError("disco cheio")

    monkeypatch.setattr(Path, "write_text", morre_no_meio)
    with pytest.raises(OSError, match="disco cheio"):
        gravar(
            [NoteEvent(pitch=45, onset_s=1.0, offset_s=1.5, instrument="electric_bass")], destino
        )
    monkeypatch.undo()

    assert destino.read_text() == antes
    assert list(tmp_path.iterdir()) == [destino]
