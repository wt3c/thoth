"""Tablatura GP5 de baixo → guia de estudo baseado nos ataques escritos.

Uma ligadura de duração não revela legato de execução (ADR-022, ADR-033).
Função de acorde, técnica e intenção só são fatos quando o arquivo as informa.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

import guitarpro as gp
from music21 import key, pitch

from thoth.services.notas import nome_da_nota
from thoth.services.tab_referencia import _faixa, _notas
from thoth.services.tonalidade import estimar_tom, tom_de_texto

_INTERVALOS = (
    "uníssono", "segunda menor", "segunda maior", "terça menor", "terça maior",
    "quarta justa", "trítono", "quinta justa", "sexta menor", "sexta maior",
    "sétima menor", "sétima maior", "oitava justa",
)
_GRAUS = ("1º", "2º", "3º", "4º", "5º", "6º", "7º")
_ESCALAS = {
    "maior": (0, 2, 4, 5, 7, 9, 11),
    "menor": (0, 2, 3, 5, 7, 8, 10),
}
_FIGURAS = {1: "semibreve", 2: "mínima", 4: "semínima", 8: "colcheia", 16: "semicolcheia"}
_FONTE_INTERVALOS = "https://open-musictheory.github.io/docs/fundamentals/intervals/"
_FONTE_RITMO = "https://openmusictheory.github.io/rhythmicValues.html"
_FONTE_ESCALAS = "https://open-musictheory.github.io/docs/fundamentals/scales/"
_FONTE_BAIXO = "https://www.fender.com/articles/techniques/how-to-play-bass-guitar"
_FONTE_TECNICA = "https://www.fender.com/articles/techniques/master-hammer-ons-and-pull-offs"
_FONTE_QUINTAS = (
    "https://hub.yamaha.com/guitars/bass/"
    "the-importance-of-roots-fifths-and-octaves-in-bass-playing/"
)


@dataclass(slots=True)
class _Nota:
    altura: int
    corda: int
    casa: int
    compasso: int
    tempo: float
    duracao: float
    figura: str
    ultimo_compasso: int
    continuacoes: int
    tecnica: tuple[str, ...]


def _nome(altura: int, *, bemois: bool) -> str:
    return f"{nome_da_nota(altura, bemois=bemois)}{altura // 12 - 1}"


def _nome_na_escala(altura: int, grafias: tuple[pitch.Pitch, ...] | None, *, bemois: bool) -> str:
    """A armadura pode pedir E# onde a escrita cromática padrão mostraria F."""
    if grafias is not None:
        for grau in grafias:
            if grau.pitchClass == altura % 12:
                for oitava in range(altura // 12 - 2, altura // 12 + 1):
                    if pitch.Pitch(f"{grau.name}{oitava}").midi == altura:
                        return f"{grau.name.replace('-', 'b')}{oitava}"
    return _nome(altura, bemois=bemois)


def _tecnicas(nota: gp.Note) -> tuple[str, ...]:
    """Somente marcações efetivamente codificadas na nota GP5."""
    efeito = nota.effect
    rotulos = []
    if efeito.hammer:
        rotulos.append("ligado por hammer-on/pull-off (marcação GP5)")
    if efeito.slides:
        rotulos.append("slide (marcação GP5)")
    if efeito.ghostNote:
        rotulos.append("nota fantasma (marcação GP5)")
    if efeito.palmMute:
        rotulos.append("palm mute (marcação GP5)")
    if efeito.vibrato:
        rotulos.append("vibrato (marcação GP5)")
    if efeito.bend is not None:
        rotulos.append("bend (marcação GP5)")
    if efeito.staccato:
        rotulos.append("staccato (marcação GP5)")
    return tuple(rotulos)


def _ler_notas(track: gp.Track) -> tuple[list[_Nota], int]:
    notas: list[_Nota] = []
    soando: dict[int, _Nota] = {}
    pausas = 0
    ppq = gp.Duration.quarterTime
    for numero, medida in enumerate(track.measures, start=1):
        for voz in medida.voices:
            for beat in voz.beats:
                if beat.status == gp.BeatStatus.rest:
                    pausas += 1
                tempo = 1 + (beat.start - medida.header.start) / ppq
                duracao = beat.duration.time / ppq
                for nota in beat.notes:
                    if nota.type == gp.NoteType.tie:
                        anterior = soando.get(nota.string)
                        if anterior is not None:
                            anterior.duracao += duracao
                            anterior.ultimo_compasso = numero
                            anterior.continuacoes += 1
                        continue
                    if nota.type != gp.NoteType.normal:
                        continue
                    altura = track.strings[nota.string - 1].value + nota.value
                    atual = _Nota(
                        altura=altura,
                        corda=nota.string,
                        casa=nota.value,
                        compasso=numero,
                        tempo=tempo,
                        duracao=duracao,
                        figura=_FIGURAS.get(beat.duration.value, f"1/{beat.duration.value}")
                        + (" pontuada" if beat.duration.isDotted else ""),
                        ultimo_compasso=numero,
                        continuacoes=0,
                        tecnica=_tecnicas(nota),
                    )
                    notas.append(atual)
                    soando[nota.string] = atual
    notas.sort(key=lambda n: (n.compasso, n.tempo, n.altura))
    return notas, pausas


def _intervalo(anterior: _Nota, atual: _Nota) -> str:
    diferenca = atual.altura - anterior.altura
    distancia = abs(diferenca)
    direcao = "ascendente" if diferenca > 0 else "descendente" if diferenca < 0 else "repetido"
    if distancia <= 12:
        nome = _INTERVALOS[distancia]
    elif distancia % 12 == 0:
        nome = f"{distancia // 12} oitavas"
    else:
        return f"intervalo composto {direcao} ({distancia} semitons)"
    return f"{nome} {direcao} ({distancia} semitons)"


def _tempo(posicao: float) -> str:
    inteiro = int(posicao)
    parte = Fraction(posicao - inteiro).limit_denominator(16)
    if not parte:
        return str(inteiro)
    return f"{inteiro} + {parte}"


def _possibilidade(anterior: _Nota | None, atual: _Nota, anteanterior: _Nota | None) -> str:
    if anterior is None:
        return (
            "Inicia a linha observada; o acorde não conhecido impede afirmar "
            "sua função harmônica."
        )
    salto = atual.altura - anterior.altura
    if anteanterior is not None and atual.altura - anteanterior.altura == 12:
        return (
            "Retoma a nota de dois ataques atrás uma oitava acima; a nota "
            "intermediária pode ligar os registros. A harmonia decide sua função."
        )
    if salto == 0:
        return "Repete a altura; pode reforçar o pulso ou criar um padrão rítmico."
    if abs(salto) % 12 == 0:
        return (
            "Repete a classe de nota em outra oitava; muda o registro sem mudar "
            "a classe de altura."
        )
    if abs(salto) % 12 == 7:
        return (
            "Forma uma quinta justa com a nota anterior; pode reforçar uma relação "
            "fundamental-quinta, se a harmonia confirmar."
        )
    if abs(salto) <= 2:
        return (
            "Move-se por um ou dois semitons; pode ser passagem escalar ou "
            "aproximação, conforme as notas e acordes ao redor."
        )
    return (
        "Cria um salto melódico; a finalidade harmônica depende dos acordes "
        "e do contexto da música."
    )


def _padroes(notas: list[_Nota]) -> list[str]:
    encontrados: list[str] = []
    for a, b, c in zip(notas, notas[1:], notas[2:], strict=False):
        if b.altura - a.altura == 7 and c.altura - a.altura == 12:
            encontrados.append(
                f"Compasso {a.compasso}: **fundamental-quinta-oitava** em "
                f"{_nome(a.altura, bemois=False)} → {_nome(b.altura, bemois=False)} → "
                f"{_nome(c.altura, bemois=False)}. A quinta reforça a primeira nota; "
                "a oitava repete sua classe em registro mais agudo. "
                "Chamá-la de fundamental do acorde depende da harmonia."
            )
    return encontrados


def gerar_guia(caminho: Path, *, faixa: int | None = None, tom: str | None = None) -> str:
    """Lê um GP5 local e produz Markdown sem executar o pipeline de áudio."""
    if not caminho.is_file():
        raise ValueError(f"{caminho} não existe")
    if caminho.suffix.lower() != ".gp5":
        raise ValueError("o guia lê tablatura .gp5")
    tonalidade = tom_de_texto(tom) if tom else None
    try:
        song = gp.parse(str(caminho))
    except Exception as erro:
        raise ValueError(f"não foi possível ler GP5: {erro}") from erro
    track = _faixa(song, faixa, caminho.name)
    notas, pausas = _ler_notas(track)
    if not notas:
        raise ValueError("a faixa selecionada não tem notas de baixo")
    if tonalidade is None:
        tonalidade = estimar_tom(_notas(song, track))

    bemois = bool(tonalidade and tonalidade.bemois)
    afinacao = ", ".join(
        _nome(corda.value, bemois=bemois) for corda in reversed(track.strings)
    )
    titulo_interno = " ".join(song.title.split())
    titulo = (
        caminho.stem.removesuffix(".todos")
        # Só `?`: o título não coube no cp1252 do GP5 e o nome do arquivo tem o original.
        if titulo_interno.strip("? ").casefold() in {"", "mix", "thoth"}
        else titulo_interno
    )
    linhas = [
        f"# Guia de estudo — {titulo}", "",
        f"**Fonte:** `{caminho.name}` · **Faixa:** {track.name} · "
        f"**Andamento no arquivo:** {song.tempo} BPM · **Afinação (grave → aguda):** {afinacao}.",
        f"**Conteúdo:** {len(notas)} {'ataque' if len(notas) == 1 else 'ataques'}, "
        f"{pausas} {'pausa escrita' if pausas == 1 else 'pausas escritas'}. "
        "Os compassos abaixo seguem a ordem escrita do arquivo; repetições não são desdobradas.",
        *(
            [
                f"**Entrada do baixo:** primeiro ataque no compasso {notas[0].compasso}; "
                "os compassos anteriores não têm ataques de baixo escritos."
            ]
            if notas[0].compasso > 1
            else []
        ),
        "",
        "## Antes de tocar: o que este arquivo permite saber", "",
        "Corda, casa, altura e posição rítmica são observações da tablatura. "
        "Cada casa sobe um semitom em relação à corda solta; duas casas são um tom. "
        "A corda mais grave aparece embaixo na tab comum. O GP5 numera da "
        "mais aguda (1) para a mais grave (4 num baixo de quatro cordas). "
        "O número 0 significa corda solta.",
        "Uma **ligadura de sustentação** une a mesma altura sem novo ataque escrito. "
        "Ela pode apenas dividir uma duração na escrita, inclusive na barra do compasso; "
        "não prova legato entre alturas diferentes.",
        "O Thoth não mede com segurança hammer-on, pull-off, slide, slap, pop, "
        "palheta, dedos, dinâmica ou abafamento (ADR-033). Quando o GP5 não traz "
        "marcação específica, a técnica usada é **não determinada**. "
        "As sugestões de execução são exercícios, não transcrição da técnica original.",
        "",
        "## Ferramentas de teoria para ler a linha", "",
        "- **Pulso e ritmo:** BPM é o número de pulsações por minuto. Em 4/4 há quatro "
        "tempos de semínima por compasso. Semibreve = 4 tempos; mínima = 2; "
        "semínima = 1; colcheia = 1/2; semicolcheia = 1/4. Um ponto acrescenta "
        "metade do valor. Pausas também ocupam tempo. Um ataque fora da parte forte "
        "pode produzir síncope, mas isso depende do contexto rítmico. "
        "`tempo 1 + 1/2` significa meio pulso após o início do primeiro tempo; "
        "`1 + 3/4`, três quartos de pulso depois.",
        "- **Intervalo:** distância entre duas alturas. Um semitom é uma casa; "
        "uma quinta justa tem 7 semitons e uma oitava tem 12. "
        "Notas sucessivas formam intervalo melódico; simultâneas, harmônico. "
        "Os nomes calculados abaixo usam distância cromática: a grafia das notas "
        "e a tonalidade podem dar outro nome diatônico ao mesmo número de semitons.",
        "- **Oitava:** a mesma classe de nota em outro registro. Na mesma corda, "
        "ela fica 12 casas acima. Em afinação por quartas, também costuma ficar "
        "duas cordas mais agudas e duas casas adiante.",
        "- **Quinta:** a quinta justa fica 7 semitons acima da nota de referência. "
        "O par fundamental-quinta não distingue sozinho acorde maior de menor: "
        "a terça é decisiva.",
        "- **Escala e grau:** escala é um conjunto organizado de alturas em torno "
        "de uma tônica. A maior usa 0-2-4-5-7-9-11 semitons; a menor natural, "
        "0-2-3-5-7-8-10. A pentatônica maior usa 0-2-4-7-9; "
        "a pentatônica menor, 0-3-5-7-10; a blues menor acrescenta a quinta "
        "diminuta (6). A menor harmônica eleva o 7º grau da menor natural; "
        "a menor melódica ascendente eleva o 6º e o 7º. "
        "Uma mesma coleção pode sugerir mais de uma tonalidade ou modo.",
        "- **Acorde e arpejo:** acorde reúne alturas com função harmônica; arpejo "
        "apresenta suas notas sucessivamente. Fundamental, terça, quinta e sétima "
        "são referências úteis, mas a linha do baixo sozinha não identifica "
        "necessariamente o acorde do momento.",
        "- **Cromatismo e passagem:** uma nota fora da escala pode aproximar a "
        "próxima por semitom; classificá-la como passagem exige ouvir o contexto.",
        "- **Legato e articulação:** legato descreve conexão sonora. Hammer-on "
        "faz soar uma nota mais aguda com a mão de digitação; pull-off solta uma "
        "nota para fazer soar a inferior; slide desloca o dedo pela corda. "
        "Staccato separa notas. Uma ligadura de duração é diferente dessas técnicas.",
        "- **Groove:** posição dos ataques, pausas, repetições, acentos e relação "
        "com a bateria moldam a sensação rítmica. O GP5 desta linha não informa "
        "por si só os acentos e a intenção do músico.",
        "",
    ]

    tonica: int | None
    modo: str | None
    escala: tuple[int, ...] | None
    grafias_escala: tuple[pitch.Pitch, ...] | None
    if tonalidade is not None:
        nome_tonica, modo_ingles = tonalidade.nome.split()
        chave = key.Key(nome_tonica, modo_ingles)
        tonica = chave.tonic.pitchClass
        modo = "maior" if modo_ingles == "major" else "menor"
        escala = _ESCALAS[modo]
        grafias_escala = tuple(chave.pitches[:-1])
        nomes_escala = ", ".join(
            altura.name.replace("-", "b")
            for altura in grafias_escala
        )
        linhas.extend(["## Tonalidade de referência", ""])
        if tom:
            linhas.append(
                f"**{tom}**, informada por você. Escala {modo} natural: {nomes_escala}. "
                "Os graus abaixo descrevem pertencimento a esta escala, não o acorde "
                "que soa em cada instante."
            )
        else:
            rotulo = f"{nome_tonica.replace('-', 'b').capitalize()} {modo}"
            linhas.append(
                f"**tom candidato: {rotulo}** — estimado das notas da tablatura "
                f"(margem de grafia {tonalidade.margem:.2f}). Escala {modo} natural: "
                f"{nomes_escala}. A margem compara grafias de sinais opostos; "
                "não confirma a tônica nem o modo. A linha de baixo isolada pode "
                "caber em várias harmonias. Os graus abaixo são hipóteses "
                "condicionais, e o acorde não conhecido impede afirmar a função "
                "de cada nota. Confira com a música ou informe `--tom`."
            )
            if not tonalidade.confiavel:
                linhas.append(
                    "**Margem curta:** a grafia do candidato também é incerta; "
                    "os nomes cromáticos da leitura usam sustenidos por cautela."
                )
                grafias_escala = None
        linhas.append("")
    else:
        tonica = modo = escala = None
        grafias_escala = None
        linhas.extend([
            "## Tonalidade de referência", "",
            "**Tonalidade não informada.** O acorde não conhecido e a linha isolada "
            "não autorizam atribuir graus, função harmônica ou escala à música. "
            "Use `--tom` se você souber o tom por fonte independente.", "",
        ])

    linhas.extend(["## Leitura nota por nota", ""])
    compasso_atual = 0
    for indice, nota in enumerate(notas):
        if nota.compasso != compasso_atual:
            compasso_atual = nota.compasso
            linhas.extend([f"### Compasso {compasso_atual}", ""])
        anterior = notas[indice - 1] if indice else None
        anteanterior = notas[indice - 2] if indice >= 2 else None
        nome = _nome_na_escala(nota.altura, grafias_escala, bemois=bemois)
        corda = _nome(track.strings[nota.corda - 1].value, bemois=bemois)
        linhas.append(
            f"{indice + 1}. **{nome}** — corda {nota.corda} ({corda} solta), "
            f"casa {nota.casa}; tempo {_tempo(nota.tempo)}; figura escrita: {nota.figura}; "
            f"ocupa {nota.duracao:g} "
            f"{'tempo' if nota.duracao == 1 else 'tempos'}."
        )
        if nota.casa == 0:
            linhas.append("   - **Braço:** corda solta; não pressione casa alguma.")
        else:
            linhas.append(
                f"   - **Braço:** pressione a casa {nota.casa}; ela eleva a corda "
                f"solta em {nota.casa} "
                f"{'semitom' if nota.casa == 1 else 'semitons'}."
            )
        if anterior:
            linhas.append(
                f"   - **Ligação com a nota anterior:** {_intervalo(anterior, nota)}; "
                f"{'mesma corda' if anterior.corda == nota.corda else 'troca de corda'}."
            )
        else:
            linhas.append("   - **Ligação com a nota anterior:** primeiro ataque da faixa.")
        if tonica is not None and isinstance(escala, tuple):
            distancia = (nota.altura - tonica) % 12
            rotulo_grau = (
                "Na escala informada" if tom else "Grau se o tom candidato estiver correto"
            )
            if distancia in escala:
                grau = _GRAUS[escala.index(distancia)]
                linhas.append(
                    f"   - **{rotulo_grau}:** {grau} grau de "
                    f"{tom or rotulo}."
                )
            else:
                linhas.append(
                    f"   - **{rotulo_grau}:** nota fora da escala natural; pode ser "
                    "cromatismo, empréstimo ou parte de outro acorde."
                )
        linhas.append(
            f"   - **Por que pode vir aqui:** "
            f"{_possibilidade(anterior, nota, anteanterior)}"
        )
        if nota.ultimo_compasso > nota.compasso:
            linhas.append(
                f"   - **Escrita:** ligadura de sustentação atravessa até o "
                f"compasso {nota.ultimo_compasso}; não há novo ataque nessa continuação."
            )
        elif nota.continuacoes:
            linhas.append(
                "   - **Escrita:** a nota foi ligada a outra figura no mesmo compasso "
                "para completar a duração; não há novo ataque."
            )
        linhas.append(
            "   - **Técnica:** "
            + ("; ".join(nota.tecnica) if nota.tecnica else "não determinada pelo GP5.")
        )
        linhas.append("")

    linhas.extend(["## Padrões para observar", ""])
    padroes = _padroes(notas)
    linhas.extend(f"- {padrao}" for padrao in padroes)
    if not padroes:
        linhas.append(
            "- Nenhum desenho fundamental-quinta-oitava ascendente apareceu em "
            "três ataques consecutivos; procure repetição, passos e saltos na leitura acima."
        )
    linhas.extend([
        "", "## Roteiro de prática", "",
        "1. Leia a afinação e encontre cada corda solta; depois localize as casas sem tocar.",
        "2. Marque os tempos com metrônomo no BPM do arquivo; conte pausas e ataques.",
        "3. Toque um compasso por vez lentamente, dizendo o nome da nota e a casa.",
        "4. Cante a direção de cada intervalo antes de tocá-lo; compare quinta e oitava.",
        "5. Pratique o desenho fundamental-quinta-oitava, se ele aparecer. "
        "Compare notas separadas e uma versão legato como exercício de técnica.",
        "6. Volte ao áudio original para conferir altura, ritmo, articulação e acorde. "
        "Corrija a tab antes de estudar um erro da transcrição.",
        "", "## Fontes para continuar", "",
        f"- [Open Music Theory — intervalos]({_FONTE_INTERVALOS})",
        f"- [Open Music Theory — valores rítmicos e ligaduras]({_FONTE_RITMO})",
        f"- [Open Music Theory — escalas e graus]({_FONTE_ESCALAS})",
        f"- [Fender — fundamentos do contrabaixo]({_FONTE_BAIXO})",
        f"- [Fender — hammer-on e pull-off]({_FONTE_TECNICA})",
        f"- [Yamaha — fundamentais, quintas e oitavas]({_FONTE_QUINTAS})",
        "- Decisões locais: ADR-022 (ligadura), ADR-031 (tonalidade) e "
        "ADR-033 (limite da inferência de técnica) em `tasks/decisions.md`.",
        "",
    ])
    return "\n".join(linhas)
