# Thoth — plano de execução

> Áudio → partitura e tablatura, foco em contrabaixo. Uso pessoal. CPU-only.
> Decisões em `tasks/decisions.md`.

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
- [ ] Fixtures: 5–10 linhas de baixo em MIDI (escalas, walking, groove em
      semicolcheias, graves no E/B) → fluidsynth + soundfont → WAV
- [ ] Rodar o pipeline e medir **Onset F1** com `mir_eval`
- [ ] Repetir com `small` vs `medium`, cronometrando em CPU

### Camada 2 — perceptual assistida (dispensa treino)
- [ ] Auralização: original em um canal, MIDI no outro. Se descolar, qualquer
      ouvido percebe
- [ ] Rodar a auralização sobre o corpus de `tasks/corpus.md` — **reportar F1
      por grupo**, nunca um número agregado (Grupo A é otimista por construção)

### Camada 3 — referência externa (ADR-007)
- [ ] Escolher música clássica com tab de baixo **humana** — filtrar
      `aiGenerated == false` em `/api/meta/{songId}/revisions` do Songsterr
      (verificados: 14, 14046, 371). A tab da SOJA é `aiGenerated: true` e
      **não serve** — seria circular
- [ ] Conferir oitava e notas contra essa tab
- [ ] Opcional: baixar manualmente o `.gp5` da tab da comunidade no UG Pro e
      ler com PyGuitarPro. Download manual — o Thoth não faz scraping do UG

### Comparações a fazer
- [ ] **mix direto** vs **stem do Demucs** → decide a condicional C1.
      Medir no **Grupo B** (mix real); o Grupo A não discrimina separação
- [ ] **com** vs **sem** `--instruments` → decide se vale condicionar

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

## Fase 2 — MuScriptor + ground truth ⬅️ **ATUAL**

- [x] **Verificador de oitava** (`services/octave_check.py`) — razão `f0 / 2·f0`
      por nota, limiar 0,40, 7 testes contra WAV real gerado pelo ffmpeg.
      Roda sobre o **stem**, não sobre a mix: validado nos dois, pega 12/12 no
      stem e só 6/12 na mix (bumbo e guitarra enchem a banda de 30,9 Hz).
- [ ] Mais um dado para essa validação (2026-09-22, primeira execução da CLI
      ponta a ponta): no stem do Demucs da fixture `walking` o limiar sinaliza
      **4 de 15 notas** (27%), todas G2/A2 — bem acima dos 8,7% medidos em
      material real. Fixture sintética passada pelo Demucs não é material real,
      então isto não condena o limiar; é mais uma amostra de que a taxa de
      alarme depende forte do material
- [ ] Validar o limiar **fora do Equus** — ele foi calibrado nas mesmas 12 notas
      em que foi medido. Taxa de alarme por faixa: jorge 1,9%, sade 12,9%,
      neo 15,8%; sem referência não dá para saber quanto disso é erro real.
      Depende do `.gp5` de *Equus* (ADR-007), a baixar manualmente do UG.
- [x] `MuscriptorTranscriber` atrás do `Protocol Transcriber` — subprocesso via
      `uvx` (torch fora do projeto), `small` + livre + `--detect-tempo false`.
      7 testes: 6 de parsing puro + 1 contra o modelo real (`slow`).
- [ ] **Não fatiar áudio antes de transcrever** — o rótulo do instrumento depende
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
      projeto pessoal, sem necessidade de CI. O portão roda localmente sob
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
- [ ] Ligaduras no GP5 (hoje: figura + pausa; ataque exato, duração truncada — ADR-013)

**Pronto quando:** abrir sem erro no TuxGuitar.

## Condicionais — só com evidência da Fase 0

- [x] **C1** `DemucsSeparator` (`htdemucs_ft`) — **aprovada** e promovida a etapa
      fixa do pipeline (ADR-010). Custo conhecido: erra a oitava em 7% das notas
      no material grave e denso — mitigação na Fase 2, não motivo para reverter.
- [ ] **C2** quantizador próprio — o Beat This! é dependência dura do MuScriptor
      (ADR-003 corrigido), não condicional. Pendente: `cloud.cp.jku.at` inacessível
      daqui, então ou achamos espelho do `beat_this-final0.ckpt`, ou escrevemos o
      quantizador e rodamos sempre com `--detect-tempo false`.

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

## Fase 5 — API e UI ⬅️ **ATUAL**

- [x] FastAPI: `POST /jobs`, `GET /jobs`, `GET /jobs/{id}`,
      `GET /jobs/{id}/artifacts/{fmt}`. Jobs em memória e falha de pipeline como
      estado do job, não 500 (ADR-015). O resumo devolve descartes, notas fora do
      braço e avisos de oitava — a tablatura sozinha não conta o que foi perdido
- [x] alphaTab servido localmente (sem CDN): renderiza, toca e **controla andamento
      (estudar a 50–70%)** — ferramenta de estudo central para iniciante (ADR-006).
      `scripts/vendor_alphatab.py` resolve os `import` em vez de listar arquivos;
      a lista fixa trazia só a fachada de 4 KB e deixava a página em branco
- [x] `thoth serve` — sobe API e página em `127.0.0.1` por padrão
- [ ] **Abrir a página no navegador** — verificação manual, como foi com o
      TuxGuitar: servidor respondendo 200 para todos os ativos prova que o
      servidor está certo, não que o alphaTab renderiza e toca

## Fase 6 — Opcionais

- [ ] Sync do cursor via Spotify `currently-playing`
- [ ] Containerfile + compose (CPU)
- [ ] Multi-instrumento: guitarra polifônica, piano, bateria

## Pendências para o Welington

- [ ] Aval para `omarchy-pkg-install musescore` (não instalado; TuxGuitar já está)
