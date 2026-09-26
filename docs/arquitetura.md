# Arquitetura do Thoth

Este documento explica como o Thoth foi projetado, como seus componentes se conectam e por que as principais decisões foram tomadas. Ele foi escrito para servir a dois públicos ao mesmo tempo:

- quem está começando no projeto e precisa formar um modelo mental antes de ler o código;
- quem avalia arquitetura de software e de solução e precisa verificar responsabilidades, limites, qualidade, riscos e evolução.

O documento descreve o código existente. Quando houver divergência, as fontes canônicas são `src/thoth/cli.py`, `src/thoth/services/pipeline.py` e os registros em `tasks/decisions.md`.

## 1. Resumo executivo

O Thoth é uma aplicação local que transforma áudio em partitura e tablatura. Seu foco inicial é o contrabaixo elétrico, com suporte também a bateria e a perfis de guitarra. O processamento é **CPU-only**, não depende de um serviço próprio na nuvem e mantém os dados do usuário na máquina.

A solução combina:

1. ingestão de arquivo local ou vídeo do YouTube;
2. normalização do áudio;
3. separação do instrumento com Demucs;
4. transcrição de notas com MuScriptor;
5. regras musicais próprias para tempo, ritmo, rótulos, braço e acordes;
6. exportação para GP5, MusicXML e áudios auxiliares;
7. acesso por linha de comando ou por uma interface web local.

A ideia arquitetural mais importante é: **modelos de aprendizado de máquina sugerem eventos; as regras de domínio transformam essas sugestões em uma partitura utilizável e explicam o que foi descartado**.

## 2. Diagramas interativos

Os diagramas são arquivos HTML autossuficientes. Eles permitem trocar tema, inspecionar os elementos e ativar visões focadas. A interface do visualizador usa alguns termos em inglês porque essa é a interface fornecida pela ferramenta de renderização; o conteúdo arquitetural está em português.

- [Arquitetura de componentes](diagramas/arquitetura-componentes.html): quem chama quem e quais são os limites da aplicação.
- [Fluxo do processamento](diagramas/fluxo-processamento.html): como os dados mudam do áudio de entrada até a entrega.
- [Sequência de execução](diagramas/sequencia-execucao.html): diferença entre uma execução pela CLI e um job iniciado pela página web.

Os JSONs na mesma pasta são as fontes editáveis e versionadas dos diagramas.

## 3. O problema que a arquitetura resolve

Reconhecer notas em uma gravação não é o mesmo que escrever música. O áudio mistura instrumentos, ruído, reverberação e pequenas imprecisões de tempo. Mesmo quando um modelo reconhece a altura correta, ainda faltam respostas para perguntas como:

- Em qual corda e em qual traste a nota deve ser tocada?
- Duas notas próximas representam um acorde ou um erro de tempo?
- A pulsação detectada está em 70 BPM ou em 140 BPM?
- Uma nota abaixo do alcance do instrumento deve interromper toda a música?
- Como representar duração, pausa, ligadura e tablatura em formatos diferentes?

Por isso, o Thoth separa três responsabilidades:

- **percepção**: ferramentas externas analisam o sinal de áudio;
- **decisão musical**: serviços do Thoth aplicam regras mensuráveis;
- **representação**: adapters escrevem formatos de arquivo e áudios de estudo.

Essa divisão evita colocar regras de música dentro da CLI, da API ou de uma biblioteca externa.

## 4. Contexto da solução

### 4.1 Atores e sistemas externos

| Elemento | Papel | Tipo de integração |
|---|---|---|
| Pessoa usuária | Escolhe fonte, instrumento, afinação, digitação, BPM e tom | CLI ou navegador local |
| Sistema de arquivos | Guarda cache, resultados, modelos já baixados e arquivos de entrada | Leitura e escrita local |
| `ffmpeg`/`ffprobe` | Normalizam áudio, medem duração e produzem mixagens | Subprocesso |
| `yt-dlp` | Obtém áudio e metadados do YouTube | Subprocesso com rede |
| Demucs | Separa a mix em stems | `uvx`, CPU |
| MuScriptor | Converte o stem em eventos de nota | `uvx`, CPU |
| FluidSynth + soundfont | Renderizam as notas para a auralização | Subprocesso local |
| Hugging Face | Fornece os pesos na primeira utilização | Download externo e aceite de licença |

**Stem** é uma faixa de áudio que tenta isolar uma família, como baixo, bateria ou “outros”. Ele não é garantia de isolamento perfeito.

### 4.2 O que está fora do escopo

- processamento em GPU;
- execução distribuída;
- banco de dados;
- autenticação e autorização;
- armazenamento remoto do áudio;
- fila durável de jobs;
- edição colaborativa;
- garantia de transcrição perfeita.

Essas ausências são coerentes com o cenário atual: uso pessoal, local e de uma música por vez.

## 5. Estilo arquitetural

O núcleo segue **ports and adapters**, também chamado de arquitetura hexagonal.

- Um **port** é um contrato que declara uma capacidade necessária sem escolher a tecnologia. Em Python, o projeto usa `Protocol`.
- Um **adapter** implementa esse contrato para uma ferramenta ou formato específico.
- O **domínio** contém os conceitos musicais compartilhados.
- Os **services** contêm decisões e algoritmos próprios.
- O **pipeline** compõe tudo na ordem correta.

Exemplo: o pipeline depende do port `Separator`, e não diretamente da implementação do Demucs. Em produção recebe `DemucsSeparator`; em um teste pode receber uma implementação pequena e determinística. Isso é **inversão de dependência**: a regra central conhece a abstração, não a ferramenta concreta.

### 5.1 Direção permitida das dependências

| Camada | Pode conhecer | Não deve conhecer |
|---|---|---|
| `domain/` | biblioteca padrão e tipos do domínio | disco, rede, FastAPI, Typer, torch ou modelos de ML |
| `services/` | domínio e ports | detalhes da interface web ou do terminal |
| `adapters/` | domínio, ports e bibliotecas externas | regras de apresentação da CLI/API |
| `api/` e `cli.py` | pipeline e modelos de resposta | algoritmos musicais duplicados |

Há uma composição pragmática em `pipeline.py`: ele importa os adapters padrão para montar a aplicação, mas aceita ports injetados. Assim, o fluxo principal continua testável sem esconder a configuração real.

## 6. Componentes e responsabilidades

### 6.1 `domain/models.py`

Define o vocabulário estável da aplicação com `dataclass` imutável e com `slots`.

| Modelo | Significado |
|---|---|
| `AudioAsset` | Identidade, título, duração e WAV normalizado de uma fonte |
| `NoteEvent` | Nota reconhecida: altura MIDI, início, fim e rótulo do instrumento |
| `TabNote` | Nota musical já posicionada em corda e traste |
| `EventoPercussivo` | Ataque de uma peça de bateria |
| `AcordeImpossivel` | Grupo de notas que não coube numa digitação válida |
| `Posicionamento` | Notas posicionadas e acordes que ficaram de fora |

Imutabilidade reduz mudanças acidentais entre etapas. `slots` reduz memória e impede a criação silenciosa de atributos com nomes errados.

### 6.2 `domain/ports.py`

Contém os contratos entre o pipeline e o mundo externo:

- `AudioSource`: fonte → `AudioAsset`;
- `Separator`: mix → stems;
- `Transcriber`: áudio → `NoteEvent`;
- `FretAssigner`: linha monofônica → tablatura;
- `AtribuidorDeAcordes`: notas polifônicas → posições de acorde;
- `Exporter`: tablatura → arquivo;
- ports próprios para bateria e piano;
- `Progresso`: anúncio do início de cada estágio.

Contratos separados para baixo, acordes, bateria e piano impedem combinações semanticamente inválidas. Por exemplo, bateria não tem corda, traste ou afinação.

### 6.3 `domain/instrumentos.py`

Um `PerfilInstrumento` agrupa:

- família musical;
- rótulos aceitos do MuScriptor;
- stem do Demucs;
- programa General MIDI;
- afinação, quando o instrumento tem braço.

Os perfis implementados incluem baixo, bateria, piano acústico/elétrico e três tipos de guitarra. O pipeline público aceita hoje baixo, bateria e guitarras. O exportador MusicXML de piano já existe, mas a integração completa do piano ao pipeline ainda não foi liberada.

### 6.4 `adapters/ingest/`

`resolver_fonte()` escolhe a implementação pela referência recebida:

- `LocalFileSource` calcula uma identidade a partir do conteúdo e usa `ffmpeg` para gerar WAV estéreo de 44,1 kHz;
- `YtDlpSource` extrai o ID do vídeo, baixa o áudio e conserva metadados suficientes para reutilizar o cache.

A identidade estável evita processar novamente o mesmo conteúdo só porque o caminho mudou.

### 6.5 `adapters/separation/demucs.py`

Executa Demucs 4.1.0 com o modelo `htdemucs_ft`, em CPU. O adapter:

- seleciona o stem requerido pelo perfil;
- pede também a faixa complementar “sem o stem”;
- encena a saída em diretório temporário;
- publica o cache somente depois da execução completa.

O Demucs sempre vem antes da transcrição porque medições mostraram que a mix completa gera mais contaminação.

### 6.6 `adapters/transcription/muscriptor.py`

Executa MuScriptor 0.3.0 em um ambiente Python 3.12 isolado pelo `uvx`. O adapter converte JSONL em `NoteEvent` e usa decodificação livre: deixa o modelo reconhecer rótulos e filtra depois.

Isso é importante porque forçar um instrumento cedo demais esconde erros de classificação. Em trechos energeticamente ativos sem notas, pode ocorrer uma segunda passagem controlada para recuperar buracos da transcrição.

### 6.7 `services/`

Esta pasta contém a inteligência própria da solução.

| Serviço | Responsabilidade |
|---|---|
| `tempo.py` | estima BPM, mede confiança, ajusta fase e corrige dobra de andamento |
| `rhythm.py` | alinha eventos à grade, cria ticks, pausas, durações e acordes |
| `fretboard.py` | escolhe corda/traste com Viterbi para uma linha monofônica |
| `acordes.py` | escolhe uma digitação conjunta para acordes de guitarra |
| `rotulos.py` | classifica contaminação e recupera trechos de baixo mal rotulados |
| `octave_check.py` | procura evidência espectral para possíveis erros de oitava |
| `tonalidade.py` | estima ou interpreta o tom e sua armadura |
| `auralizacao.py` | sintetiza notas e combina original/síntese em canais separados |
| `cache_notas.py` | persiste eventos tratados em JSONL |
| `comparacao.py` | compara transcrição com tablatura humana e produz vereditos |
| `alinhamento_audio.py` | alinha referência e stem por DTW cromático |
| `evaluation.py` | calcula métricas objetivas para baixo, polifonia e bateria |
| `model_lock.py` | verifica revisão e SHA-256 dos pesos esperados |
| `nomes.py` | produz nomes de arquivo seguros e estáveis |

**Viterbi** é um algoritmo que encontra a sequência global de menor custo. Em vez de escolher o melhor traste para cada nota isoladamente, ele considera também a transição da mão entre notas. O perfil “iniciante” penaliza mais saltos e regiões difíceis; o “experiente” aceita movimentos mais amplos.

**DTW**, ou Dynamic Time Warping, alinha sequências que evoluem em velocidades ligeiramente diferentes. Aqui ele permite comparar uma tablatura humana com o áudio sem exigir que os dois relógios coincidam perfeitamente.

### 6.8 `adapters/export/`

- `Gp5Exporter` produz arquivos Guitar Pro 5 com ritmo, pausas, ligaduras e tablatura.
- `MusicXmlExporter` produz partitura convencional e uma pauta de tablatura no mesmo MusicXML.
- exportadores próprios representam bateria em faixa de percussão.
- `MusicXmlPianoExporter` representa vozes polifônicas de piano, ainda fora do pipeline público.

Os adapters tratam detalhes específicos de cada formato. Por exemplo, GP5 exige que cada beat com nota tenha estado `normal`; MusicXML precisa de ajustes explícitos para afinação, digitação e beams.

### 6.9 `cli.py`

É uma fachada fina implementada com Typer. Ela:

- valida opções amigáveis;
- apresenta progresso com Rich;
- chama services ou o pipeline;
- formata resultados e diagnósticos.

A CLI não implementa regras musicais. Isso permite reutilizar o mesmo comportamento na API.

### 6.10 `api/app.py` e `web/`

A API FastAPI envolve o pipeline em jobs locais. A página estática usa alphaTab vendorizado para mostrar e reproduzir a partitura sem depender de CDN.

Estados de um job:

| Estado | Significado |
|---|---|
| `na fila` | pedido aceito e aguardando a trava |
| `rodando` | pipeline em execução |
| `pronto` | resultado e artefatos disponíveis |
| `erro` | exceção capturada e registrada no próprio job |

Uma `threading.Lock` garante somente um pipeline por processo. O histórico fica em memória, limitado a 50 jobs concluídos. Reiniciar o servidor apaga o histórico, mas não apaga cache nem artefatos.

Endpoints:

| Método e caminho | Função |
|---|---|
| `POST /jobs` | valida o pedido, cria o job e responde `202` |
| `GET /jobs` | lista o histórico em memória |
| `GET /jobs/{id}` | informa estado, diagnósticos e formatos disponíveis |
| `GET /jobs/{id}/artifacts/{formato}` | entrega um artefato pronto |
| `GET /` | serve a interface web ou explica como instalar o alphaTab |

## 7. Pipeline em detalhes

`services/pipeline.py` é o único lugar que conhece a ordem completa. Essa centralização evita fluxos ligeiramente diferentes entre CLI, API e testes.

### 7.1 Validação antecipada

Antes de gastar minutos de CPU, o pipeline recusa:

- BPM fora da faixa aceita;
- tom ilegível;
- instrumento ainda não integrado à produção de partitura.

Falhar cedo aqui reduz custo e torna o erro atribuível à entrada.

### 7.2 Obtenção e normalização

A fonte produz um `AudioAsset`. O conteúdo normalizado vai para `cache/`, separado da pasta final. Arquivo local e YouTube convergem para o mesmo contrato a partir deste ponto.

### 7.3 Andamento

Quando o usuário não informa BPM, `librosa` estima o andamento usando a mix, pois a bateria fornece pulsação mais clara. Depois, os inícios das notas refinam BPM e fase da grade. O resultado registra se o valor foi estimado e se é confiável.

### 7.4 Separação

O Demucs recebe a mix e produz o stem do perfil:

- `bass` para baixo;
- `drums` para bateria;
- `other` para guitarra.

O stem `other` não significa “guitarra”: ele pode conter piano e outros instrumentos. Por isso os rótulos do transcritor continuam necessários.

### 7.5 Transcrição

O MuScriptor processa o stem inteiro. Não há divisão arbitrária em trechos, pois o contexto ajuda o modelo a decidir o instrumento. Cada evento carrega altura MIDI, início, duração e rótulo.

### 7.6 Caminho do baixo

1. filtra os rótulos de baixo conhecidos;
2. identifica trechos ativos em que o baixo pode ter sido rotulado como outro instrumento;
3. readmite candidatos de forma explícita e relatável;
4. verifica possíveis erros de oitava;
5. remove sobreposições incompatíveis com a linha monofônica;
6. ajusta ritmo e fase;
7. descarta notas que não cabem no braço;
8. executa Viterbi para escolher corda e traste.

### 7.7 Caminho da guitarra

1. aceita apenas o rótulo do perfil selecionado;
2. separa erro de rótulo dentro da família de contaminação por outra família;
3. une notas que caem no mesmo tique;
4. mede andamento pelo primeiro ataque de cada acorde;
5. usa `ViterbiAcordes` para posicionar todas as notas juntas;
6. relata acordes impossíveis sem cancelar a música inteira.

Não usa monofonização nem recuperação de baixo, pois ambas pressupõem uma nota por vez.

### 7.8 Caminho da bateria

1. seleciona ataques rotulados como bateria;
2. agrupa ataques simultâneos na grade;
3. mapeia peças para a pauta de percussão;
4. relata peça desconhecida, repetição impossível no mesmo tique ou excesso de peças;
5. exporta sem tom, cordas ou trastes.

Um silêncio inicial de 100 ms é aplicado somente à bateria porque a medição mostrou melhora importante para esse perfil e mudança indesejada nos demais.

### 7.9 Exportação e entrega

Depois do caminho específico do instrumento, o trecho comum:

- estima tonalidade quando aplicável;
- escreve GP5 e MusicXML;
- copia mix, stem e faixa complementar para a pasta da música;
- tenta produzir a auralização;
- devolve um `Resultado` com artefatos, contagens, descartes e avisos.

A auralização é um auxílio de auditoria: um canal toca o original e o outro, as notas sintetizadas. A falha de FluidSynth ou do soundfont é registrada, mas não invalida uma partitura já produzida.

## 8. Dados, cache e consistência

### 8.1 Separação entre `cache/` e `out/`

| Diretório | Finalidade | Pode ser apagado? |
|---|---|---|
| `cache/` | resultados intermediários identificados pela fonte | sim; o custo é reprocessar |
| `out/` | pasta portável por música, com entregáveis nomeados pelo título | sim, se os resultados não forem mais necessários |

O repositório ignora áudio, cache, resultados e pesos. Isso reduz risco de publicar material protegido ou arquivos pessoais.

### 8.2 Escrita atômica

Arquivos críticos são gravados ao lado do destino com sufixo `.parcial` e publicados com `os.replace`. Diretórios de stems são montados em área temporária e promovidos apenas no fim.

“Atômico” significa que outros leitores veem o estado antigo ou o novo, nunca metade de um arquivo. Isso protege contra processo interrompido e cache parcialmente escrito.

### 8.3 Reprodutibilidade dos modelos

`models.lock.toml` registra repositório, revisão e SHA-256 esperados. Os pesos não entram na imagem nem no Git por tamanho e licença. O primeiro uso os baixa; os serviços de lock verificam sua identidade.

## 9. Tratamento de erros e observabilidade

O projeto distingue três classes de problema:

1. **entrada inválida**: erro imediato antes de processamento caro;
2. **falha técnica**: subprocesso falha e a mensagem conserva o final do `stderr`;
3. **incerteza musical**: dado suspeito é descartado ou marcado, sem perder o restante.

O terceiro caso é deliberado. Uma única nota impossível não deve desperdiçar uma transcrição longa. Para impedir falhas silenciosas, `Resultado` carrega:

- distribuição bruta de rótulos;
- notas descartadas e fora do braço;
- trechos sem baixo;
- suspeitas de oitava;
- contaminação e erros de rótulo;
- acordes impossíveis;
- ataques de bateria descartados por motivo;
- confiança do andamento;
- falha isolada da auralização.

Hoje não há logs estruturados, métricas operacionais persistentes ou tracing. Para execução pessoal isso é aceitável; para uma futura operação multiusuário, seria uma lacuna arquitetural.

## 10. Qualidades arquiteturais

### 10.1 Manutenibilidade

- regras agrupadas por conceito musical;
- integração externa atrás de ports;
- pipeline único para todas as entradas;
- decisões não óbvias registradas em ADRs;
- tipos estritos com mypy.

### 10.2 Testabilidade

Os ports permitem substituir fontes, separadores, transcritores e exportadores. Ao mesmo tempo, integrações críticas possuem testes reais marcados para que mocks não escondam contratos incorretos.

### 10.3 Desempenho

Os modelos são os principais consumidores de tempo. As decisões de desempenho são:

- CPU-only para compatibilidade da máquina-alvo;
- modelo MuScriptor `small` por equilíbrio medido;
- cache de fonte, stems e notas;
- um job por vez para evitar competição e corrupção;
- subprocessos isolados por `uvx` para conciliar dependências.

### 10.4 Portabilidade

- código Python gerenciado por `uv`;
- suporte documentado para Linux e Windows;
- Containerfile para ambiente controlado;
- formatos de saída portáveis;
- restrição intencional a Python 3.12 por compatibilidade do MuScriptor.

### 10.5 Privacidade e segurança

- processamento e armazenamento locais;
- nenhum segredo da aplicação;
- nenhum upload para serviço próprio;
- rede limitada a YouTube e obtenção inicial de pesos;
- nomes de saída sanitizados;
- interface web destinada a `localhost`.

A API não possui autenticação. Ela não deve ser exposta em uma interface pública sem adicionar controle de acesso, limites de upload, isolamento de processos e validação operacional.

### 10.6 Confiabilidade

- caches publicados atomicamente;
- arquivos intermediários incompletos não são tratados como sucesso;
- falhas de etapas opcionais não destroem resultados válidos;
- histórico limitado impede crescimento indefinido da memória;
- jobs simultâneos são serializados.

## 11. Estratégia de testes

### 11.1 Pirâmide prática

| Nível | O que comprova | Exemplos |
|---|---|---|
| Unidade | algoritmo e regra isolada | ritmo, tonalidade, nomes, Viterbi |
| Integração local | contrato com binário ou formato real | ffmpeg, FluidSynth, round-trip GP5/MusicXML |
| Pesado | modelo real em CPU | Demucs e MuScriptor |
| Rede | contrato externo atual | canário do YouTube com `yt-dlp` |
| Navegador | página realmente renderizada | Chromium via CDP |

A suíte padrão exclui `slow`, `network` e `navegador`. Portanto, uma suíte padrão verde não prova modelos, rede ou navegador. Cada afirmação sobre essas camadas precisa da seleção correspondente.

Comandos de qualidade:

```bash
uv run pytest -n auto
uv run ruff check src/ tests/
uv run mypy src/

# Modelos e ferramentas pesadas, sem rede
uv run pytest -m "slow and not network"

# Contrato real do YouTube
uv run pytest -m network

# Interface em Chromium real
uv run pytest -m navegador
```

## 12. Implantação e operação

### 12.1 Execução nativa

É o modo principal. O `uv` instala a aplicação e resolve as bibliotecas Python; ferramentas de áudio ficam no sistema. A instalação completa para Linux e Windows está no [README](../README.md#instalação).

### 12.2 Contêiner

O `Containerfile` cria uma execução somente em CPU e não incorpora pesos. Volumes preservam `cache/` e `out/`. Isso melhora reprodutibilidade, mas não transforma o sistema numa plataforma multiusuário.

### 12.3 Operação web

`thoth serve` inicia Uvicorn e a aplicação FastAPI. A arquitetura supõe uma única instância:

- jobs estão na memória do processo;
- a trava não coordena processos diferentes;
- os diretórios são locais;
- não existe fila durável.

Usar múltiplos workers violaria essas suposições. Para o cenário atual, execute um processo e exponha apenas em `localhost`.

## 13. Decisões arquiteturais centrais

Os detalhes e medições completas estão em `tasks/decisions.md`. Abaixo está o mapa de decisões que mais definem a solução.

| Tema | Decisão | Consequência |
|---|---|---|
| Hardware | CPU-only | execução mais lenta, porém compatível e previsível |
| Runtime | Python 3.12 | atende simultaneamente projeto e MuScriptor |
| Transcrição | MuScriptor `small`, decodificação livre | melhor equilíbrio medido e erros de rótulo visíveis |
| Separação | Demucs sempre antes de transcrever | mais custo, menos contaminação |
| Orquestração | um pipeline central | CLI e API permanecem consistentes |
| Erro musical | descartar e relatar | resultado parcial útil sem silêncio operacional |
| Posicionamento | Viterbi com perfis de custo | decisão considera sequência e nível do músico |
| Interface | alphaTab local | estudo não depende de CDN |
| Jobs | memória, teto 50, um por vez | simplicidade adequada ao uso pessoal |
| Cache | somente resultado completo e escrita atômica | interrupções não parecem sucesso |
| Saída | pasta por música | resultado fácil de mover e estudar |
| Modelos | pesos fora da imagem e travados por hash | imagem menor e identidade verificável |
| Expansão | perfil e caminho por família | baixo não herda polifonia; bateria não herda braço |

## 14. Riscos e limites conhecidos

| Risco ou limite | Impacto | Controle atual | Evolução provável |
|---|---|---|---|
| Modelos podem errar altura e rótulo | partitura incorreta | diagnósticos, comparação e descarte explícito | melhorar dados e critérios medidos |
| CPU pode levar minutos por música | espera longa | progresso, cache e job em background | fila/processo dedicado se virar multiusuário |
| Jobs não sobrevivem a reinício | histórico web perdido | artefatos permanecem no disco | persistência durável somente se necessária |
| Stem `other` mistura famílias | contaminação na guitarra | filtragem e relatório por família | separador ou classificador especializado |
| Piano está parcialmente implementado | perfil/exportador sem fluxo público | rejeição antes do custo pesado | concluir ramo próprio e testes reais |
| API sem autenticação | exposição indevida se publicada | uso em localhost | gateway/autenticação antes de rede compartilhada |
| Dependência de binários do sistema | instalação mais trabalhosa | README por sistema e contêiner | diagnóstico automático de pré-requisitos |
| Licença dos pesos é não comercial | limita uso do modelo | pesos fora do repositório e licença documentada | rever motor para cenário comercial |

## 15. Como evoluir sem quebrar a arquitetura

### 15.1 Adicionar nova fonte de áudio

1. implementar `AudioSource`;
2. normalizar para o mesmo contrato WAV;
3. produzir `AudioAsset` com identidade estável;
4. registrar a escolha em `resolver_fonte()`;
5. testar fonte real e reaproveitamento do cache.

### 15.2 Trocar o transcritor

1. implementar `Transcriber`;
2. converter a saída externa para `NoteEvent`;
3. manter rótulos e tempos observáveis;
4. injetar no pipeline para comparação objetiva;
5. só mudar o padrão depois de medir no corpus.

### 15.3 Adicionar um instrumento

1. criar ou ajustar `PerfilInstrumento`;
2. decidir se a família é monofônica, polifônica, percussiva ou outra;
3. criar um port próprio se o contrato musical for diferente;
4. implementar tratamento e exportador;
5. integrar a ramificação em `pipeline.py`;
6. validar com ferramenta/modelo real e registrar a decisão no ADR.

### 15.4 Transformar em serviço multiusuário

Isso não é apenas “subir o FastAPI”. Exigiria, no mínimo:

- autenticação e autorização;
- fila durável e workers isolados;
- persistência de jobs;
- armazenamento de objetos;
- cotas de CPU, tamanho e duração;
- cancelamento e retentativa idempotente;
- observabilidade estruturada;
- política de privacidade, retenção e direitos autorais;
- coordenação de cache entre processos;
- análise da licença do modelo.

## 16. Guia de leitura do código para uma pessoa júnior

Uma ordem eficiente é:

1. `domain/models.py`: aprenda os nomes usados pelo sistema;
2. `domain/ports.py`: veja as fronteiras entre regras e ferramentas;
3. `services/pipeline.py`: acompanhe a história completa;
4. `services/rhythm.py` e `services/fretboard.py`: veja como uma previsão vira tablatura;
5. um adapter de cada grupo: local, Demucs, MuScriptor e GP5;
6. `cli.py`: veja a fachada síncrona;
7. `api/app.py`: veja o mesmo caso de uso embrulhado em jobs;
8. testes equivalentes: use-os como exemplos executáveis;
9. `tasks/decisions.md`: entenda por que soluções aparentemente mais simples foram rejeitadas.

Ao depurar, descubra primeiro a camada do problema:

- áudio não chegou ou formato inválido → ingestão;
- instrumento vazou ou sumiu → separação;
- eventos estranhos ou rótulo incorreto → transcrição;
- corda, traste, ritmo ou tom → services;
- arquivo abre errado → exportador;
- comando ou resposta HTTP → CLI/API.

## 17. Glossário

| Termo | Explicação simples |
|---|---|
| Adapter | tradução entre o núcleo e uma tecnologia concreta |
| Auralização | áudio de conferência com a transcrição sintetizada |
| BPM | batidas por minuto, medida de andamento |
| Cache | resultado intermediário guardado para evitar repetição |
| CLI | interface usada pelo terminal |
| Dataclass | classe Python voltada a representar dados |
| Domínio | conceitos e regras essenciais do problema |
| General MIDI | convenção numérica para timbres e percussão |
| GP5 | formato do Guitar Pro 5 |
| Grade rítmica | posições discretas onde notas e pausas são alinhadas |
| Job | pedido acompanhado por estado enquanto executa |
| MusicXML | formato aberto para intercâmbio de partituras |
| Onset | instante em que uma nota ou ataque começa |
| Port | contrato abstrato esperado pelo núcleo |
| Protocol | mecanismo de tipagem estrutural usado para os ports |
| Stem | faixa que tenta isolar um instrumento ou família |
| Tick | unidade discreta de tempo musical usada na exportação |
| Tablatura | escrita que indica corda e traste, além da nota |
| Viterbi | busca da melhor sequência global segundo custos |

## 18. Referências internas

- [README: instalação e uso](../README.md)
- [ADRs: decisões e medições](../tasks/decisions.md)
- [Corpus de avaliação](../tasks/corpus.md)
- [Resultados da fase inicial](../tasks/fase0-resultados.md)
- [Diagnóstico de ritmo](../tasks/ritmo-diagnostico.md)
- [Pipeline canônico](../src/thoth/services/pipeline.py)
- [Contratos do domínio](../src/thoth/domain/ports.py)
- [API de jobs](../src/thoth/api/app.py)
