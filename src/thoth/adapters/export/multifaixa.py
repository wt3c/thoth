"""Composição de partituras já quantizadas em arquivos multifaixa."""

from __future__ import annotations

import copy
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

import guitarpro as gp


def _compasso_vazio(faixa: gp.Track, cabecalho: gp.MeasureHeader) -> gp.Measure:
    compasso = gp.Measure(faixa, cabecalho)
    voz = gp.Voice(compasso)
    pausa = gp.Beat(voz, duration=gp.Duration(value=gp.Duration.whole))
    pausa.status = gp.BeatStatus.rest
    voz.beats.append(pausa)
    compasso.voices = [voz, *(gp.Voice(compasso) for _ in range(3))]
    return compasso


@dataclass(frozen=True, slots=True)
class CompositorGp5:
    """Reúne faixas GP5 sem reinterpretar notas ou ritmo."""

    def combinar(self, entradas: list[Path], saida: Path) -> Path:
        if not entradas:
            raise ValueError("sem partituras GP5 para combinar")

        fontes = [gp.parse(str(caminho)) for caminho in entradas]
        musica = copy.deepcopy(max(fontes, key=lambda fonte: len(fonte.measureHeaders)))
        musica.tracks.clear()

        canal_melodico = 0
        for fonte in fontes:
            for original in fonte.tracks:
                faixa = copy.deepcopy(original)
                faixa.song = musica
                faixa.number = len(musica.tracks) + 1
                indice_canal = 9 if faixa.isPercussionTrack else canal_melodico
                if not faixa.isPercussionTrack:
                    canal_melodico += 1
                    if canal_melodico == 9:
                        canal_melodico += 1
                faixa.channel.channel = indice_canal
                faixa.channel.effectChannel = indice_canal
                faixa.measures = faixa.measures[: len(musica.measureHeaders)]
                for indice, compasso in enumerate(faixa.measures):
                    compasso.track = faixa
                    compasso.header = musica.measureHeaders[indice]
                    for voz in compasso.voices:
                        voz.measure = compasso
                        for beat in voz.beats:
                            beat.voice = voz
                while len(faixa.measures) < len(musica.measureHeaders):
                    faixa.measures.append(
                        _compasso_vazio(faixa, musica.measureHeaders[len(faixa.measures)])
                    )
                musica.tracks.append(faixa)

        saida.parent.mkdir(parents=True, exist_ok=True)
        gp.write(musica, str(saida))
        return saida


def _com_ids_unicos(elementos: list[ET.Element], prefixo: str) -> None:
    ids = {
        elemento.attrib["id"]
        for raiz in elementos
        for elemento in raiz.iter()
        if "id" in elemento.attrib
    }
    mapa = {identificador: f"{prefixo}-{identificador}" for identificador in ids}
    for raiz in elementos:
        for elemento in raiz.iter():
            if (identificador := elemento.attrib.get("id")) in mapa:
                elemento.attrib["id"] = mapa[identificador]


@dataclass(frozen=True, slots=True)
class CompositorMusicXml:
    """Reúne listas de partes MusicXML e elimina colisões de identificadores."""

    def combinar(self, entradas: list[Path], saida: Path) -> Path:
        if not entradas:
            raise ValueError("sem partituras MusicXML para combinar")

        raizes = [ET.parse(caminho).getroot() for caminho in entradas]
        destino = copy.deepcopy(raizes[0])
        lista_destino = destino.find("part-list")
        if lista_destino is None:
            raise ValueError("MusicXML sem part-list")
        lista_destino.clear()
        for parte in list(destino.findall("part")):
            destino.remove(parte)

        for indice, raiz in enumerate(raizes, start=1):
            lista = raiz.find("part-list")
            if lista is None:
                raise ValueError("MusicXML sem part-list")
            declaracoes = [copy.deepcopy(elemento) for elemento in list(lista)]
            partes = [copy.deepcopy(parte) for parte in raiz.findall("part")]
            elementos = [*declaracoes, *partes]
            _com_ids_unicos(elementos, f"T{indice}")
            for declaracao in declaracoes:
                if "number" in declaracao.attrib:
                    declaracao.attrib["number"] = f"{indice}-{declaracao.attrib['number']}"
                lista_destino.append(declaracao)
            destino.extend(partes)

        saida.parent.mkdir(parents=True, exist_ok=True)
        ET.ElementTree(destino).write(saida, encoding="utf-8", xml_declaration=True)
        return saida
