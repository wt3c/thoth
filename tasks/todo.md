# Thoth — plano de execução

> Áudio → partitura e tablatura, foco em contrabaixo. Uso pessoal. CPU-only.
> Decisões em `tasks/decisions.md`.

## Fase 0 — Spike de viabilidade ⬅️ **ATUAL (bloqueada: faltam os áudios)**

Sem escrever código. Medir se a qualidade justifica o projeto.

- [ ] `uvx muscriptor transcribe --help` → **verificar** as flags reais
      (`--instruments`, `--model`, `--format`). Não assumir.
- [ ] Aceitar a licença CC BY-NC 4.0 no HuggingFace
- [ ] Rodar em **5 músicas cujo baixo o Welington sabe tocar**
- [ ] Para cada uma, 3 condições: **mix direto** · **stem do Demucs** · **com `--instruments`**
- [ ] Medir por condição: tempo em CPU (`small` vs `medium`), % de notas certas,
      erros de oitava, qualidade do ritmo
- [ ] Planilha 5 × 3 × 4 + decisão **seguir / ajustar / abortar**

**Pronto quando:** a planilha existir e a decisão estiver tomada.

## Fase 1 — Esqueleto e domínio ✅ **CONCLUÍDA (2026-09-21)**

- [x] `uv init` com Python 3.12 fixo (ADR-004)
- [x] `domain/models.py` — `AudioAsset`, `NoteEvent`, `TabNote`, afinações
- [x] `domain/ports.py` — `AudioSource`, `Transcriber`, `Separator`, `FretAssigner`, `Exporter`
- [x] `LocalFileSource` — ffmpeg → WAV 44.1 kHz estéreo, `source_id` = SHA-256 do conteúdo
- [x] Cache por `source_id`: cache hit não reconverte
- [x] `cli.py` (Typer): `thoth fetch`
- [x] 6 testes contra **ffmpeg real** (sem mock — Regra 3); ruff + mypy strict limpos

## Fase 2 — MuScriptor + ground truth

- [ ] `MuscriptorTranscriber` atrás do `Protocol Transcriber`
- [ ] `models.lock.toml` com SHA-256 dos pesos (checkpoints somem da internet)
- [ ] Fixtures sintéticas: MIDI → fluidsynth + soundfont → WAV (5–10 linhas de baixo:
      escalas, walking, groove em semicolcheias, graves no E/B)
- [ ] Gate de Onset F1 via `mir_eval`, calibrado na 1ª execução e travado como regressão
- [ ] `@pytest.mark.slow` para o que carrega modelo

**Pronto quando:** o F1 estiver documentado e travado.
**Cuidado:** F1 sintético é métrica de regressão, não de qualidade real.

## Fase 3 — Motor de tablatura (Viterbi/DP)

- [ ] Estados (corda, traste) válidos por afinação: EADG · BEADG · Drop D · custom
- [ ] Custo: distância de traste, troca de corda, janela de posição da mão,
      bônus de corda solta, penalidade de traste alto
- [ ] Hypothesis: pitch(corda,traste) == pitch original; nenhum traste > `max_fret`

**Pronto quando:** as tabs das fixtures forem tocáveis no instrumento.

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
- [ ] alphaTab servido localmente (sem CDN): renderiza, toca, controla andamento (estudar a 70%)

## Fase 6 — Opcionais

- [ ] Sync do cursor via Spotify `currently-playing`
- [ ] Containerfile + compose (CPU)
- [ ] Multi-instrumento: guitarra polifônica, piano, bateria

## Pendências para o Welington

- [ ] **Caminho de 5 arquivos de áudio** — bloqueia a Fase 0
- [ ] Aval para `omarchy-pkg-install musescore` (não instalado; TuxGuitar já está)
