# Thoth — contrato de projeto

> Arquivo canônico para qualquer agente (Claude Code, Codex, outro). O `CLAUDE.md`
> importa este conteúdo e acrescenta o que só vale para o Claude Code.

Áudio → partitura e tablatura, foco em contrabaixo elétrico. **Uso pessoal, CPU-only,
rodando na máquina.** O `README.md` é introdutório; as fontes canônicas de comportamento
são `src/thoth/cli.py`, `src/thoth/services/pipeline.py` e `tasks/decisions.md`. Quando o
README e elas discordarem, elas vencem — e o README se corrige junto.

## Este não é um projeto do MPRJ

Nada de Infisical, Keycloak, OpenShift, GitLab interno ou qualquer convenção
corporativa. **Não há secret do projeto nem serviço remoto de aplicação** — nenhum
`.env`, nenhuma credencial em código, nada para configurar. A rede aparece só em dois
pontos externos: ingestão do YouTube via `yt-dlp` e a busca inicial dos pesos no
HuggingFace (`hf auth login`, licença aceita por repositório). Se uma instrução global
falar em secrets ou IAM, ela não se aplica aqui.

## O que um agente novo erra primeiro

### 1. O código é em português

Identificadores, docstrings, comentários, mensagens de CLI e nomes de teste são em
**pt-BR**: `auralizacao`, `resolver_fonte`, `afinacao`, `cordas`, `notas`,
`descartadas`, `test_cada_nota_ocupa_um_beat_proprio`. Inglês aparece só onde o domínio
já é inglês (`NoteEvent`, `TabNote`, `fret`, `onset_s`) ou em API de terceiro. Escrever
`tuning_resolver` no meio disso quebra o idioma do arquivo — siga o que está em volta.

Acentuação correta é obrigatória em todo texto em português, inclusive docstrings e
comentários.

### 2. `requires-python = ">=3.12,<3.13"` é teto, não defasagem

O MuScriptor exige Python 3.10–3.12 (ADR-004). O teto é deliberado. **Não "atualize".**

### 3. A suíte padrão não roda o que é caro

`addopts = "-m 'not slow and not network and not navegador'"`. Ou seja:

| Seleção                          | O que exercita                                   |
|----------------------------------|--------------------------------------------------|
| padrão                           | tudo que é barato, inclusive `ffmpeg`/`fluidsynth` reais |
| `-m "slow and not network"`      | modelo e ferramenta pesada local (MuScriptor, Demucs) — minutos em CPU |
| `-m network`                     | o canário do `yt-dlp` contra o YouTube (também é `slow`) |
| `-m navegador`                   | Chromium de verdade via CDP, página renderizada  |

`-m slow` sozinho **inclui** o teste de rede. Para exercitar só os modelos locais, use
`-m "slow and not network"`.

**Suíte verde não prova que o modelo, a rede ou o navegador rodaram.** Antes de afirmar
que algo funciona nessas camadas, rode a seleção correspondente e cite a saída.

### 4. O repositório é público; áudio nunca entra nele

`audio/`, `cache/`, `out/`, `*.gp5`, `*.musicxml` estão no `.gitignore` (ADR-005) —
inclusive a auralização, que carrega o mix original num dos canais. Os pesos do
MuScriptor são **CC BY-NC 4.0**: não são versionados, `models.lock.toml` guarda só a
identidade deles (repo, revisão, sha256), conferida por teste.

Não introduza **novo** caminho específico desta estação em arquivo versionado. Os que
já existem são exceção conhecida, não precedente: `SOUNDFONT =
Path("/usr/share/soundfonts/FluidR3_GM.sf2")` em `services/auralizacao.py` e em duas
fixtures. Configuração de agente que for local vai em `.claude/settings.local.json`
(ignorado).

### 5. Quando o docstring e o ADR discordam, o ADR prevalece

O comportamento do pipeline mudou algumas vezes por medição (ADR-010, 019, 021), e
docstring é o que fica para trás. Em 2026-09-23 três foram acertados — `rhythm.py`,
`gp5.py` e `ports.py`, todos descrevendo BPM obrigatório e separação opcional. Ao
tocar um módulo, confira o docstring contra o ADR da área e corrija junto.

## Arquitetura — ports e adapters

```
domain/     models.py (dataclasses frozen, slots) · ports.py (Protocol)
            sem I/O, sem torch, sem dependência de ML
adapters/   ingest · transcription · separation · export — cada um implementa um Protocol
services/   lógica própria: fretboard (Viterbi), rhythm, tempo, octave_check,
            evaluation, auralizacao, cache_notas, nomes, model_lock, pipeline
api/        FastAPI: jobs em memória, estado serializado, artefatos e página de estudo
cli.py      fachada fina sobre services
```

- Integração nova entra **atrás de um `Protocol` em `domain/ports.py`**, não como
  import direto no service.
- `services/pipeline.py` é a única função que conhece a ordem dos estágios. A ordem e
  as restrições embutidas nela são medidas, não preferência — o docstring do módulo
  cita o ADR de cada uma.
- O pipeline **descarta e relata** em vez de falhar (ADR-014): nota fora do braço não
  pode custar os minutos de processamento da música inteira.

## Portão de entrega

```bash
uv run pytest -n auto              # suíte padrão
uv run ruff check src/ tests/
uv run mypy src/                   # strict
```

Os três precisam passar. `uv` para tudo (`uv sync`, `uv add`, `uv run`) — nunca `pip`
nem `python` direto.

## Como trabalhar aqui

- **TDD.** Teste primeiro, implementação depois. Vale para código novo e para
  alteração de código existente.
- **Mock é exceção justificada.** Contrato de biblioteca binária (PyGuitarPro),
  formato de saída do MuScriptor, parsing de áudio: precisa de pelo menos um teste
  batendo no recurso real, ainda que marcado `slow`.
- **Decisão arquitetural → ADR** em `tasks/decisions.md` (já em ADR-021). Emenda de
  ADR existente é seção `### Emenda (data)`, não reescrita do original.
- **Correção do usuário durante a tarefa → `tasks/lessons/<domínio>.md`.** Existem
  `audio.md`, `exportadores.md`, `navegador.md` e `workflow.md`.
- **Plano e estado → `tasks/todo.md`.** Fases marcadas; o que está `[ ]` é o que falta.
- Leia `tasks/decisions.md` antes de mudar comportamento do pipeline: quase toda
  escolha não óbvia (separar sempre, transcrever o stem inteiro, filtrar por conjunto
  de rótulos) já foi medida e tem ADR.

## Duas armadilhas já pagas

**Port de fixture/baseline é cópia, nunca reescrita** (`tasks/lessons/workflow.md`). Uma
fixture reescrita de memória levantou o F1 de 0,682 para 0,882 — o erro se disfarçou de
melhoria. Imprima o valor medido ao lado do piso: portão que passa não diz nada sobre a
margem.

**`gp.Beat.status` nasce `empty` no PyGuitarPro** (`tasks/lessons/exportadores.md`). O
arquivo grava sem erro e a `Song` em memória parece perfeita, mas a leitura funde o
compasso num beat só. Todo beat com nota precisa de `BeatStatus.normal`; pausa, de
`rest`. Teste de round-trip de formato rítmico afirma **estrutura** (quantos beats, qual
o `start`), não o conjunto achatado de notas.
