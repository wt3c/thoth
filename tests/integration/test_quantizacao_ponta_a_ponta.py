"""Referência conhecida → pipeline rítmico → GP5 → releitura → `avaliar`.

O portão que faltava entre a quantização e o arquivo. Os testes de unidade dos
exportadores afirmam estrutura (quantos beats, qual o `start`); nenhum fechava o
ciclo devolvendo o arquivo gravado a segundos e comparando com a linha de
partida. Sem isso, ADR-021 (grade) e ADR-022 (ligadura) só tinham prova pontual.

Sem modelo e sem áudio: a referência é sintética e está aqui, não em `cache/`,
que é gitignorado (ADR-005). Cabe na suíte padrão de propósito — portão que só
roda quando alguém lembra não é portão.
"""

from __future__ import annotations

from pathlib import Path

import guitarpro as gp
import pytest

from thoth.adapters.export.gp5 import Gp5Exporter
from thoth.domain.models import TUNING_BASS_4, NoteEvent
from thoth.services.evaluation import avaliar
from thoth.services.fretboard import ViterbiFretAssigner
from thoth.services.rhythm import alinhar, monofonizar
from thoth.services.tempo import ajustar

BPM = 96.0
SEMINIMA = 60.0 / BPM

#: `(altura, início, duração)` em semínimas, quatro compassos. Tudo múltiplo de
#: semicolcheia, então a grade não tem o que arredondar: qualquer divergência na
#: releitura é defeito nosso, não folga de quantização.
#:
#: Três das treze notas atravessam a barra (23%, a proporção medida em Is It A Crime
#: no censo do ADR-022) e há pausa, semicolcheia e sustentação longa. Uma travessia só
#: não bastaria: a mediana da razão de duração é robusta por construção e engoliria
#: uma nota ruim sem se mover.
LINHA = [
    (36, 0.00, 1.00),
    (38, 1.00, 0.50),
    (40, 1.50, 0.25),
    (41, 1.75, 0.25),
    (43, 2.00, 2.50),   # atravessa: 2,00 + 2,50 = 4,50
    (45, 4.50, 1.50),
    (38, 6.00, 0.50),   # seguida de pausa até 7,50
    (48, 7.50, 1.25),   # atravessa: 7,50 + 1,25 = 8,75
    (36, 8.75, 0.25),
    (43, 9.00, 1.00),
    (41, 10.00, 2.25),  # atravessa: 10,00 + 2,25 = 12,25
    (38, 12.25, 0.75),
    (36, 13.00, 3.00),  # termina exatamente na barra
]


def _referencia() -> list[NoteEvent]:
    return [
        NoteEvent(pitch=p, onset_s=inicio * SEMINIMA,
                  offset_s=(inicio + duracao) * SEMINIMA, instrument="electric_bass")
        for p, inicio, duracao in LINHA
    ]


def _exportar(referencia: list[NoteEvent], destino: Path) -> gp.Song:
    """O caminho de verdade: mesma ordem de `services/pipeline.py`."""
    bpm, fase = ajustar([n.onset_s for n in referencia], BPM)
    notas, descartadas = monofonizar(alinhar(referencia, bpm, fase), bpm)
    assert not descartadas, "a linha de referência é monofônica; nada deveria ser descartado"
    tabs = ViterbiFretAssigner().assign(notas, TUNING_BASS_4)
    alvo = Gp5Exporter(bpm=bpm).export(tabs, destino / "quantizacao.gp5", TUNING_BASS_4)
    return gp.parse(str(alvo))


def _reler(song: gp.Song, cordas: tuple[int, ...]) -> list[NoteEvent]:
    """GP5 de volta a segundos, fundindo cada ligadura na nota que ela continua.

    É a leitura que importa: o que o Guitar Pro toca, não o que a `Song` em
    memória contém. A ligadura só existe para que a soma das figuras seja a
    duração real, então desfazê-la aqui é o que fecha o ciclo.
    """
    segundos = 60.0 / song.tempo / gp.Duration.quarterTime
    inicio_zero = song.tracks[0].measures[0].start
    notas: list[NoteEvent] = []
    for medida in song.tracks[0].measures:
        for beat in medida.voices[0].beats:
            for nota in beat.notes:
                fim = (beat.start - inicio_zero + beat.duration.time) * segundos
                if nota.type is gp.NoteType.tie and notas:
                    notas[-1] = NoteEvent(
                        pitch=notas[-1].pitch, onset_s=notas[-1].onset_s,
                        offset_s=fim, instrument=notas[-1].instrument,
                    )
                    continue
                altura = cordas[len(cordas) - nota.string] + nota.value
                notas.append(NoteEvent(
                    pitch=altura, onset_s=(beat.start - inicio_zero) * segundos,
                    offset_s=fim, instrument="electric_bass",
                ))
    return notas


@pytest.fixture(scope="module")
def relido(tmp_path_factory: pytest.TempPathFactory) -> list[NoteEvent]:
    # Escopo de módulo: `ajustar` faz busca em 400 por 120, e as cinco afirmações
    # olham o mesmo arquivo. Por teste, o portão custaria cinco exportações.
    destino = tmp_path_factory.mktemp("quantizacao")
    return _reler(_exportar(_referencia(), destino), TUNING_BASS_4)


def test_o_ciclo_completo_nao_perde_nem_inventa_nota(relido: list[NoteEvent]) -> None:
    assert [n.pitch for n in relido] == [p for p, _, _ in LINHA]


def test_onset_e_altura_sobrevivem_ao_arquivo(relido: list[NoteEvent]) -> None:
    resultado = avaliar(_referencia(), relido)

    assert resultado.onset_f1 == 1.0, resultado
    assert resultado.note_f1 == 1.0, resultado


def test_a_duracao_tambem_sobrevive(relido: list[NoteEvent]) -> None:
    """As métricas de duração do ADR-023 concordam com o arquivo.

    Medido com o corte na barra reativado, para saber o que cada métrica enxerga:
    `Scores(onset_f1=1.0, note_f1=1.0, nota_offset_f1=0.923, duracao_ratio=1.0)`.
    As duas antigas pontuam **1,000 com três notas encurtadas** — era o ponto cego
    que o ADR-023 fechou. A `duracao_ratio` também não se move, porque mediana é
    robusta por construção: três notas ruins em treze não a deslocam. Só a
    `nota_offset_f1` cai, e apenas 7,7%.

    Por isso o portão de verdade é `test_nenhuma_nota_volta_encurtada`, nota a
    nota. Aqui a afirmação é que o avaliador lê o mesmo arquivo que o teste.
    """
    resultado = avaliar(_referencia(), relido)

    assert resultado.nota_offset_f1 == 1.0, resultado
    assert resultado.duracao_ratio == 1.0, resultado


def test_nenhuma_nota_volta_encurtada(relido: list[NoteEvent]) -> None:
    """Nota a nota, sem mediana no meio: é aqui que o corte na barra reprova."""
    encurtadas = [
        (p, duracao, round((n.offset_s - n.onset_s) / SEMINIMA, 4))
        for (p, _, duracao), n in zip(LINHA, relido, strict=True)
        if round((n.offset_s - n.onset_s) / SEMINIMA, 4) < duracao
    ]
    assert not encurtadas, f"(altura, esperada, lida) em semínimas: {encurtadas}"


def test_a_grade_exata_nao_deriva_um_tick(relido: list[NoteEvent]) -> None:
    """Múltiplo de semicolcheia com BPM exato: divergência aqui é bug, não folga."""
    esperado = [t * SEMINIMA for _, inicio, duracao in LINHA
                for t in (inicio, inicio + duracao)]
    lido = [t for n in relido for t in (n.onset_s, n.offset_s)]
    assert lido == pytest.approx(esperado, abs=1e-9)
