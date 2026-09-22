# Lições — workflow

## Port de estímulo: copiar a fonte, nunca reescrever de memória

**2026-09-22.** Ao promover as fixtures da Fase 0 a portão de regressão, reescrevi a
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
- Corolário: portão que passa não diz nada sobre a margem. Imprimir o valor medido ao
  lado do piso é barato e é o que separa "passou" de "passou raspando".

Mesma família do bug do gerador de A/B da rodada anterior: nos dois casos o código de
medição estava errado, os dois produziam saída plausível, e nenhum dos dois seria pego
pelo resultado do teste — só por olhar o número de perto.
