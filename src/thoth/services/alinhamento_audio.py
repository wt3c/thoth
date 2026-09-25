"""Tab humana levada ao tempo do stem do baixo por DTW sobre croma (ADR-042).

O alinhamento do ADR-041 usa a transcrição, e por isso não pode julgar a nota: o encaixe
foi escolhido para os nomes coincidirem. Este usa só o áudio, e a transcrição fica livre
para ser julgada.

Os parâmetros saíram da medição do ADR-042, e cada um corrigiu uma falha vista nela:

- **`subseq=False`**: a tab cobre a música inteira; com subsequência o caminho colapsou
  num trecho de 60 s.
- **um 13º bin de silêncio**, nos dois lados: sem ele, quadro sem nota da tab (croma
  uniforme) e quadro quieto do áudio (croma normalizado, que faz ruído parecer nota) se
  pareciam com qualquer coisa, e o DTW ficou no piso de acaso.
- **`norm=None` e normalização L2 à mão, distância euclidiana** — pelo mesmo motivo.
- **banda de Sakoe-Chiba de 10%**: o caminho não salta para outra repetição do riff.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import librosa
import numpy as np

from thoth.domain.models import NoteEvent

SR = 22050
HOP = 2048  # ~93 ms
BANDA = 0.1
#: Quadro de áudio abaixo deste percentil de energia conta como silêncio.
PERCENTIL_DO_SILENCIO = 15
#: A nota da tab decai no croma dela, como a corda decai no áudio.
DECAIMENTO = (1.0, 0.4)


def _croma_do_audio(y: np.ndarray) -> np.ndarray:
    croma = librosa.feature.chroma_cqt(
        y=y, sr=SR, hop_length=HOP, fmin=librosa.note_to_hz("A0"), n_octaves=5, norm=None
    )
    energia = croma.sum(axis=0)
    silencio = energia < np.percentile(energia, PERCENTIL_DO_SILENCIO)
    croma = croma / (np.linalg.norm(croma, axis=0, keepdims=True) + 1e-9)
    croma[:, silencio] = 0
    return np.vstack([croma, silencio[None].astype(float)])


def _croma_da_tab(referencia: Sequence[NoteEvent]) -> np.ndarray:
    quadros = int(max(n.offset_s for n in referencia) * SR / HOP) + 2
    croma = np.zeros((13, quadros))
    for n in referencia:
        i, j = int(n.onset_s * SR / HOP), int(n.offset_s * SR / HOP) + 1
        croma[n.pitch % 12, i:j] += np.linspace(*DECAIMENTO, max(j - i, 1))
    croma[12, croma[:12].sum(axis=0) == 0] = 1.0
    croma /= np.linalg.norm(croma, axis=0, keepdims=True)
    return croma


def alinhar_ao_stem(referencia: Sequence[NoteEvent], stem: Path) -> list[NoteEvent]:
    """Cada nota da tab no instante do stem em que o DTW a põe — altura intocada."""
    if not referencia:
        raise ValueError("a tab não tem notas")
    y, _ = librosa.load(stem, sr=SR)
    _, caminho = librosa.sequence.dtw(
        X=_croma_da_tab(referencia),
        Y=_croma_do_audio(y),
        metric="euclidean",
        subseq=False,
        global_constraints=True,
        band_rad=BANDA,
    )
    caminho = caminho[::-1]
    # O caminho pode parar vários quadros de áudio num quadro da tab: fica a média.
    quadros_tab = np.unique(caminho[:, 0])
    quadros_audio = np.array([caminho[caminho[:, 0] == k, 1].mean() for k in quadros_tab])
    ataques = np.interp(
        [n.onset_s for n in referencia], quadros_tab * HOP / SR, quadros_audio * HOP / SR
    )
    return [
        NoteEvent(n.pitch, float(t), float(t) + (n.offset_s - n.onset_s), n.instrument)
        for n, t in zip(referencia, ataques, strict=True)
    ]
