"""MuscriptorTranscriber — parsing puro rápido, mais um teste contra o modelo real.

O JSONL do MuScriptor emite `start` e `end` em linhas separadas, ligadas por
`index` ↔ `start_event_index`. O parsing é lógica pura e se testa sem I/O; a
chamada ao modelo é I/O de verdade e tem teste real marcado como `slow`
(Regra 3 — mock não cobriria mudança de formato de saída).
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from thoth.adapters.transcription.muscriptor import (
    MuscriptorTranscriber,
    parse_jsonl,
    trechos_sem_nota,
)

JSONL = """\
{"type": "start", "pitch": 23, "start_time": 0.22, "index": 0, "instrument": "electric_bass"}
{"type": "end", "end_time": 0.36, "start_event_index": 0}
{"type": "start", "pitch": 60, "start_time": 0.10, "index": 1, "instrument": "acoustic_piano"}
{"type": "end", "end_time": 0.90, "start_event_index": 1}
{"type": "start", "pitch": 35, "start_time": 0.50, "index": 2, "instrument": "electric_bass"}
{"type": "end", "end_time": 0.75, "start_event_index": 2}
"""


def test_le_notas_de_todos_os_instrumentos() -> None:
    notas = parse_jsonl(JSONL)

    assert [n.pitch for n in notas] == [60, 23, 35]
    assert [n.instrument for n in notas] == ["acoustic_piano", "electric_bass", "electric_bass"]


def test_ordena_por_onset_e_nao_pela_ordem_do_arquivo() -> None:
    """O piano aparece depois no arquivo e antes no tempo."""
    assert [n.onset_s for n in parse_jsonl(JSONL)] == [0.10, 0.22, 0.50]


def test_filtra_por_instrumento() -> None:
    notas = parse_jsonl(JSONL, instrument="electric_bass")

    assert [n.pitch for n in notas] == [23, 35]
    assert [(n.onset_s, n.offset_s) for n in notas] == [(0.22, 0.36), (0.50, 0.75)]


def test_nota_sem_evento_de_fim_nao_some_nem_tem_duracao_negativa() -> None:
    """Truncamento no fim do áudio não pode derrubar a transcrição inteira."""
    truncado = (
        '{"type": "start", "pitch": 40, "start_time": 1.0, "index": 0, "instrument": "drums"}\n'
    )

    (nota,) = parse_jsonl(truncado)

    assert nota.pitch == 40
    assert nota.offset_s > nota.onset_s


def test_linha_vazia_e_ignorada() -> None:
    assert parse_jsonl("\n\n") == []


def test_comando_nunca_usa_instruments(tmp_path: Path) -> None:
    """ADR-008: condicionar o decoder degrada a saída; o filtro é nosso, depois."""
    comando = MuscriptorTranscriber()._comando(tmp_path / "a.wav", tmp_path / "b.jsonl")

    assert "--instruments" not in comando
    assert comando[comando.index("-m") + 1] == "small"  # ADR-009
    assert comando[comando.index("--detect-tempo") + 1] == "false"  # checkpoint inacessível


#: Soundfont do sistema (pacote `fluid-soundfont-gm`), usada como fonte sonora real.
SOUNDFONT = Path("/usr/share/soundfonts/FluidR3_GM.sf2")


@pytest.mark.slow
def test_transcreve_audio_real(tmp_path: Path) -> None:
    """Contra o modelo real, com som de instrumento real (fluidsynth + FluidR3).

    Duas armadilhas medidas em 2026-09-22, ambas ao escrever este teste:

    1. Onda sintética pura (seno, triangular) faz o MuScriptor devolver **zero**
       notas — material fora da distribuição de treino, sem ataque nem timbre.
       Daí a renderização com soundfont, como nas fixtures da Fase 0.
    2. A fixture precisa ser **longa**. Com 5 notas (2,9 s) o modelo acerta as
       alturas e rotula tudo como `acoustic_piano`; com 15 notas (8 s), mesmo
       timbre e mesmo programa GM, rotula `electric_bass`. O rótulo depende de
       contexto, e o filtro por rótulo descartaria a linha inteira.
    """
    import pretty_midi

    if not SOUNDFONT.exists() or shutil.which("fluidsynth") is None:
        pytest.skip("requer fluidsynth e FluidR3_GM.sf2 instalados")

    esperadas = [36, 38, 40, 41, 43, 45, 47, 48, 47, 45, 43, 41, 40, 38, 36]
    midi = pretty_midi.PrettyMIDI()
    baixo = pretty_midi.Instrument(program=33)  # GM Electric Bass (finger)
    for i, pitch in enumerate(esperadas):
        baixo.notes.append(
            pretty_midi.Note(velocity=100, pitch=pitch, start=0.2 + i * 0.5, end=0.65 + i * 0.5)
        )
    midi.instruments.append(baixo)
    mid = tmp_path / "linha.mid"
    midi.write(str(mid))

    bruto, wav = tmp_path / "bruto.wav", tmp_path / "linha.wav"
    subprocess.run(
        ["fluidsynth", "-ni", "-q", "-F", str(bruto), "-r", "44100", str(SOUNDFONT), str(mid)],
        check=True,
    )
    # O fluidsynth rende baixo demais; sem normalizar, o modelo erra por volume.
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(bruto), "-af", "volume=12dB", str(wav)],
        check=True,
    )

    notas = MuscriptorTranscriber().transcribe(wav, instrument="electric_bass")

    assert notas, "o modelo real não devolveu nenhuma nota de baixo"
    assert all(n.offset_s > n.onset_s for n in notas)
    # Afrouxado de propósito: o critério de qualidade é o F1 do teste de
    # regressão, não este teste. Aqui só se verifica que o adapter conversa
    # com o modelo e devolve algo do registro certo.
    assert min(n.pitch for n in notas) >= 24
    assert max(n.pitch for n in notas) <= 60


# --- Buraco do prelude forcing (emenda do ADR-008, 2026-09-25) --------------------

#: Finge ser o MuScriptor: com o prelude forcing (padrão) só transcreve até
#: `CORTE_S`, como em *Eyrie*; sem ele, transcreve tudo com outra altura, para o
#: teste saber de qual passada cada nota veio. Cada chamada fica registrada.
FALSO = """\
import json, sys
from pathlib import Path
args = sys.argv[1:]
Path(args[args.index("--log") + 1]).open("a").write(" ".join(args) + "\\n")
sem_prelude = "--no-prelude-forcing" in args
fim = {duracao} if sem_prelude else {corte}
pitch = 40 if sem_prelude else 30
linhas = []
t, i = 0.25, 0
while t < fim:
    linhas.append({{"type": "start", "pitch": pitch, "start_time": t, "index": i,
                   "instrument": "electric_bass"}})
    linhas.append({{"type": "end", "end_time": t + 0.3, "start_event_index": i}})
    t, i = t + 0.5, i + 1
Path(args[args.index("-o") + 1]).write_text("\\n".join(json.dumps(x) for x in linhas))
"""


def _falso(tmp_path: Path, corte: float, duracao: float) -> tuple[MuscriptorTranscriber, Path]:
    import sys

    script, log = tmp_path / "falso.py", tmp_path / "chamadas.log"
    script.write_text(FALSO.format(corte=corte, duracao=duracao))
    # `--log` vai no fim do comando; o falso o lê, o MuScriptor real nunca o recebe.
    return MuscriptorTranscriber(binary=(sys.executable, str(script), "--log", str(log))), log


def _stem(tmp_path: Path, duracao: float) -> Path:
    """Baixo soando o tempo todo: ruído grave constante basta para a energia."""
    import numpy as np
    import soundfile as sf

    sr = 22050
    t = np.arange(int(duracao * sr)) / sr
    caminho = tmp_path / "bass.wav"
    sf.write(caminho, 0.2 * np.sin(2 * np.pi * 55 * t), sr)
    return caminho


def test_trecho_soando_sem_nota_e_buraco() -> None:
    energia = [-20.0] * 60
    onsets = [t / 2 for t in range(0, 40)] + [t / 2 for t in range(80, 120)]  # nada de 20 a 40 s

    (buraco,) = trechos_sem_nota(energia, onsets)

    assert 20 <= buraco[0] <= 23
    assert 37 <= buraco[1] <= 40


def test_silencio_sem_nota_nao_e_buraco() -> None:
    energia = [-20.0] * 20 + [-90.0] * 20 + [-20.0] * 20
    onsets = [t / 2 for t in range(0, 40)] + [t / 2 for t in range(80, 120)]

    assert trechos_sem_nota(energia, onsets) == []


def test_pausa_curta_nao_e_buraco() -> None:
    """Uma pausa de poucos segundos é música, não o modelo travado."""
    energia = [-20.0] * 60
    onsets = [t / 2 for t in range(0, 60)] + [t / 2 for t in range(72, 120)]  # 6 s sem nota

    assert trechos_sem_nota(energia, onsets) == []


def test_buraco_e_preenchido_pela_passada_sem_prelude(tmp_path: Path) -> None:
    transcritor, log = _falso(tmp_path, corte=20.0, duracao=60.0)

    notas = transcritor.transcribe(_stem(tmp_path, 60.0))

    chamadas = log.read_text().splitlines()
    assert len(chamadas) == 2
    assert "--no-prelude-forcing" in chamadas[1]
    primeira = [n for n in notas if n.pitch == 30]
    segunda = [n for n in notas if n.pitch == 40]
    fim_1 = max(n.onset_s for n in primeira)
    ini_2, fim_2 = min(n.onset_s for n in segunda), max(n.onset_s for n in segunda)
    print(f"primeira passada até {fim_1:.2f} s, segunda de {ini_2:.2f} a {fim_2:.2f} s")
    assert max(n.onset_s for n in primeira) < 20
    assert min(n.onset_s for n in segunda) >= 20  # a segunda só entra no buraco
    # ... mas entra logo: a vizinhança que atrasa o início do buraco não pode virar lacuna.
    assert min(n.onset_s for n in segunda) < 20.5
    assert max(n.onset_s for n in segunda) > 55
    assert [n.onset_s for n in notas] == sorted(n.onset_s for n in notas)


def test_sem_buraco_nao_ha_segunda_passada(tmp_path: Path) -> None:
    transcritor, log = _falso(tmp_path, corte=60.0, duracao=60.0)

    notas = transcritor.transcribe(_stem(tmp_path, 60.0))

    assert len(log.read_text().splitlines()) == 1
    assert {n.pitch for n in notas} == {30}


# --- Silêncio na frente do áudio (ADR-045) ------------------------------------------

#: Finge ser o MuScriptor que ouve de verdade: dá uma nota no primeiro instante com som
#: do áudio que recebeu, mais as de `--extras` (instantes no áudio recebido).
OUVINTE = """\
import json, sys
from pathlib import Path
import numpy as np
import soundfile as sf
args = sys.argv[1:]
y, sr = sf.read(args[args.index("transcribe") + 1], always_2d=True)
t0 = float(np.flatnonzero(np.abs(y).max(axis=1) > 1e-4)[0] / sr)
Path(args[args.index("--log") + 1]).write_text(f"{t0} {args[args.index('transcribe') + 1]}")
eventos = [(t0, t0 + 0.3), *json.loads(args[args.index("--extras") + 1])]
linhas = []
for i, (ini, fim) in enumerate(eventos):
    linhas.append({"type": "start", "pitch": 40 + i, "start_time": ini, "index": i,
                   "instrument": "electric_bass"})
    linhas.append({"type": "end", "end_time": fim, "start_event_index": i})
Path(args[args.index("-o") + 1]).write_text("\\n".join(json.dumps(x) for x in linhas))
"""


#: O valor que a bateria usa (ADR-045); aqui só precisa ser maior que zero.
SILENCIO = 0.1


def _ouvinte(
    tmp_path: Path, extras: list[tuple[float, float]], silencio: float = SILENCIO
) -> MuscriptorTranscriber:
    """O instante do primeiro som ouvido e o arquivo recebido ficam em `ouvido.txt`."""
    import json
    import sys

    script = tmp_path / "ouvinte.py"
    script.write_text(OUVINTE)
    return MuscriptorTranscriber(
        binary=(
            sys.executable, str(script),
            "--extras", json.dumps(extras), "--log", str(tmp_path / "ouvido.txt"),
        ),
        silencio_inicial_s=silencio,
    )


def _ouvido(tmp_path: Path) -> tuple[float, str]:
    t0, caminho = (tmp_path / "ouvido.txt").read_text().split(" ", 1)
    return float(t0), caminho


def test_sem_silencio_o_modelo_recebe_o_arquivo_original(tmp_path: Path) -> None:
    """ADR-045: o silêncio troca o rótulo do baixo (`walking` vira piano); o padrão é 0,
    e com 0 o caminho do baixo é o de antes, sem nem regravar o áudio."""
    stem = _stem(tmp_path, 10.0)

    (nota,) = _ouvinte(tmp_path, [], silencio=0.0).transcribe(stem)

    assert MuscriptorTranscriber().silencio_inicial_s == 0.0
    assert _ouvido(tmp_path)[1] == str(stem)
    assert nota.onset_s == pytest.approx(0.0, abs=1e-3)


def test_modelo_recebe_silencio_na_frente_e_o_tempo_volta_ao_original(tmp_path: Path) -> None:
    """ADR-045: o MuScriptor perde ataques de bateria no começo do áudio."""
    (nota,) = _ouvinte(tmp_path, []).transcribe(_stem(tmp_path, 10.0))

    assert _ouvido(tmp_path)[0] == pytest.approx(SILENCIO, abs=1e-3)
    # O ouvinte deu a nota onde ouviu o primeiro som; descontado, é 0 no áudio original.
    assert nota.onset_s == pytest.approx(0.0, abs=1e-3)
    assert nota.offset_s == pytest.approx(0.3, abs=1e-3)


def test_nota_inteira_dentro_do_silencio_e_descartada(tmp_path: Path) -> None:
    """Som que não existe no áudio original não pode virar nota."""
    extras = [(0.0, SILENCIO / 2)]

    notas = _ouvinte(tmp_path, extras).transcribe(_stem(tmp_path, 10.0))

    assert [n.pitch for n in notas] == [40]


def test_nota_que_atravessa_o_fim_do_silencio_comeca_em_zero(tmp_path: Path) -> None:
    extras = [(SILENCIO / 2, SILENCIO + 0.5)]

    notas = _ouvinte(tmp_path, extras).transcribe(_stem(tmp_path, 10.0))

    atravessa = next(n for n in notas if n.pitch == 41)
    assert atravessa.onset_s == 0.0
    assert atravessa.offset_s == pytest.approx(0.5, abs=1e-3)


@pytest.mark.slow
def test_taxonomia_do_escopo_multi_instrumento_existe_no_motor() -> None:
    """Os rótulos que os perfis do ADR-044 aceitam precisam existir no motor fixado.

    Uma troca de nome no MuScriptor faria um perfil filtrar tudo em silêncio.
    """
    from thoth.domain.instrumentos import PERFIS

    saida = subprocess.run(
        [*MuscriptorTranscriber().binary, "list-instruments"],
        check=True, capture_output=True, text=True,
    ).stdout
    observados = set(saida.split())
    esperados = set().union(*(p.rotulos for p in PERFIS.values()))

    assert esperados <= observados, f"faltam {esperados - observados}; motor: {sorted(observados)}"
