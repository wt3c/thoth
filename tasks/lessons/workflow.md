# Lições — workflow

## Reprocessar o acervo em multifaixa sem perder trabalho concluído

**2026-09-29.** O lote real de 13 músicas (todas menos _Eyrie_, que já tinha a
multifaixa) confirmou a ordem e os custos do fluxo `--instrumento todos`.
`DemucsMultifaixaSeparator` executa `htdemucs_ft` sobre a mix completa em CPU;
uma separação pode levar dezenas de minutos, e stems/áudios longos podem levar
mais tempo no MuScriptor. Processos simultâneos podem aumentar a vazão total,
mas consomem vários núcleos e alguns GB de RAM cada. Durante uma separação, os arquivos ficam
sob `cache/stems/<source_id>/htdemucs_ft/4.1.0-multifaixa.parcial`; quando o
estágio termina, são publicados sob `4.1.0-multifaixa`. Não tratar a ausência de
arquivos na pasta final enquanto `.parcial` existe como falha nem iniciar uma
segunda separação para o mesmo ID.

**Como aplicar:**

- Reaproveitar `cache/yt_<id>/meta.json`, `mix.wav` e `notas.jsonl` quando
  pertencem à música solicitada. A URL com o ID registrado faz o
  `YtDlpSource` atingir esse cache; não baixar a mix outra vez.
- Ler a afinação real da faixa `Baixo` no GP5 solo anterior e passá-la ao
  pipeline. Não deduzir afinação apenas pelo número de cordas: há afinações
  diferentes com o mesmo número. Conferir a afinação relendo o GP5 multifaixa.
- O perfil `todos` separa os stems completos uma vez; guitarra e bateria
  compartilham os stems. A transcrição e a inclusão de cada perfil são
  condicionais aos eventos válidos encontrados. Faixa ausente deve ser relatada,
  não inventada nem criada vazia (ADR-047). GP5/MusicXML são saídas da
  multifaixa; os stems são intermediários de cache.
- Se a solicitação cobre apenas tablaturas e os WAVs existentes devem ser
  mantidos, a rotina interna pode passar `_gerar_auralizacao=False`. Em uma
  execução sob sandbox, a chamada ao FluidSynth da auralização ficou presa; não
  repetir essa etapa para produzir GP5/MusicXML. A geração de auralização é uma
  tarefa separada e deve ser reavaliada quando solicitada.
- `gerar_guia(caminho)` **retorna o conteúdo Markdown como `str`**; não retorna
  um caminho nem grava o arquivo. Gravar esse conteúdo explicitamente em
  `<nome>.estudo.md` ou `<nome>.todos.estudo.md` ao lado do GP5. Um erro nessa
  etapa pode retornar código diferente de zero depois de GP5 e MusicXML já terem
  sido gravados: verificar os artefatos antes de repetir o pipeline caro.
- Ao derivar o caminho do GP5 solo a partir de `nome.todos.gp5`, remover o
  sufixo completo `.todos.gp5` antes de acrescentar `.gp5`. Não usar
  `Path.with_suffix()` sobre o título: títulos como `... ft. ...` contêm pontos
  que não são extensões.
- Cobertura final: para cada música, abrir o GP5 multifaixa com PyGuitarPro,
  confirmar `Baixo` e `Bateria`, conferir a afinação, verificar e fazer parse do
  MusicXML e confirmar a presença dos guias solo e multifaixa. A contagem do lote
  atual foi 13/13. Verificar as faixas observadas em cada música; não exigir as
  cinco categorias quando um perfil não teve eventos válidos.

## Não exigir que o iniciante saiba o tom antes de estudar a tab

**2026-09-28.** O primeiro guia só mostrava graus quando o usuário informava `--tom`. O usuário perguntou se o tom
não podia ser extraído da tablatura — justamente a necessidade de quem está começando teoria musical. O GP5 gerado não
grava a tonalidade estimada em sua armadura, mas suas notas permitem reutilizar a estimativa já existente no pipeline.

**Como aplicar:** oferecer a análise disponível automaticamente, identificando-a como candidato e mostrando seus
limites. Um dado conhecido informado pelo usuário prevalece. Não transferir ao iniciante um pré-requisito que a
ferramenta consegue estimar; tampouco apresentar a hipótese como fato musical.

## Port de estímulo: copiar a fonte, nunca reescrever de memória

**2026-09-22.** Ao promover as fixtures da Fase 0 a teste de regressão, reescrevi a fixture `misto` de memória em vez de
copiar o gerador original. Saiu com outra linha de baixo e outro sustain do piano. Resultado: nota F1 **0,882 contra a
baseline 0,682** — que eu poderia ter lido como "o port melhorou as coisas" e travado como número de referência.

O estímulo é parte da medição. Mudá-lo invalida a baseline em silêncio, e o erro se disfarça de melhoria — a direção que
menos desperta suspeita.

**Como aplicar:**

- Port de fixture/estímulo/avaliador é **cópia**, não reescrita. Se a fonte não estiver disponível para copiar, o número
  antigo não pode ser reaproveitado como baseline.
- O teste de que o port foi fiel é **reproduzir o número anterior exatamente**. Cinco das seis fixtures bateram na
  terceira casa; a sexta divergir foi o sinal, e só apareceu porque imprimi os valores medidos ao lado das baselines em
  vez de confiar no verde.
- Corolário: teste que passa não diz nada sobre a margem. Imprimir o valor medido ao lado do piso é barato e é o que
  separa "passou" de "passou raspando".

Mesma família do bug do gerador de A/B da rodada anterior: nos dois casos o código de medição estava errado, os dois
produziam saída plausível, e nenhum dos dois seria pego pelo resultado do teste — só por olhar o número de perto.

## "Gate" não é "portão"

**2026-09-24.** Correção do Welington: eu vinha traduzindo _gate_ por "portão" — 58 vezes em 13 arquivos, de ADR a
docstring. A tradução é literal e o sentido não chega: em português, "portão" não evoca "o que precisa passar antes de
seguir".

**Como aplicar:** escolher a palavra pelo sentido do trecho, não pelo dicionário.

- os três comandos antes de entregar (pytest, ruff, mypy) → **verificação de entrega** (o comando é `/verificacao`);
- teste que trava um número medido → **teste de regressão**;
- teste como proteção, em geral → **teste**;
- métrica que só informa → **não é critério de aprovação**.

Vale para todo termo de jargão em inglês: traduzir só quando a palavra em português carrega o mesmo sentido; se não
houver, o termo técnico usual é melhor que o literal.

## O usuário não é juiz de música

**2026-09-25.** Correção do Welington: o conhecimento de música dele é nulo, e o Thoth existe justamente para ele
aprender. Eu vinha pedindo que ele escolhesse margem de acerto, recomendasse o que fazer com o limiar de oitava e
deixando para ele a "passada perceptual" de ouvido.

**Como aplicar:**

- Qualidade e acerto musical se decidem por **medição** (tab humana, piso de acaso, referência sintética), nunca por
  julgamento dele. Se não há como medir, dizer isso, e não transferir a decisão.
- Decisão de método (qual limiar, qual margem) é minha: decidir pela medição, registrar no ADR e informar. Pedir
  aprovação do **plano de trabalho**, não do juízo musical.
- Verificação manual só o que dispensa ouvido treinado: "sai som?", "o cursor anda?". "Soa certo?" não é pergunta para
  ele.
- Explicar termo musical na primeira vez que aparece (oitava, classe de altura, tab).
