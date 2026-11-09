"""As afinações do mapa do braço não divergem das do pipeline (ADR-058)."""

from __future__ import annotations

import json
from pathlib import Path

from thoth.domain.models import AFINACOES

AFINACOES_BRACO = (
    Path(__file__).resolve().parents[2] / "braco" / "src" / "dominio" / "afinacoes.json"
)

#: Nome no pipeline → id no braço. Só as que existem nos dois lados.
COMUNS = {"4": "baixo-4", "5": "baixo-5", "6": "baixo-6", "drop-d": "baixo-drop-d"}


def test_presets_comuns_tem_as_mesmas_alturas() -> None:
    braco = {a["id"]: tuple(a["cordas"]) for a in json.loads(AFINACOES_BRACO.read_text("utf-8"))}

    comparadas = {nome: (AFINACOES[nome], braco.get(id_braco)) for nome, id_braco in COMUNS.items()}
    print(comparadas)

    assert set(COMUNS) == set(AFINACOES), "afinação nova no pipeline: decidir se entra no braço"
    assert all(pipeline == lado_braco for pipeline, lado_braco in comparadas.values())
