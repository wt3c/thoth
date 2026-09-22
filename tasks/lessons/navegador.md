# Lições — verificação no navegador

## Headless que sai cedo produz diagnóstico falso

`chromium --headless --virtual-time-budget=N` e `--screenshot` **não** mantêm a
página viva até o trabalho assíncrono terminar: o processo sai, e uma página que
ainda estava carregando fica indistinguível de uma página quebrada.

Isso custou um diagnóstico inteiro. A conclusão "o web worker do alphaTab nunca
termina o render" tinha evidência aparentemente forte — o `import` do core dentro
de um worker nunca resolvia, `renderFinished` nunca disparava, e desligar o worker
"consertava". Nada disso era real: o navegador morria antes. Sob sessão
controlada, o worker importa o core normalmente e `useWorkers: false` não muda
nada. A causa verdadeira era outra (ADR-016).

**Regra:** verificação de comportamento assíncrono no navegador exige sessão
controlada em tempo real (CDP — `tests/navegador/cdp.py`), nunca `dump-dom` com
tempo virtual.

**Controle obrigatório:** toda asserção sobre a página vem acompanhada de uma
prova de que a sessão viveu o tempo pedido (`performance.now()` no teste, ou um
heartbeat via `setTimeout`). Sem esse controle, "não aconteceu" e "não deu tempo"
são a mesma leitura — e a diferença entre os dois foi todo o erro acima.

## Teste de servidor não vê página quebrada

O servidor pode responder 200 para cada arquivo e a página ainda assim não
renderizar nada. Já aconteceu duas vezes neste projeto: vendorização incompleta
do alphaTab (ADR-015) e `scrollElement` errado (ADR-016). A asserção tem de ser
sobre o resultado visível — contar `#tab svg` —, não sobre eventos do alphaTab
nem sobre a existência do container: ambos dão sinal de sucesso com o bug ativo.
