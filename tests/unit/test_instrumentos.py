"""Tipos de domínio e perfis da expansão multi-instrumento (ADR-044).

Nenhum destes toca o caminho do baixo: os ports só mudam para o instrumento que a
medição aprovar. Aqui se garante que bateria não finge altura nem duração e que
nenhum perfil mistura rótulos do MuScriptor por conveniência.
"""

from __future__ import annotations

import pytest

from thoth.domain.instrumentos import PERFIS, TUNING_GUITARRA_6
from thoth.domain.models import EventoPercussivo, NoteEvent, Transcricao
from thoth.services.pipeline import ROTULOS_DE_BAIXO


def _nota(pitch: int, onset: float, instrument: str = "electric_bass") -> NoteEvent:
    return NoteEvent(pitch=pitch, onset_s=onset, offset_s=onset + 0.2, instrument=instrument)


# --- EventoPercussivo --------------------------------------------------------------


def test_ataque_de_bateria_nao_tem_altura_nem_duracao() -> None:
    ataque = EventoPercussivo(instante_s=1.5, peca_gm=36)

    assert ataque.rotulo == "drums"
    assert not hasattr(ataque, "pitch")
    assert not hasattr(ataque, "offset_s")


def test_ataques_iguais_sao_iguais() -> None:
    assert EventoPercussivo(1.0, 38) == EventoPercussivo(1.0, 38)
    assert EventoPercussivo(1.0, 38) != EventoPercussivo(1.0, 42)


@pytest.mark.parametrize("instante, peca", [(-0.1, 36), (1.0, -1), (1.0, 128)])
def test_ataque_invalido_e_recusado(instante: float, peca: int) -> None:
    with pytest.raises(ValueError):
        EventoPercussivo(instante_s=instante, peca_gm=peca)


# --- Transcricao -------------------------------------------------------------------


def test_drums_vira_ataque_na_borda_e_o_resto_continua_nota() -> None:
    """O MuScriptor põe a peça GM no campo `pitch`; o domínio não precisa saber disso."""
    bruto = [
        _nota(36, 0.5, "drums"),
        _nota(40, 0.25),
        _nota(42, 0.25, "drums"),
        _nota(60, 0.1, "acoustic_piano"),
    ]

    t = Transcricao.do_muscriptor(bruto)

    assert t.ataques == (EventoPercussivo(0.25, 42), EventoPercussivo(0.5, 36))
    assert [(n.pitch, n.instrument) for n in t.notas] == [
        (60, "acoustic_piano"),
        (40, "electric_bass"),
    ]


def test_transcricao_ordena_por_instante_e_depois_por_altura_ou_peca() -> None:
    t = Transcricao(
        notas=(_nota(45, 1.0), _nota(40, 1.0), _nota(50, 0.5)),
        ataques=(EventoPercussivo(1.0, 42), EventoPercussivo(1.0, 36), EventoPercussivo(0.2, 38)),
    )

    assert [(n.onset_s, n.pitch) for n in t.notas] == [(0.5, 50), (1.0, 40), (1.0, 45)]
    assert [(a.instante_s, a.peca_gm) for a in t.ataques] == [(0.2, 38), (1.0, 36), (1.0, 42)]


def test_transcricao_recusa_nota_com_rotulo_de_bateria() -> None:
    """Ataque de bateria dentro de `notas` voltaria a fingir altura."""
    with pytest.raises(ValueError, match="drums"):
        Transcricao(notas=(_nota(36, 0.0, "drums"),), ataques=())


def test_transcricoes_iguais_sao_iguais_independente_da_ordem_de_entrada() -> None:
    a = Transcricao(notas=(_nota(40, 1.0), _nota(41, 0.0)), ataques=())
    b = Transcricao(notas=(_nota(41, 0.0), _nota(40, 1.0)), ataques=())

    assert a == b


# --- Perfis ------------------------------------------------------------------------

#: Os seis rótulos do escopo, conferidos em `muscriptor list-instruments` (0.3.0).
ROTULOS_DO_ESCOPO = {
    "acoustic_piano",
    "electric_piano",
    "acoustic_guitar",
    "clean_electric_guitar",
    "distorted_electric_guitar",
    "drums",
}


def test_perfil_do_baixo_usa_os_mesmos_rotulos_do_pipeline() -> None:
    """Duas fontes para o mesmo conjunto divergiriam em silêncio."""
    assert PERFIS["baixo"].rotulos == ROTULOS_DE_BAIXO
    assert PERFIS["baixo"].stem == "bass"


def test_cada_rotulo_novo_pertence_a_um_perfil_so() -> None:
    donos: dict[str, list[str]] = {}
    for nome, perfil in PERFIS.items():
        for rotulo in perfil.rotulos:
            donos.setdefault(rotulo, []).append(nome)

    assert {r for r in donos if r in ROTULOS_DO_ESCOPO} == ROTULOS_DO_ESCOPO
    assert all(len(nomes) == 1 for nomes in donos.values()), donos


def test_guitarras_sao_perfis_separados() -> None:
    """Somar os três rótulos faria duas guitarras virarem um acorde impossível."""
    guitarras = {n: p for n, p in PERFIS.items() if p.familia == "guitarra"}

    assert {frozenset(p.rotulos) for p in guitarras.values()} == {
        frozenset({"acoustic_guitar"}),
        frozenset({"clean_electric_guitar"}),
        frozenset({"distorted_electric_guitar"}),
    }
    assert all(p.afinacao == TUNING_GUITARRA_6 for p in guitarras.values())


@pytest.mark.parametrize(
    "nome, stem, afinado",
    [
        ("bateria", "drums", False),
        ("piano-acustico", "other", False),
        ("piano-eletrico", "other", False),
        ("guitarra-limpa", "other", True),
        ("baixo", "bass", True),
    ],
)
def test_perfil_declara_stem_e_se_tem_afinacao(nome: str, stem: str, afinado: bool) -> None:
    perfil = PERFIS[nome]

    assert perfil.stem == stem
    assert (perfil.afinacao is not None) == afinado
    assert 0 <= perfil.programa_gm <= 127
