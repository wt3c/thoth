"""Cache em disco da transcrição bruta (ADR-052).

O transcritor de verdade custa minutos; aqui ele é um contador, porque o que está
em teste é o cache: quando ele serve, quando ele recusa e o que ele devolve. O
MuScriptor real passando pelo cache está em `tests/integration`, marcado `slow`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from thoth.adapters.transcription.muscriptor import MuscriptorTranscriber
from thoth.domain.models import EventoPercussivo, NoteEvent, Transcricao
from thoth.services.cache_transcricao import TranscritorEmCache, em_cache, identidade

TRANSCRICAO = Transcricao(
    notas=(
        NoteEvent(40, 0.125, 0.5, "electric_bass"),
        NoteEvent(52, 1.0 / 3, 0.9, "clean_electric_guitar"),
    ),
    ataques=(EventoPercussivo(0.25, 36), EventoPercussivo(0.75, 38)),
)


@dataclass(slots=True)
class TranscritorQueConta:
    chamadas: int = 0

    def transcribe(self, audio: Path) -> Transcricao:
        self.chamadas += 1
        return TRANSCRICAO


def _stem(pasta: Path, conteudo: bytes = b"RIFF stem") -> Path:
    pasta.mkdir(parents=True, exist_ok=True)
    stem = pasta / "bass.wav"
    stem.write_bytes(conteudo)
    return stem


def test_a_segunda_vez_nao_transcreve_e_devolve_o_mesmo(tmp_path: Path) -> None:
    base = TranscritorQueConta()
    cache = TranscritorEmCache(base, "modelo-a", tmp_path / "cache")
    stem = _stem(tmp_path / "s")

    primeira = cache.transcribe(stem)
    segunda = cache.transcribe(stem)

    assert base.chamadas == 1
    assert primeira == segunda == TRANSCRICAO


def test_o_cache_sobrevive_ao_processo(tmp_path: Path) -> None:
    """O ponto do cache em disco: outra instância, outra corrida, mesma resposta."""
    stem = _stem(tmp_path / "s")
    TranscritorEmCache(TranscritorQueConta(), "modelo-a", tmp_path / "cache").transcribe(stem)

    base = TranscritorQueConta()
    resultado = TranscritorEmCache(base, "modelo-a", tmp_path / "cache").transcribe(stem)

    assert base.chamadas == 0
    assert resultado == TRANSCRICAO


def test_a_chave_e_o_conteudo_do_stem_nao_o_caminho(tmp_path: Path) -> None:
    base = TranscritorQueConta()
    cache = TranscritorEmCache(base, "modelo-a", tmp_path / "cache")

    cache.transcribe(_stem(tmp_path / "um"))
    cache.transcribe(_stem(tmp_path / "outro"))
    cache.transcribe(_stem(tmp_path / "diferente", b"RIFF outro stem"))

    assert base.chamadas == 2


def test_outra_identidade_nao_aproveita_o_resultado(tmp_path: Path) -> None:
    stem = _stem(tmp_path / "s")
    TranscritorEmCache(TranscritorQueConta(), "modelo-a", tmp_path / "cache").transcribe(stem)

    base = TranscritorQueConta()
    TranscritorEmCache(base, "modelo-b", tmp_path / "cache").transcribe(stem)

    assert base.chamadas == 1


def test_transcricao_que_falha_nao_deixa_nada_no_cache(tmp_path: Path) -> None:
    @dataclass(slots=True)
    class Quebrado:
        def transcribe(self, audio: Path) -> Transcricao:
            raise RuntimeError("muscriptor morreu")

    with pytest.raises(RuntimeError):
        TranscritorEmCache(Quebrado(), "modelo-a", tmp_path / "cache").transcribe(
            _stem(tmp_path / "s")
        )

    assert not any((tmp_path / "cache").rglob("*.json"))


def test_a_identidade_do_muscriptor_muda_com_o_que_decide_a_saida() -> None:
    padrao = identidade(MuscriptorTranscriber())

    assert padrao is not None
    assert identidade(MuscriptorTranscriber()) == padrao
    assert identidade(MuscriptorTranscriber(silencio_inicial_s=0.1)) != padrao
    assert identidade(MuscriptorTranscriber(model="medium")) != padrao
    assert identidade(MuscriptorTranscriber(binary=("muscriptor",))) != padrao


def test_a_identidade_inclui_os_pesos_travados(tmp_path: Path) -> None:
    """Sem o lock não há como dizer que pesos produziram o resultado: sem cache."""
    sem_lock = identidade(MuscriptorTranscriber(), lock=tmp_path / "nao-existe.toml")
    sem_o_modelo = identidade(MuscriptorTranscriber(model="large"))

    assert sem_lock is None
    assert sem_o_modelo is None


def test_em_cache_embrulha_so_quem_tem_identidade(tmp_path: Path) -> None:
    embrulhado = em_cache(MuscriptorTranscriber(), tmp_path)
    sem_identidade = MuscriptorTranscriber(model="large")

    assert isinstance(embrulhado, TranscritorEmCache)
    assert em_cache(sem_identidade, tmp_path) is sem_identidade
