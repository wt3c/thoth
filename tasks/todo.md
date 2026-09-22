# Thoth — plano de execução

> Áudio → partitura e tablatura, foco em contrabaixo. Uso pessoal. CPU-only.
> Decisões em `tasks/decisions.md`.

## Fase 0 — Spike de viabilidade ⬅️ **ATUAL**

Sem escrever código do pipeline. Medir se a qualidade justifica o projeto.
A avaliação **não depende de saber tocar** (ADR-006).

### Preparo
- [ ] `uvx muscriptor transcribe --help` → **verificar** as flags reais
      (`--instruments`, `--model`, `--format`, auralização). Não assumir.
- [ ] Aceitar a licença CC BY-NC 4.0 no HuggingFace

### Camada 1 — objetiva (critério principal)
- [ ] Fixtures: 5–10 linhas de baixo em MIDI (escalas, walking, groove em
      semicolcheias, graves no E/B) → fluidsynth + soundfont → WAV
- [ ] Rodar o pipeline e medir **Onset F1** com `mir_eval`
- [ ] Repetir com `small` vs `medium`, cronometrando em CPU

### Camada 2 — perceptual assistida (dispensa treino)
- [ ] Auralização: original em um canal, MIDI no outro. Se descolar, qualquer
      ouvido percebe
- [ ] Vídeo de referência: SOJA — Everything Changes (`QTOyeFQgZKk`), reggae,
      baixo em primeiro plano e repetitivo

### Camada 3 — referência externa
- [ ] Conferir oitava e notas contra tablatura humana publicada de uma música
      conhecida (Songsterr/Ultimate Guitar)

### Comparações a fazer
- [ ] **mix direto** vs **stem do Demucs** → decide a condicional C1
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

## Fase 2 — MuScriptor + ground truth

- [ ] `MuscriptorTranscriber` atrás do `Protocol Transcriber`
- [ ] `models.lock.toml` com SHA-256 dos pesos (checkpoints somem da internet)
- [ ] Promover as fixtures da Fase 0 a **gate de regressão** travado no CI
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

- [ ] **C1** `DemucsSeparator` (`htdemucs_ft`) — só se F1 com separação > sem
- [ ] **C2** Beat This! + quantizador próprio — só se o ritmo do MuScriptor decepcionar

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
