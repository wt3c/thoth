"""O guia lê GP5 binário real, inclusive a estrutura rítmica após releitura."""

from __future__ import annotations

from pathlib import Path

import guitarpro as gp
from typer.testing import CliRunner

from thoth.adapters.export.gp5 import Gp5Exporter
from thoth.cli import app
from thoth.domain.models import TUNING_BASS_4, NoteEvent, TabNote
from thoth.services.fretboard import ViterbiFretAssigner
from thoth.services.guia_estudo import gerar_guia


def _tab(destino: Path) -> Path:
    eventos = [
        NoteEvent(28, 0.0, 0.5, "electric_bass"),
        NoteEvent(35, 0.5, 1.0, "electric_bass"),
        NoteEvent(40, 1.0, 1.5, "electric_bass"),
    ]
    notas = [TabNote(eventos[0], 0, 0), TabNote(eventos[1], 1, 2), TabNote(eventos[2], 2, 2)]
    return Gp5Exporter(bpm=120, titulo="Exercício").export(notas, destino, TUNING_BASS_4)


def test_guia_explica_cada_nota_intervalos_e_padrao_com_gp5_real(tmp_path: Path) -> None:
    guia = gerar_guia(_tab(tmp_path / "exercicio.gp5"), tom="E menor")

    assert "Exercício" in guia
    assert "E1" in guia and "B1" in guia and "E2" in guia
    assert "quinta justa ascendente" in guia
    assert "fundamental-quinta-oitava" in guia
    assert "1º grau" in guia and "5º grau" in guia
    assert "Compasso 1" in guia
    assert "hammer-on" in guia and "não determinada" in guia
    assert "não prova" in guia


def test_guia_nao_converte_ligadura_de_sustentacao_em_novo_ataque(tmp_path: Path) -> None:
    evento = NoteEvent(28, 1.75, 2.5, "electric_bass")
    tab = Gp5Exporter(bpm=120).export(
        [TabNote(evento, 0, 0)], tmp_path / "ligada.gp5", TUNING_BASS_4
    )

    guia = gerar_guia(tab)

    assert guia.count("**E1**") == 1
    assert "ligadura de sustentação" in guia
    assert "compasso 2" in guia


def test_guia_explica_ligadura_dentro_do_mesmo_compasso(tmp_path: Path) -> None:
    evento = NoteEvent(28, 0.0, 0.625, "electric_bass")
    tab = Gp5Exporter(bpm=120).export(
        [TabNote(evento, 0, 0)], tmp_path / "duracao.gp5", TUNING_BASS_4
    )

    guia = gerar_guia(tab)

    assert guia.count("**E1**") == 1
    assert "ligada a outra figura no mesmo compasso" in guia


def test_guia_sem_tom_mostra_candidato_sem_afirmar_acorde(tmp_path: Path) -> None:
    guia = gerar_guia(_tab(tmp_path / "sem_tom.gp5"))

    assert "tom candidato" in guia
    assert "estimado das notas da tablatura" in guia
    assert "margem" in guia
    assert "não confirma a tônica nem o modo" in guia
    assert "acorde não conhecido" in guia


def test_guia_estima_tom_de_linha_de_baixo_em_gp5_real(tmp_path: Path) -> None:
    alturas = [29, 32, 34, 36, 39, 29, 36, 34, 32, 29, 39, 36] * 3
    eventos = [
        NoteEvent(p, i * 0.5, (i + 1) * 0.5, "electric_bass")
        for i, p in enumerate(alturas)
    ]
    tab = Gp5Exporter(bpm=120).export(
        ViterbiFretAssigner().assign(eventos, TUNING_BASS_4),
        tmp_path / "fa_menor.gp5", TUNING_BASS_4,
    )

    guia = gerar_guia(tab)

    assert "tom candidato: F menor" in guia
    assert "Ab" in guia
    assert "grau se o tom candidato estiver correto" in guia.lower()
    assert "não confirma a tônica nem o modo" in guia


def test_tom_informado_prevalece_sobre_estimativa_da_tab(tmp_path: Path) -> None:
    guia = gerar_guia(_tab(tmp_path / "manual.gp5"), tom="E menor")

    assert "informada por você" in guia
    assert "tom candidato" not in guia


def test_guia_relata_tecnica_so_quando_gp5_a_marca(tmp_path: Path) -> None:
    tab = _tab(tmp_path / "tecnica.gp5")
    song = gp.parse(str(tab))
    notas = [
        nota for medida in song.tracks[0].measures
        for beat in medida.voices[0].beats for nota in beat.notes
    ]
    notas[1].effect.hammer = True
    gp.write(song, str(tab))

    guia = gerar_guia(tab)

    assert guia.count("ligado por hammer-on/pull-off (marcação GP5)") == 1
    assert guia.count("Técnica:** não determinada") == 2


def test_guia_explica_figura_ritmica_e_rejeita_tom_invalido(tmp_path: Path) -> None:
    tab = _tab(tmp_path / "figuras.gp5")

    guia = gerar_guia(tab)
    assert "semínima" in guia
    assert "figura escrita" in guia
    resultado = CliRunner().invoke(app, ["estudar", str(tab), "--tom", "xyz"])
    assert resultado.exit_code != 0
    assert "não é um tom" in resultado.output


def test_guia_escreve_graus_com_grafia_da_escala_informada(tmp_path: Path) -> None:
    evento = NoteEvent(29, 0.0, 0.5, "electric_bass")
    tab = Gp5Exporter(bpm=120).export(
        [TabNote(evento, 0, 1)], tmp_path / "grafia.gp5", TUNING_BASS_4
    )

    guia = gerar_guia(tab, tom="F# maior")

    assert "F#, G#, A#, B, C#, D#, E#" in guia
    assert "**E#1**" in guia
    assert "7º grau" in guia


def test_guia_escreve_subdivisao_legivel_para_iniciante(tmp_path: Path) -> None:
    evento = NoteEvent(28, 0.375, 0.5, "electric_bass")
    tab = Gp5Exporter(bpm=120).export(
        [TabNote(evento, 0, 0)], tmp_path / "subdivisao.gp5", TUNING_BASS_4
    )

    guia = gerar_guia(tab)

    assert "tempo 1 + 3/4" in guia
    assert "meio pulso" in guia


def test_guia_de_gp5_antigo_prefere_nome_do_arquivo_a_titulo_mix(tmp_path: Path) -> None:
    eventos = [NoteEvent(28, 0.0, 0.5, "electric_bass")]
    tab = Gp5Exporter(bpm=120, titulo="mix").export(
        [TabNote(eventos[0], 0, 0)], tmp_path / "Eyrie.todos.gp5", TUNING_BASS_4
    )

    guia = gerar_guia(tab)

    assert guia.startswith("# Guia de estudo — Eyrie\n")


def test_guia_explica_quando_o_baixo_entra_depois_do_primeiro_compasso(
    tmp_path: Path,
) -> None:
    evento = NoteEvent(28, 2.0, 2.5, "electric_bass")
    tab = Gp5Exporter(bpm=120).export(
        [TabNote(evento, 0, 0)], tmp_path / "entrada.gp5", TUNING_BASS_4
    )

    guia = gerar_guia(tab)

    assert "primeiro ataque no compasso 2" in guia
    assert "compassos anteriores" in guia


def test_cli_estudar_grava_markdown_ao_lado_da_tab(tmp_path: Path) -> None:
    tab = _tab(tmp_path / "exercicio.gp5")

    resultado = CliRunner().invoke(app, ["estudar", str(tab), "--tom", "E menor"])

    assert resultado.exit_code == 0, resultado.output
    markdown = tmp_path / "exercicio.estudo.md"
    assert markdown.is_file()
    assert "fundamental-quinta-oitava" in markdown.read_text(encoding="utf-8")
    assert str(markdown) in resultado.output


def test_cli_estudar_recusa_arquivo_inexistente(tmp_path: Path) -> None:
    resultado = CliRunner().invoke(app, ["estudar", str(tmp_path / "ausente.gp5")])

    assert resultado.exit_code != 0
    assert "não existe" in resultado.output
