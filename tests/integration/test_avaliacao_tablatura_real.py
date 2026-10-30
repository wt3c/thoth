"""O gabarito humano e a saída passam pelos leitores reais de GP5."""

from pathlib import Path

from tests.unit.test_tab_referencia import B, _baixo, _gravar
from thoth.adapters.export.gp5 import Gp5Exporter
from thoth.domain.models import TUNING_BASS_4, NoteEvent
from thoth.services.evaluation import avaliar_tablatura
from thoth.services.fretboard import PADRAO, ViterbiFretAssigner
from thoth.services.tab_referencia import ler_tab


def test_mesmo_re_em_outra_corda_nao_aprova_a_tablatura(tmp_path: Path) -> None:
    referencia = _gravar(tmp_path, [_baixo([[B(4, 5, corda=3), B(4), B(4), B(4)]])])
    notas = [NoteEvent(38, 0.0, 0.5, "electric_bass")]
    posicionadas = ViterbiFretAssigner().assign(notas, TUNING_BASS_4)
    gerada = Gp5Exporter(bpm=120).export(posicionadas, tmp_path / "gerada.gp5", TUNING_BASS_4)

    resultado = avaliar_tablatura(ler_tab(referencia).tablatura, ler_tab(gerada).tablatura)

    assert resultado.alturas == resultado.duracoes == 1
    assert resultado.posicoes == resultado.completas == 0
    assert not resultado.coincide


def test_alcance_da_mao_corrige_a_corda_no_gp5_relido(tmp_path: Path) -> None:
    referencia = _gravar(
        tmp_path,
        [_baixo([[B(8, 3, corda=4), B(8, 5, corda=3), B(8, 3, corda=4), B(8), B(2)]])],
    )
    notas = [
        NoteEvent(p, i * 0.25, (i + 1) * 0.25, "electric_bass") for i, p in enumerate([31, 38, 31])
    ]
    posicionadas = ViterbiFretAssigner(custos=PADRAO, alcance_da_mao=3).assign(notas, TUNING_BASS_4)
    gerada = Gp5Exporter(bpm=120).export(posicionadas, tmp_path / "alcance.gp5", TUNING_BASS_4)

    resultado = avaliar_tablatura(
        ler_tab(referencia).tablatura,
        ler_tab(gerada).tablatura,
        tolerancia_s=0,
        tolerancia_duracao_s=0,
    )

    assert resultado.completas == 3
    assert resultado.coincide
