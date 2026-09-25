# Thoth — plano de execução

> Áudio → partitura e tablatura, foco em contrabaixo. Uso pessoal. CPU-only.
> Decisões em `tasks/decisions.md`.

## Próxima sessão — o que está aberto (fechado em 2026-09-24)

Estado: verificação de entrega verde (343 passed na suíte padrão, ruff e mypy limpos; varredura `slow`
de beams 32767/0). As nove músicas reexportadas em `out/` em 2026-09-24 com o conserto
de beams: **0 mal-formados**. Conferir `git status -sb` — o push fica a pedido.

Em 2026-09-24 fecharam: a forma (B) dos beams (ADR-039 — 2496 → 0 na varredura de todos
os 32767 compassos contíguos), README alinhado à CLI e licença MIT, `demucs@4.1.0`
pregado, e o custo da auralização na API aceito (emenda do ADR-037). O MuseScore 4.7.4
já está instalado (`/usr/bin/mscore`).

Nada do que resta é barato: tudo depende de material externo ou de sessão manual.

### 1. Bloqueados em material externo

- ~~Validar o limiar de oitava fora do Equus~~ — feito em 2026-09-25 com as três tabs
  alinhadas ao stem. A primeira medição pegou o módulo quebrado; remedido (segunda
  emenda do ADR-030): separa fraco (AUC 0,75), alarma de 8 a 27%. Diagnóstico, não triagem.
- Tab clássica **humana** para conferir oitava e notas — só por download seu (`.gp5` do
  UG Pro ou Songsterr Plus). Automatizar o Songsterr está fora (emenda do ADR-007:
  `robots.txt` e `ai.txt` deles). A da SOJA é `aiGenerated: true` e não serve.

### 2. Verificação manual — navegador; nada que exija ouvido treinado

> O usuário não julga acerto musical (lição em `tasks/lessons/workflow.md`): o que
> exige ouvido treinado precisa virar medição ou fica declarado como não verificado.

- ~~Tocar e cursor~~ — virou teste `navegador` em 2026-09-25 (ver Fase 5).
- Passada perceptual (auralização) sobre o corpus de `tasks/corpus.md`, F1 por grupo.
  **Sem caminho hoje:** exige ouvido treinado, que o usuário não tem. Só sai do lugar
  se virar medição (ex.: tab humana de cada música do corpus, como no ADR-042).

### 3. Aberto sem urgência

- Fase 6: sync de cursor via Spotify (precisa de app e OAuth seus) e multi-instrumento
  (escopo grande, validação por ouvido). O contêiner fechou (ADR-040).
- Fora do contrato do ADR-039: fórmula não inteira (7/16) e anacruse no conserto de beams
  — só importa se a fórmula deixar de ser 4/4 fixo.

## Fase 0 — Spike de viabilidade ✅ **CONCLUÍDA (2026-09-22) — veredito: SEGUIR**

Sem escrever código do pipeline. Medir se a qualidade justifica o projeto.
A avaliação **não depende de saber tocar** (ADR-006).

### Preparo
- [x] `uvx muscriptor transcribe --help` → flags verificadas na v0.3.0 (2026-09-21):
      `-f midi|json|jsonl` · `-m small|medium|large` · `-d auto|cpu|cuda|mps` ·
      `--instruments` · `--auralize` + `--soundfont` · `--detect-tempo
      true|false|best-effort` · `--sampling/-t` · `--cfg-coef` · `--notes` · `-o -`
      Nomes de instrumento (`list-instruments`): `electric_bass`, `acoustic_bass`,
      `contrabass`, `clean_electric_guitar`, `distorted_electric_guitar`, `drums`…
      **Sem MusicXML/PDF/tab** — ver correção no ADR-003.
- [x] Aceitar a licença CC BY-NC 4.0 no HuggingFace + `hf auth login` na estação

### Camada 1 — objetiva (critério principal)
- [x] Fixtures: 6 linhas de baixo em MIDI (`tests/sintetico.py`) → fluidsynth +
      soundfont → WAV normalizado a −1 dBFS
- [x] **Onset F1** com `mir_eval` (`services/evaluation.py`), travado por fixture
      como teste de regressão em `tests/integration/test_regressao_fase0.py`
- [x] Medir o **pipeline completo** (com separação) contra ground truth: no
      `misto`, nota F1 0,682 → **0,968** com separação, onset inalterado em 0,938
      (ADR-010, emenda de 2026-09-22). Separar recupera altura, não tempo
- [x] Repetir com `small` vs `medium`, cronometrando em CPU — feito em 2026-09-24,
      emenda do ADR-009: com separação o `medium` não degenera, mas não ganha em
      nenhuma fixture, custa ~2× e em `escala` rotula o baixo como `acoustic_guitar`.
      A comparação em áudio real fica com a Camada 3 (precisa de tab humana)

### Camada 2 — perceptual assistida (dispensa treino)
- [x] Auralização: original em um canal, MIDI no outro (`thoth auralizar`,
      ADR-020). Se descolar, qualquer ouvido percebe
- [ ] Rodar a auralização sobre o corpus de `tasks/corpus.md` — **reportar F1
      por grupo**, nunca um número agregado (Grupo A é otimista por construção)

### Camada 3 — referência externa (ADR-007)
- [x] Tabs humanas escolhidas: três `.gp5` da comunidade do UG, baixados à mão
      pelo usuário para `samples/` (ignorada pelo git): *Fear Is the Key*, *Dance
      of Death*, *And Plague Flowers*. O Songsterr ficou fora (emenda do ADR-007)
- [x] `thoth comparar <tab.gp5> <fonte>` (ADR-041):
  - [x] leitor da tab → `NoteEvent` em segundos: faixa de baixo, andamento de
        **todas** as faixas na posição exata, repetições com finais alternativos,
        ligaduras, compasso que não é 4/4. D.S./coda fora, declarado
  - [x] ~~alinhamento só por ataque~~ — medido e derrubado: a tab deslocada casava
        quase tanto quanto a alinhada. Alinhamento pelo nome da nota (sem oitava),
        escala + deslocamento globais, correção por trecho de ±80 ms
  - [x] relatório: mesma oitava / acima / abaixo nos pares de mesmo nome, com o piso
        de acaso (tab deslocada) ao lado; escala na borda da grade é recusada
  - [x] subcomando na CLI, lendo `notas.jsonl` do cache como o `auralizar`
  - [x] rodar nas três músicas → ADR-041
- [x] Conferir oitava contra essa tab: duas oitavas quase nunca (6 de 1266 pares, só
      em *And Plague Flowers*); 5–15% a uma.
      *Dance of Death* ficou no piso de acaso — não confirma nada; *And Plague
      Flowers* só alinhou em 60–300 s
- [x] "Nota errada" contra tab: exige alinhar a tab ao stem do baixo (DTW), não à
      transcrição (ADR-041, consequência) → ADR-042
  - [x] medir: DTW sobre croma do stem nas três tabs (78/≤64, 79/≤45, 60/≤55); porta só
        de áudio não separa da música errada — descartada
  - [x] `services/alinhamento_audio.py`: tab → tempo do stem por DTW (porte literal do
        script de medição), teste com áudio sintético
  - [x] `comparacao.veredito_de_nota`: certa/oitava/errada por janela de 60 s, piso ao
        lado, janela conclusiva só com certa ≥ piso + 10 pontos; o resto "inconclusivo"
  - [x] CLI `comparar`: tabela por janela quando há stem em cache; sem stem, recado
  - [x] rodar nas três músicas, conferir contra a medição → ADR-042: errada 14,1% /
        15,4% nas janelas conclusivas de *Fear* e *And Plague Flowers*; *Dance* 1 de 9
- [x] Refazer *And Plague Flowers* com `--afinacao 5` (emenda do ADR-041): 89,3%
      contra piso de 71,9%, alinhamento igual — a afinação não mudava o quadro
- [x] **Transcrição some depois de 511 s** em *And Plague Flowers* (`yt_ArBcOGvMvGU`):
      era o filtro de rótulo — o baixo vira `clean_electric_guitar`. Trechos sem baixo
      agora são relatados e readmitidos (emenda do ADR-008); vai até 654,9 s, 1558 pares,
      89,5% na mesma oitava contra piso de 75,2%

### Comparações a fazer
- [x] **mix direto** vs **stem do Demucs** → decidido no ADR-010 (separar sempre)
- [x] **com** vs **sem** `--instruments` → decidido no ADR-008 (sem; filtrar por
      conjunto de rótulos)

**Pronto quando:** planilha com F1 por condição + tempo em CPU + decisão
**seguir / ajustar / abortar**.
**Cuidado:** F1 sintético é métrica de regressão, não de qualidade real.

## Fase 1 — Esqueleto e domínio ✅ **CONCLUÍDA (2026-09-21)**

- [x] `uv init` com Python 3.12 fixo (ADR-004)
- [x] `domain/models.py` — `AudioAsset`, `NoteEvent`, `TabNote`, afinações
- [x] `domain/ports.py` — `AudioSource`, `Transcriber`, `Separator`, `FretAssigner`, `Exporter`
- [x] `LocalFileSource` — ffmpeg → WAV 44.1 kHz estéreo, `source_id` = SHA-256 do conteúdo
- [x] Cache por `source_id`: cache hit não reconverte
- [x] `YtDlpSource` + `resolver_fonte()` — URL do YouTube ou caminho local (ADR-005)
- [x] `cli.py` (Typer): `thoth fetch <arquivo|URL>`
- [x] 6 testes contra **ffmpeg real** (sem mock — Regra 3); ruff + mypy strict limpos

## Fase 2 — MuScriptor + ground truth

- [x] **Verificador de oitava** (`services/octave_check.py`) — razão `f0 / 2·f0`
      por nota, limiar 0,40, 7 testes contra WAV real gerado pelo ffmpeg.
      Roda sobre o **stem**, não sobre a mix: validado nos dois, pega 12/12 no
      stem e só 6/12 na mix (bumbo e guitarra enchem a banda de 30,9 Hz).
- Mais um dado para essa validação (2026-09-22, primeira execução da CLI
      ponta a ponta): no stem do Demucs da fixture `walking` o limiar sinaliza
      **4 de 15 notas** (27%), todas G2/A2 — bem acima dos 8,7% medidos em
      material real. Fixture sintética passada pelo Demucs não é material real,
      então isto não condena o limiar; é mais uma amostra de que a taxa de
      alarme depende forte do material
- [x] Validar o limiar **fora do Equus** — ele foi calibrado nas mesmas 12 notas
      em que foi medido. Feito com as três tabs alinhadas ao stem (emenda do
      ADR-030): **não se sustenta** — alarma 31–39% das notas que a tab confirma
      (8,7% no Equus), 4–5% dos avisos são erro real, e nenhum limiar de 0,2 a 1,0
      separa. O limiar fica; o aviso deixa de valer como lista curta
- [x] **A janela do ADR-029 tinha quebrado a detecção** (emenda do ADR-029): no Equus
      caiu de 12 para 2 das 12, e o pico zero (faixa de 41 Hz entre dois pontos da FFT)
      virava nota certa em suspeita. FFT completada com zeros + janela com piso de 0,3 s:
      8 de 12, 4 de 127 alarmes. Calibração travada em `tests/integration/test_oitava_equus.py`
      (`slow`, pula sem `~/thoth-fase0`). Remedido nas tabs: segunda emenda do ADR-030
- [x] Erro de oitava **para cima** — não é do Thoth: em 91 dos 95 casos medidos o áudio desmente a
      tab (terceira emenda do ADR-030). Nada a detectar
- [ ] Discriminador do erro **para baixo** que separe melhor que o `f0 / 2·f0` (AUC 0,75,
      segunda emenda do ADR-030). Candidatos já medidos e descartados: ímpares/pares,
      `3f0/(2f0+4f0)`, meios-harmônicos. Com 84 casos em duas músicas, diferença pequena
      entre candidatos não se distingue de acaso: esperar mais tabs. *Eyrie* acrescentou só 2
      (quarta emenda do ADR-030): linha repetitiva demais para as janelas serem conclusivas
- [x] MuScriptor silencioso no fim de *Eyrie* (`_RMax1LS3pM`): o *prelude forcing* trava o
      modelo em vazio de 557 a 671 s. Segunda passada sem ele, só quando há buraco, só dentro
      do buraco (emenda do ADR-008). 0 → 382 notas no trecho, travado em
      `tests/integration/test_prelude_eyrie.py`
- [x] *Eyrie* de novo com a segunda passada: 1507 → 1809 notas, a última em 659 s (antes 555 s);
      136 e 192 notas nas janelas de 540 e 600 s, antes 25 e 0. **Qualidade não medida:** contra
      a tab, as duas janelas saem inconclusivas (600 s: certa 20% contra piso 25%), como as do
      meio da música. A tab de *Eyrie* não serve para julgar o trecho. Casos de oitava para
      baixo continuam 2
- [x] `MuscriptorTranscriber` atrás do `Protocol Transcriber` — subprocesso via
      `uvx` (torch fora do projeto), `small` + livre + `--detect-tempo false`.
      7 testes: 6 de parsing puro + 1 contra o modelo real (`slow`).
- [x] **Não fatiar áudio antes de transcrever** — o rótulo do instrumento depende
      de contexto (emenda do ADR-008): 2,9 s viram `acoustic_piano`, 8 s viram
      `electric_bass`. Vale como restrição ao montar o serviço de pipeline.
- [x] `models.lock.toml` com SHA-256 dos pesos — `small` e `medium`, com revisão
      do HF e licença. Conferido contra o cache real da estação por teste `slow`
      (1,6 GB em ~5 s). Pesos seguem fora do versionamento (ADR-005); o lock
      guarda só a identidade deles.
- [x] Promover as fixtures da Fase 0 a **gate de regressão** — `tests/sintetico.py`
      (regera as seis fixtures; áudio nunca versionado, ADR-005) +
      `tests/integration/test_regressao_fase0.py`. Válido só para o `small`
      (ADR-009) sobre o checkpoint de `models.lock.toml`, conferido por hash
      antes de medir. Sem folga: renderização byte-idêntica e
      `muscriptor@0.3.0` pregado. Cobre também o avaliador, agora em
      `thoth.services.evaluation` com 8 testes contra o mir_eval real.
- [x] ~~Travar o gate no CI~~ — **descartado** (2026-09-22, decisão do Welington):
      projeto pessoal, sem necessidade de CI. O teste de regressão roda localmente sob
      demanda: `uv run pytest -m slow`. Consequência aceita: ele só protege
      quando alguém o roda — não há nada impedindo um commit de regredir.
- [x] `@pytest.mark.slow` para o que carrega modelo

**Pronto quando:** o F1 estiver documentado e travado.
**Cuidado:** F1 sintético é métrica de regressão, não de qualidade real.

## Fase 3 — Motor de tablatura (Viterbi/DP)

- [x] Estados (corda, traste) válidos por afinação — qualquer tupla de afinação;
      EADG, BEADG e Drop D já em `thoth.domain.models`
- [x] Custo: traste alto, corda solta, deslocamento, troca de corda e janela da
      mão (ADR-012). A janela é **absoluta** (trastes 0–5), não móvel — ver ADR-012
- [x] **Modo iniciante** (ADR-006) — preset `INICIANTE`. Nasceu idêntico ao
      `PADRAO`: custo linear por traste não separa os modos. Quem separa é a
      penalidade fora da primeira posição (ADR-012)
- [x] Hypothesis: pitch(corda,traste) == pitch original; nenhum traste > `max_fret`
- [x] **Acordes / notas simultâneas** — resolvido na borda do pipeline, não no
      motor: `monofonizar` reduz o grupo à nota mais grave e relata o descarte
      (ADR-014). `assign` continua monofônico de propósito

**Medido:** as seis fixtures caem em primeira posição sob os **dois** presets — o
corpus sintético vive no grave, onde tocável e ótimo coincidem, e portanto **não**
valida o modo iniciante. A distinção se apoia no teste de contraste e na varredura
de 400 linhas aleatórias (170 divergem).

**Pronto quando:** as tabs das fixtures couberem na primeira posição quando a
linha permitir, verificado por propriedade — não por execução no instrumento.

## Fase 4 — Exportadores

- [x] GP5 via PyGuitarPro (afinação, corda/traste, tempo) — `Gp5Exporter`
- [x] MusicXML via music21 (clave de Fá 8vb, compasso, corda/traste como
      indicações) — `MusicXmlExporter`
- [x] Round-trip: grava → relê → mesmas cordas e trastes. 16 testes contra as
      bibliotecas reais (Regra 3), nenhum mock
- [x] **Abrir no TuxGuitar** — verificado pelo Welington em 2026-09-22: os quatro
      GP5 e os quatro MusicXML (incluindo `graves`, de 5 cordas) abriram
      corretamente. É o único leitor independente disponível — o round-trip
      sozinho prova consistência com quem escreveu, não validade do formato
- [x] Ligaduras no GP5 — feito pelo ADR-022 (`NoteType.tie`, fatiado nas barras); o item
      ficou aberto por engano até 2026-09-24

**Pronto quando:** abrir sem erro no TuxGuitar.

## Condicionais — só com evidência da Fase 0

- [x] **C1** `DemucsSeparator` (`htdemucs_ft`) — **aprovada** e promovida a etapa
      fixa do pipeline (ADR-010). Custo conhecido: erra a oitava em 7% das notas
      no material grave e denso — mitigação na Fase 2, não motivo para reverter.
- [x] **C2** quantizador próprio — o Beat This! é dependência dura do MuScriptor
      (ADR-003 corrigido), não condicional. Resolvido pelo segundo caminho: o
      transcritor roda sempre com `--detect-tempo false` e a quantização é nossa
      (`services/rhythm.py`).

## Fase 4.5 — Pipeline ponta a ponta ✅ **CONCLUÍDA (2026-09-22)**

Pré-requisito invisível até agora: a Fase 5 só existe se houver o que o
`POST /jobs` chame. Hoje os estágios existem isolados e nada os liga.

- [x] `DemucsSeparator` atrás do `Separator` (ADR-010) — `htdemucs_ft`,
      `--two-stems=bass`, `uvx --with "numpy<2"` (o demucs declara mal suas
      dependências). Stem descoberto por glob, não por caminho reconstruído
- [x] `services/pipeline.py` — `ref → artefatos`, uma função, sem fila nem estado
- [x] **Política de simultaneidade** (ADR-014) — decidir na borda do pipeline, não
      descobrir no meio de uma música: `assign` é monofônico e `rhythm.eventos`
      levanta erro. Deixa de ser latente no primeiro áudio real
- [x] Rótulo do instrumento por **conjunto** (`electric_bass`, `acoustic_bass`,
      `contrabass`), nunca literal — o rótulo depende de contexto (emenda do
      ADR-008) e não foi medido sobre stem do Demucs. `Counter` dos rótulos no
      resultado, como no gate de regressão
- [x] **Nota fora do braço não é fatal** (ADR-014) — apareceu no primeiro teste:
      é a assinatura do erro de oitava do Demucs, e `assign` levantava
      `AlturaImpossivelError` matando a música inteira por causa de uma nota
- [x] BPM plumbado ponta a ponta (entrada, não estimativa — ADR-013)
- [x] `thoth transcribe <ref> --out <dir> --bpm` na CLI

**Pronto quando:** `thoth transcribe` sobre um áudio real produzir `.gp5` e
`.musicxml` que abram, com o rótulo e os avisos de oitava no relatório.

## Fase 5 — API e UI

- [x] FastAPI: `POST /jobs`, `GET /jobs`, `GET /jobs/{id}`,
      `GET /jobs/{id}/artifacts/{fmt}`. Jobs em memória e falha de pipeline como
      estado do job, não 500 (ADR-015). O resumo devolve descartes, notas fora do
      braço e avisos de oitava — a tablatura sozinha não conta o que foi perdido
- [x] alphaTab servido localmente (sem CDN): renderiza, toca e **controla andamento
      (estudar a 50–70%)** — ferramenta de estudo central para iniciante (ADR-006).
      `scripts/vendor_alphatab.py` resolve os `import` em vez de listar arquivos;
      a lista fixa trazia só a fachada de 4 KB e deixava a página em branco
- [x] `thoth serve` — sobe API e página em `127.0.0.1` por padrão
- [x] **Abrir a página no navegador** — não renderizava. Causa: `scrollElement`
      apontando para o próprio `#tab`, que faz o lazy loading do alphaTab achar
      que nada está visível (ADR-016). Fechado com teste de navegador de verdade
      (`tests/navegador/`, marcador `navegador`), verificado nos dois sentidos
- [x] Reabrir job pronto por `?job=<id>`, com guarda para id inexistente
- [x] **Tocar e cursor** — medido, não ouvido (2026-09-25):
      `test_tocar_faz_sair_som_e_andar_o_cursor_e_parar_cala`. Um analisador preso a
      toda ligação com a saída de som mede o volume: 0 antes, ≈ 0,094 tocando, 0 depois
      de Parar; o cursor anda (x 198 → 235 px em 1 s). Provado nos dois sentidos:
      `enablePlayer: false` e `enableCursor: false` o fazem falhar. Limite: o autoplay
      é liberado por flag, então a política de gesto do navegador real não é exercitada

## Fase 6 — Opcionais

- [ ] Sync do cursor via Spotify `currently-playing`
- [x] Containerfile + compose (CPU) — ADR-040, job real verificado dentro do contêiner
- [ ] Multi-instrumento: guitarra polifônica, piano, bateria

## Pendências para o Welington

- [x] ~~Aval para `omarchy-pkg-install musescore`~~ — já instalado (MuseScore 4.7.4,
      conferido em 2026-09-24)

## ✅ Resolvido — GP5 gravado perdia beats no round-trip (2026-09-22)

Achado ao verificar o ADR-018 com o CLI real, **não introduzido por ele** (o mesmo
resultado aparecia com as mudanças em `git stash`).

- **Sintoma:** `out/escala.gp5` relido com PyGuitarPro trazia 4 beats com nota em vez
  de 15; cada compasso virava **um** beat com todas as notas empilhadas dentro.
- **Causa raiz:** `gp.Beat.status` nasce `BeatStatus.empty` no PyGuitarPro, e o
  exportador só ajustava o das pausas (`rest`). Na leitura, `gp3.readBeat` devolve
  `0` para beat `empty` em vez da duração, então o cursor `start` não avança e
  `getBeat(voice, start)` devolve o beat anterior — as notas seguintes entram todas
  nele. Reproduzido com PyGuitarPro puro, sem nada do Thoth: 4 beats escritos com
  `empty` → `[4]` na leitura; com `normal` → `[1, 1, 1, 1]`.
- **Correção:** `beat.status = gp.BeatStatus.normal` em `Gp5Exporter._nota`.
- **Por que a suíte não pegava:** os asserts liam as notas achatadas sobre todos os
  beats (`_lidas`), o que sobrevive à fusão. `test_cada_nota_ocupa_um_beat_proprio`
  agora afirma a estrutura, e `test_silencio_vira_pausa_e_nao_desloca_a_nota` passou
  a cobrar o ataque em ticks em vez da sequência de beats que o bug produzia.

## Fase 7 — Configuração de agentes (2026-09-23)

Contrato de projeto para os agentes que trabalham neste repositório. `AGENTS.md` é o
canônico (o Codex só lê esse); `CLAUDE.md` importa com `@AGENTS.md` e acrescenta a
cauda que só o Claude Code entende — o `@import` é resolução exclusiva do Claude, e
inverter a direção faria o Codex ler um ponteiro vazio **sem erro visível**.

- [x] `AGENTS.md` — só os *deltas* que um agente novo erraria: pt-BR no código, teto
      do Python, o que `pytest` **não** roda por padrão, repositório público
- [x] `CLAUDE.md` — `@AGENTS.md` + skills e fluxo `tasks/`
- [x] `.claude/settings.json` — allowlist estreita, nada específico da estação
      (o repositório é público); o que for local vai em `.claude/settings.local.json`,
      agora no `.gitignore`
- [x] `.claude/commands/verificacao.md` — os três comandos da verificação de entrega
- [x] Revisão do `AGENTS.md` pelo Codex contra o repositório

**Suposição declarada:** `install.py` (`~/workspace/claude-md`) gerencia o `~/.claude`
global. O `.claude/` deste repositório é versionado aqui e não entra no instalador.

- [x] Três docstrings realinhados aos ADRs (2026-09-23): `services/rhythm.py` e
      `adapters/export/gp5.py` tratavam o BPM como obrigatório (ADR-019/021) e
      `domain/ports.py` chamava a separação de opcional (ADR-010). Achado pela
      revisão do Codex sobre o `AGENTS.md`.

## Fase 8 — Análise conjunta Claude + Codex (2026-09-23)

Revisão de projeto inteiro feita em paralelo por Claude Opus 5 e Codex `gpt-5.6-sol`,
com os achados cruzados e verificados um a um contra o código. Ordem de execução
abaixo é por impacto, com dependência declarada onde existe.

**Decisão do usuário nesta rodada:** executar tudo, inclusive os itens de pesquisa
(B2/B3/B7/B9), cada um com ADR e medição antes do código. A modelagem de A1 foi
decidida na conversa: **decompor no exportador**, não partir o evento no pipeline.

### Defeitos com correção definida

- [x] **A1 — nota que cruza a barra é truncada, em GP5 e MusicXML.** (ADR-022)
      `eventos()` devolve a duração real; o GP5 fatia nas barras e liga com
      `NoteType.tie`, o MusicXML não precisou mudar — o `makeNotation` já ligava.
      Censo do acervo: em Is It A Crime, 26,3% das notas saíam encurtadas e só
      74,2% da duração soava. Verificado ponta a ponta nessa música: 778 ataques
      para 778 notas de entrada, 215 compassos e nenhum fora de 4/4.
- [x] **B6 — teste de quantização ponta a ponta.** (ADR-023)
      `tests/integration/test_quantizacao_ponta_a_ponta.py`: referência sintética em
      código (não em `cache/`, que é gitignorado) → rítmica → GP5 → releitura →
      `avaliar`. 2,9 s, na suíte padrão. Conferido: com o `rhythm.py` antigo, 3 dos 5
      testes reprovam.
- [x] **A2 — dobrar o andamento para 70–160 descarta metade das notas.** (ADR-024)
      `desdobrar()` em `tempo.py`, chamada entre transcrever e `ajustar`, só no caminho
      estimado. Critério: colisão na grade acima de 10%, no máximo duas dobras. Medido:
      colisão de 0,0–2,8% no BPM certo contra 20–37% na grade pela metade.
      `Resultado.desdobrado` + linha na CLI. Limite declarado: música sem semicolcheia
      (0,0–4,5%) não é resgatável — é limite do sinal.
- [x] **A11 — `--bpm 0` colapsa a música em uma nota.** (ADR-025) `BPM_MINIMO/MAXIMO`
      (20–300) em `tempo.py`, uma fonte para CLI, API e pipeline; `transcrever` valida
      antes do download. `AFINACOES` na CLI com `typer.BadParameter` — nome fora do
      catálogo não vira mais a afinação padrão calado (a chave virou nome no ADR-028).
- [x] **A3 — piso do teste da separação era 0,682 e o ADR-010 mediu 0,968.**
      (ADR-010, emenda 2026-09-23) `COM_SEPARACAO_NOTA_F1 = 0.968`, exato — o F1 é
      discreto (~0,03 por nota em 16). O piso antigo fica com mensagem própria:
      abaixo de 0,682 é o ADR desmentido, não regressão. Medido 2x: 0,968, margem
      +0,000, `ref=16 est=15`.
- [x] **A4 — cache do Demucs não pertencia ao modelo** que o produziu. (ADR-026)
      `separate` procura em `out_dir / self.model`; os dois modelos convivem no mesmo
      cache. Medido: stem de `mdx_extra` passava por `htdemucs_ft`.
- [x] **A5 — nenhuma escrita de cache era atômica.** (ADR-026) `thoth/arquivos.py`
      com `escrita_atomica` e `diretorio_atomico`, vizinhos do destino (o `/tmp` desta
      estação é outro ponto de montagem). Quatro sítios: notas, WAV local, WAV do
      YouTube, stems. Três testes vermelhos antes de verdes.
- [x] **A7 — `stderr` dos subprocessos era descartado** nos 6 pontos. (ADR-026)
      `thoth/processos.py` com `rodar` e `ErroDeProcesso`; cada módulo mantém o próprio
      tipo de erro na fronteira. `FileNotFoundError` continua passando direto.
- [x] **A6 — jobs concorrentes dividem arquivos**; dict `jobs` sem limite. ADR-027: execução serializada por `threading.Lock`, `status` nasce `na fila`, histórico com teto de 50 descartando os concluídos mais antigos — e nunca o que ainda não terminou. Teste de concorrência com threads reais, verificado vermelho (o segundo job entrava no pipeline com o primeiro dentro).
- [x] **A9 — `pipeline.py` instancia adapters**; `AudioSource` não é injetável.
      `transcrever(source=...)` como os outros quatro estágios: `source or resolver_fonte(ref)`.
      Sem ele, todo teste do pipeline arrastava ffmpeg ou rede.
- [x] **A10/B4 — `PADRAO` e `TUNING_BASS_DROP_D` existem e não têm porta de entrada.**
      (ADR-028) Catálogos nomeados: `AFINACOES` (`4`/`5`/`drop-d`) em `models.py` e
      `DIGITACOES` (`iniciante`/`experiente`) em `fretboard.py`. `--afinacao`/`--digitacao`
      na CLI, campos no `Pedido`, dois `<select>` na página; `--cordas` sai (drop D tem
      quatro cordas — contar cordas não a nomeia). O JS perdeu o `Number()`, e o
      formulário ganhou teste de navegador que o dirige: `-m navegador` 3 passed.
- [x] **A8 — `octave_check` ignora `offset_s`** e analisa 0,6 s fixos. (ADR-029)
      `janela_s` virou teto: a janela é `min(teto, offset - onset)`. Teste vermelho
      antes: nota de 0,3 s seguida de 30,9 Hz forte passava calada.
- [x] **A12 — `octave_check` lê o stem inteiro na memória.** (ADR-029) `setpos` +
      `readframes` por nota, arquivo aberto uma vez. Medido com `tracemalloc` em 30 s
      de WAV: pico de 26,5 MB → menos de 2 MB.
- [x] **B5 — nenhuma métrica de offset.** (ADR-023) `nota_offset_f1` e
      `duracao_ratio` em `Scores`, informativas e fora de qualquer piso. Medido: com o
      corte na barra ativo, as duas métricas antigas dão 1,000 com 3 de 13 notas
      encurtadas.
- [x] **B8 — oitava é diagnóstico, não sugestão.** (ADR-030) `pitch + 12` deixou de
      ser afirmado: a mesma razão é medida para a candidata e a sugestão só sai quando
      ela explica melhor — senão `suggested_pitch` é `None`. A comparação é entre as
      duas razões, não um segundo corte pelo `limiar` (calibrado só na original). O
      gatilho não mudou, então os testes com modelo real seguem valendo. Exposto na
      CLI, no `_resumo` e na página; `inf` vira `null` (`Infinity` quebra o
      `JSON.parse`). `-m navegador` 4 passed.

### Pesquisa — ADR e medição antes do código

- [x] **B9 — grafia sempre com sustenido.** (ADR-031) `services/tonalidade.py`:
      estimativa via music21 com **margem contra a melhor interpretação de sinal
      oposto** (o sinal é o que muda a grafia; relativas escrevem igual), teto 0,05.
      Medido no acervo: 3 de 7 músicas são tom bemol (~476 notas mal escritas) e uma
      é empate exato — o único caso recusado pela margem. Armadura errada imprime
      mais acidente que armadura nenhuma (11 contra 9 em 12 notas), então abaixo da
      margem nada muda. `--tom`/campo na página/`Pedido.tom`; exportadores com
      `armadura`. `-m navegador` 5 passed.
- [x] **B7 — digitação otimiza posição, não técnica.** (ADR-032) O estado do
      Viterbi virou `(corda, traste, mão)`: o deslocamento é cobrado contra o
      último traste **pisado**, e mão ainda não posicionada não paga nada. O
      `3 → 0 → 15` do enunciado não reproduz — a emissão limita o braço ao traste
      ≤10, e o pior salto escondido medido é 8. No acervo (7924 notas): experiente
      27 → 8 saltos acima de 4 trastes (os 8 restantes são genuínos, lidos um a um),
      iniciante 19 → 17 (o `acima_da_janela` já prendia a mão). Posição muda em
      0,28% das notas; custo de tempo abaixo do ruído. Sem peso novo em `Custos`.
      A leitura ampla de "técnica" (articulação, dinâmica) é o B3.
- [x] **B3 — nada de dinâmica nem articulação.** (ADR-033) **Resultado negativo:
      pesquisa feita, nenhum código.** As três hipóteses foram medidas e as três
      falham. Articulação é impossível: `offset_s` é preenchimento — provado contra
      fixture de duração conhecida (notas de 0,45 s com 0,10 s de silêncio voltaram
      contíguas) e 83%–99,7% de lacuna zero no acervo. Dinâmica não existe na saída
      do modelo (velocidade 120 contra 40 descartada) e, do áudio, é IQR de 2,4–5,6 dB
      sem rótulo para calibrar corte. Deslize: o discriminador dispara igual ou mais
      no controle (pares com silêncio, que não podem ser deslize). Reabre com
      tablatura de referência (Camada 3, ADR-007). O achado sobre `offset_s` foi
      para `NoteEvent.duration_s`, `tonalidade.py` e uma emenda ao ADR-022.
- [x] **B2 — representação rítmica estreita.** ADR-034. **Resultado negativo:
      pesquisa feita, nenhum código.** A premissa do item caiu: a semicolcheia ganha
      da tercina e das duas grades de swing nas sete músicas (10,4–30,8 ms contra
      27,2–58,6 e 23,9–88,4), e a fusa quase não melhora (0,1–2,9 ms em quatro) — o
      resíduo é jitter de ataque do transcritor, não erro de quantização, então
      **grade mais fina não reabre o item**. Tercina some contra controle interno em
      seis das sete. Andamento variável é real em 1 de 7 (degrau 103,0 → ~105), e a
      medida barata acusaria primeiro a música errada: limiar de n=1, reprovado no
      mesmo piso do ADR-033.

### Verificado e descartado

- A suíte **não** trava: `-n auto` 174 passed em 16,1 s, `-n 0` 174 passed em 29,3 s.
  O travamento que o Codex relatou é do sandbox dele.
- MusicXML com `Bass8vb` e sem `<transpose>` **não** é defeito: o round-trip devolve
  C2 / MIDI 36, correto, e a posição na pauta é a usual do baixo.
- `astype(np.float64)` em `_ler_mono` **não** é redundante — o buffer vem `<i2`.

## Fase 9 — tablatura dentro do MusicXML (ADR-035)

> Origem: o MuseScore abria os nossos arquivos só em notação. O `.gp5` já declara
> `tablature=True` e o importador de Guitar Pro do MuseScore ignora a flag — não há
> o que corrigir lá. O MusicXML, esse sim, não dizia nada sobre tablatura.

Sondado antes de escrever código, com `mscore` de verdade:

- `<staff-details number="2">` depois dos `<clef>` monta a pauta de tablatura;
- `<staff-tuning line="N">` com **linha 1 = corda mais grave** devolve
  `StringData [28, 33, 38, 43]` no MuseScore — a nossa afinação, na ordem certa;
- na volta pelo music21 10.5 o arquivo vira 2 `PartStaff`: `parts[0]` notação,
  `parts[1]` tablatura;
- o MuseScore **honra** o nosso `<technical>`: mandei 8-10-12-13 na corda grave,
  digitação que algoritmo nenhum escolheria, e foi exatamente o que voltou.

- [x] Testes primeiro: estrutura de duas pautas, linhas e afinação no XML cru,
      afinação de 5 cordas inteira, nome da nota só na partitura, corda/traste só
      na tablatura, e um teste contra o `mscore` real (pulado se ausente).
- [x] `MusicXmlExporter` passa a montar `PartStaff` de notação + `PartStaff` de
      tablatura sob um `StaffGroup`, e injeta `<staff-details>` após a escrita —
      o music21 10.5 emite `<staves>`, `<staff>` e a clave TAB, mas não o
      `staff-details`.
- [x] Testes existentes ancorados em `parts[0]` — sem isso passam a contar cada
      nota duas vezes e a asserção muda de significado em silêncio.
- [x] ADR-035 em `tasks/decisions.md`.

### Fechada

Verificação de entrega: `pytest -n auto` 279 passando; `-m slow` do exportador passando com o
`mscore` 4.7.4 instalado; `ruff` e `mypy --strict` limpos.

Uma asserção fora do exportador precisou de âncora: `test_pipeline.py::
test_o_tom_informado_chega_a_armadura_da_partitura` lia a armadura pela partitura
toda e passou a ver duas. O arquivo grava **uma** — o `<attributes>` é da parte
inteira e o music21 dá uma cópia a cada pauta na leitura. Ancorada em `parts[0]`.

Os sete artefatos em `out/` são anteriores a isto: ainda de uma pauta. Reexportar
é rodar o pipeline de novo nas sete.

## Fase 10 — o áudio junto da partitura (ADR-036)

> Origem: pedido direto — "quero os arquivos wav, gp5 e musicxml na mesma pasta".
> Mix e baixo isolado; sem `.mscz`, que o MuseScore não precisa desde o ADR-035.

- [x] Teste primeiro: nomes, mesma pasta dos exportadores, bytes iguais à origem,
      e não-symlink. No `slow` real, mix e baixo diferentes entre si — asserção que
      o dublê não permite, porque lá o stem é o próprio mix.
- [x] `transcrever` copia os dois para `out_dir` e os devolve em `artefatos`.
- [x] ADR-036 em `tasks/decisions.md`.
- [x] Oito músicas já processadas preenchidas sem reprocessar, e os sete `.mscz`
      apagados.

## Fase 11 — pasta por música e CLI que mostra os estágios (ADR-037)

> Origem: pedido direto — "cli colorido que mostra todas as etapas do processo",
> "salve os arquivos em pastas separadas com o nome da musica", "todos os wavs que
> você produzir". Decidido junto: nomes repetem o da música dentro da pasta, e os
> wavs são mix, baixo, sem-baixo e a auralização.

- [x] Teste primeiro: um dublê de `Progresso` coletando os nomes dos estágios na
      ordem; caminhos dentro de `out/<nome>/`; os quatro wavs presentes e com os
      bytes da origem.
- [x] `Progresso` como `Protocol` em `domain/ports.py` — o pipeline anuncia o
      estágio, quem desenha é o CLI. Sem isso o `rich` entraria num service.
- [x] `transcrever` grava numa pasta por música e copia os quatro wavs.
- [x] Auralização dentro do pipeline, e falha dela **não** mata a corrida: o
      soundfont é opcional e são minutos de CPU em jogo (ADR-014).
- [x] `transcribe` com `rich`: um estágio por linha, tempo decorrido, ✓ ao fechar.
- [x] ADR-037 em `tasks/decisions.md`, emendando o ADR-036 no que muda.
- [x] As oito músicas já em `out/` movidas para o formato novo.

### Fechada

Verificação de entrega: `pytest -n auto` 289 passando; `ruff check` e `mypy --strict` limpos.

Conferido rodando de verdade, e não só pelo teste: `thoth transcribe` numa música
cacheada imprimiu os dez estágios com o tempo de cada um — `obtendo o áudio` 0:00,
`estimando o andamento` 0:05, `separando o baixo` 0:00 (cache), `transcrevendo as
notas` **2:36**, `ajustando a grade rítmica` 0:05, `conferindo as oitavas` 0:01,
`posicionando no braço` 0:00, `exportando a partitura` 0:03, `copiando os áudios`
0:00, `auralizando` 0:06. Total 3m15 de parede, 25m53 de CPU.

As oito pastas em `out/` conferidas com 6 arquivos cada e nada solto em `out/`
(`find out -maxdepth 1 -type f` vazio). Os quatro WAVs de uma delas conferidos por
hash: distintos, e o RMS do playback (0,0896) fica entre o do mix (0,1215) e o do
baixo (0,0290), como se espera de um mix sem o baixo.

Achado que virou a Fase 12: o music21 cospe `beam: WARNING: Found a messed up beam
pair` ao gravar o MusicXML. Não foi silenciado — o aviso é sinal real, e investigar
mostrou que ele **subnotifica** o problema. Números medidos abaixo.

## Fase 12 — beams mal-formados no MusicXML ✅ **FECHADA (2026-09-24)**

> Origem: o aviso `beam: WARNING: Found a messed up beam pair` que a Fase 11 deixou
> anotado. Investigado em 2026-09-23. **São dois defeitos, não um**, e o aviso só
> cobre o menor dos dois.

### O defeito, medido nos oito arquivos já entregues

**208 beams mal-formados** — `end` ou `continue` num nível de beam sem `begin` aberto,
o que o MusicXML não admite. De 8 a 52 por música, metade em cada pauta (as duas
compartilham o ritmo). Nenhum `begin` pendurado.

O aviso do music21 aparece de 0 a 6 vezes por música: ele só dispara no subcaso que
`mergeConnectingPartialBeams` examina. **O resto sai calado.**

| forma | quantos | causa | quem tem culpa |
|-------|---------|-------|----------------|
| (A) há pausa dentro do grupo | 46 | entregamos um stream com buracos | nossa |
| (B) grupo contíguo | 162 | nota cruzando a fronteira de tempo | music21 10.5 |

> Este split vem do classificador por proximidade de pausa, que **superestima (A)**:
> `end@1` solto perto de uma pausa era contado como (A) sem estar dentro de grupo
> nenhum. A medição controlada mais abaixo o supera; o total (208) segue valendo.

### (A) — nossa: o stream vai com buracos para o `makeNotation`

`_pauta` faz `parte.insert(offset, nota)` e nunca preenche as pausas. O beam é
calculado antes de elas existirem, e duas notas a meio compasso de distância se veem
como vizinhas. Medido:

```python
ts.getBeams([Note(0.25), Rest(2.25), Note(0.25), Rest(1.25)])  # [None,None,None,None] ✅
# mas o mesmo ritmo inserido com buracos: 1/begin + 2/forward hook … 1/end + 2/end ❌
```

Com `parte.makeRests(fillGaps=True, inPlace=True)` antes do `makeNotation`, o music21
acerta sozinho: nenhum beam, que é o certo para semicolcheia isolada. **A forma (A) é
uma linha.**

### (B) — do music21: nota que cruza a fronteira de tempo

Sobrevive ao `makeRests` — é ritmo contíguo, sem pausa nenhuma. O mínimo é quatro
notas: `(2, 8, 3, 3)` semicolcheias (colcheia, mínima, colcheia pontuada, colcheia
pontuada) sai `1/begin, 1/continue, 1/end, 1/end` — dois `end`. **O music21 não avisa
em nenhum dos 18 ritmos mínimos encontrados.**

Varredura de todas as composições contíguas de um compasso 4/4 na grade de
semicolcheia, com 2 a 5 notas:

- nenhuma nota cruzando a fronteira de semínima: **0 mal-formados em 13**
- alguma nota cruzando: **132 mal-formados em 1535**

A amostra negativa é pequena (13), então isso é compatível com "cruzar o tempo é
condição necessária", não prova dela. 10.5.0 é a versão mais nova que existe no PyPI:
não há correção a montar.

### O que já foi descartado como saída

- **Não emitir beams.** Conferido: o MuseScore 4.7.4 **não** beameia sozinho quando o
  arquivo não traz beam nenhum — cada semicolcheia sai com bandeirola solta.
- **Deixar o leitor consertar.** O MuseScore não recusa o arquivo, mas o conserto é
  visível e errado: no caso mínimo de (A) ele tira a primeira nota do grupo e pendura
  o beam numa **pausa**.

### O que falta

- [x] Teste de gramática sobre o XML escrito, por (pauta, voz, nível), incluindo
      `begin` que fica aberto. É o teste que faltava: o round-trip pelo music21 não
      pega nada disso, porque ele relê o que escreveu.
- [x] (A): `makeRests(fillGaps=True)` antes do `makeNotation` em `_pauta`.
- [x] (B): refazer por tempo só o compasso quebrado — ADR-039, 2496 → 0 nos 32767
      compassos contíguos; nas nove músicas, ver o fim desta seção. Era: decidir a
      abordagem — nenhuma foi escolhida ainda. Quebrar o grupo na
      fronteira de tempo é o candidato, mas não está verificado que resolve, e não há
      botão para isso (conferido em `meter/base.py::getBeams` e
      `stream/makeNotation.py::makeBeams`).
- [x] Reexportar as músicas depois da correção — são **nove**, não oito; a conta
      anterior estava errada. Resultado abaixo.
- [x] ADR-038 com a medição. — escrito para (A); a parte (B) fica registrada como aberta.

### (A) fechada — medição controlada

O mesmo conjunto de notas de sete músicas do cache, exportado com e sem a linha do
`makeRests` (comparar com os arquivos entregues não isola nada: sem o recuo de fase do
pipeline o conjunto de notas muda — daí 248 aqui contra os 208 medidos sobre a base
entregue):

| base | mal-formados | (A) | (B) |
|------|--------------|-----|-----|
| sem a correção | 248 | 48 | 200 |
| com a correção | 200 | 0 | 200 |

Queda monotônica nas sete, nenhuma piora. Os 14 que a primeira conta ainda punha em (A)
são (B) disfarçados: `end@1` solto numa colcheia pontuada, sem `begin` em lugar nenhum.

Verificação de entrega: 291 passed + 1 xfailed (era 289), ruff e mypy limpos. O `xfail(strict=True)` de
(B) é de propósito — fica vermelho no dia em que (B) for corrigido.

O conteúdo não mudou com a correção: nos sete pares antes/depois, notas, compassos e
pausas batem exatamente — o `makeNotation` já produzia as mesmas pausas, e a correção só
muda **quando** elas existem. Nenhum `begin` aninhado nem pendurado em nenhuma das bases.

### Reexportadas e validadas — 2026-09-23

As nove pelo caminho de verdade (`thoth transcribe`, com stems e download em cache;
34 min de relógio no total, 2m03 a 8m11 por música, todas com saída 0). O validador de
gramática sobre `out/*/*.musicxml`:

| música | mal-formados |
|--------|--------------|
| Dance of Death | 50 |
| Smooth Operator | 24 |
| Seu Jorge — Tive Razão | 22 |
| SOU EU | 38 |
| Feel Like Makin' Love | 28 |
| Sade — Is It A Crime | 14 |
| Hallowed Be Thy Name | 10 |
| SOJA — Everything Changes | 2 |
| Ne Obliviscaris — Equus | **0** |
| **total** | **188** |

Nenhum `begin` pendurado, nenhum `begin` aninhado. E a asserção que importa: **0 grupos de
beam abraçando pausa** nos nove arquivos — a assinatura da forma (A) desapareceu.

Os 16 que o classificador ainda põe em "(A)" são (B) com pausa por perto: a heurística de
proximidade deixa de valer quando as pausas passam a existir em todo compasso, e a conta
estrutural acima é a que decide. Os 188 são todos (B), o defeito aberto do music21 10.5.

Os artefatos não entram no repositório (`out/` no `.gitignore`, ADR-005): o que fica
versionado é a correção que os gera e esta medição.

### (B) fechada — 2026-09-24 (ADR-039)

Só o compasso quebrado é refeito, por tempo, com o `getBeams` do music21. Varredura de
todos os 32767 compassos 4/4 contíguos: music21 sozinho 2496, primeira versão do
conserto 80 (achados pelo Codex: `measureStartOffset` do tempo, não da primeira nota),
esta **0**.

Nove músicas reexportadas pelo `thoth transcribe` real, todas com saída 0: **188 → 0**.
Nas oito comparáveis, 0 dos 2998 pares (compasso, pauta) válidos mudaram e as notas batem
exatamente; só os 94 compassos quebrados foram refeitos.

**Achado de passagem:** a reexportação de 2026-09-23 do *Equus* saiu com **4 cordas** — o
`--afinacao 5` que `tasks/corpus.md` manda usar ficou de fora, e ~444 notas abaixo do E1
foram descartadas (ADR-014) calado. A tabela de 2026-09-23 acima (Equus: 0) mediu esse
arquivo. Refeito com 5 cordas: 3251 elementos de nota, 0 mal-formados.
