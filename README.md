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
**GP5 editável**, **afinação configurável** (4/5/6 cordas, Drop D), separação antes de
transcrever (ADR-010), andamento e grade rítmica (ADR-019/021), sanity-check de oitava
e a orquestração com cache.

## Requisitos

- Python 3.12 (fixo — o MuScriptor não suporta 3.13+; o `uv` cuida disso)
- `ffmpeg` e `ffprobe` no PATH
- `yt-dlp` no PATH (só para links do YouTube)
- `fluidsynth` e a soundfont `FluidR3_GM.sf2` em `/usr/share/soundfonts/` — para a
  auralização; sem eles a partitura sai igual e o `transcribe` avisa (ADR-037)
- `uv`
- Pesos do MuScriptor: aceitar a licença no HuggingFace e `hf auth login` uma vez
- Para o `serve`: `uv run python scripts/vendor_alphatab.py` uma vez (alphaTab local, ADR-006)

## Uso

```bash
uv sync

# arquivo local
uv run thoth fetch caminho/para/musica.mp3

# link do YouTube
uv run thoth fetch "https://www.youtube.com/watch?v=QTOyeFQgZKk"

# áudio → out/<título>/ (separa, transcreve, posiciona, exporta e auraliza)
uv run thoth transcribe caminho/para/musica.mp3 --afinacao 5

# refaz só a auralização, a partir das notas em cache
uv run thoth auralizar caminho/para/musica.mp3

# oitava e nota da transcrição contra uma tab .gp5 baixada à mão (ADR-041, ADR-042)
uv run thoth comparar tab.gp5 caminho/para/musica.mp3

# API + página de estudo com alphaTab local, em 127.0.0.1; a página escolhe o
# instrumento como o --instrumento da CLI (afinação só vale para o baixo)
uv run thoth serve
```

Toda referência — em `fetch`, `transcribe` ou `auralizar` — pode ser um caminho ou uma
URL do YouTube; o Thoth detecta sozinho. O áudio normalizado fica em
`cache/<source_id>/mix.wav` e não é rebaixado nem reconvertido em execuções seguintes.

O `transcribe` grava uma pasta por música (ADR-037): `<título>.gp5`, `.musicxml`
(partitura e tablatura), `.mix.wav`, `.baixo.wav`, `.sem-baixo.wav` e `.aural.wav` —
original num canal, transcrição no outro, para ouvir se o ritmo descola. Opções:
`--afinacao` (`4`, `5`, `6`, `drop-d`), `--digitacao` (`iniciante`, `experiente`), `--bpm` e
`--tom`; `uv run thoth transcribe --help` lista todas.

`--instrumento` (`guitarra-limpa`, `guitarra-distorcida`, `guitarra-acustica`) transcreve
uma guitarra, com acordes, a partir do stem `other` (ADR-044). Os arquivos levam o perfil no
nome — `<título>.guitarra-limpa.gp5`, `.musicxml`, `.aural.wav` — e o stem e o playback saem
como `.outros.wav` e `.sem-outros.wav`: nada do baixo é sobrescrito. A afinação vem do
perfil, e `--afinacao` só vale para o baixo. O relatório separa as notas de outra guitarra, as
de outra família que vazaram para o stem e os acordes que não cabem no braço.

`--instrumento bateria` transcreve a bateria do stem `drums`, sem tablatura:
`<título>.bateria.gp5` e `.musicxml` em faixa de percussão, `.bateria.wav`,
`.sem-bateria.wav` e `.bateria.aural.wav`. O relatório conta os ataques que a partitura não
comporta — a mesma peça duas vezes no tique, peça fora do kit GM (35 a 59) e mais de seis
peças juntas.

Leva cerca de 2,5× a duração do áudio em CPU. Sem `--bpm`, o andamento é estimado do mix
e **anunciado** — confira ouvindo (ADR-019). O `auralizar` precisa das notas já em cache,
então só roda depois de um `transcribe`; o `comparar` também. O `comparar` diz a
oitava e, se o stem do baixo estiver em cache, a nota errada por janela de 60 s; cada
número sai com o piso de acaso ao lado, e vale o quanto fica acima dele. Janela perto do
piso sai inconclusiva, então a nota errada é limite inferior.

### Em contêiner (só CPU)

```bash
mkdir -p out cache           # antes: se o Docker criar, nascem de root
docker compose up --build   # → http://127.0.0.1:8000
```

A imagem traz `ffmpeg`, `fluidsynth`, a soundfont, o `yt-dlp` e o alphaTab; os pesos do
MuScriptor **não** entram nela (licença CC BY-NC) — o `hf auth login` continua sendo feito
na máquina, e o cache do HuggingFace é montado. `out/` e `cache/` são os do repositório.
O primeiro job baixa o torch do demucs e do MuScriptor para um volume; os seguintes não
(ADR-040).

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

Código deste repositório: **MIT** (`LICENSE`). Pesos do MuScriptor: **CC BY-NC 4.0** — uso
não comercial. O `Protocol Transcriber` mantém a troca de modelo barata.
