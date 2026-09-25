"""Trecho em que o baixo sumiu dos rótulos, mas o stem continuou tocando (emenda do ADR-008).

Em *And Plague Flowers* o MuScriptor passa a chamar o baixo de `clean_electric_guitar`
depois de 511 s, e o filtro de rótulo descartava os dois minutos finais em silêncio.
"""

from __future__ import annotations

from thoth.domain.models import NoteEvent
from thoth.services.rotulos import LACUNA_S, MINIMO_DE_NOTAS, readmitidas, trechos_sem_baixo


def _linha(inicio: float, fim: float, rotulo: str, passo: float = 0.25) -> list[NoteEvent]:
    return [NoteEvent(40, float(t), float(t) + 0.2, rotulo) for t in _ataques(inicio, fim, passo)]


def _ataques(inicio: float, fim: float, passo: float) -> list[float]:
    quantos = round((fim - inicio) / passo)
    return [inicio + i * passo for i in range(quantos)]


def test_baixo_que_vira_guitarra_e_relatado_com_os_rotulos() -> None:
    baixo = _linha(0.0, 10.0, "electric_bass")
    outras = _linha(10.0, 30.0, "clean_electric_guitar")

    trechos = trechos_sem_baixo(baixo, outras)

    assert len(trechos) == 1
    t = trechos[0]
    print(f"trecho {t.inicio_s:.2f} a {t.fim_s:.2f} s · {t.rotulos}")
    assert 10.0 < t.inicio_s <= 10.0 + LACUNA_S + 0.25
    assert t.fim_s == outras[-1].onset_s
    assert set(t.rotulos) == {"clean_electric_guitar"}


def test_mesma_nota_com_dois_rotulos_nao_e_trecho_sem_baixo() -> None:
    """Na transição os dois rótulos convivem: o baixo ainda está lá."""
    baixo = _linha(0.0, 30.0, "electric_bass")
    outras = _linha(0.0, 30.0, "clean_electric_guitar")

    assert trechos_sem_baixo(baixo, outras) == []


def test_poucas_notas_orfas_nao_viram_aviso() -> None:
    baixo = _linha(0.0, 10.0, "electric_bass")
    outras = _linha(20.0, 20.0 + (MINIMO_DE_NOTAS - 1) * 0.25, "acoustic_piano")

    assert trechos_sem_baixo(baixo, outras) == []


def test_bateria_nao_tem_altura_e_nao_conta() -> None:
    baixo = _linha(0.0, 10.0, "electric_bass")
    outras = _linha(20.0, 40.0, "drums")

    assert trechos_sem_baixo(baixo, outras) == []


def test_dois_trechos_separados_saem_separados() -> None:
    baixo = _linha(0.0, 10.0, "electric_bass") + _linha(40.0, 50.0, "electric_bass")
    outras = _linha(16.0, 34.0, "acoustic_piano") + _linha(56.0, 70.0, "acoustic_piano")

    trechos = trechos_sem_baixo(baixo, outras)

    assert [(t.inicio_s, t.fim_s) for t in trechos] == [(16.0, 33.75), (56.0, 69.75)]


def test_sem_nenhuma_nota_de_baixo_tudo_e_trecho() -> None:
    assert len(trechos_sem_baixo([], _linha(0.0, 10.0, "acoustic_piano"))) == 1


def test_readmite_so_o_que_esta_dentro_dos_trechos() -> None:
    """A transição, com os dois rótulos convivendo, é duplicata e continua fora."""
    baixo = _linha(0.0, 10.0, "electric_bass")
    outras = _linha(5.0, 30.0, "clean_electric_guitar") + _linha(20.0, 30.0, "drums")

    voltam = readmitidas(outras, trechos_sem_baixo(baixo, outras))

    print(f"{len(voltam)} de {len(outras)} readmitidas")
    assert voltam
    assert {n.instrument for n in voltam} == {"clean_electric_guitar"}
    assert min(n.onset_s for n in voltam) > baixo[-1].onset_s + LACUNA_S


def test_sem_trecho_nada_e_readmitido() -> None:
    assert readmitidas(_linha(0.0, 10.0, "acoustic_piano"), []) == []
