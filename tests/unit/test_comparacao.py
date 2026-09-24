"""Transcrição contra tab humana: alinhamento cego à oitava e veredito de oitava (ADR-041)."""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pytest

from thoth.domain.models import NoteEvent
from thoth.services.comparacao import CORRECAO_MAXIMA_S, JANELA_S, alinhar, comparar


def _tab(n: int = 120, semente: int = 0) -> list[NoteEvent]:
    """Linha irregular: com intervalos todos iguais, qualquer deslocamento de uma nota
    casaria tão bem quanto o certo, e o teste não distinguiria alinhamento de sorte."""
    gera = np.random.default_rng(semente)
    ataques = np.cumsum(gera.choice([0.25, 0.5, 0.75], size=n))
    alturas = gera.integers(28, 48, size=n)
    return [
        NoteEvent(int(p), float(t), float(t) + 0.2, "electric_bass")
        for t, p in zip(ataques, alturas, strict=True)
    ]


def _movida(notas: list[NoteEvent], mover: Callable[[float], float]) -> list[NoteEvent]:
    return [
        NoteEvent(n.pitch, mover(n.onset_s), mover(n.onset_s) + 0.2, n.instrument) for n in notas
    ]


def test_recupera_escala_e_deslocamento_globais() -> None:
    ref = _tab()
    est = _movida(ref, lambda t: t * 0.97 + 3.2)

    a = alinhar(ref, est)

    erros = [abs(r.onset_s - e.onset_s) for r, e in zip(a.notas, est, strict=True)]
    print(f"escala {a.escala:.4f} deslocamento {a.deslocamento_s:.3f} erro máx {max(erros):.4f}")
    assert max(erros) < 0.01


def test_escala_na_borda_da_busca_e_recusada() -> None:
    """Na borda, o melhor encaixe pode estar do lado de fora: o alinhamento falhou, e
    imprimir percentuais sobre ele seria afirmar o que não se mediu.

    A guarda é necessária, não suficiente: com a escala verdadeira fora da grade, o
    acaso às vezes faz um pico no interior (outra semente, aqui, para em 0,914). Contra
    esse caso a defesa é o piso de acaso impresso ao lado do veredito."""
    ref = _tab(n=400)
    est = _movida(ref, lambda t: t * 0.85)

    with pytest.raises(ValueError, match="borda"):
        alinhar(ref, est)


def test_corrige_deriva_local_pequena() -> None:
    """Um trecho que a banda adiantou 60 ms: a escala global não absorve, a correção sim.

    O trecho coincide com duas janelas: a correção é uma por janela, e uma deriva que
    começa no meio dela divide a janela entre dois grupos — o menor fica sem correção."""
    ref = _tab()
    t0 = ref[0].onset_s
    est = _movida(ref, lambda t: t + (0.06 if t0 + 2 * JANELA_S <= t < t0 + 4 * JANELA_S else 0.0))

    a = alinhar(ref, est)

    erros = [abs(r.onset_s - e.onset_s) for r, e in zip(a.notas, est, strict=True)]
    print(f"erro máx {max(erros):.4f}")
    assert max(erros) < 0.015


def test_correcao_local_nao_persegue_salto_maior_que_o_limite() -> None:
    """Um salto que os resíduos enxergam (95 ms, dentro da tolerância) mas passa do
    limite: a correção para no limite em vez de ir atrás. Sem o limite, trechos
    seguidos poderiam empurrar a tab até a nota vizinha. Tab longa para que o trecho
    pese pouco no ajuste global, que senão absorveria parte do salto."""
    ref = _tab(n=400)
    est = _movida(ref, lambda t: t + (0.095 if 20 <= t < 30 else 0.0))

    a = alinhar(ref, est)

    movidas = [
        r.onset_s - (n.onset_s * a.escala + a.deslocamento_s)
        for r, n in zip(a.notas, ref, strict=True)
        if 20 <= n.onset_s < 30
    ]
    assert max(abs(m) for m in movidas) <= CORRECAO_MAXIMA_S + 1e-9


def test_classifica_a_oitava_das_notas_casadas() -> None:
    """Nome de nota diferente não casa: o veredito é só de oitava."""
    ref = _tab()
    trocas = {0: 12, 1: -12, 2: 5, 3: 24}  # acima, abaixo, outra nota, acima (duas oitavas)
    est = [
        NoteEvent(n.pitch + trocas.get(i, 0), n.onset_s, n.offset_s, n.instrument)
        for i, n in enumerate(ref)
    ]

    c = comparar(ref, est)

    assert (c.casadas, c.mesma_oitava, c.oitava_acima, c.oitava_abaixo) == (119, 116, 2, 1)


def test_oitava_toda_errada_nao_muda_o_alinhamento() -> None:
    """O alinhamento é cego à oitava: se ela entrasse nele, uma transcrição toda uma
    oitava acima seria encaixada onde a oitava coincide, e o veredito se provaria sozinho."""
    ref = _tab()
    est = [NoteEvent(n.pitch + 12, n.onset_s + 1.5, n.offset_s + 1.5, n.instrument) for n in ref]

    c = comparar(ref, est)

    assert (c.casadas, c.mesma_oitava, c.oitava_acima) == (120, 0, 120)


def test_nota_sem_par_fica_fora_do_veredito() -> None:
    ref = _tab()
    extras = [NoteEvent(40, n.onset_s + 0.12, n.onset_s + 0.2, n.instrument) for n in ref[::4]]

    c = comparar(ref, sorted([*ref, *extras], key=lambda n: n.onset_s))

    assert (c.n_ref, c.n_est, c.casadas, c.mesma_oitava) == (120, 150, 120, 120)


def test_piso_de_acaso_vem_da_tab_deslocada() -> None:
    """Com a linha densa, parte dos pares casa por sorte. O piso é o mesmo veredito com
    a tab deslocada de propósito: a medida só vale o quanto fica acima dele."""
    ref = _tab()
    est = _movida(ref, lambda t: t + 3.2)

    c = comparar(ref, est)

    print(f"casadas {c.casadas} · piso {c.piso_casadas}")
    assert c.casadas == 120
    assert 0 < c.piso_casadas < c.casadas
    assert 0.0 <= c.piso_mesma_oitava <= 1.0
