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
