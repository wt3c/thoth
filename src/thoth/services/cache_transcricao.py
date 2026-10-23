"""Transcrição bruta do MuScriptor em cache no disco (ADR-052).

A transcrição é o estágio de minutos; o resto do pipeline, segundos. Até aqui ela
só sobrevivia dentro do processo (`_TranscritorComCache` do `todos`) ou já filtrada
pelo perfil (`notas.jsonl`), e trocar um parâmetro de quantização ou de digitação
custava a música inteira de novo.

A chave é o que decide a saída, não o caminho: o conteúdo do stem, os pesos que o
lock fixa, a configuração do adapter e o código-fonte dele. Sem lock não há como
dizer que pesos produziram o resultado, e então não há cache.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from thoth.adapters.transcription import muscriptor
from thoth.adapters.transcription.muscriptor import MuscriptorTranscriber
from thoth.arquivos import escrita_atomica
from thoth.domain.models import EventoPercussivo, NoteEvent, Transcricao
from thoth.domain.ports import Transcriber
from thoth.services.model_lock import carregar_lock, sha256_de

LOCK_DO_PROJETO = Path(__file__).resolve().parents[3] / "models.lock.toml"


def identidade(transcritor: MuscriptorTranscriber, lock: Path = LOCK_DO_PROJETO) -> str | None:
    """Tudo o que decide a saída do `transcritor`, ou `None` se os pesos não estão travados."""
    if not lock.is_file():
        return None
    modelo = carregar_lock(lock).get(f"muscriptor-{transcritor.model}")
    if modelo is None:
        return None
    return json.dumps(
        {
            "pesos": asdict(modelo),
            "binary": list(transcritor.binary),
            "model": transcritor.model,
            "device": transcritor.device,
            "silencio_inicial_s": transcritor.silencio_inicial_s,
            # Mudar o parsing ou a segunda passada muda a saída sem mudar parâmetro algum.
            "codigo": sha256_de(Path(muscriptor.__file__)),
        },
        sort_keys=True,
    )


@dataclass(frozen=True, slots=True)
class TranscritorEmCache:
    """Serve do disco o que o `base` já transcreveu com a mesma `identidade`."""

    base: Transcriber
    identidade: str
    pasta: Path

    def transcribe(self, audio: Path) -> Transcricao:
        chave = hashlib.sha256(self.identidade.encode()).hexdigest()[:16]
        destino = self.pasta / f"{sha256_de(audio)}-{chave}.json"
        if destino.is_file():
            dados = json.loads(destino.read_text())
            return Transcricao(
                notas=tuple(NoteEvent(**n) for n in dados["notas"]),
                ataques=tuple(EventoPercussivo(**a) for a in dados["ataques"]),
            )
        transcricao = self.base.transcribe(audio)
        with escrita_atomica(destino) as parcial:
            parcial.write_text(
                json.dumps(
                    {
                        "notas": [asdict(n) for n in transcricao.notas],
                        "ataques": [asdict(a) for a in transcricao.ataques],
                    }
                )
            )
        return transcricao


def em_cache(transcritor: MuscriptorTranscriber, cache_dir: Path) -> Transcriber:
    """O `transcritor` atrás do cache, ou ele mesmo quando não há identidade a confiar."""
    chave = identidade(transcritor)
    if chave is None:
        return transcritor
    return TranscritorEmCache(transcritor, chave, cache_dir / "transcricoes")
