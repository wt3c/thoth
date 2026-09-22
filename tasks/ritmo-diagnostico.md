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

---

## Revisão (2026-09-22): o piso, e o que ele desmente

As seções acima comparam residuais sem nunca medir o **piso** — quanto do erro é
desalinhamento de grade e quanto é o erro de onset do próprio MuScriptor. Sem esse
número, "¼ da grade" não prova colocação aleatória; prova apenas dispersão maior que a
grade, o que qualquer distribuição larga produz. A linha "erro esperado se aleatório"
da primeira tabela **afirma mais do que foi medido** e deve ser lida com essa ressalva.

### O piso

Fixtures são metronômicas a 90 BPM exatos, então todo residual nelas é erro do
transcritor:

| fixture  | verdade | transcrito |
|----------|---------|------------|
| escala   | 0,0 ms  | 5,0 ms     |
| walking  | 0,0 ms  | 8,3 ms     |
| groove16 | 0,0 ms  | 3,3 ms     |
| graves   | 0,0 ms  | 3,3 ms     |
| oitavas  | 0,0 ms  | 10,0 ms    |

**Piso: 3–10 ms.** Os 24–43 ms das músicas reais estão uma ordem de grandeza acima —
o desalinhamento é real, não jitter do transcritor.

### O erro dominante é o `round()`, não o andamento variável

Busca de BPM restrita a ±3% da estimativa do pipeline (a busca anterior, irrestrita,
corria até o teto de 192–200 BPM: artefato de faixa, não ausência de pulso):

| música           | int@t=0 | frac@t=0 | frac+fase | local 30 s | BPM ótimo |
|------------------|---------|----------|-----------|------------|-----------|
| Equus            | 34,4 ms | 57,2 ms  | 12,6 ms   | 22,1 ms    | 107,50    |
| Sou Eu           | 29,5 ms | 29,7 ms  | 10,5 ms   | 20,7 ms    | 128,00    |
| Feel Like        | 43,5 ms | 40,2 ms  | 31,5 ms   | 33,4 ms    | 87,03     |
| Tive Razão       | 42,6 ms | 32,2 ms  | 20,4 ms   | 16,6 ms    | 102,99    |
| SOJA             | 24,2 ms | 22,1 ms  | 13,5 ms   | 16,8 ms    | 154,14    |
| Is It A Crime    | 36,8 ms | 39,6 ms  | 26,2 ms   | 21,1 ms    | 111,82    |
| Smooth Operator  | 31,3 ms | 39,9 ms  | 16,9 ms   | 24,9 ms    | 119,14    |

**BPM fracionário com fase livre ganha da grade local em 5 das 7.** O andamento não
precisa variar para o ritmo descolar: `tempo.py:59` faz `bpm=round(bpm)`, e no Equus
isso são 107,5 → 108, 0,46% de erro, 3,5 s de deriva acumulada em 756 s.

**Os dois parâmetros são acoplados.** A coluna `frac@t=0` mostra que refinar só o BPM,
mantendo a âncora em `t=0`, *piora* 4 das 7 (Equus 34 → 57 ms): grade mais precisa,
ancorada no lugar errado, erra mais. Ajuste conjunto ou nenhum — não há meia correção
barata aqui.

Isso também desfaz a contradição da versão anterior, que chamava 107,5 vs 108 de
"praticamente ótimo" numa seção e de deriva catastrófica em outra. É catastrófico, e é
o achado principal.

**Andamento variável continua sem veredito.** Tive Razão, Is It A Crime e Feel Like
ainda preferem a grade local depois do ajuste conjunto — mas essas três são as que
ficam mais longe do piso, e pode ser conteúdo (ao vivo, rubato) e não arquitetura.
Decidir isso depois de medir com a grade conjunta implementada, não agora.
