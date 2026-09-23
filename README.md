# thoth

Thoth — deus egípcio da escrita, sabedoria e dos escribas.

Gera **partitura e tablatura a partir de áudio**, com foco em contrabaixo elétrico.
Uso pessoal. Tudo open source, rodando localmente em CPU.

## Como funciona

```
arquivo de áudio  ou  link do YouTube
   │
   ▼
[AudioSource]    ffmpeg | yt-dlp → WAV 44.1 kHz   cache/<source_id>/mix.wav
   ▼
[Separator]      Demucs htdemucs_ft, two-stems  → stem do baixo
   ▼
[Transcriber]    MuScriptor (Kyutai/Mirelo)    → list[NoteEvent]
   ▼
[FretAssigner]   Viterbi/DP sobre a afinação   → list[TabNote]
   ▼
[Exporters]      GP5 · MusicXML
```

O MuScriptor transcreve. O código deste repositório existe para o que ele não cobre:
**GP5 editável**, **afinação configurável** (4/5 cordas, Drop D), separação antes de
transcrever (ADR-010), andamento e grade rítmica (ADR-019/021), sanity-check de oitava
e a orquestração com cache.

## Requisitos

- Python 3.12 (fixo — o MuScriptor não suporta 3.13+; o `uv` cuida disso)
- `ffmpeg` e `ffprobe` no PATH
- `yt-dlp` no PATH (só para links do YouTube)
- `uv`

## Uso

```bash
uv sync

# arquivo local
uv run thoth fetch caminho/para/musica.mp3

# link do YouTube
uv run thoth fetch "https://www.youtube.com/watch?v=QTOyeFQgZKk"

# áudio → .gp5 e .musicxml em out/ (separa, transcreve, posiciona e exporta)
uv run thoth transcribe caminho/para/musica.mp3 --cordas 5

# original à esquerda, transcrição à direita: ouvir se o ritmo descola
uv run thoth auralizar caminho/para/musica.mp3

# API + página de estudo com alphaTab local, em 127.0.0.1
uv run thoth serve
```

Toda referência — em `fetch`, `transcribe` ou `auralizar` — pode ser um caminho ou uma
URL do YouTube; o Thoth detecta sozinho. O áudio normalizado fica em
`cache/<source_id>/mix.wav` e não é rebaixado nem reconvertido em execuções seguintes.

O `transcribe` leva cerca de 2,5× a duração do áudio em CPU. Sem `--bpm`, o andamento é
estimado do mix e **anunciado** — confira ouvindo (ADR-019). O `auralizar` precisa das
notas já em cache, então roda depois do `transcribe`.

## Desenvolvimento

```bash
uv run pytest -n auto          # suíte padrão
uv run pytest -m "slow and not network"   # modelos de verdade — minutos em CPU
uv run pytest -m network       # canário: avisa quando o YouTube quebrar o yt-dlp
uv run pytest -m navegador     # abre um Chromium e inspeciona a página renderizada
uv run ruff check src/ tests/
uv run mypy src/
```

Os marcadores `slow`, `network` e `navegador` ficam fora da suíte padrão. O canário do
yt-dlp tem os dois primeiros, então `-m slow` sozinho também toca a rede.

## Documentos

- `AGENTS.md` — contrato para agentes (o `CLAUDE.md` importa este)
- `tasks/todo.md` — plano de execução por fases
- `tasks/decisions.md` — ADRs (sem DRM · CPU-only · MuScriptor · Python 3.12)
- `tasks/lessons/` — armadilhas já pagas, por domínio

## Licenças

Código deste repositório: a definir. Pesos do MuScriptor: **CC BY-NC 4.0** — uso
não comercial. O `Protocol Transcriber` mantém a troca de modelo barata.
