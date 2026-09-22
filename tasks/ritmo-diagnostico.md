# Por que o ritmo descola (2026-09-22)

Ponto de partida: o Welington ouviu as sete auralizações e disse que a melhor foi
o *Equus* — o arranjo mais denso dos sete. Perguntado sobre o que incomodava nas
outras, respondeu **ritmo/tempo descolando**. Isso desqualificou a hipótese que
estava na fila (limiar de oitava): o limiar mede altura, e a queixa é de tempo.

Todas as medidas abaixo vêm de `cache/<id>/notas.jsonl` — onsets em tempo
absoluto, antes de qualquer quantização.

## 1. A grade não tem relação com a música

Erro de quantização contra a grade de semicolcheia, no BPM que o pipeline estimou:

| música | BPM | grade | erro mediano | erro esperado se aleatório |
|---|---|---|---|---|
| Equus | 108 | 139 ms | 34 ms | 35 ms |
| SOU EU | 129 | 116 ms | 30 ms | 29 ms |
| Feel Like Makin' Love | 86 | 174 ms | 43 ms | 44 ms |
| Tive Razão | 103 | 146 ms | 41 ms | 37 ms |
| Smooth Operator | 117 | 128 ms | 32 ms | 32 ms |
| SOJA | 152 | 99 ms | 24 ms | 25 ms |
| Is It A Crime | 112 | 134 ms | 35 ms | 34 ms |

Erro mediano ≈ **um quarto da grade** nas sete. É exatamente o valor que sai se os
ataques estiverem distribuídos ao acaso em relação à grade. Nenhuma nota "cai no
tempo" — cada uma é arredondada para a semicolcheia mais próxima de um retículo
que não tem vínculo com a execução.

## 2. Não é fase

`para_ticks` ancora a grade em `t=0`, e nenhuma gravação começa com a primeira
semínima no instante zero. A suspeita era boa e morreu na medição: varrendo a
fase de 0 à grade inteira, o erro cai de 34 ms para 34 ms (Equus), 43 → 43 (Feel
Like), 32 → 32 (Smooth). Só a Tive Razão melhora (41 → 26 ms). Fase não é a causa.

## 3. Não é o número do BPM

Busca conjunta de andamento (60–200 BPM) e fase encontra grade genuína **só no
Equus**: 107,5 BPM, resíduo caindo de 34 ms para 13 ms — e o pipeline estimou 108,
praticamente o valor ótimo. Nas outras seis o ajuste foge para o teto da faixa
(192–200 BPM), que não é descoberta de andamento: é a assinatura de que não há
estrutura periódica a encontrar, e grade mais fina sempre reduz resíduo.

O andamento estimado, portanto, está certo. O que está errado é supor que exista
**um** andamento.

## 4. É a rigidez da grade ao longo do tempo

Comparando grade global com grade reajustada a cada 30 s:

| música | global | local 30 s |
|---|---|---|
| Equus | 33 ms | 24 ms |
| SOU EU | 27 ms | 22 ms |
| Feel Like Makin' Love | 42 ms | 34 ms |
| Tive Razão | 21 ms | **13 ms** |
| Smooth Operator | 30 ms | 23 ms |
| SOJA | 24 ms | 19 ms |
| Is It A Crime | 30 ms | 19 ms |

A grade local é melhor em todas as sete, de 18% a 37%. Meio BPM de erro em 756 s
são 3,5 s de deriva acumulada — dezenas de posições de semicolcheia. A palavra que
o Welington usou, *descolando*, descreve literalmente o fenômeno: começa junto e
vai separando.

Quantizar contra os tempos rastreados pelo `librosa.beat.beat_track` melhora 4 das
7 (14% a 49%) e **piora** 2 (Equus −25%, Smooth −31%). Não serve como está.

## 5. Por que o Equus ganhou

É o único material metronômico do acervo — *play-through* de metal progressivo,
tocado contra clique, com o baixo à frente na mix. É a única música do conjunto
para a qual a premissa "existe um BPM único e constante" é verdadeira. As outras
seis são soul, reggae, MPB e gravação ao vivo: andamento humano, que respira.

O ADR-019 já registrava este limite ("um único BPM global não representa música
que muda de andamento"), citando o *Equus* como o caso problemático. A medição
inverte a frase: o *Equus* é o único caso **não** problemático.

## O que isto abre

Não é ajuste de parâmetro. `rhythm.para_ticks` converte segundos em ticks com um
escalar, e o exportador escreve 4/4 fixo — a arquitetura não tem onde guardar
andamento que varia. Decidir antes de implementar.
