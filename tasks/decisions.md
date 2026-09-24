# Decisões Arquiteturais (ADR)

## ADR-001 — Sem ingestão de streams com DRM
**Data:** 2026-09-21 · **Status:** aceito

Spotify, YouTube Music e Amazon Music entregam áudio criptografado (Ogg cifrado /
Widevine). Não há API oficial que devolva PCM. Extrair exigiria re-gravação de
loopback ou circunvenção de DRM.

**Decisão:** a entrada do Thoth é arquivo local. O `Protocol AudioSource` mantém o
encaixe aberto para outros adapters (ex.: yt-dlp), que ficam a critério do usuário e
fora deste repositório.

**Consequência:** o Spotify permanece útil só para sincronizar o cursor de reprodução
(`/me/player/currently-playing`), nunca para obter áudio.

---

## ADR-002 — CPU-only; ROCm descartado
**Data:** 2026-09-21 · **Status:** aceito

A GPU da estação Pandora é uma Radeon RX 5500 XT (Navi 14, `gfx1012`, RDNA1). A AMD
nunca deu suporte oficial a RDNA1 no ROCm, e o ROCm não está instalado — só há RADV
(Vulkan). Habilitá-lo exigiria build da comunidade com `HSA_OVERRIDE_GFX_VERSION`,
frágil e desproporcional ao ganho.

**Decisão:** inferência em CPU. O Xeon E5-2666 v3 (10c/20t, 31 GiB) sustenta o
MuScriptor `small`/`medium`.

**Consequência:** o tamanho do modelo é um trade-off de tempo, medido na Fase 0.
Cache por estágio deixa de ser conforto e vira requisito.

---

## ADR-003 — MuScriptor como motor de transcrição
**Data:** 2026-09-21 · **Status:** aceito

MuScriptor (Kyutai + Mirelo, arXiv 2607.08168, jul/2026) reporta Onset F1 **60,4**
contra **32,5** do YourMT3+ no mesmo teste. Código MIT, pesos CC BY-NC 4.0 (ok para
uso pessoal). Transcreve a mix direto — não exige separação — e já faz quantização
e detecção de tempo.

**Decisão:** MuScriptor é o transcritor, atrás do `Protocol Transcriber`.

**Consequência — o que o Thoth escreve de código próprio:** verificado na CLI real
(v0.3.0, 2026-09-21) que o `transcribe` só emite **`midi | json | jsonl`** — não há
MusicXML, PDF nem tablatura. `grep` por `musicxml|lilypond|tablature|pdf` no pacote
instalado: zero ocorrências. O MuScriptor entrega **eventos de nota**, e nada além
disso. Logo, todo o caminho nota → partitura → tablatura é código nosso:
(1) fret assignment com afinação configurável, (2) GP5 editável via PyGuitarPro,
(3) MusicXML via music21, (4) sanity-check de oitava, (5) cache/orquestração/UI.

> **Correção de premissa (2026-09-21):** a versão anterior deste ADR afirmava que o
> MuScriptor já produzia MusicXML, PDF e tablatura, e usava isso para delimitar o
> escopo do Thoth. Era falso — veio do README, não da CLI. O erro *aumentava* o
> escopo próprio em vez de reduzi-lo: a Fase 4 (music21 + PyGuitarPro) deixa de ser
> conveniência e passa a ser caminho crítico, sem a qual não existe partitura alguma.

**Consequência — o que deixa de ser construído por padrão:** Demucs e quantizador
próprio saem do caminho crítico e viram condicionais, só justificados por evidência
medida na Fase 0.

> **Correção (2026-09-21):** o Beat This! **não é condicional** — é dependência
> obrigatória do MuScriptor (`Requires-Dist: beat-this>=1.1`), usada pelo
> `--detect-tempo`. A condicional C2 passa a ser apenas o *quantizador próprio*.
> Ressalva operacional: o checkpoint vem de `cloud.cp.jku.at`, host inalcançável
> desta estação — ver `tasks/fase0-resultados.md`. Limitação conhecida: notas sobrepostas do mesmo
instrumento degradam o F1 (60,4 → 51,8) — irrelevante para baixo, que é monofônico.

---

## ADR-004 — Python fixado em 3.12
**Data:** 2026-09-21 · **Status:** aceito

O MuScriptor exige Python 3.10–3.12. O Python de sistema da Pandora é 3.14.7, e um
`requires-python = ">=3.12"` resolveria para 3.14 e quebraria na instalação.

**Decisão:** `requires-python = ">=3.12,<3.13"` e `.python-version` = 3.12. O uv
gerencia o interpretador; o Python do sistema não é tocado.

---

## ADR-005 — Ingestão do YouTube via yt-dlp
**Data:** 2026-09-21 · **Status:** aceito · **Revisa:** ADR-001

O ADR-001 manteve a ingestão restrita a arquivo local e deixou o yt-dlp fora do
repositório. O usuário pediu explicitamente o suporte a link do YouTube, ciente de
que isso contraria os termos de uso da plataforma.

**Decisão:** `YtDlpSource` implementa `AudioSource` ao lado de `LocalFileSource`, e
`resolver_fonte()` despacha pela forma da referência (URL http(s) → YouTube).

**Decisão de implementação:** chamar o **binário do sistema**, não a biblioteca
Python. O yt-dlp quebra sempre que o YouTube muda, e o binário do pacman se atualiza
junto com o sistema, sem tocar no `uv.lock`. O custo é depender do PATH — aceito.

**Consequências:**
- `source_id` = `yt_<video_id>`, sem baixar para calcular hash. Cache hit não toca a rede.
- `meta.json` ao lado do WAV guarda título/artista/duração, para o cache hit não
  precisar de rede só para saber o nome da música.
- Teste `@pytest.mark.network` funciona como **canário**: quando o YouTube quebrar o
  yt-dlp, ele falha e aponta o `pacman -Syu`.
- Áudio baixado e stems **nunca** são versionados nem redistribuídos.
- O ADR-001 continua valendo para Spotify, YouTube Music e Amazon Music (DRM).

---

## ADR-006 — Avaliação não depende do ouvido do usuário
**Data:** 2026-09-21 · **Status:** aceito

O plano original media a qualidade da Fase 0 pedindo ao usuário que comparasse a
transcrição com músicas cujo baixo ele soubesse tocar. Ele está **começando a
aprender** e não toca nada ainda — o critério era inexequível, e avaliar por ouvido
inexperiente produziria uma decisão pior do que não avaliar.

**Decisão:** a avaliação passa a ter três camadas, nenhuma exigindo habilidade
instrumental:

1. **Objetiva (principal):** ground truth sintético — MIDI conhecido → fluidsynth +
   soundfont → WAV → pipeline → `mir_eval` Onset F1. Sobe da Fase 2 para a Fase 0,
   porque agora é o critério primário, não um complemento.
2. **Perceptual assistida:** auralização do MuScriptor (original em um canal, MIDI
   transcrito no outro). Descolamento é audível por qualquer pessoa, sem treino.
3. **Referência externa:** comparar com tablatura humana publicada de uma música
   conhecida, para conferir oitava e notas sem precisar tocar.

**Ponto cego medido na Camada 2 (2026-09-22).** A Camada 2 **não arbitra oitava no
registro grave** — e isso não é falta de treino do ouvinte, é física somada à
cadeia de reprodução. Renderizando as duas hipóteses com o FluidR3:

| nota | RMS | energia abaixo de 50 Hz | 2º harmônico |
|---|---|---|---|
| B0 (30,9 Hz) | −35,3 dBFS | **24%** | 61,7 Hz |
| B1 (61,7 Hz) | −30,4 dBFS | 0% | 123,5 Hz |

Um quarto da energia do B0 está abaixo de 50 Hz, que caixa e fone comuns não
reproduzem. O que sobra audível do B0 são seus harmônicos — a começar por 61,7 Hz,
que é exatamente a **fundamental do B1**. As duas hipóteses soam quase iguais por
construção. Submetido o A/B com a linha completa, o veredito foi *"agora as duas
ficaram perfeitas"*: a Camada 2 funcionou como projetada e disse, corretamente,
que não distingue.

**Consequência:** erro de oitava no registro grave é da **Camada 3**, não da 2 —
como este ADR já previa ao escrever "para conferir oitava". Nenhuma quantidade de
escuta substitui a referência externa aqui.

**Consequência de produto — o iniciante muda as prioridades:**
- O `FretAssigner` ganha um **modo iniciante**: preferir primeira posição, cordas
  soltas e trastes baixos. Para quem começa, tocabilidade vale mais que otimização
  de deslocamento.
- O controle de andamento do alphaTab (estudar a 50–70%) sobe de "opcional" para
  funcionalidade central: é a ferramenta de estudo de fato.

---

## ADR-007 — Origem das tablaturas de referência
**Data:** 2026-09-21 · **Status:** aceito

A Camada 3 do ADR-006 (referência externa) precisa de tablaturas humanas
confiáveis. Duas fontes foram avaliadas.

**Ultimate Guitar — sem API, integração manual.**
Não há API pública oficial; só existem scrapers não oficiais, e o UG declara
scraping ilegal. **Decisão: o Thoth não faz scraping do UG.** A assinatura Pro
do usuário continua útil pelo caminho legítimo — tabs da comunidade têm download
em `.gp/.gpx/.gp3/.gp4/.gp5`, que o Thoth lê via PyGuitarPro. Tabs marcadas
"Official" não são baixáveis (restrição do próprio UG) e ficam fora do escopo.

**Songsterr — API aberta, sem chave.**
`GET /api/songs?pattern=` e `GET /api/meta/{songId}/revisions`. Já indexa a
música de teste (`songId 3334607`, SOJA — Everything Changes) com track de baixo
separado e afinação explícita.

**Filtro obrigatório — `aiGenerated`.**
A tab de baixo da SOJA é `"aiGenerated": true, "createdVia": "AI"`. Validar uma
transcrição por IA contra uma tablatura gerada por IA é circular: mede
concordância entre modelos, não acerto. **Toda referência externa exige
`aiGenerated == false`.** Verificado em songIds 14, 14046 e 371 — todas retornam
`aiGenerated=False`, `via=Editor`, com autor humano.

**Consequência:** a música de teste do usuário serve para a Camada 2
(auralização, que não depende de referência), mas **não** para a Camada 3. A
Camada 3 usa um clássico com tab humana.

### Emenda (2026-09-24) — o Songsterr também não serve por automação

Conferido nesta data: o `robots.txt` do Songsterr tem `Disallow: /api/` para todo
agente, e a política para IA (`/ai.txt`) lista o download em Guitar Pro e MIDI como
recurso pago (Plus), pedindo que nada "equivalente" seja obtido por automação. Extrair
as notas de uma tab por script para servir de referência é exatamente esse equivalente.
**O Thoth também não automatiza o Songsterr** — a regra do UG vale para ele. A API serviu
para verificar `aiGenerated`, e isso não se repete. A referência humana da Camada 3 chega
só por download legítimo feito pelo usuário (`.gp5` da comunidade no UG Pro, ou Songsterr
Plus) e entra aqui como arquivo local, lido pelo PyGuitarPro.

---

## ADR-008 — Decodificação livre + filtro por rótulo, nunca `--instruments`
**Data:** 2026-09-21 · **Status:** aceito

A leitura intuitiva do `--instruments electric_bass` é "transcreva só o baixo".
A CLI diz outra coisa: *"every instrument not in the list is forbidden from being
decoded at all"*. Proibir os outros rótulos **não faz o modelo ignorar aquele
áudio** — força o áudio deles para dentro do rótulo permitido.

Medido nos dois modelos, em áudio real (30s de `4kd_eR4216g`):

| execução | notas de baixo | extensão | máx. simultâneas |
|---|---|---|---|
| small `--instruments` | 99 | C#1..A3 | 2 |
| small livre | 89 | C#1..A3 | 1 |
| **medium `--instruments`** | **194** | C#1..**B4** | **7** |
| medium livre | 94 | C#1..A3 | 1 |

Sete notas simultâneas em B4 não é contrabaixo. Quanto melhor o modelo, **pior** o
efeito: o `medium` percebe mais conteúdo, e todo ele é despejado no baixo.
Confirmado na fixture sintética `misto` (baixo + piano): 16 notas de referência
viram 39 estimadas com `--instruments`, contra 28 em modo livre.

Em modo livre os dois modelos concordam (89 vs 94 notas, mesma extensão), e o
MuScriptor separa `acoustic_guitar`, `drums` e `distorted_electric_guitar`
sozinho.

**Decisão:** o adaptador `MuScriptorTranscriber` **sempre** decodifica livre e
filtra por `instrument == "electric_bass"` no nosso lado. O `--instruments` só
entra como otimização consciente de velocidade, jamais como seletor de instrumento.

**Custo aceito:** decodificação livre é ~2,7× mais lenta (1,06× tempo real com
`small`; ~5 min de CPU para uma música de 5 min). Aceitável para uso pessoal.

### Emenda (2026-09-22) — o rótulo depende de contexto, e o filtro depende dele

Medido ao escrever o teste real do adapter: a **mesma** linha de baixo, mesmo
programa GM e mesmo soundfont, renderizada em dois comprimentos:

| fixture | duração | rótulo atribuído |
|---|---|---|
| 5 notas | 2,9 s | `acoustic_piano` |
| 15 notas | 8,1 s | `electric_bass` |

As alturas saem corretas nos dois casos — o que muda é só o rótulo. Como esta
ADR escolhe **filtrar por rótulo** depois da decodificação livre, um rótulo
errado descarta a linha inteira em silêncio, que é pior que transcrever errado.

**Restrição derivada para o pipeline:** transcrever a faixa inteira de uma vez,
nunca fatiar em trechos curtos antes da transcrição. Se algum dia o processamento
em blocos for necessário (memória, paralelismo), o bloco precisa de contexto
suficiente — e a decisão passa a exigir medição, não suposição.

Isto **não** reabre o `--instruments`: condicionar continua sendo pior (medido no
próprio ADR-008). O que a emenda diz é que o filtro tem um modo de falha próprio,
e ele é silencioso.

---

## ADR-009 — Modelo `small` como padrão
**Data:** 2026-09-21 · **Status:** aceito

Contra a expectativa (o paper usa `medium` como padrão), o `small` é a escolha.

| | `small` | `medium` |
|---|---|---|
| fixtures sintéticas solo | 0,90–1,00 nota F1 | falha em 3 de 6 |
| áudio real, modo livre | 89 notas, coerente | 94 notas, coerente |
| velocidade (CPU, 20 threads) | 1,06× tempo real | 3,1× tempo real |

O `medium` **degenera** em áudio sintético: 291 notas para uma fixture de 15
(`escala`), 304 para uma de 12 (`oitavas`) — repetição autorregressiva clássica em
entrada fora da distribuição de treino. O `small` atravessa as mesmas fixtures com
F1 entre 0,90 e 1,00.

**Decisão:** `small` é o padrão; `medium` fica atrás de flag para comparação
pontual em áudio real.

**Consequência metodológica:** o gate de regressão sintético (Fase 2) **só vale
para `small`**. Rodar `medium` contra fixtures de fluidsynth mede distância da
distribuição de treino, não qualidade de transcrição. Fixtures sintéticas são
métrica de regressão, nunca de qualidade — agora com evidência de por quê.

### Emenda (2026-09-24) — remedido depois do ADR-010, com separação

A tabela acima é de antes da separação obrigatória. Remedido no caminho atual —
fixture renderizada → `htdemucs_ft` (demucs 4.1.0) → MuScriptor → filtro
`ROTULOS_DE_BAIXO` → `avaliar`, 50 ms —, cada estágio cronometrado à parte, CPU de 20
threads, nada mais rodando na máquina. **Medição registrada, não critério de
aprovação**; o teste de regressão continua só para o `small`.

| fixture | duração | demucs | `small` | × tempo real | nota F1 | `medium` | × tempo real | nota F1 |
|---|---|---|---|---|---|---|---|---|
| escala | 12,1 s | 31,8 s | 6,3 s | 0,52 | 0,933 | 14,7 s | 1,21 | **0,000** |
| walking | 12,8 s | 32,1 s | 6,2 s | 0,48 | 0,968 | 12,3 s | 0,96 | 0,968 |
| groove16 | 7,5 s | 24,2 s | 7,5 s | 0,99 | 1,000 | 15,4 s | 2,04 | 0,984 |
| graves | 8,8 s | 22,8 s | 5,1 s | 0,58 | 1,000 | 9,4 s | 1,07 | 0,900 |
| oitavas | 10,1 s | 23,3 s | 5,6 s | 0,55 | 0,957 | 10,8 s | 1,07 | 0,957 |
| misto | 13,1 s | 31,9 s | 6,1 s | 0,46 | 0,968 | 12,1 s | 0,92 | 0,968 |

O que muda na leitura:

- **O `medium` não degenera mais nestas fixtures.** Com o stem no lugar do áudio
  renderizado direto, nenhuma das seis explodiu em repetição (antes: 291 notas para
  15). O que sobrou foi **rótulo**: em `escala` ele devolveu 14 notas, todas
  `acoustic_guitar` — o filtro esvazia e o pipeline recusaria a música ("nenhuma nota
  de baixo"). O `small` rotulou as mesmas como `electric_bass`.
- **Em nenhuma fixture o `medium` ganhou**: empata em três, perde em três.
- **Custo:** o `medium` é ~2× o `small` na transcrição, mas o demucs domina o tempo
  de parede (3–5× o do `small` nestas durações curtas). Trocar de modelo não é onde
  está o tempo.
- O `misto` com separação sai em 0,968 com os dois — o ganho do ADR-010 não depende
  do modelo.

O `small` continua padrão. O "atrás de flag" da decisão nunca virou flag na CLI: o
`medium` só entra injetando `MuscriptorTranscriber(model="medium")`. Com esta medição
não há motivo para criá-la; a comparação em áudio real, que é a que falta, precisa de
referência humana (Camada 3, ADR-007).

---

## ADR-010 — Demucs promovido de condicional a etapa do pipeline
**Data:** 2026-09-22 · **Status:** aceito · **Revoga:** condicional C1

A C1 previa separação por fonte só se a Fase 0 mostrasse ganho. Mostrou.

Medido em 30s de mix real, `htdemucs_ft --two-stems=bass`, `small` livre:

| | mix direta | stem |
|---|---|---|
| Sade, *Is It A Crime* (ao vivo) | 67 notas, E1..C3, 1 simultânea | 62 notas, E1..C3, 1 simultânea |
| Seu Jorge, *Tive Razão* | 63 notas, E1..**F#4**, **4 simultâneas** | 52 notas, E1..F#3, 1 simultânea |

**Confirmação perceptual (Camada 2, ADR-006).** O Welington ouviu os dois pares:
*"a versão jorge_STEM ficou muito melhor, na versão MIX tem um teclado no meio"*.
O teclado do arranjo aparece **dentro do canal do baixo** na transcrição da mix.

O detalhe que importa: o MuScriptor **detectou o teclado corretamente** — 341 notas
rotuladas `acoustic_piano` no mesmo arquivo — e ainda assim vazou parte dele para o
`electric_bass`. Rotular certo não impede o vazamento. Nenhum ajuste de flag
resolve isso; só remover o instrumento do áudio antes da transcrição.

**Decisão:** `DemucsSeparator` (`htdemucs_ft`, `--two-stems=bass`) entra no caminho
crítico, antes do transcritor, **sempre** — sem heurística de "separar só quando
precisar".

O par de controle decidiu isso. No Sade a separação derrubou 67 notas para 62, o
que admitia duas leituras opostas: lixo removido ou nota real comida. A escuta
resolveu — o Welington comparou os dois e eles *"soaram equivalentes"*. Separar
não custa qualidade em mix limpa, então não há motivo para uma heurística de
re-execução condicional carregar complexidade no pipeline.

**Custo aceito:** separação de 30s leva 88s em CPU; transcrever o stem cai para 10s
(contra 42s na mix, pois há um instrumento só). Total ~2,4× mais lento — ~16 min
para uma música de 5 min, contra ~7 min. Aceitável para uso pessoal.

**Armadilha de empacotamento:** o `demucs` declara mal suas dependências — falha com
`ModuleNotFoundError: numpy`. Exige `--with "numpy<2"` no `uvx`, ou pin equivalente
no adaptador.

### Emenda (2026-09-22, após o Grupo C)

O "custo aceito" acima vale para mix esparsa. Em mix densa a separação **paga por
si**: no Ne Obliviscaris a mix leva 106s para 30s de áudio (1238 eventos, dos quais
769 de guitarra distorcida) e o stem leva 20s — 5× mais rápido, pois o decoder não
gasta passos com instrumentos que vamos descartar. Quanto mais cheio o arranjo,
mais barato fica separar antes.

A escuta do `neo_STEM` trouxe *"pegou o som da dedilhada"*. A investigação que
isso disparou achou um problema diferente e maior: **a separação erra a oitava**.
Em 12 de 165 notas (7%) o stem diz B0 onde a mix diz B1, e as evidências
disponíveis — continuidade melódica e espectro — apontam para a mix. Detalhe e
ressalvas em `fase0-resultados.md`; pendente de escuta A/B focada.

Isto **não reverte** a decisão de separar sempre: o vazamento do teclado no
`jorge` é erro de instrumento (nota que não existe), enquanto o salto de oitava é
erro de altura numa nota real — mais barato de corrigir, e corrigível com o
áudio original em mãos. Mas desmonta a leitura de que separar sai de graça.
**Condiciona a Fase 1:** o teste de regressão precisa de uma verificação de
oitava contra o espectro da mix original, não só de métricas contra o stem.

### Emenda (2026-09-22, ground truth)

Tudo acima foi decidido por escuta e por contagem de notas — nunca contra
gabarito, porque o acervo real não tem. A fixture `misto` tem: baixo e piano
saem do mesmo MIDI, e o que o piano ocupa é conhecido nota a nota.

| `misto`, `small`, tolerância 50 ms | onset F1 | nota F1 |
|---|---|---|
| sem separação | 0,938 | 0,682 |
| com separação | 0,938 | **0,968** |

**O onset não se move.** Separar não recupera *quando* — recupera *qual*. O piano
não estava criando ataques falsos; estava sequestrando a altura de notas de baixo
que o transcritor já ouvia no tempo certo. Bate exatamente com o que a escuta do
`jorge` dizia, e explica por que rotular certo não bastava: o rótulo é do evento,
a altura vem do espectro misturado.

Vale para uma fixture sintética, e só. As outras cinco são baixo solo saído de
MIDI limpo — medi-las com Demucs responderia *"atrapalha?"*, não *"ajuda?"*.
Travado em `tests/integration/test_separacao_fase0.py`, com o número sem
separação como piso: se uma troca de modelo o derrubar, o que se reabre é este
ADR, não o piso.

### Emenda (2026-09-23, o piso era o número errado)

"Com o número sem separação como piso" estava errado, e o erro era de tipo:
0,682 é o valor de **não separar**. O teste pedia que separar não fosse pior que
não separar — e a separação mede 0,968. Sobravam 0,286 de espaço livre: a
separação podia perder **quatro notas de dezesseis** e o teste passava calado,
exatamente o vazio que a lição de `workflow.md` descreve ("teste que passa não diz
nada sobre a margem").

O piso agora é `COM_SEPARACAO_NOTA_F1 = 0.968`, o valor medido, **exato**. O F1 aqui
é discreto: 16 notas de referência fazem a menor diferença possível valer ~0,03, e
não existe flutuação menor que isso para uma folga absorver. Medido duas vezes
seguidas na mesma máquina: 0,968 nas duas, `ref=16 est=15` (precisão perfeita, uma
nota não encontrada).

O piso antigo fica, com a mensagem própria: cair abaixo de 0,682 não é regressão da
separação, é o ADR-010 desmentido, e são coisas diferentes de investigar. O teste
imprime a margem contra o piso.

---

## ADR-011 — Baixo-primeiro é limite medido, não preferência
**Data:** 2026-09-22 · **Status:** aceito

O objetivo secundário ("idealmente qualquer instrumento") encontra um teto no
motor escolhido. Medido no Grupo C com guitarra neo-soul (Toshiki Soejima):
208 notas na mix, **7–8 simultâneas** — acorde real, não artefato.

Diferente do baixo, aqui não há teste de plausibilidade estrutural: uma linha de
baixo com 6 notas juntas é obviamente erro; um acorde de neo-soul não é. A
verificação teve que ser perceptual, e o veredito foi *"o som ficou misturado"* —
a manifestação audível da fraqueza já documentada do MuScriptor em notas
sobrepostas do mesmo instrumento (onset F1 60,4 → 51,8).

**Decisão:** o pipeline é validado, medido e entregue **para baixo**. Outros
instrumentos monofônicos (voz, contrabaixo, fagote) são extensão plausível;
polifonia densa (guitarra de acompanhamento, piano) fica fora de escopo enquanto
o motor for o MuScriptor. Não gastar Fase 4 tentando gerar tablatura de guitarra.

**Limitação adjacente:** o `htdemucs_ft` não tem stem de guitarra — ela cai em
`other`, junto com teclados e sopros. Mesmo que o motor melhorasse, o separador
não entrega guitarra isolada.

---

## ADR-012 — Custo de tablatura: o que separa iniciante de experiente
**Data:** 2026-09-22 · **Status:** aceito

O posicionamento é um caminho ótimo sobre a frase (Viterbi), com cinco pesos:
`traste_alto` e `corda_solta` na emissão, `deslocamento` e `troca_corda` na transição,
e `acima_da_janela` na emissão. Dois presets: `PADRAO` e `INICIANTE` (ADR-006).

**O achado que motiva este ADR é negativo.** Na primeira versão os dois presets
produziam **tablatura idêntica** em todas as linhas testadas — o modo iniciante existia
só como rótulo. A causa não é calibração ruim: um custo *linear* por traste desloca
todas as opções de uma nota na mesma direção, então mudar seu peso quase nunca inverte
o argmin. Nenhuma reponderação dos quatro termos originais separa os modos.

**Decisão:** o que separa é uma penalidade que só morde *fora* da zona confortável —
`acima_da_janela * max(0, traste - 5)`, zero em `PADRAO` e alta em `INICIANTE`. Com ela,
170 de 400 linhas aleatórias divergem, e na direção certa (o iniciante desce o braço).

**Duas limitações, explícitas:**

1. A janela é **absoluta** (trastes 0–5), não a posição corrente da mão que a expressão
   "janela de posição da mão" do `todo.md` sugeria. Para quem está aprendendo, a
   primeira posição é o objetivo em si — uma janela móvel premiaria ficar coerente em
   qualquer região do braço, inclusive alta, que é o oposto do ADR-006. A mão móvel já
   está representada pelo termo de `deslocamento`.
2. Acima do traste 5 o termo vira **offset constante** dentro da linha: numa frase que
   vive genuinamente entre os trastes 7 e 12, ele não discrimina nada e a escolha volta
   a ser dos outros quatro termos. Isso é aceitável porque tal frase não tem alternativa
   em primeira posição — mas não confunda com "o modo iniciante age em toda linha".

**O corpus sintético não valida essa distinção.** As seis fixtures da Fase 0 caem em
primeira posição sob os **dois** presets: elas vivem no registro grave, onde a solução
tocável e a ótima coincidem. A distinção se apoia num teste de contraste explícito e na
varredura aleatória, não nas fixtures.

---

## ADR-013 — Andamento é entrada do exportador, não estimativa
**Data:** 2026-09-22 · **Status:** aceito

Nenhum formato de partitura guarda segundos: GP5 e MusicXML guardam compassos,
tempos e figuras. A transcrição, porém, sai em segundos absolutos — e o Thoth não
estima andamento, porque o checkpoint do Beat This! está inacessível (C2).

**Decisão:** `bpm` é parâmetro explícito dos exportadores, com grade de semicolcheia
e compasso fixo 4/4. Não há palpite silencioso: um BPM errado não quebra nada, produz
tablatura legível e errada — o pior modo de falha possível, porque não se anuncia.

**Consequências assumidas nesta primeira versão:**

- **GP5 sem ligaduras.** Nota mais longa que a maior figura representável vira a maior
  figura que couber, e o resto vira pausa. O *ataque* fica exato, que é o que se lê numa
  tablatura. O MusicXML não tem esse limite: o `makeNotation` do music21 resolve
  ligaduras e pausas sozinho a partir dos offsets.
- **Monofonia.** Notas que caem no mesmo tique são **recusadas** (`ValueError`), não
  empilhadas — a tablatura é monofônica (ADR-012) e empilhar produziria posição
  impossível de tocar. Falhar alto é melhor que emitir tab que ninguém consegue tocar.
- **4/4 fixo.** Compasso composto ou mudança de fórmula ficam para quando houver
  material que exija.

O round-trip é verificado contra as bibliotecas reais (grava arquivo, relê, compara
corda, traste, altura, afinação, andamento e clave). Isso prova consistência, **não**
validade para outro leitor — a verificação no TuxGuitar continua sendo manual.

### Emenda (2026-09-24)

A primeira consequência — **GP5 sem ligaduras** — não vale mais desde o ADR-022: a
duração que não cabe numa figura, ou que atravessa a barra, sai em beats
`NoteType.tie` encadeados, e o resto deixou de virar pausa. O restante deste ADR
(BPM explícito, monofonia, 4/4 fixo) continua como está.

## ADR-014 — O pipeline descarta e relata, em vez de falhar
**Data:** 2026-09-22 · **Status:** aceito

Dois casos derrubavam o pipeline inteiro num erro, e os dois são esperados em
áudio real:

1. **Notas simultâneas.** `assign` é monofônico e `rhythm.eventos` recusa duas
   notas no mesmo tick. O corpus de baixo mal tem simultaneidade (ADR-010: máximo
   de 1 no stem das duas faixas medidas), mas "mal tem" não é "não tem" — um
   dobrado ou um harmônico mal decodificado basta.
2. **Notas fora do braço.** É a assinatura exata do erro de oitava do Demucs
   (ADR-010: B0 onde a mix diz B1): num baixo de 4 cordas, B0 simplesmente não
   existe. `assign` levanta `AlturaImpossivelError`.

**Decisão:** nenhum dos dois é fatal. A simultaneidade é reduzida à **nota mais
grave** do grupo; a nota fora do braço é removida. Ambas vão para o `Resultado`
(`descartadas`, `fora_do_braco`) e para o relatório da CLI.

**Por que a mais grave:** num acorde de contrabaixo quem sustenta a harmonia é a
fundamental, e o que costuma acompanhá-la é vazamento de outro instrumento ou
parcial mal decodificada — não uma segunda voz.

**Por que não falhar:** o pipeline custa ~2,5× a duração do áudio em CPU, ~16 min
para uma música de 5 min. Perder isso por causa de uma nota é desproporcional; a
tablatura com uma nota a menos é utilizável, e o relatório diz onde olhar.

**Por que não descartar em silêncio:** silêncio aqui viraria exatamente o defeito
que o verificador de oitava foi feito para evitar — erro plausível que nenhuma
etapa posterior detecta.

**A colisão é medida na grade, não no relógio.** Duas notas a 20 ms de distância
são eventos distintos no áudio e o mesmo tick de semicolcheia. Quem recusa é o
tick, então quem filtra tem de olhar o tick — filtrar por onset cru deixaria o
erro passar intacto para o exportador. Por isso `monofonizar` mora em
`services/rhythm.py`, ao lado da grade, e não no pipeline.

## ADR-015 — UI local: alphaTab vendorizado, jobs em memória
**Data:** 2026-09-22 · **Status:** aceito

**alphaTab servido daqui, nunca de CDN.** Estudar é a finalidade do projeto
(ADR-006) e não pode depender de internet nem transformar cada sessão num pedido
a um terceiro. Os 4,6 MB de dist **não** são versionados — mesma regra do áudio e
dos pesos (ADR-005). O que fica no repositório é a identidade: versão `1.8.4` e
SHA-256 do `.tgz` em `scripts/vendor_alphatab.py`, como o `models.lock.toml` faz
com os pesos. Faltando o vendor, a raiz responde **503 com o comando**, em vez de
servir uma página em branco.

**O script resolve os `import`, não carrega uma lista fixa.** A lista fixa falhou
na primeira tentativa: `alphaTab.min.mjs` tem 4 KB e é só uma fachada que importa
`core` (2,3 MB), `worker` e `worklet`. O servidor respondia 200 para tudo que eu
tinha pedido, e a página abriria em branco com um 404 no console do navegador —
um defeito que nenhum teste de servidor pega, porque o servidor estava certo. O
teste que fecha isso é estrutural: todo `import` relativo dos módulos
vendorizados tem de resolver para arquivo existente.

**Jobs vivem em memória, no processo.** Uso pessoal, uma música por vez.
Reiniciar perde o histórico e não perde nada caro: os artefatos ficam em disco
nomeados pelo `source_id`, e repetir um job reaproveita o cache de ingestão e o
de separação. Banco de dados aqui seria estado para um usuário só.

**Falha do pipeline é estado do job, não 500.** "Nenhuma nota de baixo" é
diagnóstico para quem pediu — o servidor funcionou. O 409 fica para o artefato
pedido antes da hora.

**O que a API expõe de propósito:** contagem de descartes, notas fora do braço e
avisos de oitava (ADR-014). A tablatura sozinha não avisa o que foi jogado fora.

---

## ADR-016 — A página de estudo não configura `scrollElement`

**Contexto.** A página abria e não mostrava nada. O alphaTab dava todos os sinais
de sucesso: `scoreLoaded`, `renderStarted`, `renderFinished`, a superfície
`.at-surface` criada com 358 px de altura e três blocos filhos com as larguras
certas. Só que os três blocos estavam vazios — nenhum `<svg>` no documento.

**Causa raiz.** `player.scrollElement` apontava para `#tab`, o próprio container
da partitura. O `scrollElement` é o *viewport que rola*, não o conteúdo que é
rolado; com ele apontando para o próprio conteúdo, o lazy loading do alphaTab
conclui que nenhuma parte está visível e nunca dispara `partialRenderFinished` —
os blocos são posicionados pelo layout e ficam sem desenho.

**Decisão.** Remover `scrollElement`. O `#tab` mora num `.painel` sem `overflow`,
então quem rola é o documento — que já é o padrão do alphaTab. Se um dia o `#tab`
for embrulhado num container `overflow:auto`, o certo é `scrollElement` apontar
para *esse* embrulho, nunca para o `#tab`.

**Descartado:** `useWorkers: false` e `enableLazyLoading: false`. Ambos fazem a
página renderizar, e ambos tratam sintoma: o primeiro não tem relação nenhuma com
a falha (foi diagnóstico errado — ver lição), o segundo desliga um recurso bom
para contornar uma configuração errada.

**Reabrir um job pronto (`?job=<id>`).** Entrou junto porque era o que faltava
para o teste de regressão existir sem re-rodar o pipeline, e é útil por si: dá
para voltar a uma transcrição sem gastar minutos de CPU de novo. Abriu um caminho
de 404 que antes era inalcançável (o id vinha sempre de um POST recém-aceito), daí
a guarda no `acompanhar` — sem ela o laço giraria para sempre com a tela em branco.

**Teste.** `tests/navegador/` (marcador `navegador`, fora da suíte padrão) sobe a
API com executor de mentira e artefato GP5 de verdade, abre o Chromium e conta
`#tab svg`. Verificado nos dois sentidos: passa com o fix e falha com o
`scrollElement` de volta. Nenhuma asserção mais fraca serve — `renderFinished`,
`.at-surface` presente e `innerHTML` não vazio **passam** com o bug ativo.

---

## ADR-017 — Artefatos nomeados pelo título, não pelo `source_id`

**Data:** 2026-09-22 · **Status:** aceito

**Contexto.** O pipeline gravava `out/9aa6eda3591aa060.gp5`. O `source_id` é uma
boa chave (estável, única, é o que indexa o cache), mas é um péssimo rótulo: com
meia dúzia de transcrições em `out/`, não dá para saber qual é qual sem abrir. O
`AudioAsset` já carrega `title` — do `meta.json` no YouTube, do nome do arquivo
no local — então não foi preciso buscar metadado novo.

**Decisão.** `out/<título>.<formato>`, via `services/nomes.nome_de_arquivo()`.
Título preservado legível, com acentos: o destino é o gerenciador de arquivos e o
MuseScore, não uma URL. A sanitização troca `/ \ : * ? " < > |` e controles por
hífen, colapsa repetições, tira ponto e espaço das pontas (ponto inicial esconde
o arquivo; final quebra no Windows) e trunca em 120 caracteres — os títulos reais
do cache trazem `:` e `/`, e a barra criaria diretório em vez de arquivo.

**Colisão resolvida por sobrescrita.** Dois títulos iguais de fontes diferentes
passam a ocupar o mesmo arquivo. Aceito conscientemente: o uso é pessoal, e a
alternativa (sufixo do `source_id` ao colidir) troca um nome limpo por um nome
sujo para um caso que ainda não aconteceu. Reversível quando acontecer.

**O que não muda.** `cache/<source_id>/` e `cache/stems/<source_id>/` continuam
no id: ali ele é chave de cache, não rótulo para humano. A API também não muda —
ela serve `job.resultado.artefatos[formato]`, que é o `Path` real, e nunca
remontou o nome a partir do `source_id`.

**Teste.** `tests/unit/test_nomes.py` usa os títulos reais do cache (o do Toshiki
Soejima tem `:` e `/` no mesmo título) e cobre o fallback: título que se reduz a
nada volta ao `source_id`, senão o artefato viraria um `.gp5` oculto e sem nome.

---

## ADR-018 — Nome da nota escrito na partitura e na tablatura

**Data:** 2026-09-22 · **Status:** aceito

**Contexto.** Ler tablatura de baixo é ler traste, não nota: o estudo fica preso
à posição e não vira conhecimento do braço. O nome da nota ao lado da figura
fecha essa lacuna sem exigir nada do leitor.

**Decisão.** Cada nota exportada leva o nome da sua classe de altura, via
`services/notas.nome_da_nota()` — no GP5 como `Beat.text` (é o que o Guitar Pro e
o alphaTab desenham sobre o beat) e no MusicXML como `lyric` (é o que o MuseScore
desenha sob a nota). Ambos já existiam nas dependências atuais; nenhuma entrou.

**Sem oitava.** `E`, não `E1`. A oitava já está dita pela corda e pelo traste, e
repeti-la em cada figura polui a leitura — que é justamente o que a mudança quer
melhorar.

**Sempre sustenido.** A tecla preta entre lá e si sai `A#`, nunca `Bb`, inclusive
numa música em fá. Distinguir as duas exige armadura de clave, e o Thoth não
estima tonalidade (mesma família do `--bpm`, ADR-013). Fica declarado no módulo,
não escondido.

**Pausa não recebe texto**, senão apareceria um rótulo solto no meio do compasso.
Tem teste próprio.

**Teste.** Round-trip real nos dois formatos (`test_gp5_export.py`,
`test_musicxml_export.py`): grava o arquivo, relê com PyGuitarPro e com music21 e
confere o texto na nota certa. Mock aqui provaria só que chamo a API como imagino.

---

## ADR-019 — `--bpm` opcional: estimativa declarada em vez de exigência

**Data:** 2026-09-22 · **Status:** aceito · **Emenda o ADR-013**

**Contexto.** O ADR-013 fez do andamento uma entrada obrigatória para evitar
palpite silencioso virando tablatura errada. A justificativa continua correta, mas
a decisão tinha uma suposição não declarada: a de que quem usa sabe o BPM. O
Welington disse, com todas as letras, que está começando os estudos e não sabe o
andamento de nenhuma das músicas. Para esse usuário, o ADR-013 exigia a resposta
antes de permitir a pergunta — a ferramenta ficava inutilizável.

**Decisão.** `--bpm` passa a ser opcional. Informado, manda sempre e nada muda.
Ausente, o andamento é estimado do **mix** (não do stem: o pulso está na bateria,
que a separação justamente remove) e o resultado é **anunciado em amarelo** no
CLI, exposto no JSON do job (`bpm_estimado`, `bpm_confiavel`) e marcado como aviso
na página. O que o ADR-013 proibia era o palpite *silencioso*; um palpite alto e
corrigível não viola o princípio, cumpre.

**Dois estimadores, não um.** Medindo as fixtures de andamento conhecido (90 BPM),
cada método errou onde o outro acertou: `beat_track` leu o `misto` a 45 (metade) e
`feature.tempo` leu o `groove16` a 117. O desacordo entre eles vira o campo
`confiavel` — é o sinal honesto de "confira este aqui". Nas seis músicas do acervo
os dois concordam em quatro e divergem em três casos previsíveis (prog metal e
neo-soul rubato).

**Dobra para a faixa musical (70–160).** O erro de dobro/metade é o modo de falha
clássico, e é o que aparece nos dados. Dobrar ou dividir até cair na faixa corrige
o `misto` (45 → 90) sem inventar nada.

**Custo aceito:** entra o `librosa` (BSD) como dependência de produção. É a mesma
peça prevista para o C2, então não é dívida nova.

**Limite conhecido, não resolvido aqui:** um único BPM global não representa
música que muda de andamento — o *Equus* é exatamente esse caso. Seguir a curva de
tempo real exigiria mudança de andamento por compasso no exportador, que hoje é
4/4 fixo. Fica anotado, não escondido.

**Teste.** `tests/unit/test_tempo.py` roda o estimador real contra áudio real
renderizado a 90 BPM — inclusive o `misto`, que sem a dobra sairia a 45, e o
`groove16`, que precisa relatar desacordo.

---

## ADR-020 — Auralização nativa, com as notas em cache

**Data:** 2026-09-22 · **Status:** aceito · **Implementa a Camada 2 do ADR-006**

**Contexto.** A Camada 2 existia desde o ADR-006, mas era feita por fora: o
MuScriptor gerava a auralização, o Thoth não. Isso deixava a única verificação de
qualidade que não exige tab humana nem treino musical dependente de uma ferramenta
que o Thoth não controla — e fora do alcance de quem só roda `thoth`.

**Decisão.** `thoth auralizar <ref>` gera um WAV estéreo: o mix original à
esquerda, a transcrição renderizada à direita.

**As notas vão para o cache.** A transcrição custa minutos de CPU por música, e o
resultado dela morria com o processo: sobravam o `.gp5` e o `.musicxml`, ambos já
quantizados pelo BPM. Auralizar a partir deles mediria o exportador junto com o
transcritor — uma estimativa de andamento dobrada apareceria como transcrição
descolada, e o diagnóstico apontaria para o lugar errado. O pipeline passa a
gravar `cache/<id>/notas.jsonl`, em tempo absoluto, e a auralização lê de lá.
JSONL porque música longa passa de três mil notas e o arquivo continua legível
com `head`.

**Soundfont, não onda sintética.** Um seno em E1 (41 Hz) é quase inaudível em
caixa de notebook — exatamente na região que mais importa no baixo. O
`FluidR3_GM.sf2` (Electric Bass finger, GM 33) traz os harmônicos pelos quais a
altura é reconhecida no meio da música.

**O canal curto é esticado, nunca truncado.** `apad` iguala a transcrição à
duração do original. Cortar no menor dos dois esconderia o fim da música, que é
justamente onde o erro de andamento mais acumula.

**Custo aceito:** `pretty-midi` sai do grupo de dev para dependência de runtime, e
`fluidsynth` + soundfont viram pré-requisito da auralização (só dela — o resto do
pipeline não os toca). Ausência de qualquer um dos dois falha com mensagem
explícita, não silenciosamente.

**Teste.** `tests/unit/test_auralizacao.py` roda fluidsynth e ffmpeg de verdade
sobre áudio de verdade: confere que os dois canais existem e diferem, que a
duração bate com a do original e que o canal da direita tem mais energia durante
uma nota do que no intervalo entre notas.

## ADR-021 — O andamento é refinado pelas notas, junto com a fase da grade

**Data:** 2026-09-22 · **Status:** aceito

### Contexto

Escuta das sete transcrições do acervo: só o Equus soou certo, as outras seis com
"ritmo descolando". A medição está em `tasks/ritmo-diagnostico.md`.

O piso do transcritor, medido nas fixtures (metronômicas a 90 BPM exatos), é de 3 a
10 ms. As músicas reais ficavam entre 24 e 43 ms de distância mediana da semicolcheia
mais próxima — uma ordem de grandeza acima. O desalinhamento era real, não jitter.

A causa é `tempo.py`, que devolvia `round(bpm)`. No Equus são 107,5 → 108: 0,46% de
erro, 3,5 s de deriva acumulada ao longo de 756 s, dezenas de posições de semicolcheia.
O erro não aparece no início da música, só no fim — que é a descrição literal de
"descolando". O Equus escapou por ser o único material metronômico do acervo, e mesmo
ele saía a 34 ms.

### Decisão

`ajustar(onsets, bpm, faixa)` procura andamento e fase **em conjunto**, minimizando a
distância mediana dos onsets transcritos à grade. A busca fica restrita a ±3% da
estimativa do áudio.

- **Juntos, não em sequência.** Refinar o BPM mantendo a âncora em `t=0` *piora* quatro
  das sete (Equus 34 → 57 ms): grade mais precisa ancorada no lugar errado erra mais
  que grade grosseira alinhada por acaso. Não existe meia correção aqui.
- **±3% e não busca livre.** A busca irrestrita corria até o teto de 192–200 BPM em
  seis das sete — artefato de faixa, não pulso encontrado. O mix continua sendo a
  âncora: as notas refinam o andamento, não o escolhem. Transcrição ruim não pode
  arrastar o resultado para o dobro.
- **`--bpm` informado não é refinado** (`faixa=0`), só tem a fase ajustada. O número
  que você deu continua mandando (ADR-019); a âncora da grade ninguém informou.
- **O arquivo guarda o BPM arredondado, a quantização usa o fracionário.** GP5 e
  MusicXML só têm campo inteiro de andamento. As posições das notas ficam certas e a
  reprodução corre ~0,5% fora do original — o inverso, quantizar no inteiro, é o bug
  que este ADR corrige.
- **O deslocamento acontece antes de `monofonizar`.** `monofonizar` deduplica ticks e
  `eventos` recusa ticks repetidos: as duas contas têm de ser a mesma grade. Feitas em
  fases diferentes, um par aprovado por uma colapsa na outra e o exportador estoura —
  reproduzido em teste antes da correção.
- **O deslocamento de fase é só da partitura.** `notas.jsonl` continua em tempo
  absoluto do áudio: a auralização toca o MIDI contra o original, e deslocar ali
  dessincronizaria os dois canais.

### Consequência

Residual mediano, medido com as funções entregues:

| música          | antes   | depois  | BPM            |
|-----------------|---------|---------|----------------|
| Equus           | 34,4 ms | 12,6 ms | 108 → 107,50   |
| Sou Eu          | 29,5 ms | 10,5 ms | 129 → 128,00   |
| Feel Like       | 43,5 ms | 31,5 ms | 86 → 87,03     |
| Tive Razão      | 42,6 ms | 20,4 ms | 103 → 102,99   |
| SOJA            | 24,2 ms | 13,5 ms | 152 → 154,14   |
| Is It A Crime   | 36,8 ms | 26,2 ms | 112 → 111,82   |
| Smooth Operator | 31,3 ms | 16,9 ms | 117 → 119,14   |

Melhora nas sete, de 27% a 64%. Quatro chegam perto do piso do transcritor; três
(Feel Like, Is It A Crime, Tive Razão) continuam longe e preferiam uma grade
reajustada a cada 30 s. **Andamento variável segue sem veredito** — pode ser conteúdo
(ao vivo, rubato) e não arquitetura, e agora dá para medir sem o erro grosso por cima.

Verificado ponta a ponta no Equus (`--cordas 5`, a maior correção de andamento,
108 → 107,50): exporta sem estourar e mantém 3180 notas contra 3172 antes, com 28
descartes contra 36. A grade melhor alinhada preserva notas, não as perde.

A busca é O(400 × 120 × notas), alguns segundos numa música longa, contra minutos de
transcrição: irrelevante no total.

### Emenda (2026-09-23)

O veredito que ficou pendente saiu no ADR-034, e as três suspeitas nomeadas acima
estavam erradas em duas. Feel Like (`yt_5zqlgMh4aYs`) e Is It A Crime
(`yt_U-SHfpm5Bxk`) não têm andamento variável: o resíduo alto delas é jitter de
ataque do transcritor, e o ajuste por janela nelas balança sem tendência. Tive Razão
(`yt_8m6wrCCRvm8`) é o caso real — e é um degrau, 103,0 por cinco janelas e depois um
platô em ~105, não a deriva contínua que "reajustar a cada 30 s" pressupunha.

A decisão deste ADR não muda: a grade constante segue adequada, e o ADR-034 registra
por que o aviso de andamento variável não é implementável com um único caso.

## ADR-022 — A sustentação é escrita com ligadura, decomposta no exportador

**Data:** 2026-09-23 · **Status:** aceito

### Emenda (2026-09-23)

A "duração real" que `eventos()` passou a devolver é real no sentido de *não
truncada na barra* — não no sentido de sustentação medida. O MuScriptor preenche
`offset_s` com o onset da nota seguinte (ADR-033, provado contra fixture de duração
conhecida), então a ligadura que este ADR passou a escrever liga a nota até a
próxima, e não até onde ela parou de soar. O censo de notas encurtadas e a decisão
de decompor no exportador não mudam: ambos foram medidos sobre exatamente estes
dados. O que muda é a leitura — o legato que o ADR-022 restaurou é o legato do
transcritor, que é o único que existe nesta entrada.

### Contexto

`eventos()` cortava a duração de cada nota no fim do compasso, e o exportador GP5
escrevia a maior figura que coubesse e enchia **o resto com pausa**. As duas coisas
juntas apagavam sustentação: uma nota de 1,5 semínima começando no "quatro e" era
lida como colcheia seguida de pausa, e o legato do baixo virava staccato.

O corte estava em `rhythm.py`, camada compartilhada, mas o motivo era do GP5: um beat
vive dentro de um compasso e não tem como atravessar a barra. O MusicXML não tem essa
restrição — o `makeNotation` do music21 monta a ligadura sozinho a partir do offset — e
pagava o preço de uma limitação que não era dele.

Censo nas sete músicas do acervo, com a grade do ADR-021 (`cache/yt_*/notas.jsonl`):

| música          | notas | encurtadas | duração que soava |
|-----------------|-------|------------|-------------------|
| Equus           | 3180  | 53 (1,7%)  | 93,0%             |
| Sou Eu          | 779   | 104 (13,4%)| 92,3%             |
| Feel Like       | 1196  | 106 (8,9%) | 90,7%             |
| Tive Razão      | 1059  | 73 (6,9%)  | 93,8%             |
| SOJA            | 872   | 15 (1,7%)  | 96,3%             |
| Is It A Crime   | 778   | 205 (26,3%)| 74,2%             |
| Smooth Operator | 634   | 82 (12,9%) | 91,5%             |

Não é caso de canto: em Is It A Crime, uma nota em cada quatro saía curta e um quarto
da duração da música inteira virava pausa.

### Decisão

**`eventos()` devolve a duração inteira; quem decide como representá-la é o
exportador.** O único corte que resta é o da nota seguinte, que é musical — ataque novo
encerra o anterior — e não um limite de formato.

- **GP5** fatia o evento nas barras (`_fatiar_na_barra`), decompõe cada fatia em figuras
  e emite `gp.NoteType.tie` em tudo que não é o ataque. O nome da nota (`beat.text`) vai
  só no ataque: repetido na continuação, se leria como outro ataque.
- **MusicXML** não mudou uma linha. Recebendo o `quarterLength` verdadeiro, o
  `makeNotation` já produzia a ligadura — a limitação do GP5 é que o cegava.

### Consequências

- Cada compasso continua fechando em quatro tempos; o que sobra é a mesma nota
  continuando, não pausa.
- `tipos == [normal, tie]` e a soma das durações viraram teste de round-trip nos dois
  exportadores — nenhum mock: grava o arquivo e relê.
- A limitação "sem ligaduras" sai do docstring do `gp5.py`. Continuam valendo o 4/4
  fixo, a grade de semicolcheia e o andamento único (ADR-021).
- Ligadura entre compassos **vizinhos** é o que o fatiamento resolve. Nota que atravesse
  mais de uma barra sai igualmente encadeada, sem caso especial.
- `eventos()` tem exatamente dois consumidores, os dois exportadores (conferido por
  `grep` em `src/`): a mudança de contrato não alcança a auralização nem a avaliação.
- Verificado na música inteira de Is It A Crime, o pior caso do censo: **778 ataques
  para 778 notas de entrada nos dois formatos**, 215 compassos e nenhum fora de 4/4.
  Os três testes de ligadura do MusicXML foram conferidos vermelhos com o
  `rhythm.py` antigo — sem isso não passariam de tautologia escrita depois do fato.

## ADR-023 — Duração passa a ser medida: métrica informativa e teste ponta a ponta

**Data:** 2026-09-23 · **Status:** aceito

### Contexto

O ADR-006 fixou duas métricas e justificou não cobrar duração: o MuScriptor não é
confiável em offset, e exigir isso mediria o sustain do soundfont. A ressalva
continua certa. O que ela não previu é que **sem régua nenhuma de duração, um defeito
de duração nosso fica invisível**.

Medido no teste novo, com o corte na barra do ADR-022 reativado e três de treze notas
encurtadas:

```
Scores(onset_f1=1.0, note_f1=1.0, nota_offset_f1=0.923, duracao_ratio=1.0)
```

As duas métricas do ADR-006 pontuam **1,000**. Um quarto da duração de Is It A Crime
virava pausa e nenhum número do projeto se movia.

### Decisão

**Duas métricas novas em `Scores`, informativas e nunca critério de aprovação.**

- `nota_offset_f1` — nota F1 cobrando a duração, `offset_ratio=0.2` (padrão do
  mir_eval e da literatura). Comparável com publicação.
- `duracao_ratio` — mediana de duração estimada ÷ referência nas notas casadas por
  onset e altura, com o casamento feito em `offset_ratio=None`: filtrar por duração
  antes de medir duração escolheria só os acertos. `None`, não zero, quando nada casa —
  zero se leria como "todas as durações saíram nulas".

**Nenhuma das duas entra em piso de regressão.** A ressalva do ADR-006 é o motivo: o
número misturaria sustain do soundfont com erro de transcrição. Elas existem para
medir mudança nossa entre duas execuções do mesmo estímulo, não para reprovar o
modelo.

**E um teste ponta a ponta na suíte padrão** (`tests/integration/test_quantizacao_ponta_a_ponta.py`):
referência sintética → `ajustar`/`alinhar`/`monofonizar` → Viterbi → GP5 → releitura
do arquivo de volta a segundos, fundindo ligaduras → `avaliar`.

- A referência é **código, não arquivo**: `cache/` e `out/` são gitignorados (ADR-005),
  e teste que depende de artefato ausente não protege nada.
- Sem modelo e sem áudio, então fica **fora** dos marcadores `slow`/`network`: 2,9 s.
  Teste que só roda quando alguém lembra não protege nada.
- Três das treze notas atravessam a barra — 23%, a proporção medida em Is It A Crime.
  Uma travessia só não serviria: com uma, o corte na barra **passava** por todas as
  métricas, porque o erro caía exatamente em `0,2 × referência`.

### Consequências

- A afirmação que reprova a regressão é **nota a nota**
  (`test_nenhuma_nota_volta_encurtada`), não agregada. Mediana é robusta por
  construção: é o que se quer de um resumo e o oposto do que se quer de um teste.
- `Scores` ganhou dois campos. Nenhum consumidor constrói `Scores` posicionalmente
  fora do módulo (conferido por `grep`); os dois testes de igualdade foram acertados.
- A régua para B3 (dinâmica e articulação) já existe quando aquele item chegar.

## ADR-024 — A dobra para a faixa musical é desfeita pelas notas, por colisão na grade

**Data:** 2026-09-23 · **Status:** aceito

### Contexto

`dobrar_para_faixa` divide ou multiplica a estimativa até cair em [70, 160) — é a
defesa clássica contra o erro de dobro/metade de todo estimador. Mas ela **decide antes
de existir nota alguma**: o andamento é estimado do mix (é onde está a bateria), a
separação vem depois e a transcrição depois dela.

Consequência medida: uma música a 170 BPM sai dobrada para 85. A semicolcheia da grade
passa a ter o dobro da duração, ataques distintos caem no mesmo tick e `monofonizar` os
descarta como simultâneos. **64 notas viram 33.** Não é arredondamento: é metade da
música apagada, e o relatório de descarte culpa polifonia.

Só é alcançável pelo caminho **estimado** — `dobrar_para_faixa` é chamada apenas em
`estimar_andamento`. Um `--bpm` informado atravessa com `faixa=0` e nunca é dobrado.

### Medição — colisão na grade de semicolcheia, sete músicas do acervo

| música          | ÷2    | certo | ×2   |
|-----------------|-------|-------|------|
| Equus           | 37,0% | 1,2%  | 0,0% |
| Feel Like       | 22,5% | 2,8%  | 0,0% |
| Tive Razão      | 20,0% | 0,4%  | 0,0% |
| Sou Eu          | 4,5%  | 0,3%  | 0,0% |
| Is It A Crime   | 4,5%  | 1,0%  | 0,0% |
| Smooth Operator | 3,3%  | 0,2%  | 0,0% |
| SOJA            | 0,0%  | 0,0%  | 0,0% |

No andamento certo, 0,0–2,8%. Na grade grosseira pela metade, 20–37% onde há
semicolcheia — e **0,0–4,5% onde não há**. O sinal vale num sentido só: colisão alta
prova grade grossa; colisão baixa não prova nada.

### Decisão

`desdobrar(onsets, bpm)` em `services/tempo.py`, chamada no pipeline **entre a
transcrição e `ajustar`**, só no caminho estimado: dobra o BPM enquanto a colisão
passar de 10%, no máximo duas vezes.

- **O critério é colisão, não resíduo.** Resíduo melhora monotonicamente com grade mais
  fina, então escolher por resíduo elegeria sempre o candidato mais rápido.
- **Assimétrico de propósito.** Grade mais fina nunca colide mais, logo "menos colisão"
  também seria degenerado. O que autoriza dobrar é a colisão estar **alta** — não o
  dobro estar melhor.
- **10% está longe dos dois lados:** 3,6× o pior caso correto medido (2,8%) e menos da
  metade do melhor caso a resgatar (20,0%).
- **Mínimo de 8 notas.** Em 4 notas, uma colisão é 25%: a taxa seria ruído.
- **Teto de duas dobras.** Sem ele, ataques muito densos (trêmolo, ruído de transcrição)
  levariam a um andamento que instrumento nenhum toca.
- **Antes de `ajustar`, não depois.** `ajustar` refina ±3%; de 85 ele não alcança 170.

### Consequências

- Sou Eu, Is It A Crime, Smooth Operator e SOJA **não seriam resgatadas** se estivessem
  dobradas: 0,0–4,5% de colisão, abaixo do limiar. Música sem semicolcheia não denuncia
  grade grossa, e nenhuma medida de onset pode inventar essa informação. Isto é limite
  do sinal, não do limiar.
- `Resultado.desdobrado` e uma linha da CLI: o ADR-019 proíbe corrigir andamento em
  silêncio, e dobrar o BPM relatado é correção grande.
- `--bpm` informado continua intocado, e há teste disso: colisão total com `--bpm 90`
  devolve 90.
- `services/tempo.py` passou a importar `services/rhythm.py` (por `para_ticks`). Mesma
  camada, sem ciclo — `rhythm` só conhece `domain`.

## ADR-025 — Pedido inválido é recusado na entrada, não interpretado

**Data:** 2026-09-23 · **Status:** aceito

### Contexto

Dois parâmetros de `transcribe` aceitavam qualquer coisa e davam um jeito:

- **`--bpm 0`** atravessava tudo. `para_ticks` multiplica por `bpm/60`, então **toda**
  nota vira o tick zero; `monofonizar` guarda uma e descarta o resto como simultâneas.
  Medido: 4 notas entram, 1 sai — e o relatório diz "descartada: simultânea", culpando
  o áudio por um número que quem pediu digitou. `--bpm -120` é pior: grade negativa.
- **`--cordas 6`** virava 4 calado. A tablatura sai plausível — só que para outro
  instrumento. É o modo de falha mais caro que existe: nada avisa.

A API já se defendia (`Field(ge=20, le=300)`, `cordas` 4–5). Só a CLI e o uso como
biblioteca estavam abertos, com os limites duplicados em número solto.

### Decisão

- `BPM_MINIMO, BPM_MAXIMO = 20, 300` em `services/tempo.py`, uma fonte só, importada
  pela CLI (`min=`/`max=` do Typer), pela API (`Field`) e pelo pipeline.
- `transcrever` **valida antes de tudo**: antes do download, antes da separação. Quem
  usa como biblioteca não passa pela CLI, e o erro não pode custar minutos de CPU.
- A faixa aceita (20–300) é deliberadamente mais larga que a faixa musical de
  `dobrar_para_faixa` (70–160). A primeira recusa erro de digitação; a segunda desfaz
  dobro/metade de uma *estimativa*. Confundir as duas recusaria um pedido legítimo de
  180 BPM.
- `AFINACOES = {4: TUNING_BASS_4, 5: TUNING_BASS_5}` na CLI, e `typer.BadParameter` para
  o que não está no catálogo. A porta de entrada do `TUNING_BASS_DROP_D` é outro item
  (A10/B4) e cabe aqui quando chegar: o dicionário é o lugar.

### Consequências

- `--bpm 0`, `--bpm -120` e `--bpm 9999` falham com código de saída 2 e mensagem do
  Typer citando a faixa; `--cordas 6` cita as afinações que existem.
- Validação em dois lugares (fachada e pipeline) é deliberada, não redundância
  esquecida: a fachada dá mensagem boa, o pipeline garante a invariante.
- Nenhum `--bpm` dentro da faixa mudou de comportamento. `--bpm 20` continua sendo
  aceito e continua sendo uma grade grosseira — isto recusa o impossível, não o ruim.

### Emenda (2026-09-23, a chave do catálogo passou a ser nome)

O catálogo de afinações mudou de chave: `{4: ..., 5: ...}` virou
`{"4": ..., "5": ..., "drop-d": ...}`, e mora em `domain/models.py` (ADR-028). Só o
**tipo da chave** mudou; a decisão desta ADR fica inteira:

- Nome fora do catálogo continua sendo `typer.BadParameter` na CLI e 422 na API —
  nunca queda calada para a afinação padrão.
- A mensagem continua listando o que existe, agora pelos nomes.
- O motivo da troca é que contar cordas não conseguia nomear drop D: são quatro
  cordas, como a padrão, e nenhuma afinada igual. O parágrafo acima que previa o
  dicionário como lugar do `TUNING_BASS_DROP_D` se cumpriu — com chave de outro tipo.

## ADR-026 — O cache guarda só o que está inteiro, e a ferramenta que falha explica por quê

**Data:** 2026-09-23 · **Status:** aceito

### Emenda (2026-09-24) — a versão do demucs entra na chave

O item 3 fez o cache pertencer ao modelo, mas não à versão: com `demucs@4.1.0` pregado
(emenda do ADR-039), um stem de outra versão ainda passaria por este. O cache agora é
`<out>/<modelo>/<versão>/<nome>/`, e `DemucsSeparator.versao` é o único lugar do valor —
o comando e a chave leem o mesmo campo. Stem sob o layout antigo, sem versão, não conta
como cache de ninguém. Trocar o pin e voltar não exige apagar nada: cada versão tem o
próprio diretório.

Os 13 stems desta estação foram movidos para `htdemucs_ft/4.1.0/` em vez de refeitos:
4.1.0 é a única versão que o `uv` desta estação já baixou. Verificado com o demucs real
(`-m "slow and not network"` nos dois testes de separação, 78 s).

### Contexto

Três defeitos da mesma família: o Thoth chama seis ferramentas externas, guarda o
resultado delas em cache, e não tratava nem a falha nem a interrupção.

1. **`stderr` descartado em seis pontos.** Com `capture_output=True` e `check=True`, o
   `CalledProcessError` do Python guarda o texto num atributo e **não o põe na
   mensagem**. A falha chegava como "returned non-zero exit status 1"; o motivo, que a
   ferramenta escreveu por extenso, morria ali. Num pipeline de minutos por música, é a
   diferença entre corrigir e adivinhar.
2. **Nenhuma escrita de cache era atômica.** O teste de cache é `existe?`. Interrupção
   no meio — Ctrl-C, disco cheio, a ferramenta morrendo — deixava arquivo pela metade
   que **toda execução seguinte aceitava como pronto**. O demucs escreve `no_bass.wav`
   antes de `bass.wav`: morrer entre os dois deixava meio stem de pé.
3. **O cache do demucs não pertencia ao modelo.** `localizar_stems` varria `out_dir`
   inteiro com `rglob`, e o demucs aninha por modelo (`<out>/<modelo>/<nome>/`). Stem do
   `mdx_extra` passava por `htdemucs_ft` — e a diferença entre dois separadores é
   exatamente o que o ADR-010 mede.

### Decisão

- **`thoth/processos.py`**: `rodar(comando, timeout=...)` devolve o `stdout` e levanta
  `ErroDeProcesso` com o fim do `stderr` (800 caracteres — o começo é banner de versão,
  o fim é o motivo). `FileNotFoundError` **continua passando direto**: "não está
  instalada" é outra conversa, e a auralização depende disso para o fluidsynth.
  Módulo de topo, não de `services/`, porque quem chama são adapters e services.
- Cada módulo **mantém o próprio tipo de erro na fronteira**: a auralização traduz
  `ErroDeProcesso` em `AuralizacaoError`, o `ytdlp_source` continua com o tratamento
  próprio e o `IngestError` dele — ele já não descartava o `stderr`, então não foi
  mexido.
- **`thoth/arquivos.py`**: `escrita_atomica(destino)` e `diretorio_atomico(destino)`,
  dois gerenciadores de contexto que dão um caminho **vizinho do destino** e promovem
  com `os.replace` só na saída sem erro. Convenção para toda escrita de cache daqui
  para frente.
  - Vizinho, e nunca `tempfile`: `/tmp` nesta estação é outro ponto de montagem, e
    `os.replace` entre montagens levanta `Invalid cross-device link`.
  - A extensão é preservada (`mix.wav` → `mix.parcial.wav`): ffmpeg e yt-dlp escolhem
    o formato de saída por ela.
  - `.parcial` fica fora de tudo que qualquer verificação de cache procura, então
    sobra de execução anterior nunca é confundida com resultado.
- **`separate` procura em `out_dir / self.model`**, não em `out_dir`. O modelo já está
  no caminho que o demucs escreve; passou a estar no caminho que o Thoth lê. O
  diretório provisório se chama `<modelo>.parcial` — nunca `<modelo>` —, e o nível
  aninhado é promovido para que o resultado não fique em `<out>/<modelo>/<modelo>/`.

### Consequências

- Os quatro caminhos de escrita de cache (notas JSONL, WAV convertido, WAV do YouTube,
  stems do demucs) são atômicos. Testes discriminantes, verificados vermelhos antes:
  falha no meio deixa o destino **intocado** e nenhum `.parcial` para trás.
- Trocar o modelo do demucs não exige mais apagar cache na mão; os dois convivem.
- `local_source:50` e `auralizacao:152` mandavam o `stderr` do ffmpeg para o terminal ao
  vivo; agora ele aparece só na falha. Com `-loglevel error` nos dois, não se perde
  nada — mas é mudança de comportamento, e está registrada aqui.
- O teste da separação foi remedido depois da mudança de layout: 0,968, o mesmo valor,
  com o demucs real (`ref=16 est=15`).

## ADR-027 — Um job por vez, e histórico com teto

**Data:** 2026-09-23
**Contexto:** A API aceitava jobs concorrentes e guardava todos para sempre.

Dois pipelines simultâneos não são independentes: escrevem no mesmo diretório
encenado do cache de separação (`<modelo>.parcial`, que um apagaria debaixo do
outro, ADR-026) e exportam para o mesmo nome de artefato, derivado do título
(ADR-017). O primeiro sintoma não seria erro, seria arquivo trocado — o pior modo
de falha possível numa ferramenta de estudo.

O dict `jobs` também não tinha teto. Num processo que fica de pé por semanas,
cada `Resultado` retido segura as notas transcritas da música inteira.

### Decisão

- **Execução serializada** por um `threading.Lock` em `_Estado`, tomado dentro de
  `_rodar`. Não é limitação disfarçada de feature: o módulo já dizia "uso pessoal,
  uma música por vez" — agora o código garante o que o docstring afirmava.
- **`Job.status` nasce `"na fila"`** e vira `"rodando"` dentro da trava. Quem
  espera passa a saber que espera, em vez de ver "rodando" por minutos sem que
  nada rode. A UI e os testes só comparam com `pronto`/`erro`, e exibem o resto
  como texto: o estado novo aparece sem quebrar nada.
- **`LIMITE_DE_JOBS = 50`**, aplicado em `criar` por `descartar_antigos`, que
  descarta os **concluídos** mais antigos (`dict` preserva ordem de inserção).
- Job na fila ou rodando **nunca** é descartado, mesmo sendo o mais antigo. Se só
  houver inacabados, o histórico passa do teto de propósito: perder o resultado de
  minutos de CPU é pior que guardar um job a mais.

### Consequências

- Uma fila serializada, não um pool: dois pedidos simultâneos terminam ambos, em
  ordem. O segundo espera, e o teste prova que ele não entra no pipeline enquanto
  o primeiro está dentro.
- Paralelismo real (jobs em processos, cache por job) fica fora de escopo; o custo
  aqui é CPU, e a estação tem uma.
- O teto é do histórico, não do disco: artefato exportado continua em `out/`
  depois do job sair da memória — é o que o ADR-017 já previa.

## ADR-028 — Afinação e digitação por nome, não por contagem

**Data:** 2026-09-23 · **Status:** aceito

### Contexto

Duas constantes existiam, eram usadas por testes e não tinham porta de entrada
nenhuma — nem CLI, nem API, nem página de estudo:

- **`TUNING_BASS_DROP_D`** (D1 A1 D2 G2). O seletor era `--cordas 4|5`, e drop D tem
  **quatro** cordas: contar cordas não consegue nomeá-la. A constante estava
  inalcançável por construção, não por esquecimento.
- **`PADRAO`** em `fretboard.py`, o perfil de custos do baixista experiente.
  `ViterbiFretAssigner.custos` tem `INICIANTE` como default (ADR-006), então `PADRAO`
  só existia para quem usasse a biblioteca direto.

### Decisão

- **Dois catálogos nomeados, cada um no módulo que é dono do conceito:**
  `AFINACOES = {"4", "5", "drop-d"}` em `domain/models.py` e
  `DIGITACOES = {"iniciante", "experiente"}` em `services/fretboard.py`.
- **`--afinacao` e `--digitacao`** na CLI, `afinacao` e `digitacao` no `Pedido` da API,
  dois `<select>` na página de estudo. O `--cordas`/`cordas` sai: dois seletores para a
  mesma coisa seria pior que trocar o nome de um.
- Nome desconhecido é recusado, citando o catálogo — `typer.BadParameter` na CLI,
  `field_validator` (422) na API. É a decisão do ADR-025, que ganhou uma emenda.
- `Executor` (o Protocol da API) passa a carregar `assigner`, porque a digitação
  escolhida só chega ao pipeline por ele.
- **`PADRAO` não é o default**, apesar do nome: o default é `INICIANTE` (ADR-006). Está
  escrito no `#:` do `DIGITACOES` porque "padrão" em pt-BR convida a "corrigir" isso, e
  a troca pareceria melhoria — a mesma forma da armadilha de fixture reescrita em
  `lessons/workflow.md`.

### Consequências

- `--afinacao drop-d` passa a existir, e o perfil do experiente também. Nenhuma
  constante do `fretboard` ou de afinação fica sem porta de entrada.
- O JS do formulário perdeu o `Number()`: `Number("drop-d")` é `NaN`, que serializa
  como `null` e daria 422. Nenhum teste de servidor pegava isso — a suíte padrão pula
  `navegador` —, então o formulário ganhou teste próprio, que **dirige a página**:
  preenche, clica em Transcrever e confere a afinação que chegou ao executor.
  Verificado: `uv run pytest -m navegador` → 3 passed.
- A escolha de digitação vale para a exportação, não para a tela: reexportar com outro
  perfil é um job novo. Fazer a página recalcular a digitação exigiria o assigner no
  navegador — está fora de escopo.

## ADR-029 — A janela do aviso de oitava é a nota, e só a nota

**Data:** 2026-09-23 · **Status:** aceito

### Contexto

`verificar_oitavas` tinha dois defeitos de janela, um de correção e um de custo:

1. **Ignorava `offset_s`.** Analisava 0,6 s fixos a partir do `onset_s`. Numa linha de
   semicolcheias a 120 BPM a nota dura 0,125 s: a janela media quase cinco notas. Se a
   vizinha tiver a fundamental que falta na analisada, o aviso não sai — e é justamente
   o caso que ele existe para pegar. Medido no teste novo: nota de 0,3 s seguida de um
   30,9 Hz forte passava calada.
2. **Lia o stem inteiro na memória.** `_ler_mono` fazia `readframes(getnframes())` e
   convertia tudo para `float64` antes de olhar qualquer nota. Para os 16 min de
   *Equus*: ~170 MB de quadros e ~680 MB de `float64`, para analisar meio segundo por
   nota. Medido num WAV de 30 s: pico de 26,5 MB para uma nota.

### Decisão

- A janela é `min(janela_s, offset_s - onset_s)`. `janela_s` passa a ser **teto**, não
  tamanho. O piso de 50 ms (abaixo disso não há resolução) fica como estava.
- A leitura é por posição: `setpos` + `readframes` dos quadros daquela nota, com o
  arquivo aberto uma vez para a lista toda. `_ler_mono` virou `_trecho_mono`.
- Nota que começa depois do fim do arquivo continua sem opinião, agora por
  `total - inicio` dar zero quadros — nunca por `setpos` fora do arquivo.

### Consequências

- Nota curta é medida com menos resolução: 0,2 s dão 5 Hz de bin, que ainda separam
  30,9 de 61,7 Hz — as duas hipóteses do caso da Fase 0, 30 Hz apartadas. Abaixo de
  50 ms a função continua calada em vez de opinar mal.
- O limiar de 0,40 foi calibrado com janela de 0,6 s (Fase 0). Janela menor mede a
  nota, não a vizinhança, então a razão fica mais fiel — mas a calibração não foi
  refeita nota a nota: o que foi verificado é que os testes com modelo real continuam
  no mesmo número.
- O custo de memória passa a ser uma janela, não a música: ~0,2 MB para 0,5 s. Medido
  no teste: pico abaixo de 2 MB onde antes eram 26,5 MB.

## ADR-030 — a oitava acima é ranqueada, não afirmada (B8)

**Data:** 2026-09-23 · **Status:** aceito

### Contexto

`OctaveWarning.suggested_pitch` era `nota.pitch + 12` incondicional: o mesmo número
para toda nota sinalizada, sem nenhuma medição por trás. O aviso dizia "a fundamental
não se sustenta" (medido) e "então é uma oitava acima" (palpite), com a mesma cara. E
o palpite era o que chegava ao usuário: a CLI imprimia `pitch@instante`, o `_resumo`
expunha `pitch` e `onset_s`, e a página repetia os dois — a razão medida, que é a
única evidência que o módulo tem, não saía em lugar nenhum.

O discriminador do ADR-007 é interno à nota: `f0 / 2·f0`. Ele se aplica igualmente à
hipótese `pitch + 12`, cuja fundamental é o 2º harmônico desta nota e cujo 2º
harmônico é o 4º desta. Medir as duas custa um pico a mais no espectro que já está
calculado.

### Decisão

- A sugestão sai **só quando a candidata explica melhor**: `razao(p+12) > razao(p)`.
  Quando não explica, `suggested_pitch` é `None` — a nota continua sinalizada, sem
  alternativa. `OctaveWarning` ganha `suggested_ratio` ao lado de `fundamental_ratio`.
- **A comparação é entre as duas razões, não um segundo corte pelo `limiar`.** O 0,40
  foi calibrado na população da hipótese original (Fase 0: 12/12 pegas, 11/127 falsos)
  e nunca na da candidata. `limiar` continua com um único trabalho: decidir se avisa.
  Quem for "consertar" isto depois adicionando um segundo corte está reusando uma
  calibração que não existe.
- O gatilho (`razao < limiar`) não muda em byte nenhum: o **conjunto** de notas
  avisadas é o mesmo de antes, só o que se diz sobre cada uma mudou.
- Expor nos três lugares: CLI (uma linha por aviso, com as duas razões), `_resumo`
  (`sugestao`, `razao`, `razao_sugerida`) e a página.
- `inf` serializa como `null`. A razão da candidata é `inf` quando não há 4º harmônico
  no trecho, e `json.dumps` emite `Infinity` — que é JSON inválido e faz o
  `JSON.parse` da página recusar o corpo inteiro. Nenhum teste que use `.json()` do
  Python percebe, porque o `json` da biblioteca padrão aceita `Infinity` na leitura.

### Consequências

- O aviso passa a ser diagnóstico: `23@1.2s → 35 (razão 3,00 contra 0,12)` ou
  `23@1.2s → nenhuma oitava explica melhor (razão 0,33)`.
- Os testes com modelo real não precisaram ser refeitos — o gatilho é idêntico e
  nada em `tests/integration/test_separacao_fase0.py` afirma sobre a sugestão. A
  corrida `-m "slow and not network"` de antes desta mudança (12 passed em 205 s)
  continua valendo.
- Quem consumia `suggested_pitch` como `int` passa a receber `int | None`. Único
  consumidor no repositório era o próprio aviso.
- A página ganhou teste que a dirige (`-m navegador`, 4 passed): a suíte padrão não
  olha para o `index.html`, e foi exatamente essa a armadilha paga no ADR-028.

## ADR-031 — a grafia do acidente segue o tom, com margem (B9)

**Data:** 2026-09-23 · **Status:** aceito

### Contexto

O ADR-018 fixou o sustenido porque o Thoth não sabia o tom: a tecla preta entre lá e
si saía sempre `A#`. Em tom bemol isso está errado em toda nota alterada.

Medido em `cache/*/notas.jsonl` (sete músicas, corpus local — `cache/` é gitignorado
pelo ADR-005, então **este registro é a única cópia do número**):

| fonte           | notas | com acidente | tom estimado  | corr  | melhor de sinal oposto | margem |
|-----------------|-------|--------------|---------------|-------|------------------------|--------|
| yt_4dJz6U3_Xlk  | 3180  | 439 (13,8%)  | e minor (+1)  | 0,696 | d minor (−1) −0,078    | 0,774  |
| yt_4kd_eR4216g  |  779  | 593 (76,1%)  | c# minor (+4) | 0,726 | A- major (−4) 0,324    | 0,403  |
| yt_5zqlgMh4aYs  | 1197  | 258 (21,6%)  | f minor (−4)  | 0,590 | C major (0) 0,590      | 0,000  |
| yt_8m6wrCCRvm8  | 1059  | 110 (10,4%)  | a minor (0)   | 0,788 | d minor (−1) 0,277     | 0,511  |
| yt_QTOyeFQgZKk  |  872  | 598 (68,6%)  | c# minor (+4) | 0,882 | e- minor (−6) 0,262    | 0,620  |
| yt_U-SHfpm5Bxk  |  778  | 185 (23,8%)  | f minor (−4)  | 0,783 | C major (0) 0,456      | 0,327  |
| yt_g81jzIwyDjg  |  634  |  33 (5,2%)   | d minor (−1)  | 0,778 | G major (+1) 0,684     | 0,095  |

Três das sete estimam tom bemol — nelas *toda* nota alterada saía mal escrita, ~476
notas somadas. E uma delas é um **empate exato**: fá menor 0,590 contra dó maior
0,590. Esse é o caso que decide o desenho.

Errar aqui é pior que não opinar, e de um jeito que o `--bpm` não tem: andamento
errado se ouve, armadura errada é **silenciosa** — não muda nota nenhuma, só como
ela é escrita. Medido numa linha de 12 notas em mi menor, contando `<accidental>` no
MusicXML: **7** acidentes impressos com a armadura certa, **9** sem armadura nenhuma
(o que havia), **11** com quatro bemóis errados. O music21 não respeleta contra a
armadura, então não há acidente duplo — o custo do erro é bequadro em quase toda nota.

### Decisão

- `services/tonalidade.py`: `estimar_tom(notas)` (music21/Krumhansl, ponderado pela
  duração) e `tom_de_texto("Bb maior")`. `Tonalidade` tem `nome`, `sharps` e `margem`.
- **A margem é contra a melhor interpretação de sinal oposto**, não contra a segunda
  colocada. O que decide a grafia é o sinal da armadura: mi menor e sol maior escrevem
  igual, então empate entre relativas é inofensivo. Com a segunda colocada crua, seis
  das sete margens ficariam entre 0,06 e 0,10 e o empate real não se distinguiria.
- `MARGEM_MINIMA = 0.05`. Na tabela, seis passam (0,095 a 0,774) e só o empate exato
  (0,000) é recusado — o vizinho mais próximo dele está quase dez vezes acima.
- Abaixo da margem, **nada muda**: sustenidos e nenhuma armadura, exatamente o que a
  partitura tinha antes deste ADR. É o mesmo princípio do `andamento.confiavel`.
- `tom` informado manda e não passa por margem (`margem is None`) — ADR-019.
  Ilegível é `ValueError`/`BadParameter`/422, nunca dó maior calado (ADR-025).
- Os dois exportadores recebem `armadura: int | None`. O MusicXML escreve
  `key.KeySignature`; o GP5 não tem onde escrevê-la e usa o sinal só para o nome do
  beat. `nome_da_nota(pitch, *, bemois=False)` mantém o sustenido como default.
- Validação do `--tom` antes do download e dos minutos de CPU, como o `--bpm` (ADR-025).

### Consequências

- A parte que pode **piorar** o artefato é a armadura no MusicXML, e é exatamente ela
  que a margem protege. Quem quiser mexer no número mexe sabendo disso.
- O tom aparece na CLI, no `_resumo` (`{nome, armadura, margem}`) e na página, que
  ganhou campo de tom e relato da grafia — com teste de navegador que dirige os dois
  (`-m navegador`, 5 passed).
- A estimativa roda sobre as notas que vão para a partitura, com teto de 2000 notas
  (é um histograma ponderado: música longa satura muito antes). Foi com esse teto que
  a tabela acima foi medida.
- Nenhum teste lê `cache/`: as fixturas de tonalidade são linhas sintéticas em código,
  como manda o ADR-023. O corpus serviu para escolher o número, não para travá-lo.

## ADR-032 — a posição da mão faz parte do estado, não da nota (B7)

**Data:** 2026-09-23 · **Status:** aceito

### Contexto

O custo de transição era medido entre dois trastes: `if traste_a and traste_b`.
Corda solta zerava a conta — corretamente, porque a mão não se move para tocá-la —,
mas também **apagava** de onde ela estava. A nota seguinte partia do traste 0, e
atravessar o braço através de uma solta saía de graça.

O enunciado do checklist (`3 → 0 → 15 sai de graça`) **não reproduz**: o custo de
emissão limita o braço ao traste ≤10 no acervo, então o teleporte existe mas é curto.
Medido nas sete músicas de `cache/` (7924 notas de baixo de 4 cordas), contando
pisada → solta(s) → pisada com distância acima de 4 trastes:

| perfil     | saltos >4 trastes | saltos >2 trastes | pior salto | posição muda |
|------------|-------------------|-------------------|------------|--------------|
| experiente | 27 → **8**        | 76 → **54**       | 8 trastes  | 22 (0,28%)   |
| iniciante  | 19 → **17**       | 64 → **62**       | 5 trastes  | 2 (0,03%)    |

O iniciante quase não se move porque o `acima_da_janela = 2.0` e o `deslocamento =
1.5` do ADR-006 já prendem a mão no grave — o defeito estava escondido pelo perfil
default. Ou seja: **quem usa o Thoth como ele vem não vai ver diferença.** Quem
escolhe "experiente" perde 70% dos saltos inventados.

Os 8 que sobram no experiente são genuínos, e foi por isso que foram lidos um a um:
em cinco deles o destino é o traste 9 do pitch 52, cujas alternativas são 14, 19 e 24
— o 9 *é* a opção barata; em dois o destino é o traste 1 do pitch 29, que é a **única**
casa possível. A mão precisa mesmo andar. Estão **precificados, não escondidos**.

### Decisão

O estado do Viterbi passa de `(corda, traste)` para `(corda, traste, mão)`, onde
`mão` é o último traste **pisado** — e `None` enquanto a mão ainda não foi colocada
no braço. O deslocamento é cobrado contra `mão`, não contra o traste anterior.

- `mão = None` na abertura não paga nada: antes do primeiro ataque há o tempo do
  mundo para posicionar, e cobrar contra a pestana inventaria um salto na primeira
  nota — o mesmo erro, do outro lado. Com os pesos de hoje isso não é observável na
  saída (deslocamento-desde-a-pestana e emissão crescem os dois com o traste, na
  mesma direção, então nunca invertem a escolha), então o teste que o trava usa
  pesos que isolam o termo. Se `Custos` mudar, o teste avisa.
- **Nenhum peso novo.** A correção é de estado, não de calibração: não reabre nada
  que o ADR-006/ADR-028 mediu.
- O número de estados **não explode**: nota pisada colapsa a mão no próprio traste,
  então as mãos só ramificam dentro de uma corrida de soltas consecutivas — no
  máximo tantas quantas a última pisada tinha opções (≤4). Medido: 0,06s → 0,06s
  para as 7924 notas, diferença abaixo do ruído.

### Consequências

- `_transicao` recebe o estado, não um par — assinatura privada, sem chamador fora
  do módulo (verificado por grep antes da mudança).
- A leitura ampla do título do item ("digitação otimiza posição, não técnica":
  articulação, dinâmica, deslizes, pestana) **não** entra aqui — é território do B3,
  e fica registrado para não desaparecer.
- Nenhum teste de regressão se move: o `COM_SEPARACAO_NOTA_F1 = 0.968` mede detecção de
  nota, não digitação.

## ADR-033 — dinâmica e articulação não são inferíveis desta entrada (B3)

**Data:** 2026-09-23 · **Status:** aceito · **Resultado: negativo, nenhum código**

### Contexto

O item B3 propunha inferir candidatos de dinâmica e articulação do stem — RMS no
ataque, duração, continuidade de pitch — e expô-los como aviso, não como verdade.
As três hipóteses foram medidas antes de qualquer linha de código. As três falham,
por três motivos diferentes.

**1. Articulação: `offset_s` é preenchimento, não medida.** Provado na fonte, não
inferido. Uma fixture renderizada com notas de 0,45 s separadas por 0,10 s de
silêncio — duração *conhecida* — passou pelo modelo real e voltou com vãos
contíguos: `0,51→1,09`, `1,09→1,65`, `1,65→2,20`. No acervo, a lacuna
`offset → próximo onset` é **exatamente zero** em 83,3% a 99,7% das notas (as
lacunas não nulas são pausas entre frases: p99 até 1652 ms). Ou seja,
`duration_s` é tempo até a próxima nota. Qualquer razão duração/passo mede a
convenção do transcritor: ela dá 83% a 99,6% de "legato", o que não é observação
musical nenhuma.

**2. Dinâmica: não está na saída do modelo, e do áudio não há como calibrar.** A
mesma fixture foi renderizada com velocidade MIDI alternando 120 e 40 — proporção
de 3:1. Os campos do JSONL cru são exatamente `index, instrument, pitch,
start_time, type` e `end_time, start_event_index, type`: **não há campo de
dinâmica**, e a diferença de velocidade é descartada. Do áudio, o RMS dos
primeiros 50 ms contra a mediana da música dá IQR de 2,4 a 5,6 dB, e notas acima
de +6 dB são 0,0% a 1,7% (zero na música mais longa). Para comparação, p→f num
instrumento real é da ordem de 20 dB. Existe sinal no ataque medido contra o
próprio sustain da nota (mediana +0,9 a +5,1 dB, p75 até +15,7) — mas ~0 dB em
`yt_4dJz6U3_Xlk`, e é nível de saída do Demucs, não a mão de quem toca.

**3. Deslize: o discriminador testado não tem poder.** Pico espectral em 25–350 Hz
por quadro de 46 ms, procurando quadro cujo f0 caia estritamente entre as duas
alturas. Controle interno: o mesmo teste em pares separados por mais de 150 ms de
silêncio, que **não podem** ser deslize.

| música          | candidatos | transita | controle | transita |
|-----------------|-----------:|---------:|---------:|---------:|
| yt_4dJz6U3_Xlk  | 60 | 70% |  3 | 67% |
| yt_4kd_eR4216g  | 60 | 57% | 60 | **72%** |
| yt_5zqlgMh4aYs  | 60 | 40% | 39 | **46%** |
| yt_8m6wrCCRvm8  | 60 | 70% | 46 | 59% |
| yt_QTOyeFQgZKk  | 60 | 70% | 60 | 65% |
| yt_U-SHfpm5Bxk  | 60 | 13% | 14 | **21%** |
| yt_g81jzIwyDjg  | 60 | 33% |  8 | 12% |

Em três músicas o controle dispara **mais** que os candidatos. O que o teste acha
é o pico espectral vagando entre harmônicos e vazamento de outros instrumentos no
stem.

### Decisão

**Nada é implementado.** Nem serviço, nem aviso, nem campo.

O padrão de calibração deste projeto é o dele mesmo: o F1 de 0,968, o limiar de
oitava sobre 12 notas erradas conhecidas, a margem do ADR-031 sobre sete músicas.
B3 não tem rótulo nenhum — e um aviso cujo corte não se calibra não é aviso, é
palpite com aparência de medida. O único sinal residual (ataque contra o próprio
sustain) é exatamente a forma de coisa que parece entregável e depois dispara de
forma inconsistente conforme o material.

Precisão nas duas direções, para não superafirmar o negativo:

- **Articulação** é impossibilidade provada: o dado não contém a informação.
- **Dinâmica** não está na saída do modelo e, do áudio, tem espalhamento pequeno
  e sem rótulo para calibrar. Não é "fisicamente impossível" — é inverificável
  aqui.
- **Deslize** é *este discriminador* sem poder, não prova de que deslize seja
  indetectável. Um rastreador de f0 de verdade (pYIN, CREPE) não foi tentado, e
  seria dependência pesada nova numa estação CPU-only — o que é por si só motivo
  para não persegui-lo agora.

O que reabriria o item: tablatura humana de referência (Camada 3 do ADR-007) para
servir de rótulo. Sem isso, não há o que medir contra.

### Consequências

O achado sobre `offset_s` vale muito além de B3, e ninguém procurando por ele vai
abrir um ADR chamado "B3 não dá". Ele foi registrado onde o leitor tropeça:

- **`NoteEvent.duration_s`** ganhou docstring — era a propriedade sem documentação
  nenhuma, e é o lugar onde o fato pertence.
- **`services/tonalidade.py`** — o comentário dizia que a ponderação por duração
  impede a nota de passagem de pesar como "a tônica que fica soando". Sob
  preenchimento isso prometia mais do que o dado dá; o peso é o do *espaço* na
  frase. Os números do ADR-031 continuam válidos: foram medidos exatamente nesta
  condição.
- **ADR-022** ganhou emenda: a "duração real" é real por não ser truncada na
  barra, não por ser sustentação medida.
- **`octave_check` fica melhor do que sabia**: janela que para no `offset_s` é
  janela que para no próximo onset, que é precisamente o que o ADR-029 queria.

Para **B2**, isto já resolve metade da medição: tudo que se leia de duração lê o
preenchimento. Mas **onset é medida de verdade**, e swing é fenômeno de razão
entre onsets — a medição de B2 deve apontar para razões de intervalo entre
ataques contra a grade, ignorando duração.

## ADR-034 — a grade de semicolcheia não é o teto; o jitter do transcritor é (B2)

**Data:** 2026-09-23 · **Status:** aceito · **Resultado: negativo, nenhum código**

### Contexto

O item B2 afirmava que a representação rítmica — só semicolcheia reta, andamento
constante — era o maior teto de fidelidade depois das ligaduras. Medido no acervo
local (`cache/*/notas.jsonl`, sete músicas; `cache/` é gitignorado pelo ADR-005, então
**este registro é a única cópia dos números**), a premissa está errada.

Só onsets entram na medição: o ADR-033 provou que `offset_s` é preenchimento até a
nota seguinte, então toda leitura derivada de duração leria o transcritor, não a
música.

**1. Qual grade explica os ataques.** Distância mediana do onset à posição mais
próxima de cada grade, no BPM já refinado pelo ADR-021:

| música          | BPM    | 16as    | tercina | 32as    | swing 0,60 | swing 2/3 |
|-----------------|--------|---------|---------|---------|------------|-----------|
| yt_4dJz6U3_Xlk  | 107,50 | 12,6 ms | 46,9 ms | 12,4 ms |  60,0 ms   |  65,7 ms  |
| yt_4kd_eR4216g  | 128,02 | 10,4 ms | 38,3 ms | 10,3 ms |  88,4 ms   |  83,5 ms  |
| yt_5zqlgMh4aYs  |  87,03 | 30,8 ms | 58,6 ms | 21,0 ms |  77,4 ms   |  81,5 ms  |
| yt_8m6wrCCRvm8  | 102,99 | 20,0 ms | 42,0 ms | 15,0 ms |  62,6 ms   |  56,0 ms  |
| yt_QTOyeFQgZKk  | 154,14 | 13,5 ms | 27,2 ms | 10,6 ms |  23,9 ms   |  32,7 ms  |
| yt_U-SHfpm5Bxk  | 111,82 | 26,2 ms | 45,1 ms | 15,5 ms |  65,9 ms   |  69,5 ms  |
| yt_g81jzIwyDjg  | 119,14 | 16,9 ms | 36,7 ms | 14,6 ms |  50,4 ms   |  50,3 ms  |

A semicolcheia ganha das sete rivais nas sete músicas, com folga: nenhuma grade de
tercina ou de swing chega perto. **E a grade de fusa quase não melhora** — quatro
músicas ganham 0,1 a 2,9 ms dobrando a resolução. Dobrar a grade só ajuda se o
resíduo for erro de quantização; aqui ele não é. O resíduo de 10 a 31 ms é jitter de
ataque do transcritor, e nenhuma representação rítmica o alcança.

**2. Tercina existe?** Massa de onsets que fica mais perto da grade de tercina que da
de semicolcheia, contra um **controle interno**: semicolcheias sintéticas perfeitas
mais o jitter medido daquela mesma música. O controle mede quanto de "tercina" o
próprio jitter fabrica.

| música          | jitter  | medido | controle |
|-----------------|---------|--------|----------|
| yt_4dJz6U3_Xlk  | 12,6 ms |  4,7%  |   5,0%   |
| yt_4kd_eR4216g  | 10,4 ms | 10,8%  |   5,0%   |
| yt_5zqlgMh4aYs  | 30,8 ms | 14,2%  |  12,5%   |
| yt_8m6wrCCRvm8  | 20,0 ms |  9,3%  |   9,5%   |
| yt_QTOyeFQgZKk  | 13,5 ms |  1,6%  |   8,9%   |
| yt_U-SHfpm5Bxk  | 26,2 ms | 15,9%  |  13,2%   |
| yt_g81jzIwyDjg  | 16,9 ms | 10,1%  |  10,7%   |

Seis das sete ficam **em cima ou abaixo** do controle: o que parecia tercina é o
jitter. Só `yt_4kd_eR4216g` se destaca, com o dobro do controle (10,8% contra 5,0%).

**3. O andamento varia?** Melhor BPM por janela de 60 s, com o global como âncora,
nas sete. O espalhamento cru acusa duas músicas — mas espalhamento cru não distingue
andamento que muda de ajuste que balança, e a série inteira é que mostra qual é qual:

| música          | espalha | série por janela                        | correl | vizinhas | razão |
|-----------------|---------|-----------------------------------------|--------|----------|-------|
| yt_5zqlgMh4aYs  |  4,8%   | 87,1 87,1 87,4 87,1 89,1 88,1 88,7 84,9 | −0,07  | 0,56 BPM |   7,5 |
| yt_8m6wrCCRvm8  |  2,8%   | 103,0 ×5 → 105,8 105,4 104,6            | +0,75  | 0,05 BPM |  58   |
| yt_U-SHfpm5Bxk  |  1,1%   | 110,9..112,1 em oito janelas            | −0,21  | 0,20 BPM |   6,0 |
| yt_4dJz6U3_Xlk  |  0,4%   | 107,4..107,8 em doze janelas            | +0,16  | 0,06 BPM |   6,7 |
| yt_4kd_eR4216g  |  0,2%   | 128,0 ×5 → 128,2                        | +0,73  | 0,06 BPM |   3,3 |
| yt_QTOyeFQgZKk  |  0,1%   | 154,1..154,3 em cinco janelas           | +0,64  | 0,10 BPM |   2,0 |
| yt_g81jzIwyDjg  |  0,1%   | 119,1..119,2 em quatro janelas          | +0,27  | 0,09 BPM |   1,1 |

Nenhuma das duas medidas simples serve sozinha, e é isso que decide o item:

- **Espalhamento cru aponta a música errada primeiro.** `yt_5zqlgMh4aYs` espalha mais
  que todas (4,8%) e não tem andamento variável: série sem tendência, vizinhas a
  0,56 BPM uma da outra. É a música de pior jitter do acervo (30,8 ms) — ataque
  disperso faz o ajuste por janela balançar.
- **Correlação sozinha é pior ainda.** Ela vale +0,73 em `yt_4kd_eR4216g`, tão alta
  quanto no caso real, sobre uma série que vai de 128,0 a 128,2. Em série plana a
  correlação mede o arredondamento da busca, não a música: por ela, três das sete
  seriam acusadas.

O que separa é a **razão entre o espalhamento e o desvio entre vizinhas** — quanto o
andamento anda comparado a quanto ele treme. Aí `yt_8m6wrCCRvm8` fica em 58 e todas as
outras em 7,5 ou menos, uma ordem de grandeza de folga. É o caso genuíno: cinco
janelas em 103,0 e depois um platô em ~105, com vizinhas a 0,05 BPM. Um **degrau**,
não deriva contínua.

### Decisão

Nada muda. Semicolcheia reta e andamento constante continuam como estão.

- **Swing e tercina não existem neste acervo.** Não é que o ganho seja pequeno: as
  grades alternativas explicam os ataques *pior* que a atual, nas sete, e o controle
  interno absorve a massa de tercina em seis das sete. Implementar detecção aqui seria
  escrever um discriminador que dispara no ruído.
- **O teto é o jitter de ataque, não a grade.** A fusa custa resolução dobrada e
  devolve 0,1 a 2,9 ms em quatro músicas. Enquanto o ataque do transcritor tiver 10 a
  31 ms de dispersão, nenhuma grade mais fina melhora a leitura — o caminho para
  fidelidade rítmica passa por onset, não por representação. **Não reabrir B2 por
  acrescentar grades.**
- **O aviso de andamento variável não é implementável com uma medida barata.** As
  duas simples erram, e em direções diferentes: espalhamento cru acusa primeiro a
  música mais ruidosa, e correlação acusa três músicas planas. Sobra a razão entre as
  duas, que separa com folga de uma ordem de grandeza — mas sobre **um único exemplo
  positivo** em sete. Limiar tirado de n=1 é o mesmo piso que o ADR-033 reprovou:
  discriminador sem controle que o sustente.

### Consequência

- O acervo sai da pesquisa com dois fios soltos, registrados para não serem perdidos
  nem arredondados: `yt_4kd_eR4216g` com o dobro da tercina do seu controle, sem
  explicação; e o degrau de andamento de `yt_8m6wrCCRvm8`, real e único.
- **O que reabriria:** mais material com degrau de andamento (dois ou três casos já
  permitiriam calibrar contra o controle de ruído), ou queda no jitter de ataque —
  Camada 3 do ADR-007 — que é o que tornaria a grade fina e o swing mensuráveis.
- Quando reabrir, o conserto do degrau é **mapa de andamento com duas seções**, não
  rastreador de andamento contínuo: a série medida é um platô seguido de outro.
- Nenhum código mudou, então a verificação de entrega da tarefa anterior continua valendo.

---

## ADR-035 — a tablatura mora dentro do MusicXML, em duas pautas

**Data:** 2026-09-23
**Status:** aceito

### Contexto

O `.musicxml` saía como partitura, e só. Corda e traste viajavam nele desde sempre,
como `<technical><string>/<fret>` — informação certa, que nenhum leitor desenhava,
porque o arquivo declarava uma pauta de notação e mais nada. Quem abria via a partitura
e concluía, com razão, que a tablatura não estava lá.

O `.gp5` não resolve esse lado. Ele declara `TrackSettings.tablature=True`, e o
TuxGuitar e o Guitar Pro honram: abrem com a tablatura na tela. O MuseScore 4.7
**ignora** essa flag no importador de Guitar Pro e monta a pauta pelo template
`electric-bass` dele (`stdNormal`, clave de Fá 8vb). Medido, não suposto: o `.mscx`
resultante traz um `StaffType group="pitched"` e nenhum de tablatura. Não há nada a
corrigir no nosso GP5 — o buraco estava no MusicXML, que é o formato que o MuseScore
lê por inteiro.

Quatro sondagens antes de escrever código:

1. `<staff-details>` depois dos `<clef>`, dentro do mesmo `<attributes>`: aceito.
2. `<staff-tuning line="1">` é a linha de **baixo** da tablatura, logo a corda mais
   grave. Com a ordem do nosso `tuning` (grave → agudo), o MuseScore reconstrói
   `StringData` como `[28, 33, 38, 43]`. Invertida, o arquivo abre sem erro e mostra
   trastes errados.
3. O music21 10.5 lê o arquivo de volta como duas `PartStaff`: `parts[0]` notação,
   `parts[1]` tablatura.
4. O MuseScore **honra** o nosso `<technical>` — desde que corda e traste sejam
   compatíveis com a altura da nota. A primeira sondagem mandou digitação
   contraditória, o MuseScore descartou e recalculou, e isso se disfarçou de "o
   MuseScore recalcula sempre". Com digitação válida alternativa, ele preserva.

### Decisão

O `MusicXmlExporter` monta **duas `PartStaff` na mesma parte**, sob um `StaffGroup`
com colchete e barras ligadas: notação em cima, tablatura embaixo.

- **A altura é a mesma nas duas.** Pauta que discorda da outra é pior que pauta
  nenhuma; há teste afirmando a igualdade.
- **O nome da nota fica só na notação.** Na tablatura ele repetiria o traste que está
  ao lado.
- **Corda e traste ficam só na tablatura**, que é onde se leem.
- **Andamento e armadura entram pela pauta de notação.** O `<attributes>` é da parte
  inteira, então o arquivo grava uma armadura só — mas o music21 entrega uma cópia a
  cada pauta na leitura. Teste que percorre a partitura toda conta duas: ancorar em
  `parts[0]` não é detalhe de estilo, é o que mantém a asserção com significado.
- **`<staff-details>` é injetado no XML depois da escrita** (`_com_afinacao`). O
  music21 10.5 emite `<staves>`, `<staff>` por nota e a clave TAB, mas não emite
  `staff-lines` nem `staff-tuning` — e sem eles o leitor cai na afinação default. A
  injeção é costura de formato, então o teste afirma o **XML cru**: é ali que está o
  contrato com o leitor.

### Alternativa descartada

Promover o script que convertia `.gp5` em `.mscz` de duas pautas via CLI do MuseScore.
Funcionava, e foi o que entregou os sete arquivos desta sessão — mas resolve na saída
o que estava errado na origem, amarra o projeto a um binário do MuseScore instalado e
não beneficia nenhum outro leitor de MusicXML.

### Consequência

- Quem abrir o `.musicxml` — MuseScore, MusicXML de qualquer leitor — vê partitura e
  tablatura, com a digitação do Viterbi (ADR-032) preservada, não recalculada.
- Os sete artefatos em `out/` foram gerados antes desta mudança: ainda são de uma
  pauta. Reexportar é rodar o pipeline de novo.
- A cinco cordas entra inteira: o si grave é a corda que sumiria numa afinação escrita
  em tamanho fixo, e há teste com `TUNING_BASS_5` cobrindo isso.
- Um teste `slow` roda o `mscore` de verdade e afirma a digitação importada, não só a
  existência da pauta (Regra 3 — o round-trip pelo music21 não prova o leitor).

---

## ADR-036 — o áudio sai junto da partitura

**Data:** 2026-09-23
**Status:** aceito

### Contexto

`out/` saía com `.gp5` e `.musicxml` e mais nada que se pudesse ouvir. O mix e o
stem de baixo existiam — mas no `cache/`, em diretórios nomeados por hash da fonte
(`cache/yt_g81jzIwyDjg/mix.wav`, `cache/stems/<id>/htdemucs_ft/mix/bass.wav`).
Quem abrisse a pasta de saída para estudar tinha a partitura e precisava caçar a
música em outro lugar.

### Decisão

`transcrever` copia dois áudios para `out_dir`, nomeados pelo título como os
demais artefatos (ADR-017): `<título>.mix.wav` e `<título>.baixo.wav`. Os dois
entram no `Resultado.artefatos`, então a API os lista em `formatos` e os serve
pelo mesmo endpoint dos outros.

- **Cópia, não link simbólico.** A pasta de saída é o que se abre e se move; ela
  não pode depender de um diretório nomeado por hash continuar existindo. Há teste
  afirmando que não é symlink e que os bytes batem com a origem.
- **Mix e baixo, não os quatro stems.** O `no_bass.wav` existe e sairia de graça,
  mas não foi pedido; o `.aural.wav` continua sendo produzido só pelo comando
  `auralizar`, que é opt-in.
- **Cópia incondicional, sem guarda por tamanho.** Rodar de novo reescreve ~90 MB
  por música. São segundos contra os quinze minutos do pipeline: a guarda não se
  paga e abriria a chance de manter arquivo velho.

### Consequência

- `out/` cresce ~90 MB por música. Continua fora do git (ADR-005) — áudio nunca
  entra neste repositório, que é público.
- O teste `slow` do caminho completo ganhou a asserção que só ele pode fazer: com
  o Demucs real, mix e baixo são arquivos **diferentes**. No dublê da suíte rápida
  o separador devolve o próprio áudio como stem, então lá os dois são iguais por
  construção e a asserção não diria nada.
- Os `.mscz` que eu gerava à mão para ver as duas pautas no MuseScore não têm mais
  função desde o ADR-035, e os sete que estavam em `out/` foram apagados a pedido.

---

## ADR-037 — uma pasta por música, todo o áudio dentro, e o estágio na tela

**Data:** 2026-09-23
**Status:** aceito — supera o ADR-036 na parte de onde e quantos áudios saem

### Contexto

Pedido direto: "cli colorido que mostra todas as etapas do processo", "salve os
arquivos em pastas separadas com o nome da musica", "todos os wavs que você
produzir".

Dois problemas distintos, um de saída e um de tela.

Na saída: o ADR-036 pôs mix e baixo em `out/` plano, ao lado do `.gp5` e do
`.musicxml`. Com oito músicas isso é quarenta arquivos intercalados, e os de uma
mesma música só se agrupam porque o nome começa igual. Além disso, dois áudios que
o pipeline já produzia ficavam de fora: o `no_bass.wav`, que o Demucs devolve junto
com o baixo e ninguém usava, e a auralização, que só saía pelo comando `auralizar`
rodado à mão depois.

Na tela: o `transcribe` imprimia uma frase antes da chamada — "separando e
transcrevendo — ~2,5x a duração do áudio em CPU…" — e depois nada por minutos. Medido
nesta sessão numa música de 5'34": 2m36 só na transcrição. Uma frase solta não diz em
qual estágio se está, nem se algo travou.

### Decisão

**Uma pasta por música, e o nome repetido dentro dela.** `out/<título>/<título>.gp5`,
`.musicxml`, `.mix.wav`, `.baixo.wav`, `.sem-baixo.wav`, `.aural.wav`. Repetir o nome
é redundante dentro da pasta e é exatamente o ponto: o arquivo arrastado para fora
dela continua dizendo de que música é (a propriedade que o ADR-017 comprou).

**Os quatro áudios, e a auralização dentro do pipeline.** O `no_bass` era desperdício
puro — o Demucs já o escrevia no cache. A auralização deixa de ser opt-in e sai junto:
é o arquivo com que se confere se a transcrição descola do original, e quem acabou de
esperar quinze minutos não deveria precisar de um segundo comando para ouvir isso.

**Falha na auralização vira relato, não exceção.** Ela depende de `fluidsynth` e de
soundfont, e nenhum dos dois vale os minutos de CPU já gastos: volta em
`Resultado.falha_na_auralizacao` e a CLI avisa em amarelo, com a partitura entregue
(mesma forma do ADR-014). Há teste afirmando que o `.gp5` sobrevive à falha.

**`Progresso` como `Protocol` em `domain/ports.py`, com um método só.** O pipeline
anuncia `inicia(etapa, detalhe)` antes de cada estágio; quem desenha é a CLI, com
`rich`. Não há "terminou" porque o estágio seguinte fecha o anterior e o último fecha
quando `transcrever` devolve — quem desenha sabe disso, o pipeline não precisa saber.
É o que mantém terminal, cor e barra fora dos services. O default é um objeto nulo
(`_Silencio`), não dez `if progresso is not None`.

Detalhes de terminal que custaram medição: `markup=False` em tudo, porque título de
música tem `[` (`[Official Video]`) e como marcação engoliria o resto da linha;
`highlight=False` no `Console`, porque o rich colore número e pontuação no meio do
título; `soft_wrap=True`, porque caminho quebrado em duas linhas não se copia.
`processos.py::rodar` usa `capture_output=True`, então Demucs, MuScriptor e ffmpeg não
escrevem no terminal e não atropelam a região viva do `rich`.

### Alternativa descartada

Deixar a auralização opt-in e pôr uma flag `--sem-auralizacao` no `transcribe`. Flag
para desligar um estágio de seis segundos num pipeline de quinze minutos é
configuração que ninguém vai usar.

Reprocessar as oito músicas em vez de mover os arquivos. Custaria ~40 min de CPU para
produzir os mesmos bytes: o `.gp5` e o `.musicxml` já vinham do exportador de duas
pautas (ADR-035). Movidas, e o que faltava foi preenchido.

### Consequência

- `out/` passa a ~200 MB por música (quatro WAVs em vez de dois). Continua fora do
  git (ADR-005) — e agora inclusive a auralização, que carrega o mix original num
  dos canais.
- **Todo job da API paga a auralização.** `api/app.py:199` chama a mesma
  `pipeline.transcrever`, então cada job agora roda `fluidsynth` e `ffmpeg` sobre a
  faixa inteira. Foram 6s na música medida; não é gratuito, e se a API virar o
  caminho principal isso é o primeiro lugar a olhar.
- O comando `auralizar` grava na pasta da música, não em `out/` plano — fora disso
  ele produziria uma segunda cópia num segundo lugar.
- O dublê de separação da suíte rápida precisou produzir um `no_bass` **distinto**
  (silêncio, arquivo próprio): apontá-lo para a entrada faria mix, baixo e sem-baixo
  saírem com os mesmos bytes, e o teste de cópia não distinguiria fiação correta de
  laço gravando o mix três vezes. O teste `slow` afirma o que só ele pode: com o
  Demucs real os três são dois a dois diferentes.
- `no_bass` é opcional no contrato do `Separator` — quem dubla a separação não é
  obrigado a produzir playback para exercitar o resto. Há teste com um separador que
  devolve só `{"bass": …}`.
- Fora de terminal (log, CI, teste) o `rich` não anima: imprime cada estágio concluído
  como uma linha `✓ <estágio>  0:00:00`. É o que se quer num log, e é o que os testes
  da CLI afirmam.

### Emenda (2026-09-24) — o custo da auralização na API fica

A consequência acima deixou aberto se a API deveria pedir o pipeline sem auralização.
Fica como está: é a mesma conta da alternativa descartada — seis segundos num job de
quinze minutos não pagam uma flag nem um segundo caminho no pipeline. Reabre se a API
virar o caminho principal e o custo aparecer medido lá.

---

## ADR-038 — as pausas entram antes do `makeNotation`, e a gramática do beam é afirmada no XML cru

**Data:** 2026-09-23
**Status:** aceito na parte (A); a parte (B) fica aberta e documentada

### Contexto

O music21 cospe `beam: WARNING: Found a messed up beam pair` ao gravar o MusicXML.
Investigar o aviso mostrou que ele **subnotifica**: dispara de 0 a 6 vezes por música,
mas os arquivos entregues traziam **208** beams mal-formados — `end` ou `continue` num
nível sem `begin` aberto, o que o MusicXML não admite. O aviso só cobre o subcaso que
`mergeConnectingPartialBeams` examina; o resto sai calado.

São **dois defeitos, não um**:

- **(A), nossa.** `_pauta` fazia `parte.insert(offset, nota)` e nunca preenchia as
  pausas. O beam é calculado antes de elas existirem, e duas notas a meio compasso de
  distância se veem como vizinhas. Com pausas explícitas o music21 acerta:
  `ts.getBeams([Note, Rest, Note, Rest])` devolve `[None, None, None, None]`.
- **(B), do music21 10.5.** Ritmo contíguo, sem pausa nenhuma. Mínimo de quatro notas —
  `(2, 8, 3, 3)` semicolcheias sai `1/begin, 1/continue, 1/end, 1/end`, dois `end`.
  10.5.0 é a versão mais nova do PyPI: não há correção a montar.

### Decisão

1. **`parte.makeRests(fillGaps=True, inPlace=True)` no fim de `_pauta`**, antes que o
   `makeNotation` beameie. É uma linha, e vale mais que escrever beaming próprio.
2. **A gramática é afirmada sobre o XML cru**, por `(pauta, voz, nível)`, incluindo
   `begin` que fica aberto no fim do compasso. Por duas razões: o round-trip pelo
   music21 não vê nada disso (ele relê o que ele mesmo escreveu), e as duas pautas do
   ADR-035 convivem no mesmo `<measure>` — somar as duas acusa erro que não existe.
3. **(B) fica marcado `xfail(strict=True)`**, não silenciado. `strict` faz o teste ficar
   vermelho no dia em que a correção entrar: xfail que passa calado vira defeito
   esquecido.

### Medição

Experimento controlado — o **mesmo** conjunto de notas de sete músicas do cache
exportado com e sem a linha do `makeRests` (comparar com o arquivo entregue não isola
nada: sem o recuo de fase do pipeline o conjunto de notas muda, e as contagens sobre a
base entregue foram 208):

| base | mal-formados | (A) | (B) |
|------|--------------|-----|-----|
| sem a correção | 248 | 48 | 200 |
| com a correção | 200 | 0 | 200 |

A queda é monotônica em todas as sete músicas, nenhuma piora. Os 14 que uma primeira
conta ainda classificava como (A) são (B) disfarçados: `end@1` solto numa colcheia
pontuada, sem `begin` em lugar nenhum — a pausa estava por perto, não dentro do grupo.

### Alternativas descartadas

- **Não emitir beam nenhum.** O MuseScore 4.7.4 **não** beameia sozinho quando o arquivo
  não traz beam: cada semicolcheia sai com bandeirola solta.
- **Deixar o leitor consertar.** O MuseScore aceita o arquivo, mas o conserto é visível e
  errado: no caso mínimo de (A) ele tira a primeira nota do grupo e pendura o beam numa
  **pausa**.
- **Silenciar o aviso.** `UserSettings['warnings'] = 0` grava em `~/.music21rc` — config
  de estação, e o aviso é sinal verdadeiro.

### Consequência

- Restam **200** beams mal-formados de forma (B), em ritmo sincopado. O MuseScore abre e
  desenha; o defeito é o grupo desenhado errado, não arquivo recusado.
- Os oito arquivos já em `out/` seguem com a forma (A): só reexportar os corrige.
- A varredura de compassos 4/4 contíguos na grade de semicolcheia deu 0 mal-formados em
  13 sem nota cruzando a fronteira de semínima, contra 132 em 1535 com nota cruzando —
  compatível com "cruzar o tempo é condição necessária", mas a amostra negativa é
  pequena (13) e isso não é prova.

### Emenda (2026-09-24)

Os números da seção **Consequência** acima foram escritos antes da reexportação e
ficaram velhos: sobre as **nove** músicas reexportadas (não oito) sobraram **188**
mal-formados de forma (B), não 200 — `tasks/todo.md`, Fase 12. A forma (B) foi
corrigida no ADR-039, e o `xfail(strict=True)` saiu junto, como previsto.

---

## ADR-039 — o compasso de beam quebrado é refeito por tempo; os que saem certos ficam

**Data:** 2026-09-24
**Status:** aceito — fecha a forma (B) do ADR-038

### Contexto

A forma (B) do ADR-038: ritmo contíguo, com nota cruzando a fronteira de semínima, e o
music21 10.5 escreve `end` sem `begin`, calado. É a versão mais nova do PyPI; não há
correção a montar. O ADR-038 deixou duas saídas em aberto: quebrar o grupo na fronteira
de tempo, ou aceitar e documentar.

### Decisão

**`_consertar_beams`, depois do `makeNotation`, refaz só o compasso quebrado.**

1. `pauta.makeBeams(inPlace=True)` explícito. O exportador de MusicXML refaz os beams
   de toda pauta que não esteja marcada (`m21ToXml.py`, `streamStatus.beams`) — o
   conserto feito sobre o stream do `makeNotation` era apagado no `write`. Rodar aqui e
   marcar `pauta.streamStatus.beams = True` é o que faz o arquivo sair com o que foi
   examinado.
2. Cada compasso passa pelo mesmo autômato que os testes rodam sobre o XML cru
   (`_beams_quebrados`). Se está certo, fica.
3. Se está quebrado, é refeito **um tempo por vez** com o próprio
   `TimeSignature.getBeams` do music21: o trecho de cada tempo são os elementos que
   **começam** nele, e nenhum grupo atravessa a fronteira. A nota que cruza fica no
   tempo em que começa; sozinha nele, sai com bandeirola.
4. `measureStartOffset` é o offset da **primeira nota do trecho**, não o do tempo. O
   `getBeams` supõe que a lista começa ali; quando o tempo abre com a cauda de uma nota
   que veio cruzando, passar o início do tempo desalinha o nível 2. Foi o defeito que o
   Codex achou na revisão, com `(5, 1, 1, 1, 2, 3, 3)` semicolcheias.

### Medição

Varredura de **todos** os compassos 4/4 contíguos na grade de semicolcheia — as
2¹⁵ − 1 = 32767 composições de 16 semicolcheias em 2 ou mais notas, exportadas pelo
`MusicXmlExporter` de verdade e validadas no XML cru:

| versão | mal-formados |
|--------|--------------|
| music21 10.5 sozinho (`16a2553`) | 2496 |
| primeira versão do conserto (`measureStartOffset` = início do tempo) | 80 |
| esta | **0** |

Os 80 intermediários são todos o caso do item 4, e passaram por uma varredura que ia só
até 5 notas (1940 ritmos, 151 quebrados sem correção, 0 com ela): o menor tem 7. Daí a
varredura do teste (`slow`, ~2 min em paralelo) não ter corte. Ela põe 512 compassos por
arquivo — um por arquivo custaria ~16 min — e o lote não esconde nada: sem a correção, o
subconjunto de 2 a 5 notas dá os mesmos 151 nas duas montagens.

A conta de 1548 ritmos da Fase 12 veio de um script não versionado que não se
reproduz; não é usada como base (`tasks/lessons/workflow.md`).

Nas nove músicas, reexportadas pelo `thoth transcribe` de verdade (2026-09-24, todas
com saída 0): **188 → 0** mal-formados. Nas oito comparáveis, **nenhum** dos 2998 pares
(compasso, pauta) que o music21 já escrevia válidos mudou de beam, e as notas batem
exatamente com as de antes; foram refeitos só os 94 compassos quebrados, nas duas
pautas. A nona, *Equus*, não é
comparável: a exportação de 2026-09-23 saiu com 4 cordas em vez das 5 de
`tasks/corpus.md` — 2807 elementos de nota contra 3251 agora, e a diferença (444) é o
que cai abaixo do E1 (445 elementos na nova), descartado pelo ADR-014 sem ninguém notar.
Refeita com `--afinacao 5`: 0 mal-formados.

### Alternativas descartadas

- **Refazer todo compasso por tempo.** Zera os mal-formados, mas altera **1468 de 3670**
  compassos que o music21 já escrevia válidos — entre eles colcheia + colcheia pontuada
  que atravessa o tempo no mesmo grupo (Dance of Death, c. 14), notação comum e
  legítima. O conserto é do defeito, não troca de estilo; há teste afirmando que esse
  grupo continua como o music21 o escreve.
- **Sanear só os tokens** (trocar o `end` órfão por `begin`, ou apagá-lo). Fecha a
  gramática, mas o grupo resultante é arbitrário: o conserto passa a depender de onde o
  music21 errou, não do ritmo.
- **Aceitar e documentar.** O MuseScore abre o arquivo, mas desenha o grupo errado, e
  2496 em 32767 compassos contíguos não é caso raro.

### Consequência

- Fora do contrato de hoje, e não coberto: fórmula com duração não inteira em semínimas
  (7/16 — o `range` ignora o resto) e compasso com `paddingLeft` (anacruse). O
  exportador fixa 4/4 e `_pauta` preenche o início com pausas, então nenhum dos dois
  acontece; se a fórmula deixar de ser fixa, este é o primeiro lugar a olhar. Achados
  da mesma revisão do Codex.

### Emenda — o Demucs pregado (mesma data)

`DemucsSeparator` chama `uvx --with 'numpy<2' demucs@4.1.0`. Sem versão, o `uvx`
resolveria o release mais novo a cada cache frio, e os stems — e as medições do ADR-010
feitas sobre eles — mudariam sem aviso. 4.1.0 é a única versão no cache do `uv` desta
estação. **O cache de stems continua identificado só pelo modelo** (`htdemucs_ft`), não
pela versão: um stem produzido por outra versão seria reutilizado sem rodar o 4.1.0. Hoje
todos vieram do 4.1.0; mudar a versão pregada exige limpar `cache/stems/`.

### Emenda (2026-09-24, depois)

O cache de stems passou a levar a versão na chave — `<out>/<modelo>/<versão>/` (emenda do
ADR-026). Mudar o pin já não exige limpar `cache/stems/`.

---

## ADR-040 — contêiner só CPU, sem os pesos na imagem

**Data:** 2026-09-24 · **Status:** aceito

### Contexto

A Fase 6 previa `Containerfile` + compose para CPU. O Thoth chama seis programas de fora
(`ffmpeg`, `ffprobe`, `fluidsynth`, `yt-dlp` e, por `uvx`, o demucs e o MuScriptor), mais
o alphaTab vendorizado por `npm pack`. Na máquina isso é uma lista de requisitos no README;
no contêiner, vem pronto.

### Decisão

- **Os pesos do MuScriptor não entram na imagem.** São CC BY-NC 4.0 e o ADR-005 já os
  deixa fora do repositório pelo mesmo motivo. O cache do HuggingFace da máquina é montado
  (`${HF_HOME:-~/.cache/huggingface}`); `hf auth login` e o aceite da licença continuam
  fora do contêiner.
- **O torch também não.** O demucs e o MuScriptor continuam por `uvx`, com as mesmas versões
  pregadas, e baixam no primeiro job para o volume `uv-cache` (pesos do demucs em
  `torch-cache`). Pré-aquecer na imagem somaria gigabytes de CUDA que a máquina não usa.
- **Dois estágios:** o `npm pack` do alphaTab roda num estágio descartável; a imagem final
  não carrega Node.
- **O soundfont vai por link simbólico.** O Debian instala em `/usr/share/sounds/sf2/`, e
  a auralização procura em `/usr/share/soundfonts/` (caminho do Arch, exceção já conhecida
  no AGENTS.md). Um `ln -s` na imagem, em vez de tornar o caminho configurável sem outro
  motivo.
- **Usuário `thoth` (uid 1000)**, para que `out/` e `cache/` montados fiquem com o dono do
  repositório. As duas pastas precisam existir antes do `up` — se o Docker as criar, nascem
  de root e o primeiro job não grava (o README manda o `mkdir -p`). Máquina cujo usuário
  não é o 1000 precisa de `user:` no compose. Os diretórios dos volumes nomeados são criados na imagem com esse dono: o
  volume herda o dono do ponto de montagem, e sem isso nasce de root — medido, o primeiro
  job falhou com `Permission denied` no cache do `uv`.
- `serve --host 0.0.0.0` dentro do contêiner; quem restringe ao localhost é o `ports:
  127.0.0.1:8000:8000` do compose.

### Verificação (2026-09-24)

`docker compose up --build`, depois `GET /` → 200, `GET /vendor/alphatab/alphaTab.min.mjs`
→ 200 e um `POST /jobs` real com a fixture `misto` (baixo + piano, `bpm=90`): status
`pronto`, 15 notas `electric_bass`, 0 descartadas, os seis formatos (`gp5`, `musicxml`,
`mix`, `baixo`, `sem-baixo`, `aural`) servidos com 200, e os arquivos em `out/` com o dono
do repositório. O stem saiu em `htdemucs_ft/4.1.0/`. Imagem: 3,09 GB (o `chown -R` do
primeiro rascunho recopiava o venv numa camada e custava 800 MB a mais).

### Não coberto

- O `yt-dlp` vai pelo `uv tool install`, sem versão pregada, como o da máquina. Se o
  YouTube passar a exigir um runtime de JavaScript, a imagem não o tem; o canário
  (`-m network`) roda na máquina, não no contêiner.
- Só `amd64` e só CPU, como o resto do projeto.

---

## ADR-041 — tab humana contra transcrição: alinhamento cego à oitava, veredito só de oitava, piso de acaso ao lado

**Data:** 2026-09-24 · **Status:** aceito

### Contexto

A Camada 3 pede referência externa. O usuário baixou à mão três `.gp5` da comunidade do
Ultimate Guitar (ADR-007, emenda) para `samples/`, ignorada pelo git: *Fear Is the Key*,
*Dance of Death*, *And Plague Flowers*. O `thoth comparar <tab.gp5> <fonte>` lê a tab
(`services/tab_referencia.py`) e a compara às notas em cache (`notas.jsonl`) da mesma
música (`services/comparacao.py`).

A tab está em tempo de partitura e a gravação em tempo de execução: antes de comparar, é
preciso alinhar. O plano aprovado alinhava **só pelo ataque**, para a altura da
transcrição nunca entrar na própria medida.

### O que a medição derrubou

Só o ataque não alinha uma linha de baixo. Com quatro, cinco notas por segundo e ±0,1 s
de tolerância, a tab deslocada de propósito casava quase o mesmo número de ataques que a
alinhada, e o acerto de altura não separava os dois:

| Música | casados, alinhada | casados, deslocada | mesma altura, alinhada | mesma altura, deslocada |
|---|---|---|---|---|
| *Fear Is the Key* | 944 | 785–892 | 61,9% | 35,8–56,5% |
| *Dance of Death* | 1474 | 1401–1431 | 27,0% | 22,5–**40,7%** |

Em *Dance of Death* deslocar a tab **melhorava** o acerto: o alinhamento estava errado.
Em *And Plague Flowers* a escala parou em 0,900, a borda da grade. Com 0,05 s de
tolerância *Dance* seguiu igual; *Fear* separou melhor (65,3% contra 36,8–52,7%), mas
ainda com a tab uma nota ao lado perto do alinhado.

### Decisão

- **O alinhamento usa o nome da nota** (a classe de altura, sem a oitava): um ataque da
  tab só conta se houver, a ±0,1 s, um ataque da transcrição com o mesmo nome. Estrutura
  igual à do plano: escala e deslocamento globais em grade, refinados por mínimos
  quadrados, e correção por trecho de 10 s limitada a ±80 ms.
- **O veredito é só de oitava**: entre os pares de mesmo nome, mesma oitava, acima ou
  abaixo. "Nota errada" deixa de ser medida — o encaixe foi escolhido para os nomes
  coincidirem. A oitava ficou de fora do alinhamento, então o veredito dela não se prova
  sozinho (teste: uma transcrição toda uma oitava acima casa inteira, e 100% acima).
- **Piso de acaso sempre ao lado.** O mesmo veredito com a tab deslocada ±0,25 e ±0,5 s,
  a uma e duas notas de distância — o erro em que o alinhamento cairia. A CLI imprime o
  deslocamento que mais casou.
- **Escala na borda da grade é recusada** com recado, não percentual. A guarda é
  necessária, não suficiente: em teste sintético com a escala verdadeira fora da grade, o
  acaso às vezes faz um pico no interior. Contra isso, a defesa é o piso.
- A tolerância de 0,1 s (e não os 50 ms do ADR-006) fica: a tab é grade, não execução.

### Resultado (2026-09-24)

| Música | pares | piso | mesma oitava | piso | acima | abaixo |
|---|---|---|---|---|---|---|
| *Fear Is the Key* | 704 (49% da tab) | 582 | 88,2% | 85,2% | 6,1% | 5,7% |
| *Dance of Death* | 861 (36%) | 803 | 84,8% | 84,3% | 0,3% | 14,9% |
| *And Plague Flowers* | 1266 (35%) | 876 | 89,6% | 74,9% | 5,0% | 5,5% |

- **Duas oitavas é raro**: nenhum par em *Fear* e *Dance*, 6 de 1266 em *And Plague
  Flowers* (contados em "acima"/"abaixo"). O erro de uma oitava fica entre 5% e 15%.
- ***Dance of Death* está no piso**: o alinhamento não se confirma, e 84,8% é o que sai
  de qualquer encaixe. O desvio para baixo (14,9% contra 0,3% acima) aparece também com a
  tab deslocada (107 a 123 abaixo contra 1 a 4 acima), então é do **registro** — trechos em que a tab e o Thoth leem a linha em
  oitavas diferentes —, não de um par a par. Se o erro é do Thoth ou da tab, esta medida
  não diz.
- *Fear Is the Key* fica 3 pontos acima do piso: sinal fraco. A tab mapeada cai em
  3,6–322,5 s, dentro da transcrição (0,5–319,3 s).
- ***And Plague Flowers* não alinhou a música inteira.** A tab mapeada vai de −5,2 s a
  663,4 s — começa antes do áudio. Por janela de 60 s, só 60–300 s alinha: 91% a 100%
  na mesma oitava contra um piso de 61% a 83%. Fora disso fica no piso ou sem par. A
  margem da linha da tabela vem desse trecho, não da música. Duas ressalvas somam-se: a
  transcrição foi feita com a afinação de 4 cordas (a tab é de 5, com B0) e para em
  511 s de 653 s de áudio.
- **A coluna de pares não se compara com o piso de forma justa.** O número alinhado é o
  máximo de uma busca em grade; cada deslocamento do piso é um sorteio sem otimização.
  No teste sintético com a escala fora da grade, o alinhamento falho deu 20 pares
  contra um piso de 10. Só a fração na mesma oitava é comparável, porque a oitava não
  entra na busca.

### Limites

- D.S./coda não são seguidos; final alternativo ocupa um compasso. Nenhuma das três usa
  D.S.; *And Plague Flowers* tem uma repetição aberta sem fecho no compasso 344.
- Tab de comunidade tem erro próprio e pode ser de outra versão da música.
- A extensão mapeada da tab não é conferida contra a do áudio: em *And Plague Flowers*
  isso teria recusado o encaixe global. Guarda possível, do mesmo tipo da borda.
- 36% a 49% da tab entra em par: o veredito vale para as notas em que tab e transcrição
  concordam no nome, que não são uma amostra neutra.

### Consequência

A pergunta "o Thoth erra a oitava?" tem resposta parcial: quase nunca por duas, de 5% a 15%
por uma, e a medida só se sustenta onde a fração na mesma oitava fica acima do piso —
em *Fear*, por pouco, e no trecho de 60–300 s de *And Plague Flowers*. Para "a nota está certa?" a
tab de comunidade, alinhada automaticamente, não serve. O próximo passo, se houver, é
alinhar a tab ao stem do baixo e não à transcrição (DTW sobre o envelope de ataques), o
que devolveria "nota errada" à medida.


### Emenda (2026-09-24) — *And Plague Flowers* refeita com `--afinacao 5`

A transcrição foi refeita com a afinação de 5 cordas, a mesma da tab (B0). Agora há
notas abaixo de E1 (122, a mais grave B0 = 23), e 2402 notas contra 2280.

| | pares | mesma oitava | piso | acima | abaixo |
|---|---|---|---|---|---|
| 4 cordas | 1266 | 89,6% | 74,9% | 5,0% | 5,5% |
| 5 cordas | 1294 | 89,3% | 71,9% | 4,9% | 5,8% |

O alinhamento não mudou (escala 1,0482, deslocamento −31,836 s, tab mapeada de −5,2 s a
663,4 s), e continua valendo só o trecho de 60–300 s, com 90% a 100% na mesma oitava
contra um piso de 61% a 83%. A afinação não era o que segurava o resultado.

Dois achados que a primeira rodada não registrou:

- **O vídeo é um cover de baixo** (Martino Garattoni), não a gravação da banda. A tab é da
  faixa do baixista do disco. Onde os dois tocam a mesma linha a comparação vale; onde o
  cover difere, o desencontro não é erro de ninguém.
- **A transcrição para em 511 s, e o baixo não.** O stem separado segue a −24 dB até
  cerca de 600 s e só cai perto de 640 s, mas nenhuma nota passa de 511,4 s — com 4
  cordas ou com 5. O cache guarda só as notas finais, então esta rodada não diz se é o
  MuScriptor que para ou um filtro do pipeline que descarta. Fica aberto no todo.
