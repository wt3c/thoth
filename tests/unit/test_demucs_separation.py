"""Separador do Demucs: montagem do comando, descoberta do stem e cache."""

from __future__ import annotations

import wave
from pathlib import Path

import pytest

from tests.sintetico import SOUNDFONT, renderizar
from thoth.adapters.separation import DemucsSeparator, localizar_stems
from thoth.processos import ErroDeProcesso


def _toca(caminho: Path) -> Path:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_bytes(b"")
    return caminho


def test_comando_carrega_numpy_antigo() -> None:
    """O demucs declara mal as dependências e quebra com numpy 2 (ADR-010)."""
    comando = DemucsSeparator()._comando(Path("a.wav"), Path("/saida"))
    assert comando[:3] == ["uvx", "--with", "numpy<2"]


def test_comando_prega_a_versao_do_demucs() -> None:
    """Sem versão, o `uvx` pega a mais nova do dia e os stems mudam calados.

    Mesma regra do `muscriptor@0.3.0`: as medições do ADR-010 e o cache por
    modelo (ADR-026) só valem para o separador que as produziu. 4.1.0 é a única
    versão que esta estação já rodou.
    """
    comando = DemucsSeparator()._comando(Path("a.wav"), Path("/saida"))
    assert comando[3] == "demucs@4.1.0"


def test_a_versao_pregada_e_a_que_vai_no_comando() -> None:
    """A versão é um campo só: o comando e a chave do cache leem o mesmo valor."""
    comando = DemucsSeparator(versao="4.0.1")._comando(Path("a.wav"), Path("/saida"))
    assert comando[3] == "demucs@4.0.1"


def test_comando_fixa_modelo_dispositivo_e_dois_stems() -> None:
    comando = DemucsSeparator()._comando(Path("a.wav"), Path("/saida"))
    assert comando[comando.index("-n") + 1] == "htdemucs_ft"
    assert comando[comando.index("-d") + 1] == "cpu"  # a estação não tem CUDA
    assert comando[comando.index("--two-stems") + 1] == "bass"
    assert comando[comando.index("-o") + 1] == "/saida"
    assert comando[-1] == "a.wav"


def test_localizar_encontra_stem_em_subdiretorio_com_hash(tmp_path: Path) -> None:
    """O demucs aninha por modelo e nome do arquivo — que aqui é um SHA-256."""
    ninho = tmp_path / "htdemucs_ft" / ("a" * 64)
    esperado = _toca(ninho / "bass.wav")
    _toca(ninho / "no_bass.wav")

    assert localizar_stems(tmp_path)["bass"] == esperado


def test_localizar_reclama_quando_nao_ha_stem(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match=r"bass\.wav"):
        localizar_stems(tmp_path)


def test_separar_reaproveita_stem_existente(tmp_path: Path) -> None:
    """Separar custa ~88s por 30s de áudio: repetir à toa é caro demais."""
    _toca(tmp_path / "htdemucs_ft" / "4.1.0" / "x" / "bass.wav")
    # `false` falha na hora: se o cache não pegar, o subprocesso denuncia.
    separador = DemucsSeparator(binary=("false",))

    assert separador.separate(Path("a.wav"), tmp_path)["bass"].name == "bass.wav"


def test_separar_propaga_falha_do_demucs(tmp_path: Path) -> None:
    with pytest.raises(ErroDeProcesso):
        DemucsSeparator(binary=("false",)).separate(Path("a.wav"), tmp_path)


@pytest.mark.slow
@pytest.mark.skipif(not SOUNDFONT.exists(), reason="soundfont ausente")
def test_stem_real_sai_em_pcm_16_bits(tmp_path: Path) -> None:
    """O `octave_check` lê com `wave` e divide por 32768 — só serve PCM 16."""
    wav, _ = renderizar("escala", tmp_path)

    stems = DemucsSeparator().separate(wav, tmp_path / "stems")

    assert stems["bass"].exists()
    with wave.open(str(stems["bass"])) as f:
        assert f.getsampwidth() == 2
        assert f.getframerate() == 44100


def test_stem_de_outro_modelo_nao_conta_como_cache(tmp_path: Path) -> None:
    """O modelo está no caminho e a varredura o ignorava: `mdx_extra` passava por
    `htdemucs_ft`, e a diferença entre os dois é justamente o que o ADR-010 mede."""
    _toca(tmp_path / "mdx_extra" / "x" / "bass.wav")
    # `true` não separa nada: se o stem alheio fosse aceito, ninguém notaria.
    with pytest.raises(FileNotFoundError, match=r"bass\.wav"):
        DemucsSeparator(binary=("true",)).separate(Path("a.wav"), tmp_path)


def test_cada_modelo_tem_o_proprio_cache(tmp_path: Path) -> None:
    """Trocar de modelo não pode exigir apagar o cache na mão."""
    _toca(tmp_path / "htdemucs_ft" / "4.1.0" / "x" / "bass.wav")
    _toca(tmp_path / "mdx_extra" / "4.1.0" / "x" / "bass.wav")

    for modelo in ("htdemucs_ft", "mdx_extra"):
        achado = DemucsSeparator(model=modelo, binary=("false",)).separate(Path("a.wav"), tmp_path)
        assert achado["bass"].parent.parent.parent.name == modelo


def test_stem_sem_versao_no_caminho_nao_conta_como_cache(tmp_path: Path) -> None:
    """Antes de 2026-09-24 o cache era `<out>/<modelo>/<nome>/`, sem a versão: não há
    como saber de que demucs aquele stem veio, então ele não é cache de ninguém."""
    _toca(tmp_path / "htdemucs_ft" / "x" / "bass.wav")
    # `true` não separa nada: se o stem sem versão fosse aceito, ninguém notaria.
    with pytest.raises(FileNotFoundError, match=r"bass\.wav"):
        DemucsSeparator(binary=("true",)).separate(Path("a.wav"), tmp_path)


def test_stem_de_outra_versao_nao_conta_como_cache(tmp_path: Path) -> None:
    """Mudar o pin não pode reaproveitar calado o stem da versão anterior."""
    _toca(tmp_path / "htdemucs_ft" / "4.0.1" / "x" / "bass.wav")
    with pytest.raises(FileNotFoundError, match=r"bass\.wav"):
        DemucsSeparator(binary=("true",)).separate(Path("a.wav"), tmp_path)


def test_cada_versao_tem_o_proprio_cache(tmp_path: Path) -> None:
    """Trocar o pin e voltar não exige apagar nem refazer nada."""
    for versao in ("4.0.1", "4.1.0"):
        _toca(tmp_path / "htdemucs_ft" / versao / "x" / "bass.wav")

    for versao in ("4.0.1", "4.1.0"):
        achado = DemucsSeparator(versao=versao, binary=("false",)).separate(
            Path("a.wav"), tmp_path
        )
        assert achado["bass"].parent.parent.name == versao


def test_demucs_morto_no_meio_nao_deixa_stem_pela_metade(tmp_path: Path) -> None:
    """O demucs escreve `no_bass.wav` antes de `bass.wav`: morrer entre os dois
    deixava meio stem no cache, e `--two-stems` nunca mais seria refeito inteiro."""
    # `$8` é o `-o` do comando montado por `_comando`; `$0` é o nome do programa.
    finge = ("sh", "-c", 'mkdir -p "$8/htdemucs_ft/x" && : > "$8/htdemucs_ft/x/no_bass.wav"'
             " && exit 3", "demucs")

    with pytest.raises(ErroDeProcesso):
        DemucsSeparator(binary=finge).separate(Path("a.wav"), tmp_path)

    assert list(tmp_path.rglob("*.wav")) == []


def test_o_stem_fica_no_lugar_documentado(tmp_path: Path) -> None:
    """A promoção do diretório provisório não pode aninhar o modelo duas vezes:
    `<out>/<modelo>/<versão>/<nome>/bass.wav` é o caminho que o docstring promete."""
    # Imita o demucs: escreve sob `<-o>/<modelo>/<nome do arquivo>/`. `$8` é o `-o`.
    finge = ("sh", "-c", 'mkdir -p "$8/htdemucs_ft/a" && : > "$8/htdemucs_ft/a/bass.wav"'
             ' && : > "$8/htdemucs_ft/a/no_bass.wav"', "demucs")

    achado = DemucsSeparator(binary=finge).separate(Path("a.wav"), tmp_path)

    assert achado["bass"] == tmp_path / "htdemucs_ft" / "4.1.0" / "a" / "bass.wav"
    assert sorted(achado) == ["bass", "no_bass"]
