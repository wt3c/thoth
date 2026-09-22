# thoth

Thoth — deus egípcio da escrita, sabedoria e dos escribas.

Gera **partitura e tablatura a partir de áudio**, com foco em contrabaixo elétrico.
Uso pessoal. Tudo open source, rodando localmente em CPU.

## Como funciona

```
arquivo de áudio
   │
   ▼
[AudioSource]    ffmpeg → WAV 44.1 kHz         cache/<source_id>/mix.wav
   ▼
[Transcriber]    MuScriptor (Kyutai/Mirelo)    → list[NoteEvent]
   ▼
[FretAssigner]   Viterbi/DP sobre a afinação   → list[TabNote]
   ▼
[Exporters]      GP5 · MusicXML · MIDI
```

O MuScriptor faz a transcrição, a quantização e a detecção de tempo. O código deste
repositório existe para o que ele não cobre: **GP5 editável**, **afinação configurável**
(4/5 cordas, Drop D), sanity-check de oitava e a orquestração com cache.

## Requisitos

- Python 3.12 (fixo — o MuScriptor não suporta 3.13+; o `uv` cuida disso)
- `ffmpeg` e `ffprobe` no PATH
- `uv`

## Uso

```bash
uv sync
uv run thoth fetch caminho/para/musica.mp3
```

## Desenvolvimento

```bash
uv run pytest -n auto          # suíte padrão
uv run pytest -m slow          # carrega modelos de verdade — minutos em CPU
uv run ruff check src/ tests/
uv run mypy src/
```

Testes marcados `slow` e `network` ficam fora da suíte padrão.

## Documentos

- `tasks/todo.md` — plano de execução por fases
- `tasks/decisions.md` — ADRs (sem DRM · CPU-only · MuScriptor · Python 3.12)

## Licenças

Código deste repositório: a definir. Pesos do MuScriptor: **CC BY-NC 4.0** — uso
não comercial. O `Protocol Transcriber` mantém a troca de modelo barata.
