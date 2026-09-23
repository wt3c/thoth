"""Escrita no cache que falha pela metade não pode virar cache (ADR-026).

Contra o sistema de arquivos real: o que está em teste é `os.replace` e o que
ele garante, e um mock dele testaria a minha leitura do manual.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from thoth.arquivos import diretorio_atomico, escrita_atomica


def test_o_destino_so_aparece_no_fim(tmp_path: Path) -> None:
    destino = tmp_path / "sub" / "notas.jsonl"
    with escrita_atomica(destino) as parcial:
        parcial.write_text("metade")
        assert not destino.exists()
    assert destino.read_text() == "metade"


def test_falha_no_meio_nao_toca_no_destino(tmp_path: Path) -> None:
    """É a diferença que interessa: sem isto, o arquivo antigo some ou trunca."""
    destino = tmp_path / "notas.jsonl"
    destino.write_text("bom")

    with pytest.raises(RuntimeError), escrita_atomica(destino) as parcial:
        parcial.write_text("lixo")
        raise RuntimeError("morri no meio")

    assert destino.read_text() == "bom"


def test_falha_no_meio_nao_deixa_parcial_para_tras(tmp_path: Path) -> None:
    """Sobra de `.parcial` é o que um cache ingênuo aceitaria na próxima vez."""
    destino = tmp_path / "notas.jsonl"

    with pytest.raises(RuntimeError), escrita_atomica(destino) as parcial:
        parcial.write_text("lixo")
        raise RuntimeError("morri no meio")

    assert list(tmp_path.iterdir()) == []


def test_o_parcial_guarda_a_extensao(tmp_path: Path) -> None:
    """O ffmpeg escolhe o formato pela extensão: perdê-la troca o arquivo de tipo."""
    with escrita_atomica(tmp_path / "mix.wav") as parcial:
        assert parcial.suffix == ".wav"
        assert parcial != tmp_path / "mix.wav"
        parcial.write_bytes(b"")


def test_diretorio_so_aparece_inteiro(tmp_path: Path) -> None:
    destino = tmp_path / "htdemucs_ft"
    with diretorio_atomico(destino) as parcial:
        (parcial / "x").mkdir(parents=True)
        (parcial / "x" / "bass.wav").write_bytes(b"")
        assert not destino.exists()

    assert (destino / "x" / "bass.wav").exists()


def test_diretorio_pela_metade_nao_sobrevive(tmp_path: Path) -> None:
    destino = tmp_path / "htdemucs_ft"

    with pytest.raises(RuntimeError), diretorio_atomico(destino) as parcial:
        (parcial / "x").mkdir(parents=True)
        (parcial / "x" / "no_bass.wav").write_bytes(b"")
        raise RuntimeError("demucs morreu antes do bass")

    assert not destino.exists()
    assert list(tmp_path.iterdir()) == []


def test_diretorio_substitui_sobra_de_execucao_anterior(tmp_path: Path) -> None:
    """Demucs que morreu depois do `no_bass` deixa o diretório meio escrito."""
    destino = tmp_path / "htdemucs_ft"
    (destino / "x").mkdir(parents=True)
    (destino / "x" / "no_bass.wav").write_bytes(b"")

    with diretorio_atomico(destino) as parcial:
        (parcial / "x").mkdir(parents=True)
        (parcial / "x" / "bass.wav").write_bytes(b"")

    assert (destino / "x" / "bass.wav").exists()
    assert not (destino / "x" / "no_bass.wav").exists()
