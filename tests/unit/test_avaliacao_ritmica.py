"""A avaliação rítmica mede velocidade sem esconder erros com escala temporal."""

import json
from dataclasses import asdict, replace

import numpy as np
import pytest

from thoth.services.avaliacao_ritmica import EventoRitmico, boletim, comparar_ritmo


def _linha(
    alturas: list[int],
    velocidade: float = 1.0,
    atraso: float = 0.0,
) -> list[EventoRitmico]:
    return [
        EventoRitmico(p, atraso + i / velocidade, 0.5 / velocidade, i, 0.5)
        for i, p in enumerate(alturas)
    ]


def test_velocidade_dobrada_nao_e_confundida_com_ritmo_correto() -> None:
    resultado = comparar_ritmo(_linha([36, 38, 40]), _linha([36, 38, 40], velocidade=2))

    assert resultado.velocidade_relativa == pytest.approx(2)
    assert resultado.intervalos_corretos == 2
    assert resultado.erro_intervalo_pulsos_mediano == 0


def test_deslocamento_inicial_nao_muda_a_medida_de_velocidade() -> None:
    resultado = comparar_ritmo(_linha([36, 38, 40]), _linha([36, 38, 40], atraso=5))

    assert resultado.velocidade_relativa == pytest.approx(1)
    assert resultado.intervalos_corretos == 2
    assert resultado.duracoes_corretas == 3


def test_altura_errada_e_nota_ausente_sao_relatadas_separadamente() -> None:
    resultado = comparar_ritmo(_linha([36, 38, 40, 41]), _linha([36, 39, 41]))

    assert resultado.omissoes == 1
    assert resultado.extras == 0
    assert resultado.alturas_divergentes == 1
    assert resultado.pares == 2


def test_figuras_e_duracoes_diferentes_aparecem_mesmo_com_alturas_iguais() -> None:
    ref = _linha([36, 38, 40])
    est = [ref[0], EventoRitmico(38, 1, 0.25, 1.25, 0.25), ref[2]]

    resultado = comparar_ritmo(ref, est)

    assert resultado.velocidade_relativa == 1
    assert resultado.intervalos_corretos == 0
    assert resultado.erro_intervalo_pulsos_mediano == pytest.approx(0.25)
    assert resultado.duracoes_corretas == 2


def test_sem_intervalos_correspondentes_nao_inventa_uma_velocidade() -> None:
    resultado = comparar_ritmo(_linha([36, 38, 40]), _linha([38]))

    assert resultado.velocidade_relativa is None
    assert resultado.intervalos_comparaveis == 0
    assert resultado.omissoes == 2


def test_estimativa_vazia_relata_todas_as_omissoes() -> None:
    resultado = comparar_ritmo(_linha([36, 38]), [])

    assert resultado.omissoes == 2
    assert resultado.pares == resultado.extras == 0
    assert resultado.velocidade_relativa is None


def test_nota_extra_nao_e_confundida_com_omissao() -> None:
    resultado = comparar_ritmo(_linha([36, 40]), _linha([36, 38, 40]))

    assert resultado.extras == 1
    assert resultado.omissoes == resultado.alturas_divergentes == 0
    assert resultado.pares == 2
    assert resultado.intervalos_comparaveis == 0


def test_notas_repetidas_deixam_a_ambiguidade_explicita() -> None:
    resultado = comparar_ritmo(_linha([36, 36]), _linha([36]))

    assert resultado.alinhamento_ambiguo
    assert resultado.omissoes == resultado.pares == 1
    assert resultado.extras == resultado.alturas_divergentes == 0


def test_referencia_vazia_e_recusada() -> None:
    with pytest.raises(ValueError, match="referência"):
        comparar_ritmo([], _linha([36]))


def test_metricas_com_tempos_numpy_podem_ser_gravadas_no_relatorio() -> None:
    eventos = [
        EventoRitmico(38, np.float64(i), np.float64(0.5), np.float64(i), np.float64(0.5))
        for i in range(3)
    ]

    resultado = comparar_ritmo(eventos, eventos)

    assert json.loads(json.dumps(asdict(resultado)))["intervalos_corretos"] == 2


def test_velocidade_por_trecho_nao_some_na_mediana_global() -> None:
    ref = _linha([36 + i % 12 for i in range(60)])
    est = [
        EventoRitmico(
            e.altura, i / 2 if i <= 20 else i - 10, 0.5, e.inicio_pulsos, e.duracao_pulsos
        )
        for i, e in enumerate(ref)
    ]

    resultado = comparar_ritmo(ref, est)

    assert resultado.velocidade_relativa == 1
    assert resultado.janelas[0].velocidade_relativa == 2
    assert resultado.janelas[1].velocidade_relativa == 1
    assert resultado.janelas[0].inicio_s == 0
    assert resultado.janelas[1].inicio_s == 20


def test_janela_nao_positiva_e_recusada() -> None:
    with pytest.raises(ValueError, match="janela"):
        comparar_ritmo(_linha([36]), _linha([36]), janela_s=0)


def test_nota_repetida_omitida_nao_vira_meia_velocidade() -> None:
    alturas = [36, 38, 40, 40, 40, 40, 43, 45, 47]
    ref = _linha(alturas)
    est = [e for i, e in enumerate(ref) if i != 4]

    resultado = comparar_ritmo(ref, est)

    assert resultado.velocidade_relativa == 1
    assert resultado.velocidade_p10 == 1
    assert resultado.intervalos_ambiguos > 0
    assert resultado.intervalos_comparaveis == resultado.intervalos_corretos


def test_repeticao_com_mesmo_tamanho_continua_comparavel() -> None:
    resultado = comparar_ritmo(_linha([40, 40, 40, 43]), _linha([40, 40, 40, 43], velocidade=2))

    assert resultado.intervalos_ambiguos == 0
    assert resultado.intervalos_comparaveis == 3
    assert resultado.velocidade_relativa == pytest.approx(2)


def test_deslocamento_de_semicolcheia_erra_a_posicao_mas_nao_a_figura() -> None:
    ref = _linha([36, 38, 40])
    est = [replace(e, inicio_pulsos=e.inicio_pulsos + 0.25) for e in ref]

    resultado = comparar_ritmo(ref, est)

    assert resultado.intervalos_corretos == 2
    assert resultado.posicoes_corretas == 0


def test_deslocamento_de_um_pulso_inteiro_mantem_a_posicao_no_pulso() -> None:
    ref = _linha([36, 38, 40])
    est = [replace(e, inicio_pulsos=e.inicio_pulsos + 1) for e in ref]

    assert comparar_ritmo(ref, est).posicoes_corretas == 3


def test_digitacao_compara_a_corda_pela_altura_solta() -> None:
    ref = [replace(e, corda=c) for e, c in zip(_linha([40, 45, 50]), [28, 33, 38], strict=True)]
    est = [replace(e, corda=c) for e, c in zip(_linha([40, 45, 50]), [28, 28, 33], strict=True)]

    resultado = comparar_ritmo(ref, est)

    assert resultado.digitacoes_comparaveis == 3
    assert resultado.digitacoes_corretas == 1


def test_sem_corda_a_digitacao_nao_e_comparada() -> None:
    resultado = comparar_ritmo(_linha([36, 38]), _linha([36, 38]))

    assert resultado.digitacoes_comparaveis == resultado.digitacoes_corretas == 0


def test_boletim_resume_cada_dimensao_numa_fracao() -> None:
    ref = [replace(e, corda=28) for e in _linha(list(range(30, 90)))]
    est = [
        replace(e, inicio_s=e.inicio_s / 2 if e.inicio_s < 20 else e.inicio_s - 10)
        for e in ref[:50]
    ]
    est[1] = replace(est[1], inicio_pulsos=est[1].inicio_pulsos + 0.25)

    nota = boletim(comparar_ritmo(ref, est))

    assert nota.andamento == pytest.approx(2 / 3)  # janelas: 2x, 1x, 1x
    assert nota.figuras == pytest.approx(47 / 49)
    assert nota.posicao_no_pulso == pytest.approx(49 / 50)
    assert nota.altura == pytest.approx(50 / 60)
    assert nota.digitacao == 1


def test_boletim_sem_material_comparavel_nao_inventa_nota() -> None:
    nota = boletim(comparar_ritmo(_linha([36]), []))

    assert nota.andamento is nota.figuras is nota.posicao_no_pulso is nota.digitacao is None
    assert nota.altura == 0
