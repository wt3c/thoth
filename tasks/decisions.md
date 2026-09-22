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
**Condiciona a Fase 1:** o portão de regressão precisa de uma verificação de
oitava contra o espectro da mix original, não só de métricas contra o stem.

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
