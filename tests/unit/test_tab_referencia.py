"""Leitor de tab `.gp5` como referência (Camada 3, ADR-041).

Os arquivos são sintéticos, escritos pelo próprio PyGuitarPro: as tabs baixadas pelo
usuário são conteúdo de terceiros e não podem virar fixture de um repositório público.
Cada teste escreve e **relê** o arquivo — o leitor só vê o que sobrevive ao formato.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import guitarpro as gp
import pytest

from thoth.services.tab_referencia import ler_tab

GUITARRA = (64, 59, 55, 50, 45, 40)
BAIXO_4 = (43, 38, 33, 28)  # como o GP guarda: da corda mais aguda para a mais grave


@dataclass(frozen=True, slots=True)
class B:
    """Um beat: figura (4 = semínima) e, se houver, a nota na corda mais grave."""

    figura: int
    casa: int | None = None
    tipo: gp.NoteType = gp.NoteType.normal
    tempo: int | None = None


@dataclass(slots=True)
class Faixa:
    nome: str
    cordas: tuple[int, ...]
    compassos: list[list[B]]
    percussao: bool = False


def _gravar(
    tmp_path: Path,
    faixas: list[Faixa],
    *,
    bpm: int = 120,
    formulas: list[tuple[int, int]] | None = None,
    repeticoes: dict[int, dict[str, int | bool]] | None = None,
) -> Path:
    n = len(faixas[0].compassos)
    song = gp.Song(tempo=bpm)
    song.tracks.clear()
    song.measureHeaders.clear()
    for i in range(n):
        header = gp.MeasureHeader(number=i + 1)
        if formulas:
            num, den = formulas[i]
            header.timeSignature = gp.TimeSignature(
                numerator=num, denominator=gp.Duration(value=den)
            )
        for chave, valor in (repeticoes or {}).get(i, {}).items():
            setattr(header, chave, valor)
        song.addMeasureHeader(header)

    for numero, f in enumerate(faixas, start=1):
        track = gp.Track(song, number=numero, name=f.nome)
        track.isPercussionTrack = f.percussao
        track.strings = [gp.GuitarString(i + 1, v) for i, v in enumerate(f.cordas)]
        track.measures.clear()
        for header, beats in zip(song.measureHeaders, f.compassos, strict=True):
            medida = gp.Measure(track, header)
            voz = gp.Voice(medida)
            for b in beats:
                beat = gp.Beat(voz, duration=gp.Duration(value=b.figura))
                if b.casa is None:
                    beat.status = gp.BeatStatus.rest
                else:
                    beat.status = gp.BeatStatus.normal
                    beat.notes.append(
                        gp.Note(beat, value=b.casa, string=len(f.cordas), type=b.tipo)
                    )
                if b.tempo is not None:
                    beat.effect.mixTableChange = gp.MixTableChange(
                        tempo=gp.MixTableItem(value=b.tempo)
                    )
                voz.beats.append(beat)
            medida.voices = [voz, gp.Voice(medida)]
            track.measures.append(medida)
        song.tracks.append(track)

    destino = tmp_path / "ref.gp5"
    gp.write(song, str(destino))
    return destino


def _baixo(compassos: list[list[B]]) -> Faixa:
    return Faixa("Baixo", BAIXO_4, compassos)


def _ataques(caminho: Path) -> list[tuple[float, int]]:
    return [(round(n.onset_s, 4), n.pitch) for n in ler_tab(caminho).notas]


def test_notas_em_segundos_no_andamento_da_musica(tmp_path: Path) -> None:
    arq = _gravar(tmp_path, [_baixo([[B(4, 0), B(4, 2), B(4, 3), B(4, 5)]])])

    notas = ler_tab(arq).notas

    assert [(n.onset_s, n.offset_s, n.pitch) for n in notas] == [
        (0.0, 0.5, 28),
        (0.5, 1.0, 30),
        (1.0, 1.5, 31),
        (1.5, 2.0, 33),
    ]
    assert {n.instrument for n in notas} == {"electric_bass"}


def test_mudanca_de_andamento_em_outra_faixa_vale_para_o_baixo(tmp_path: Path) -> None:
    """Na tab de *Fear Is The Key* as seis mudanças estão na faixa da bateria."""
    baixo = _baixo([[B(1, 0)], [B(2, 0), B(2, 5)]])
    bateria = Faixa("Bateria", (0,) * 6, [[B(1)], [B(2), B(2, tempo=60)]], percussao=True)

    arq = _gravar(tmp_path, [baixo, bateria])

    # compasso 1: 2 s a 120; meia nota a 120 = 1 s; a segunda meia já a 60 = 2 s
    assert [(n.onset_s, n.offset_s) for n in ler_tab(arq).notas] == [
        (0.0, 2.0),
        (2.0, 3.0),
        (3.0, 5.0),
    ]


def test_compasso_que_nao_e_quatro_por_quatro(tmp_path: Path) -> None:
    arq = _gravar(
        tmp_path,
        [_baixo([[B(4, 0), B(4, 0), B(4, 0)], [B(8, 3), B(8, 3), B(8, 3)]])],
        formulas=[(3, 4), (3, 8)],
    )

    assert _ataques(arq) == [
        (0.0, 28),
        (0.5, 28),
        (1.0, 28),
        (1.5, 31),
        (1.75, 31),
        (2.0, 31),
    ]


def test_ligadura_estende_a_nota_anterior(tmp_path: Path) -> None:
    arq = _gravar(tmp_path, [_baixo([[B(2, 3), B(2, 3, gp.NoteType.tie)], [B(1, 5)]])])

    notas = ler_tab(arq).notas

    assert [(n.onset_s, n.offset_s, n.pitch) for n in notas] == [
        (0.0, 2.0, 31),
        (2.0, 4.0, 33),
    ]


def test_nota_morta_nao_tem_altura_e_fica_fora(tmp_path: Path) -> None:
    arq = _gravar(tmp_path, [_baixo([[B(2, 0), B(2, 0, gp.NoteType.dead)]])])

    assert _ataques(arq) == [(0.0, 28)]


def test_repeticao_toca_o_trecho_de_novo(tmp_path: Path) -> None:
    arq = _gravar(
        tmp_path,
        [_baixo([[B(1, 0)], [B(1, 2)], [B(1, 3)]])],
        repeticoes={1: {"isRepeatOpen": True, "repeatClose": 1}},
    )

    assert _ataques(arq) == [(0.0, 28), (2.0, 30), (4.0, 30), (6.0, 31)]


def test_final_alternativo_toca_so_na_sua_passada(tmp_path: Path) -> None:
    arq = _gravar(
        tmp_path,
        [_baixo([[B(1, 0)], [B(1, 2)], [B(1, 3)], [B(1, 5)]])],
        repeticoes={
            0: {"isRepeatOpen": True},
            1: {"repeatAlternative": 0b01, "repeatClose": 1},
            2: {"repeatAlternative": 0b10},
        },
    )

    # 1, final 1, 1 de novo, final 2, 4
    assert [p for _, p in _ataques(arq)] == [28, 30, 28, 31, 33]


def test_escolhe_sozinho_a_unica_faixa_de_baixo(tmp_path: Path) -> None:
    guitarra = Faixa("Guitarra", GUITARRA, [[B(1, 0)]])
    arq = _gravar(tmp_path, [guitarra, _baixo([[B(1, 0)]])])

    ref = ler_tab(arq)

    assert ref.faixa == "Baixo"
    assert [n.pitch for n in ref.notas] == [28]


def test_sem_faixa_de_baixo_recusa_listando_as_faixas(tmp_path: Path) -> None:
    arq = _gravar(tmp_path, [Faixa("Guitarra", GUITARRA, [[B(1, 0)]])])

    with pytest.raises(ValueError, match="1: Guitarra"):
        ler_tab(arq)


def test_duas_faixas_de_baixo_pedem_escolha(tmp_path: Path) -> None:
    arq = _gravar(
        tmp_path,
        [Faixa("Baixo A", BAIXO_4, [[B(1, 0)]]), Faixa("Baixo B", BAIXO_4, [[B(1, 5)]])],
    )

    with pytest.raises(ValueError, match="--faixa"):
        ler_tab(arq)
    assert [n.pitch for n in ler_tab(arq, faixa=2).notas] == [33]
