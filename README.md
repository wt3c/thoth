# thoth

Thoth — deus egípcio da escrita, sabedoria e dos escribas.

Gera **partitura e tablatura a partir de áudio**, com foco em contrabaixo elétrico. Uso pessoal. Tudo open source,
rodando localmente em CPU.

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

O MuScriptor transcreve. O código deste repositório existe para o que ele não cobre: **GP5 editável**, **afinação
configurável** (4/5/6 cordas, Drop D), separação antes de transcrever (ADR-010), andamento e grade rítmica
(ADR-019/021), sanity-check de oitava e a orquestração com cache.

## Instalação

Há duas formas de instalar:

- **nativa em Linux** — indicada para usar a CLI, desenvolver e aproveitar diretamente os caches da máquina;
- **com Docker Compose** — indicada quando se quer isolar as dependências do sistema e usar a interface web.

O caminho nativo foi validado em Arch/Omarchy. Em Windows, macOS ou uma distribuição sem os pacotes abaixo, prefira o
contêiner. O Thoth é CPU-only: CUDA e ROCm não fazem parte da instalação.

### Windows

No Windows, o caminho recomendado é o **WSL2 com Ubuntu**. Instale o WSL2, abra o terminal do Ubuntu, clone o
repositório dentro do sistema de arquivos Linux — por exemplo, em `~/thoth`, não em `/mnt/c/` — e siga a seção
[Instalação nativa em Linux](#instalação-nativa-em-linux), usando os comandos para Debian/Ubuntu. Dessa forma, os
caminhos, executáveis e caches usados pelo pipeline permanecem iguais aos do ambiente Linux validado.

O **Docker Desktop com backend WSL2** é uma alternativa para executar a interface web: faça o clone e a autenticação
do Hugging Face dentro do WSL2 e siga [Instalação com Docker Compose](#instalação-com-docker-compose). Assim, o cache
autenticado do Hugging Face pode ser montado pelo contêiner sem depender de conversão de caminhos do Windows.

A instalação diretamente no Windows, por PowerShell ou Prompt de Comando, **não é suportada atualmente**. Embora parte
das dependências Python possa funcionar, esse caminho não foi validado e a auralização procura a soundfont no caminho
Linux fixo `/usr/share/soundfonts/FluidR3_GM.sf2`. Também seria necessário instalar e manter `ffmpeg`, `ffprobe`,
`fluidsynth`, `yt-dlp`, Node.js e npm no `PATH`. Portanto, use WSL2 ou Docker Desktop até existir suporte nativo
testado.

### O que será instalado

| Componente                      |                   Obrigatório | Finalidade                                                               |
|---------------------------------|------------------------------:|--------------------------------------------------------------------------|
| Git                             |                           sim | obter o repositório                                                      |
| `uv`                            |                           sim | instalar o Python 3.12, as dependências e executar o projeto             |
| `ffmpeg` e `ffprobe`            |                           sim | normalizar áudio e montar os arquivos de saída                           |
| `yt-dlp`                        |               só para YouTube | baixar a faixa de áudio de uma URL                                       |
| `fluidsynth` + `FluidR3_GM.sf2` |                   recomendado | gerar a auralização; sem eles, GP5 e MusicXML continuam sendo exportados |
| Node.js + npm                   |         só para `thoth serve` | baixar o alphaTab uma vez; Node não participa da execução da aplicação   |
| Docker + Compose                | só na instalação em contêiner | construir e executar a imagem local                                      |

Demucs e MuScriptor **não** são instalados globalmente. O pipeline chama versões fixadas por `uvx` e guarda os
ambientes no cache do `uv`. A primeira transcrição também baixa os pesos dos modelos; reserve alguns gigabytes em disco
e espere uma execução mais longa.

### Instalação nativa em Linux

#### 1. Instale as dependências do sistema

Em Arch Linux, Garuda ou Omarchy:

```bash
sudo pacman -S --needed git ffmpeg fluidsynth soundfont-fluid nodejs npm
```

Em Debian ou Ubuntu, a combinação equivalente — também usada pela imagem do projeto — é:

```bash
sudo apt update
sudo apt install git ffmpeg fluidsynth fluid-soundfont-gm nodejs npm
```

O código procura a soundfont exatamente em `/usr/share/soundfonts/FluidR3_GM.sf2`. Se a distribuição a instalar em
`/usr/share/sounds/sf2/FluidR3_GM.sf2`, crie o diretório e o link uma única vez:

```bash
sudo install -d /usr/share/soundfonts
sudo ln -s /usr/share/sounds/sf2/FluidR3_GM.sf2 /usr/share/soundfonts/FluidR3_GM.sf2
```

Em outra distribuição, instale pacotes que forneçam os mesmos executáveis e confira o caminho da soundfont. O
`fluidsynth` é opcional para a transcrição, mas obrigatório para gerar o `.aural.wav` e para os testes de auralização
não serem pulados.

#### 2. Instale o `uv` e o `yt-dlp`

Instale o `uv` pelo [instalador oficial](https://docs.astral.sh/uv/getting-started/installation/):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Abra um novo terminal, ou carregue novamente o arquivo de configuração do shell, e verifique:

```bash
uv --version
uvx --version
```

Para aceitar arquivos do YouTube, instale o `yt-dlp` como ferramenta isolada. Ele fica fora do `uv.lock` porque precisa
acompanhar mudanças frequentes do YouTube:

```bash
uv tool install yt-dlp
yt-dlp --version
```

Quem usará apenas arquivos locais pode pular esse comando.

#### 3. Clone e sincronize o projeto

```bash
git clone https://github.com/wt3c/thoth.git
cd thoth
uv sync --frozen
```

Não é necessário instalar Python à parte nem ativar a `.venv`. O arquivo `.python-version` pede 3.12 e o `uv` baixa um
interpretador compatível sem tocar no Python do sistema. `--frozen` garante que a instalação respeite exatamente o
`uv.lock`; os comandos seguintes usam `uv run` para entrar no ambiente automaticamente.

#### 4. Autorize os pesos do MuScriptor

Os pesos não pertencem a este repositório. Eles usam licença **CC BY-NC 4.0**, exigem conta no Hugging Face e só podem
ser usados sobre áudio para o qual você tenha os direitos necessários.

1. Abra [`MuScriptor/muscriptor-small`](https://huggingface.co/MuScriptor/muscriptor-small), leia as condições e aceite
   o acesso ao modelo. O `small` é o modelo usado pelo pipeline.
2. Autentique esta máquina com a [CLI oficial do Hugging Face](https://huggingface.co/docs/huggingface_hub/guides/cli):

   ```bash
   uvx hf auth login
   uvx hf auth whoami
   ```

O token fica no cache do Hugging Face, fora do repositório; não crie `.env` nem copie o token para arquivos do projeto.
O download dos pesos ocorre automaticamente na primeira transcrição.

#### 5. Instale os arquivos locais da interface web

Este passo é necessário apenas para `thoth serve`. O script baixa o alphaTab 1.8.4 pelo npm, confere o SHA-256 e
extrai somente os arquivos usados pela página:

```bash
uv run python scripts/vendor_alphatab.py
test -f web/vendor/alphatab/alphaTab.min.mjs
```

Depois disso, a página funciona sem CDN. Se você pretende usar somente `fetch`, `transcribe`, `auralizar` e `comparar`,
pode omitir Node.js, npm e esta etapa.

#### 6. Valide a instalação

```bash
command -v ffmpeg ffprobe
command -v fluidsynth
test -f /usr/share/soundfonts/FluidR3_GM.sf2
uv run thoth --help
```

Os três primeiros comandos não devem apresentar erro. Para validar o ambiente de desenvolvimento, execute também:

```bash
uv run pytest -n auto
uv run ruff check src/ tests/
uv run mypy src/
```

Essa suíte não baixa nem executa os modelos pesados, não acessa o YouTube e não abre o navegador. As seleções que fazem
isso estão na seção [Desenvolvimento](#desenvolvimento).

### Instalação com Docker Compose

Na máquina hospedeira, instale Git, Docker Engine e o plugin `docker compose`. Clone o repositório e autorize o modelo
no Hugging Face como descrito no passo 4; o contêiner monta o cache autenticado da máquina, pois os pesos não entram na
imagem:

```bash
git clone https://github.com/wt3c/thoth.git
cd thoth
mkdir -p out cache
docker compose up --build
```

Criar `out/` e `cache/` **antes** do primeiro `up` evita que o Docker os crie pertencendo a `root`. Quando o log indicar
que o servidor iniciou, abra <http://127.0.0.1:8000>. Para encerrar, pressione `Ctrl+C`; uma execução futura pode usar
apenas `docker compose up` enquanto `Containerfile`, `pyproject.toml` e `uv.lock` não mudarem.

A imagem já contém `ffmpeg`, `fluidsynth`, a soundfont, o `yt-dlp` e o alphaTab. No primeiro job, Demucs, MuScriptor,
PyTorch e seus pesos ainda são baixados para volumes persistentes. Se o cache do Hugging Face estiver em outro local,
informe-o ao Compose:

```bash
HF_HOME=/caminho/para/huggingface docker compose up --build
```

### Problemas comuns na instalação

- **Erro 401/403 ou “gated repository”** — aceite as condições na página do `muscriptor-small`, repita
  `uvx hf auth login` e confirme com `uvx hf auth whoami`.
- **`soundfont ausente`** — confira o arquivo em `/usr/share/soundfonts/FluidR3_GM.sf2`. A transcrição termina, mas não
  produz a auralização até o caminho ser corrigido.
- **`yt-dlp` deixou de baixar** — atualize a ferramenta com `uv tool upgrade yt-dlp`; o YouTube muda o contrato com
  frequência.
- **A raiz do `serve` responde 503** — execute novamente `uv run python scripts/vendor_alphatab.py`; isso indica que os
  arquivos locais do alphaTab não estão presentes.
- **Python incompatível** — não force 3.13 ou superior. Remova apenas a `.venv` local se ela veio de outra instalação e
  repita `uv sync --frozen`; o teto em Python 3.12 é deliberado.
- **Primeiro `transcribe` parece parado** — acompanhe as etapas mostradas pela CLI. A primeira execução prepara dois
  ambientes pesados e baixa modelos; as seguintes reutilizam os caches.

## Uso

Todos os comandos devem ser executados na raiz do repositório com `uv run thoth`. Use `--help` na raiz ou depois de um
subcomando para consultar a interface instalada:

```bash
uv run thoth --help
uv run thoth transcribe --help
```

Nos comandos que recebem `ref`, a referência pode ser um arquivo local ou uma URL do YouTube. O Thoth escolhe a fonte
automaticamente. Arquivos intermediários ficam em `cache/`; os arquivos que você abre, escuta ou move ficam em `out/`.
Use `--cache outro/diretorio` ou `--out outro/diretorio` quando precisar mudar esses locais.

### `fetch` — obter e normalizar o áudio

```bash
# Arquivo local: aceita qualquer formato que o ffmpeg consiga ler.
uv run thoth fetch caminho/para/musica.mp3

# YouTube: exige yt-dlp instalado e acesso à rede.
uv run thoth fetch "https://www.youtube.com/watch?v=QTOyeFQgZKk"
```

O `fetch` executa somente a ingestão. Ele:

1. identifica a fonte como arquivo local ou YouTube;
2. converte o áudio para WAV estéreo, 44,1 kHz;
3. grava o resultado em `cache/<source_id>/mix.wav`;
4. imprime o identificador da fonte, a duração e o caminho do WAV.

Ele **não** separa instrumentos, não transcreve notas e não produz partitura. É útil para validar a entrada, antecipar o
download do YouTube ou aquecer o cache. O `transcribe` chama essa mesma etapa automaticamente, portanto não é
obrigatório executar `fetch` antes. Se o WAV normalizado já estiver íntegro no cache, ele é reutilizado sem novo
download ou conversão.

Opção própria:

- `--cache PATH`: troca o diretório de cache; o padrão é `cache`.

### `transcribe` — executar o pipeline completo

```bash
# Baixo de quatro cordas, digitação para iniciante e andamento estimado.
uv run thoth transcribe caminho/para/musica.mp3

# Baixo de cinco cordas, BPM e tom informados explicitamente.
uv run thoth transcribe caminho/para/musica.mp3 \
  --afinacao 5 \
  --digitacao experiente \
  --bpm 96 \
  --tom "Bb maior"

# Guitarra limpa; a afinação vem do perfil do instrumento.
uv run thoth transcribe caminho/para/musica.mp3 --instrumento guitarra-limpa

# Bateria em faixa de percussão, sem tablatura de cordas.
uv run thoth transcribe caminho/para/musica.mp3 --instrumento bateria
```

Este é o comando principal. Ele executa, em ordem:

1. ingestão e normalização do áudio;
2. estimativa do andamento, quando `--bpm` não é informado;
3. separação do stem apropriado pelo Demucs;
4. transcrição do stem inteiro pelo MuScriptor;
5. filtragem dos rótulos e ajuste das notas à grade rítmica;
6. atribuição de corda e traste, ou agrupamento de acordes/ataques conforme o instrumento;
7. exportação para GP5 e MusicXML;
8. cópia do mix, do stem e do playback sem o instrumento para a pasta de saída;
9. criação da auralização, com o áudio original em um canal e a transcrição no outro.

A CLI mostra a etapa atual e o tempo gasto. Em CPU, uma música pode levar cerca de 2,5 vezes sua duração, e a primeira
execução é mais lenta porque prepara os ambientes e baixa os modelos. Falha de `fluidsynth` ou da soundfont impede
somente a auralização: os demais artefatos continuam válidos e a causa é exibida no relatório.

Principais opções:

| Opção | Padrão | Efeito |
|---|---|---|
| `--instrumento` | `baixo` | Escolhe `baixo`, `bateria`, `guitarra-acustica`, `guitarra-limpa` ou `guitarra-distorcida`. |
| `--afinacao` | `4` | Afinação do baixo: `4`, `5`, `6` ou `drop-d`; é recusada para outros instrumentos. |
| `--digitacao` | `iniciante` | Define o custo de posicionamento no braço: `iniciante` ou `experiente`. |
| `--bpm` | estimado | Fixa o andamento entre 20 e 300 BPM; informado, ele prevalece sobre a estimativa. |
| `--tom` | estimado | Fixa tom e modo, como `Bb maior` ou `f menor`; vazio, o tom é estimado das notas. |
| `--out` | `out` | Diretório raiz dos artefatos finais. |
| `--cache` | `cache` | Diretório dos áudios, stems e notas reutilizáveis. |

Sem `--bpm`, o andamento estimado é exibido com sua confiança. Confira a auralização; se o ritmo estiver errado,
repita o comando com `--bpm`. Sem `--tom`, a CLI também informa o tom estimado e evita escrever uma armadura quando a
margem é pequena.

Cada música recebe uma pasta `out/<título>/`. Os arquivos específicos dependem do instrumento:

| Instrumento | Partitura | Áudios específicos |
|---|---|---|
| baixo | `<título>.gp5`, `<título>.musicxml` | `.baixo.wav`, `.sem-baixo.wav`, `.aural.wav` |
| guitarra | `<título>.<perfil>.gp5`, `<título>.<perfil>.musicxml` | `.outros.wav`, `.sem-outros.wav`, `.<perfil>.aural.wav` |
| bateria | `<título>.bateria.gp5`, `<título>.bateria.musicxml` | `.bateria.wav`, `.sem-bateria.wav`, `.bateria.aural.wav` |

Todas as variantes também copiam `<título>.mix.wav`. No baixo, o relatório aponta simultaneidades descartadas, notas
fora do braço, trechos readmitidos e oitavas suspeitas. Na guitarra, separa erro de rótulo, contaminação do stem e
acordes que não cabem no braço. Na bateria, informa ataques repetidos no mesmo tique, peças fora do kit GM de 35 a 59
e grupos com mais de seis peças.

### `auralizar` — refazer a comparação auditiva

```bash
uv run thoth auralizar caminho/para/musica.mp3

# Usar diretórios diferentes dos padrões.
uv run thoth auralizar caminho/para/musica.mp3 --cache cache --out out
```

O `auralizar` recria apenas `<título>.aural.wav`, sem repetir Demucs, MuScriptor ou a exportação das partituras. O WAV
é estéreo: o áudio original fica à esquerda e as notas sintetizadas à direita. Diferenças de ataque ou duração entre os
canais ajudam a perceber quando a transcrição se descola do áudio.

O comando exige a transcrição **de baixo** já gravada em `cache/<source_id>/notas.jsonl`; por isso, execute
`transcribe` sem outro `--instrumento` pelo menos uma vez. Ele também exige `fluidsynth` e
`/usr/share/soundfonts/FluidR3_GM.sf2`. `--out` muda a raiz da pasta da música e `--cache` precisa apontar para o mesmo
cache usado na transcrição.

### `comparar` — avaliar contra uma tablatura humana

```bash
uv run thoth comparar tab.gp5 caminho/para/musica.mp3

# Escolher a segunda faixa quando o GP5 tiver mais de uma candidata.
uv run thoth comparar tab.gp5 caminho/para/musica.mp3 --faixa 2
```

O primeiro argumento é uma tablatura `.gp5` humana, baixada manualmente; o segundo é exatamente a referência de áudio
já usada no `transcribe`. O comando não baixa tablaturas e não aceita referência gerada por IA como validação confiável.

Ele lê `cache/<source_id>/notas.jsonl`, alinha a tab à transcrição e relata:

- faixa escolhida e quantidade de notas em cada lado;
- escala e deslocamento temporal encontrados pelo alinhamento;
- pares com o mesmo nome de nota;
- mesma oitava, oitava acima e oitava abaixo;
- piso de acaso obtido ao deslocar a referência.

Se o stem do baixo ainda estiver no cache, a tab também é alinhada ao áudio e a taxa de nota certa, erro de oitava e
nota errada é calculada em janelas de 60 segundos. Janelas próximas do piso são marcadas como inconclusivas, em vez de
serem contadas como erro. `--faixa N` usa numeração iniciada em 1; omita a opção quando o GP5 tiver uma única faixa de
baixo identificável.

### `serve` — abrir a API e a página de estudo

```bash
uv run thoth serve

# Exemplo com porta e diretórios personalizados.
uv run thoth serve --port 8080 --out out --cache cache
```

O `serve` inicia uma API FastAPI e a página de estudo com o alphaTab local. Por padrão, escuta somente em
<http://127.0.0.1:8000>, sem expor a aplicação na rede. A página permite informar o caminho de um arquivo local ou uma
URL do YouTube, escolher o instrumento, iniciar a transcrição, acompanhar o estado do job, abrir a partitura e controlar
a velocidade de estudo.

Os jobs ficam apenas na memória e são executados um por vez, pois compartilham caches e caminhos de saída. Encerrar o
servidor apaga o histórico de jobs, mas não remove os artefatos de `out/` nem o conteúdo de `cache/`. A página exige que
o alphaTab tenha sido instalado com `uv run python scripts/vendor_alphatab.py`; sem ele, a raiz responde 503 e mostra
esse comando.

Opções:

- `--host HOST`: endereço de escuta; o padrão seguro é `127.0.0.1`;
- `--port PORT`: porta HTTP, padrão `8000`;
- `--out PATH`: diretório dos artefatos gerados pelos jobs;
- `--cache PATH`: cache compartilhado pelos jobs.

## Desenvolvimento

```bash
uv run pytest -n auto          # suíte padrão
uv run pytest -m "slow and not network"   # modelos de verdade — minutos em CPU
uv run pytest -m network       # canário: avisa quando o YouTube quebrar o yt-dlp
uv run pytest -m navegador     # abre um Chromium e inspeciona a página renderizada
uv run ruff check src/ tests/
uv run mypy src/
```

Os marcadores `slow`, `network` e `navegador` ficam fora da suíte padrão. O canário do yt-dlp tem os dois primeiros,
então `-m slow` sozinho também toca a rede.

## Documentos

- `AGENTS.md` — contrato para agentes (o `CLAUDE.md` importa este)
- `tasks/todo.md` — plano de execução por fases
- `tasks/decisions.md` — ADRs (sem DRM · CPU-only · MuScriptor · Python 3.12)
- `tasks/lessons/` — armadilhas já pagas, por domínio

## Licenças

Código deste repositório: **MIT** (`LICENSE`). Pesos do MuScriptor: **CC BY-NC 4.0** — uso não comercial. O
`Protocol Transcriber` mantém a troca de modelo barata.
