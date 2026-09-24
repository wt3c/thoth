# Lições — workflow

## Port de estímulo: copiar a fonte, nunca reescrever de memória

**2026-09-22.** Ao promover as fixtures da Fase 0 a teste de regressão, reescrevi a
fixture `misto` de memória em vez de copiar o gerador original. Saiu com outra linha de
baixo e outro sustain do piano. Resultado: nota F1 **0,882 contra a baseline 0,682** — que
eu poderia ter lido como "o port melhorou as coisas" e travado como número de referência.

O estímulo é parte da medição. Mudá-lo invalida a baseline em silêncio, e o erro se
disfarça de melhoria — a direção que menos desperta suspeita.

**Como aplicar:**

- Port de fixture/estímulo/avaliador é **cópia**, não reescrita. Se a fonte não estiver
  disponível para copiar, o número antigo não pode ser reaproveitado como baseline.
- O teste de que o port foi fiel é **reproduzir o número anterior exatamente**. Cinco das
  seis fixtures bateram na terceira casa; a sexta divergir foi o sinal, e só apareceu
  porque imprimi os valores medidos ao lado das baselines em vez de confiar no verde.
- Corolário: teste que passa não diz nada sobre a margem. Imprimir o valor medido ao
  lado do piso é barato e é o que separa "passou" de "passou raspando".

Mesma família do bug do gerador de A/B da rodada anterior: nos dois casos o código de
medição estava errado, os dois produziam saída plausível, e nenhum dos dois seria pego
pelo resultado do teste — só por olhar o número de perto.

## "Gate" não é "portão"

**2026-09-24.** Correção do Welington: eu vinha traduzindo *gate* por "portão" — 58
vezes em 13 arquivos, de ADR a docstring. A tradução é literal e o sentido não chega:
em português, "portão" não evoca "o que precisa passar antes de seguir".

**Como aplicar:** escolher a palavra pelo sentido do trecho, não pelo dicionário.

- os três comandos antes de entregar (pytest, ruff, mypy) → **verificação de entrega**
  (o comando é `/verificacao`);
- teste que trava um número medido → **teste de regressão**;
- teste como proteção, em geral → **teste**;
- métrica que só informa → **não é critério de aprovação**.

Vale para todo termo de jargão em inglês: traduzir só quando a palavra em português
carrega o mesmo sentido; se não houver, o termo técnico usual é melhor que o literal.
