"""Avalia GP5 existentes contra referências locais; não transcreve nem copia notas.

Uso: uv run python scripts/avaliar_corpus_ritmico.py --manifesto corpus.json
     --destino out/avaliacao-ritmo --reproduzir
O manifesto contém `casos`: nome, referencia e gerada, com caminhos relativos à
raiz. Áudio e source_id opcionais registram a identidade da gravação avaliada.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import warnings
from collections import Counter
from dataclasses import asdict
from pathlib import Path

import guitarpro as gp
import pretty_midi

from thoth.services.avaliacao_ritmica import EventoRitmico, boletim, comparar_ritmo
from thoth.services.tab_referencia import _andamentos, _faixa, _notas, _ordem, _tablatura


def _sha256(caminho: Path) -> str:
    digest = hashlib.sha256()
    with caminho.open("rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1024 * 1024), b""):
            digest.update(bloco)
    return digest.hexdigest()


def _ler(caminho: Path) -> tuple[list[EventoRitmico], dict[str, object]]:
    song = gp.parse(str(caminho))
    faixa = _faixa(song, None, caminho.name)
    reais = _tablatura(song, faixa)
    afinacao = [c.value for c in reversed(faixa.strings)]
    estrutura: dict[str, object] = {
        "caminho": str(caminho),
        "sha256": _sha256(caminho),
        "faixa": faixa.name,
        "afinacao": afinacao,
        "bpm_inicial": song.tempo,
        "mudancas": _andamentos(song),
        "compassos_escritos": len(song.measureHeaders),
        "compassos_executados": len(_ordem(song.measureHeaders)),
        "assinaturas": dict(
            Counter(
                f"{h.timeSignature.numerator}/{h.timeSignature.denominator.value}"
                for h in song.measureHeaders
            )
        ),
        "notas": len(reais),
    }
    # Só a cópia em memória: 60 BPM torna cada segundo virtual uma semínima.
    # O mesmo leitor interpreta repetições e ties, sem um segundo parser de ritmo.
    song.tempo = 60
    for track in song.tracks:
        for medida in track.measures:
            for voz in medida.voices:
                for beat in voz.beats:
                    if beat.effect.mixTableChange is not None:
                        beat.effect.mixTableChange.tempo = None
    pulsos = _notas(song, faixa)
    assert len(reais) == len(pulsos)
    eventos = [
        EventoRitmico(
            a.event.pitch,
            a.event.onset_s,
            a.event.duration_s,
            b.onset_s,
            b.duration_s,
            afinacao[a.string],
        )
        for a, b in zip(reais, pulsos, strict=True)
    ]
    return eventos, estrutura


def _reproduzir(caminho: Path, destino: Path) -> tuple[list[EventoRitmico], dict[str, object]]:
    subprocess.run(
        ["mscore", str(caminho), "-o", str(destino)],
        check=True,
        capture_output=True,
        timeout=90,
        env=os.environ | {"QT_QPA_PLATFORM": "offscreen"},
    )
    with warnings.catch_warnings(record=True) as avisos:
        warnings.simplefilter("always", RuntimeWarning)
        midi = pretty_midi.PrettyMIDI(str(destino))
    baixos = [i for i in midi.instruments if i.notes and 32 <= i.program <= 39]
    if len(baixos) != 1:
        raise ValueError(
            f"{caminho.name}: esperada uma faixa MIDI de baixo, encontradas {len(baixos)}"
        )
    notas = sorted(baixos[0].notes, key=lambda n: (n.start, n.pitch))
    eventos = [
        EventoRitmico(
            n.pitch,
            n.start,
            n.end - n.start,
            midi.time_to_tick(n.start) / midi.resolution,
            (midi.time_to_tick(n.end) - midi.time_to_tick(n.start)) / midi.resolution,
        )
        for n in notas
    ]
    tempos, bpms = midi.get_tempo_changes()
    return eventos, {
        "caminho": str(destino),
        "sha256": _sha256(destino),
        "notas": len(eventos),
        "tempos_s": tempos.tolist(),
        "bpms": bpms.tolist(),
        "programa": int(baixos[0].program),
        "avisos_leitor": [str(aviso.message) for aviso in avisos],
    }


def avaliar_corpus(
    manifesto: Path,
    raiz: Path,
    destino: Path,
    *,
    reproduzir: bool = False,
) -> list[dict[str, object]]:
    casos = json.loads(manifesto.read_text(encoding="utf-8"))["casos"]
    if not casos:
        raise ValueError("manifesto sem casos de avaliação")
    for caso in casos:
        for chave in ("referencia", "gerada"):
            if not (raiz / caso[chave]).is_file():
                raise FileNotFoundError(raiz / caso[chave])
    destino.mkdir(parents=True, exist_ok=True)
    resultados: list[dict[str, object]] = []
    for indice, caso in enumerate(casos, start=1):
        print(f"{indice}/{len(casos)}: {caso['nome']}", flush=True)
        pasta = destino / f"{indice:02d}"
        pasta.mkdir(exist_ok=True)
        ref, metar = _ler(raiz / caso["referencia"])
        est, metae = _ler(raiz / caso["gerada"])
        comparacao = comparar_ritmo(ref, est)
        resultado: dict[str, object] = {
            "nome": caso["nome"],
            "referencia": metar,
            "gerada": metae,
            "metricas": asdict(comparacao),
            "boletim": asdict(boletim(comparacao)),
            "source_id": caso.get("source_id"),
            "observacoes": caso.get("observacoes"),
        }
        if caso.get("audio"):
            audio = raiz / caso["audio"]
            resultado["audio"] = {"caminho": str(audio), "sha256": _sha256(audio)}
        if reproduzir:
            try:
                mr, midi_ref = _reproduzir(raiz / caso["referencia"], pasta / "referencia.mid")
                me, midi_est = _reproduzir(raiz / caso["gerada"], pasta / "gerada.mid")
                resultado["reproducao"] = {
                    "referencia": midi_ref,
                    "gerada": midi_est,
                    "metricas": asdict(comparar_ritmo(mr, me)),
                }
            except (subprocess.SubprocessError, ValueError) as erro:
                resultado["erro_reproducao"] = f"{type(erro).__name__}: {erro}"
                print(f"Falha de reprodução em {caso['nome']}: {erro}", flush=True)
        (pasta / "metricas.json").write_text(
            json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        resultados.append(resultado)
    (destino / "metricas.json").write_text(
        json.dumps(resultados, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (destino / "manifesto.json").write_text(manifesto.read_text(encoding="utf-8"), encoding="utf-8")
    return resultados


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifesto", type=Path, required=True)
    parser.add_argument("--raiz", type=Path, default=Path.cwd())
    parser.add_argument("--destino", type=Path, required=True)
    parser.add_argument("--reproduzir", action="store_true")
    argumentos = parser.parse_args()
    linhas = avaliar_corpus(
        argumentos.manifesto,
        argumentos.raiz,
        argumentos.destino,
        reproduzir=argumentos.reproduzir,
    )
    if any("erro_reproducao" in linha for linha in linhas):
        raise SystemExit(1)
