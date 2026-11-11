# Lições — verificação no navegador

## Headless que sai cedo produz diagnóstico falso

`chromium --headless --virtual-time-budget=N` e `--screenshot` **não** mantêm a página viva até o trabalho assíncrono
terminar: o processo sai, e uma página que ainda estava carregando fica indistinguível de uma página quebrada.

Isso custou um diagnóstico inteiro. A conclusão "o web worker do alphaTab nunca termina o render" tinha evidência
aparentemente forte — o `import` do core dentro de um worker nunca resolvia, `renderFinished` nunca disparava, e
desligar o worker "consertava". Nada disso era real: o navegador morria antes. Sob sessão controlada, o worker importa o
core normalmente e `useWorkers: false` não muda nada. A causa verdadeira era outra (ADR-016).

**Regra:** verificação de comportamento assíncrono no navegador exige sessão controlada em tempo real (CDP —
`tests/navegador/cdp.py`), nunca `dump-dom` com tempo virtual.

**Controle obrigatório:** toda asserção sobre a página vem acompanhada de uma prova de que a sessão viveu o tempo pedido
(`performance.now()` no teste, ou um heartbeat via `setTimeout`). Sem esse controle, "não aconteceu" e "não deu tempo"
são a mesma leitura — e a diferença entre os dois foi todo o erro acima.

## Teste de servidor não vê página quebrada

O servidor pode responder 200 para cada arquivo e a página ainda assim não renderizar nada. Já aconteceu duas vezes
neste projeto: vendorização incompleta do alphaTab (ADR-015) e `scrollElement` errado (ADR-016). A asserção tem de ser
sobre o resultado visível — contar `#tab svg` —, não sobre eventos do alphaTab nem sobre a existência do container:
ambos dão sinal de sucesso com o bug ativo.

## Espera por estado intermediário vira corrida quando o job ganha uma thread

Os testes esperavam `status !== 'na fila'` e afirmavam `pronto`. Enquanto o job rodava na mesma thread que o
atendia, o primeiro estado observável depois da fila já era o final. Com a thread trabalhadora do ADR-027 (2026-10-22)
apareceu `rodando` no meio, e o teste passou a ler o estado intermediário.

**Regra:** espere pelo conjunto de estados **terminais** (`['pronto', 'erro'].includes(status)`), nunca pela saída
de um estado anterior. A condição de parada não pode depender de quantos estados existem entre o início e o fim.

## Desenho que passa nos testes de posição ainda pode estar errado na aparência

No braço (2026-11-09), a espessura das cordas crescia com o índice: a corda grave saía fina e a aguda grossa. Os
testes afirmavam posição, alvo e ordem; nenhum afirmava a espessura. O usuário notou o problema ao ver a página.

**Regra:** todo atributo visual que carrega significado (espessura, cor, ordem) precisa de uma asserção sobre a
relação que ele expressa, por exemplo "a grave é a mais grossa e a espessura cai até a aguda". O valor exato não basta.

## Dois estados que mostram a mesma coisa precisam ser limpos juntos

No braço (2026-11-09), "Nenhuma" esvaziava o filtro, mas a nota tocada no braço (`selecionada`) continuava acesa,
porque a vista mostra a selecionada mesmo fora do filtro. Na URL isso aparecia como `filtro=&nota=3`.

**Regra:** quando dois estados decidem o que aparece na tela, a ação que esconde precisa limpar os dois. O teste
afirma o resultado visível ("nada aceso"), não só o campo que a ação altera.

## "Acender a nota" precisa dizer se é o som ou o lugar

No braço (2026-11-09), tocar as notas acesas no metrônomo acendia pela altura. O mesmo som em dois lugares
acendia junto, e o usuário viu "um conjunto", não nota a nota. O e2e afirmava o **nome** da nota ("só E ou A"),
o que não distingue um lugar de dois. A URL de teste ainda pedia `casas=5`, recusada em silêncio (mínimo 12),
e o ADR registrou "5 casas" sem conferir.

**Regra:** ao destacar algo no braço, o teste afirma **quantas posições** acendem (`corda-casa`), não só qual nome
aparece. Parâmetro de URL usado em teste tem o efeito conferido na leitura antes de ir para o ADR.

## "Escolher a nota" é o gesto que a tela permite, não o que o código chama de seleção

No braço (2026-11-10), o pedido "a nota escolhida em Notas tem que servir na Teoria" foi implementado no toque
numa casa (`aoTocar`, a `selecionada`). Só que o braço abre limpo: a única forma de escolher uma nota é ligá-la
no filtro, e esse caminho não chegava na tônica. Os testes passaram e o Pages foi publicado; o usuário relatou
que nada mudou. O plano declarava a suposição, mas ela não foi conferida reproduzindo o caminho a partir do
estado inicial da página.

**Regra:** antes de implementar uma interação descrita pelo usuário, reproduzi-la no navegador a partir do
estado em que a página abre e anotar o gesto real (qual botão, qual campo muda na URL). O teste de componente
segue esse mesmo gesto, não a ação da store que parece equivalente.
