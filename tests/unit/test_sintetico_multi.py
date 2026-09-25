"""Gerador de fixtures da medição multi-instrumento (ADR-044).

O MIDI é a referência e o áudio é regerado a cada execução, sempre fora do
repositório. As exigências já pagas no baixo valem aqui: soundfont em vez de onda
pura, pico normalizado e pelo menos 8 s, porque com menos o MuScriptor troca o
rótulo do instrumento (ADR-008).
"""

from __future__ import annotations

import shutil
from collections import Counter
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from tests.sintetico import SOUNDFONT
from tests.sintetico_multi import FIXTURES_MULTI, referencia, renderizar_multi
from thoth.domain.instrumentos import PERFIS


def test_ha_fixture_isolada_e_em_mix_para_cada_perfil_novo() -> None:
    novos = {n for n in PERFIS if n != "baixo"}

    assert {f.perfil for f in FIXTURES_MULTI.values()} == novos
    for perfil in novos:
        assert f"{perfil}-isolada" in FIXTURES_MULTI
        assert f"{perfil}-mix" in FIXTURES_MULTI


@pytest.mark.parametrize("nome", sorted(FIXTURES_MULTI))
def test_fixture_dura_pelo_menos_8_s(nome: str) -> None:
    assert FIXTURES_MULTI[nome].midi.get_end_time() >= 8.0


@pytest.mark.parametrize("nome", sorted(FIXTURES_MULTI))
def test_mix_tem_distrator_e_isolada_nao(nome: str) -> None:
    fixture = FIXTURES_MULTI[nome]
    esperado = 3 if nome.endswith("-mix") else 1

    assert len(fixture.midi.instruments) == esperado


def test_referencia_da_bateria_so_tem_ataques() -> None:
    ref = referencia(FIXTURES_MULTI["bateria-mix"])

    assert ref.notas == ()
    assert {a.peca_gm for a in ref.ataques} >= {36, 38, 42, 45, 49}
    instantes = [a.instante_s for a in ref.ataques]
    assert len(instantes) > len(set(instantes)), "precisa de ataques simultâneos"


def test_fixture_de_tons_tem_os_seis_tons_gm_sozinhos() -> None:
    """Emenda do ADR-044: os tons saem com o número de outro tom, mas a fixture geral
    só tem três ataques deles. Cada tom aqui toca sozinho, para a troca ter dono."""
    ref = referencia(FIXTURES_MULTI["bateria-tons"])

    contagem = Counter(a.peca_gm for a in ref.ataques)
    assert set(contagem) == {41, 43, 45, 47, 48, 50}
    assert min(contagem.values()) >= 8
    instantes = [a.instante_s for a in ref.ataques]
    assert len(instantes) == len(set(instantes)), "nenhum ataque simultâneo"


def test_referencia_do_piano_so_tem_o_piano_e_cobre_a_extensao() -> None:
    ref = referencia(FIXTURES_MULTI["piano-acustico-mix"])

    assert ref.ataques == ()
    alturas = {n.pitch for n in ref.notas}
    assert {21, 108} <= alturas  # A0 e C8
    assert all(n.instrument == "acoustic_piano" for n in ref.notas)


def test_guitarra_tem_acorde_de_seis_notas_tocavel_na_afinacao_padrao() -> None:
    ref = referencia(FIXTURES_MULTI["guitarra-limpa-isolada"])
    por_instante: dict[float, list[int]] = {}
    for n in ref.notas:
        por_instante.setdefault(n.onset_s, []).append(n.pitch)

    assert max(len(a) for a in por_instante.values()) == 6
    assert min(n.pitch for n in ref.notas) >= 40  # E2, corda solta mais grave
    assert {len(a) for a in por_instante.values()} >= {1, 2, 6}


@pytest.mark.skipif(
    not SOUNDFONT.exists() or shutil.which("fluidsynth") is None,
    reason="requer fluidsynth e FluidR3_GM.sf2 instalados",
)
@pytest.mark.parametrize(
    "nome", ["bateria-mix", "piano-eletrico-isolada", "guitarra-distorcida-mix"]
)
def test_renderiza_wav_normalizado_fora_do_repositorio(nome: str, tmp_path: Path) -> None:
    wav = renderizar_multi(nome, tmp_path)

    audio, taxa = sf.read(wav)
    pico_db = 20 * float(np.log10(np.abs(audio).max()))
    print(f"{nome}: pico {pico_db:.2f} dBFS, {len(audio) / taxa:.1f} s")
    assert wav.parent == tmp_path
    assert taxa == 44100
    assert len(audio) / taxa >= 8.0
    assert -1.5 < pico_db < -0.5


@pytest.mark.parametrize("perfil", ["piano-acustico", "piano-eletrico"])
def test_fixture_de_extremos_poe_a0_e_c8_longe_das_bordas(perfil: str) -> None:
    """A fixture geral tem A0 no instante zero e C8 no fim, onde o modelo já perde
    ataques; aqui os dois tocam entre dós centrais, sozinhos e juntos."""
    ref = referencia(FIXTURES_MULTI[f"{perfil}-extremos"])

    extremos = [n for n in ref.notas if n.pitch in (21, 108)]
    assert sorted(n.pitch for n in extremos) == [21, 21, 108, 108]
    fim = max(n.onset_s for n in ref.notas)
    assert all(0 < n.onset_s < fim for n in extremos)
    assert {n.instrument for n in ref.notas} == PERFIS[perfil].rotulos
