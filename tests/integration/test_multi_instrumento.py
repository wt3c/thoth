"""Medição do ADR-044: bateria, piano e guitarra contra referência conhecida.

Cada perfil novo roda em três condições: a fixture isolada direto no MuScriptor, a
`-mix` direto, e a `-mix` depois do Demucs, no stem do perfil. O veredito usa a
`-mix` na melhor das duas últimas (critério fixado no ADR-044 antes de medir); a
isolada diz quanto do erro é do modelo e quanto é da mistura.

Nada aqui muda o caminho do baixo: a transcrição é filtrada pelos rótulos do perfil,
como o pipeline faz com `ROTULOS_DE_BAIXO`.
"""

from __future__ import annotations

import shutil
import time
from collections import Counter
from pathlib import Path

import pytest

from tests.sintetico import SOUNDFONT
from tests.sintetico_multi import FIXTURES_MULTI, referencia, renderizar_multi
from thoth.adapters.separation import DemucsSeparator
from thoth.adapters.transcription.muscriptor import MuscriptorTranscriber
from thoth.domain.instrumentos import PERFIS
from thoth.domain.models import Transcricao
from thoth.services.evaluation import (
    avaliar_bateria,
    avaliar_polifonico,
    confusao_bateria,
    revocacao_por_acorde,
)

pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(not SOUNDFONT.exists(), reason=f"soundfont ausente: {SOUNDFONT}"),
    pytest.mark.skipif(shutil.which("fluidsynth") is None, reason="fluidsynth ausente"),
]

CONDICOES = ("isolada", "mix", "mix-stem")
PERFIS_NOVOS = sorted(p for p in PERFIS if p != "baixo")

#: F1 medido em 2026-09-25 (`small`, `muscriptor@0.3.0`, `demucs@4.1.0 htdemucs_ft`):
#: nota F1 para piano e guitarra, F1 micro para bateria. Sem folga em `isolada` e `mix`,
#: pelo mesmo motivo do `test_regressao_fase0.py`: renderização determinística, motor
#: pregado, e com 34 a 53 eventos de referência a menor diferença já é um evento inteiro.
MEDIDO: dict[tuple[str, str], float] = {
    ("bateria", "isolada"): 0.529,
    ("bateria", "mix"): 0.867,
    ("bateria", "mix-stem"): 0.529,
    ("guitarra-acustica", "isolada"): 0.981,
    ("guitarra-acustica", "mix"): 0.705,
    ("guitarra-acustica", "mix-stem"): 0.981,
    ("guitarra-distorcida", "isolada"): 0.981,
    ("guitarra-distorcida", "mix"): 0.972,
    ("guitarra-distorcida", "mix-stem"): 0.981,
    ("guitarra-limpa", "isolada"): 0.927,
    ("guitarra-limpa", "mix"): 0.889,
    ("guitarra-limpa", "mix-stem"): 0.990,
    ("piano-acustico", "isolada"): 0.923,
    ("piano-acustico", "mix"): 0.696,
    ("piano-acustico", "mix-stem"): 0.879,
    # O modelo rotula o piano elétrico como `clean_electric_guitar` isolado e como
    # `acoustic_piano` no stem: zero é troca de rótulo, não nota errada.
    ("piano-eletrico", "isolada"): 0.0,
    ("piano-eletrico", "mix"): 0.676,
    ("piano-eletrico", "mix-stem"): 0.0,
}

#: O Demucs não repete o stem entre rodadas (duas separações da mesma fixture diferem
#: em até 0,04 na amostra; o piano deu 0,879 e 0,892). Um evento de folga em 34, só
#: onde há separação — emenda do ADR-044 (2026-09-25).
FOLGA_DEMUCS = 0.03


#: Notas acertadas nos acordes de seis notas da guitarra, de 24 (M4, 2026-09-25): o
#: teto do ADR-011 é a sobreposição de notas do mesmo instrumento, e é aqui que ele
#: apareceria primeiro. Uma nota de folga onde há Demucs, como na `FOLGA_DEMUCS`.
MEDIDO_SEIS_NOTAS: dict[tuple[str, str], int] = {
    ("guitarra-acustica", "isolada"): 23,
    ("guitarra-acustica", "mix"): 23,
    ("guitarra-acustica", "mix-stem"): 23,
    ("guitarra-distorcida", "isolada"): 24,
    ("guitarra-distorcida", "mix"): 24,
    ("guitarra-distorcida", "mix-stem"): 24,
    ("guitarra-limpa", "isolada"): 24,
    ("guitarra-limpa", "mix"): 21,
    ("guitarra-limpa", "mix-stem"): 24,
}

def _audio(perfil: str, condicao: str, tmp_path: Path) -> Path:
    fixture = f"{perfil}-{'isolada' if condicao == 'isolada' else 'mix'}"
    wav = renderizar_multi(fixture, tmp_path)
    if condicao != "mix-stem":
        return wav
    stem = PERFIS[perfil].stem
    return DemucsSeparator(stem=stem).separate(wav, tmp_path / "stems")[stem]


@pytest.mark.parametrize("condicao", CONDICOES)
@pytest.mark.parametrize("perfil", PERFIS_NOVOS)
def test_mede_perfil(perfil: str, condicao: str, tmp_path: Path) -> None:
    inicio = time.monotonic()
    audio = _audio(perfil, condicao, tmp_path)
    bruto = MuscriptorTranscriber(model="small").transcribe(audio)
    segundos = time.monotonic() - inicio

    rotulos = Counter(n.instrument for n in bruto)
    do_perfil = Transcricao.do_muscriptor(
        [n for n in bruto if n.instrument in PERFIS[perfil].rotulos]
    )
    ref = referencia(FIXTURES_MULTI[f"{perfil}-{'isolada' if condicao == 'isolada' else 'mix'}"])

    if PERFIS[perfil].familia == "bateria":
        b = avaliar_bateria(ref.ataques, do_perfil.ataques)
        f1 = b.micro.f1
        pecas = " ".join(f"{p}:{s.f1:.3f}" for p, s in sorted(b.por_peca.items()))
        resultado = (
            f"micro P {b.micro.precisao:.3f} R {b.micro.revocacao:.3f} F1 {b.micro.f1:.3f} "
            f"macro {b.macro_f1:.3f} ref={b.n_ref} est={b.n_est} peças[{pecas}]"
        )
        confusao = confusao_bateria(ref.ataques, do_perfil.ataques)
        resultado += " confusão[" + " ".join(
            f"{r if r is not None else '-'}→{e if e is not None else '-'}:{n}"
            for (r, e), n in sorted(confusao.items(), key=lambda x: (x[0][0] or 0, x[0][1] or 0))
        ) + "]"
    else:
        s = avaliar_polifonico(ref.notas, do_perfil.notas)
        f1 = s.nota.f1
        resultado = (
            f"nota P {s.nota.precisao:.3f} R {s.nota.revocacao:.3f} F1 {s.nota.f1:.3f} "
            f"ataque F1 {s.ataque.f1:.3f} ref={s.n_ref} est={s.n_est}"
        )
        por_acorde = revocacao_por_acorde(ref.notas, do_perfil.notas)
        resultado += " acordes[" + " ".join(
            f"{k}:{c}/{t}" for k, (c, t) in por_acorde.items()
        ) + "]"
    piso = max(0.0, MEDIDO[(perfil, condicao)] - (FOLGA_DEMUCS if condicao == "mix-stem" else 0))
    print(
        f"\nMEDIDO {perfil} {condicao}: {resultado} {segundos:.0f}s rótulos={dict(rotulos)} "
        f"piso={piso} margem={f1 - piso:+.3f}"
    )

    assert bruto, f"MuScriptor não devolveu nada para {perfil} {condicao}"
    assert f1 >= piso, f"{perfil} {condicao} regrediu: {f1} < {piso} medido no ADR-044"
    if (perfil, condicao) in MEDIDO_SEIS_NOTAS:
        seis = por_acorde[6][0]
        piso_seis = MEDIDO_SEIS_NOTAS[(perfil, condicao)] - (condicao == "mix-stem")
        print(f"SEIS NOTAS {perfil} {condicao}: {seis}/24 piso={piso_seis}")
        assert seis >= piso_seis, f"acordes de seis notas regrediram: {seis} < {piso_seis}"
