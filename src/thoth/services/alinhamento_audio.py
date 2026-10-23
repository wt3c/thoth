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
- **ajuste fino pelos ataques do stem**: o DTW anda em quadros de ~93 ms e deixava a tab
  18 a 50 ms atrasada; o desvio mediano até os ataques detectados no próprio stem é
  descontado da música inteira (emenda de 2026-09-30 ao ADR-042). Continua sem olhar a transcrição.
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
#: Resolução da detecção de ataques do ajuste fino: ~6 ms, bem abaixo do quadro do DTW.
HOP_DO_ATAQUE = 128
#: Só entram no desvio as notas com ataque detectado até aqui: a de quem o DTW errou por
#: uma nota inteira puxaria a mediana para a vizinha.
ALCANCE_DO_AJUSTE_S = 0.1
VOLTAS_DO_AJUSTE = 10


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


def _desvio_ate_os_ataques(ataques: np.ndarray, y: np.ndarray) -> float:
    """Mediana, com sinal, de cada nota alinhada até o ataque do stem mais próximo.

    Um número para a música inteira: medido nas cinco tabs humanas, desvio por trecho
    ou por nota não ganhou do global em nenhuma e perdeu em algumas. A janela de
    `ALCANCE_DO_AJUSTE_S` é recentrada até parar: em volta do ponto de partida ela corta a
    cauda do lado para onde o DTW errou e a mediana sai encolhida (+45 ms viravam +28
    numa volta, +3 em cinco).
    """
    detectados = librosa.onset.onset_detect(y=y, sr=SR, hop_length=HOP_DO_ATAQUE, units="time")
    if len(detectados) < 2:
        return 0.0
    desvio = 0.0
    for _ in range(VOLTAS_DO_AJUSTE):
        movidos = ataques + desvio
        i = np.clip(np.searchsorted(detectados, movidos), 1, len(detectados) - 1)
        antes, depois = detectados[i - 1] - movidos, detectados[i] - movidos
        residuo = np.where(np.abs(antes) <= np.abs(depois), antes, depois)
        perto = residuo[np.abs(residuo) <= ALCANCE_DO_AJUSTE_S]
        if not len(perto):
            break
        passo = float(np.median(perto))
        desvio += passo
        if abs(passo) < 0.001:
            break
    return desvio


def _media_por_quadro(caminho: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Cada quadro da tab e a média dos quadros de áudio em que o caminho passa nele.

    O caminho pode parar vários quadros de áudio num quadro da tab. Somar por
    `bincount` é uma passada só; filtrar o caminho inteiro por quadro era quadrático.
    """
    quadros_tab, quadro = np.unique(caminho[:, 0], return_inverse=True)
    return quadros_tab, np.bincount(quadro, weights=caminho[:, 1]) / np.bincount(quadro)


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
    quadros_tab, quadros_audio = _media_por_quadro(caminho[::-1])
    ataques = np.interp(
        [n.onset_s for n in referencia], quadros_tab * HOP / SR, quadros_audio * HOP / SR
    )
    ataques = ataques + _desvio_ate_os_ataques(ataques, y)
    return [
        NoteEvent(n.pitch, float(t), float(t) + (n.offset_s - n.onset_s), n.instrument)
        for n, t in zip(referencia, ataques, strict=True)
    ]
