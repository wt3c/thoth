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
- [ ] `models.lock.toml` com SHA-256 dos pesos (checkpoints somem da internet)
- [ ] Promover as fixtures da Fase 0 a **gate de regressão** travado no CI
      (válido só para o `small` — ADR-009 — e cobrindo também o código de
      avaliação, que já produziu dois artefatos errados na Fase 0)
- [ ] `@pytest.mark.slow` para o que carrega modelo

**Pronto quando:** o F1 estiver documentado e travado.
**Cuidado:** F1 sintético é métrica de regressão, não de qualidade real.

## Fase 3 — Motor de tablatura (Viterbi/DP)

- [ ] Estados (corda, traste) válidos por afinação: EADG · BEADG · Drop D · custom
- [ ] Custo: distância de traste, troca de corda, janela de posição da mão,
      bônus de corda solta, penalidade de traste alto
- [ ] **Modo iniciante** (ADR-006): preferir primeira posição, cordas soltas e
      trastes baixos — tocabilidade acima de otimização de deslocamento
- [ ] Hypothesis: pitch(corda,traste) == pitch original; nenhum traste > `max_fret`

**Pronto quando:** as tabs das fixtures couberem na primeira posição quando a
linha permitir, verificado por propriedade — não por execução no instrumento.

## Fase 4 — Exportadores

- [ ] GP5 via PyGuitarPro (afinação, corda/traste, tempo)
- [ ] MusicXML via music21 (clave de Fá 8vb, tonalidade, compasso)
- [ ] Round-trip: grava → relê → mesmas cordas e trastes

**Pronto quando:** abrir sem erro no TuxGuitar.

## Condicionais — só com evidência da Fase 0

- [x] **C1** `DemucsSeparator` (`htdemucs_ft`) — **aprovada** e promovida a etapa
      fixa do pipeline (ADR-010). Custo conhecido: erra a oitava em 7% das notas
      no material grave e denso — mitigação na Fase 2, não motivo para reverter.
- [ ] **C2** quantizador próprio — o Beat This! é dependência dura do MuScriptor
      (ADR-003 corrigido), não condicional. Pendente: `cloud.cp.jku.at` inacessível
      daqui, então ou achamos espelho do `beat_this-final0.ckpt`, ou escrevemos o
      quantizador e rodamos sempre com `--detect-tempo false`.

## Fase 5 — API e UI

- [ ] FastAPI: `POST /jobs`, `GET /jobs/{id}`, `GET /jobs/{id}/artifacts/{fmt}`
- [ ] alphaTab servido localmente (sem CDN): renderiza, toca e **controla andamento
      (estudar a 50–70%)** — ferramenta de estudo central para iniciante (ADR-006)

## Fase 6 — Opcionais

- [ ] Sync do cursor via Spotify `currently-playing`
- [ ] Containerfile + compose (CPU)
- [ ] Multi-instrumento: guitarra polifônica, piano, bateria

## Pendências para o Welington

- [ ] Aval para `omarchy-pkg-install musescore` (não instalado; TuxGuitar já está)
