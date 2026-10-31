# Thoth — plano de execução

> Áudio → partitura e tablatura, foco em contrabaixo. Uso pessoal. CPU-only. Decisões em `tasks/decisions.md`.

## Corpus humano para velocidade e ritmo (2026-10-30)

O usuário ouviu a candidata, reprovou principalmente velocidade e ritmo e
solicitou usar as outras versões humanas de `samples/` para melhorar o processo.
Continuar o trabalho já autorizado; o objetivo de equivalência permanece aberto.
Origem: leitores e avaliadores do Thoth, ADR-021/034/041/042/053 e testes de
quantização existentes. Não há solução musical no banco entre projetos.

1. [ ] Conferir os seis pares referência/áudio/saída, hashes, versões e afinação;
   não confundir saídas antigas homônimas com as atuais.
2. [ ] Validar GP5 → MuseScore → MIDI com fixture existente (pausas, ligaduras,
   mudança de andamento), sem copiar áudio ou notas humanas para a inferência.
3. [ ] Produzir comparativo reproduzível de velocidade, figuras, pausas,
   compassos e notas nas seis músicas; separar reprodução e transcrição.
4. [ ] Corrigir causas comprovadas por testes; avaliar generalização com uma
   música fora dos ajustes por vez; executar verificação de entrega.

Progresso (2026-10-30, Claude, retomando a sessão do Codex interrompida):

- `comparar_ritmo` informa a velocidade por janela (`janela_s`, padrão 20 s, no
  relógio da referência): a mediana global escondia trechos acelerados. TDD com
  vermelho visto (`janelas` e `janela_s` inexistentes).
- GP5 grava a marca de andamento explícita no compasso 1. Os hashes de
  `test_gp5_saida_estavel` foram refeitos; sem a marca, os bytes reproduzem os
  hashes antigos exatamente (conferido).
- MuseScore 4.7.5 recusa `catedral-voce_build.gp5` (GP5 v5.00) com código 40,
  determinístico, na importação; a causa é a faixa de bateria (sem ela, converte).
  Uma cópia só da bateria regravada pelo PyGuitarPro falha de forma intermitente
  (código 1). É limitação do leitor com o arquivo humano: o lado MIDI de Você fica
  sem medição e o script registra `erro_reproducao`; o leitor PyGuitarPro mede.
- Velocidade 0,5 em Dance of Death e Plague é artefato de alinhamento: nota
  repetida omitida faz o par consecutivo saltar um ataque. Entre alturas
  distintas, p10 sobe para 0,78 e 0,95. Eyrie não: a tab humana toca 366 s
  (68→434 s) contra 711 s da gravação; não serve de gabarito de velocidade.
- Duração total no tempo real bate com o áudio em Você, Gesu, Dance e Plague
  (±1%); Fear termina 14 s antes. O BPM escrito diverge (Você 116 × 106,
  Dance 129 × 150) com o relógio igual: as figuras compensam o andamento.

Verificação: 770 testes padrão, Ruff limpo, mypy sem erros (47 arquivos);
`-m "slow and not network"` do corpus e da reprodução MIDI: 3 passaram.

Régua corrigida (aprovada: "pode seguir"): repetição de mesma altura com
tamanhos diferentes nos dois lados torna o par ambíguo; esses intervalos saem
da velocidade e do erro de intervalo (`intervalos_ambiguos`). TDD: p10 0,75 no
vermelho. Corpus refeito em `out/avaliacao-ritmo-2026-10-30-regua2/`: p10 de
Fear 0,49 → 0,98 e de Plague 0,48 → 0,95. Onde há medida, o Thoth segue o
relógio da gravação; razões constantes (Dance 1,075, Plague 0,955) são o
andamento da tab humana diferente da gravação.

Causa do 116 × 106 em Você: a tab humana acelera aos poucos (106 → 124 → 121);
janelas de 20 s e λ = 2000 (ADR-034/053) não pagam trocas pequenas e o mapa fica
em 116 até o compasso 53. O quantizador compensa com figuras erradas: figura
igual à humana 98,6% onde o andamento escrito difere < 1% do tocado; 91,9%
(1–3%), 89,6% (3–6%), 77,6% (> 6%). Fear: 36% acima de 6%. Andamento local medido
em ±8 notas; não é totalmente independente das figuras. Próximo: varrer janela e
λ a partir do cache de notas, medindo figuras contra as tabs válidas (Você, Gesu,
Fear, Plague) com uma música fora por vez; mudança de parâmetro exige emenda ao
ADR-053. Verificação: 772 testes, Ruff, mypy limpos.

Varredura janela × λ (aprovada: "pode seguir"; só medição, programa intacto):
pipeline real com cache, stems Demucs `shifts0` refeitos (Gesu tem 762 notas
contra 765 do GP5 antigo; a régua é a rodada nova com 20 s/2000). Fração de
intervalos certos contra a tab humana:

| config | Você | Gesu | Fear | Plague |
| --- | --- | --- | --- | --- |
| 20 s / 2000 (atual) | 684/721, 2 trocas | 402/442, 0 | 284/340, 2 | 1758/1828, 6 |
| 20 s / 1000 | 701/721, 6 | 402/442, 0 | 296/350, 9 | 1764/1836, 8 |
| 10 s / 1000 | 700/721, 6 | 402/442, 0 | 300/353, 5 | 1772/1841, 9 |
| 5 s / 250 | 0,981, 19 | 0,914, 7 | 0,860, 27 | 0,963, 24 |

λ ≤ 500 põe 3 a 20 trocas em Gesu (constante); a janela pesa pouco. Deixando
Gesu de fora, as outras três escolhem (10 s, 250): Gesu cai 0,001 e ganha 9
trocas. λ = 1000 manteria Gesu, mas nas 18 fontes do cache (notas do stem
antigo + `_medir_grade` real; a aproximação reproduz 2→6, 0→0, 6→8 das rodadas
reais) 5 das 9 músicas sem troca ganham trocas: Arde Outra Vez salta de 124 para
135 e Is It A Crime começa em 106,4 em vez de 111,8. Com λ 1500 e 1250, Is It A
Crime ainda ganha 2–3. **Não adotado** (critério do ADR-053). O custo fixo por
troca não distingue a aceleração gradual de Você (106 → 124) de trocas
espúrias; com λ global não há ajuste que sirva. Scripts em scratchpad
(`varredura/`), não versionados.

Objetivo esclarecido pelo usuário: as tabs humanas são gabarito para o Thoth
**aprender a identificar**; medir na música deixada de fora. Ele julga pela
partitura tocada no Guitar Pro.

Beat This! (modelo pronto; aprovado: "pode"): checkpoint `final0` baixado de
cloud.cp.jku.at (81 058 141 bytes, sha256 `8c328b45…8331`), pacote PyPI
`beat-this` só em overlay `uv run --with`, sem entrar no projeto; 6–19 s por mix
em CPU. Andamento local contra o escrito na tab humana, os dois GP5 levados ao
áudio por `alinhar` (fração dos pontos a < 2% / < 4%):

| música | Beat This (mediana de intervalos) | Beat This (reta, dobrado ao global) | Thoth atual |
| --- | --- | --- | --- |
| Você | 0,72 / 0,82 | 0,60 / 0,69 | 0,67 / 0,84 |
| Gesu | 1,00 / 1,00 | 1,00 / 1,00 | 1,00 / 1,00 |
| Fear | 0,76 / 0,80 | 0,49 / 0,67 | 0,16 / 0,69 |
| Dance | 0,48 / 0,66 | 0,39 / 0,75 | 0,31 / 0,45 (GP5 antigo) |
| Plague | dobro (mediana 1,95) | 0,03 / 0,24 | 0,36 / 0,37 |

Plague: as duas medianas ficam em 0,955, porque a tab humana não segue a
gravação; essa música não decide. Nas fontes constantes, o Beat This bruto oscila:
grade de 20 ms (degraus de ~4%), metade/dobro por trecho (Se Eu Cair 60↔120,
Arde Outra Vez 82↔125) e Is It A Crime (ao vivo) instável. Resultado depende
do estimador local, então não escolher o estimador olhando estas 5 músicas.
Conclusão: o modelo acerta onde o mapa atual erra (Fear, Dance), mas não serve
como troca direta. Precisa de mapa robusto (continuidade de andamento, dobra
por oitava) avaliado deixando uma música de fora.

Híbrido medido em 2026-10-30 (script `hibrido/medir.py` no scratchpad). As
batidas do Beat This! entram como pontos do `mapa_de_andamento`, com o global
e a faixa ±10% do Thoth. Foram duas variantes, só batidas (B) e notas ∪ batidas
(U), com λ de 250 a 8000. Métrica: andamento do mapa contra o escrito na tab
humana, fração < 2% / < 4%. Na métrica do mapa, o atual tem Você 0,66/0,85,
Fear 0,47/0,69 e Dance 0,10/0,72, e as 8 fontes estáveis ficam sem troca.

| variante | Você | Fear | Dance | estáveis com troca |
| --- | --- | --- | --- | --- |
| B-1000 | 0,74 / 0,95 | 0,46 / 0,69 | 0,06 / 0,50 | 4 (Is It A Crime 3, Arde 2) |
| B-2000 | 0,51 / 0,58 | 0,69 / 0,69 | 0,00 / 0,00 | 0 |
| U-2000 | 0,73 / 0,92 | 0,47 / 0,69 | 0,06 / 0,36 | 2 |
| U-4000 | 0,67 / 0,88 | 0,33 / 0,69 | 0,00 / 0,00 | 0 |

Nenhuma combinação de variante e λ mantém as estáveis sem troca e, ao mesmo
tempo, empata ou melhora Você, Fear e Dance. Com λ alto Dance perde todas as
trocas, e com λ baixo aparecem trocas falsas. **Híbrido não adotado**: sem plano
e sem ADR de integração, e o Beat This! continua fora do projeto.

Custo de troca proporcional ao salto (aprovado: "pode seguir"; só medição,
programa intacto). Hipótese: hoje toda troca custa 2000 ms·nota, então o passo
pequeno da aceleração de Você custa o mesmo que o salto espúrio de Arde Outra
Vez (124 → 135). Variante no scratchpad: trocar de b para b' custa
`fixo + k·|b' − b|/bpm·100` (k em ms·nota por 1% de salto), varrendo `fixo` e
`k`; `fixo = 2000, k = 0` é o atual. Régua congelada **antes** de rodar:

1. Nenhuma das fontes do cache sem troca na régua atual ganha troca (aproximação
   `proxy2`, notas do stem antigo + `_medir_grade` real), e Gesu fica sem troca.
2. Nenhuma das 4 músicas com tab humana perde mais de 0,02 na fração de
   intervalos certos.
3. Você, Fear e Plague melhoram nessa fração.
4. O par (`fixo`, `k`) é escolhido deixando uma música de fora, entre os que
   passam em 1; a de fora não pode piorar mais de 0,02.

Se nenhum par passar, fica registrado como descartado. Se passar, plano de
mudança com TDD, emenda ao ADR-053 e revisão do plano antes da aprovação.

Resultado (2026-10-30): **descartado, nenhum par passa**. A variante com
`fixo = 2000, k = 0` reproduz o mapa original em todas as 18 fontes, conferido
com `assert`, e as rodadas reais de 20 s/2000 da varredura anterior. A grade
varreu `fixo` ∈ {250, 500, 1000, 2000} e `k` ∈ {100, 250, 500, 1000, 2000}.

- Critério 1: com `fixo` de 250 ou 500, Thalles, Sou Eu e Gesu ganham troca.
  Com `fixo` 1000, Is It A Crime ganha 1–2 trocas e Smooth Operator 1–2.
  Só `fixo` 2000 passa.
- As trocas falsas são **passos pequenos**: Is It A Crime 107,7 → 111,8 → 111,0
  e Smooth Operator 119,1 → 118,8. São do mesmo tamanho que os passos reais de
  Você (113,7 → 116,1 → 118,7 → …). O tamanho do salto não separa uma coisa
  da outra, e a hipótese cai.
- Critérios 2 e 3 no pipeline real (fração de intervalos certos, trocas):

| par | Você | Gesu | Fear | Plague |
| --- | --- | --- | --- | --- |
| 2000 / 0 (atual) | 0,949, 2 | 0,910, 0 | 0,835, 2 | 0,962, 6 |
| 2000 / 100 | igual ao atual | igual | igual | igual |
| 2000 / 250–500 | 0,921, 0 | 0,910, 0 | 0,835, 2 | 0,962, 6 |
| 2000 / 1000 | 0,921, 0 | 0,910, 0 | 0,849, 2 | 0,963, 5 |
| 1000 / 100 (falha em 1) | 0,968, 6 | 0,910, 0 | 0,853, 3 | 0,961, 8 |

Entre os pares de `fixo` 2000, 100 não muda nada e os demais tiram as trocas de
Você, que perde 0,028. Isso passa do limite de 0,02. O único par que melhora Você
e Fear (1000/100) é o mesmo ganho de λ 1000, com as mesmas trocas falsas nas
estáveis. Conclusão: o custo da troca, fixo ou proporcional, não separa
aceleração real de troca espúria. A informação que falta não está no custo, e
sim em outro sinal. Scripts (`prop.py`, `proxy_prop.py`, `rodar_prop.py`,
`prop.sh`) no scratchpad, não versionados.

### Boletim em 5 dimensões (aprovado: "pode", 2026-10-30)

Objetivo: para cada música com tab humana, uma fração em [0, 1] por dimensão,
para saber qual dimensão mais separa o Thoth da versão humana. Os pares vêm do
alinhamento por altura que `comparar_ritmo` já faz, então o relógio não escolhe
o par. As dimensões:

- **andamento**: fração das janelas de 20 s com velocidade a < 4%.
- **figuras**: intervalos corretos / intervalos comparáveis.
- **posição no pulso**: pares com a mesma posição dentro da semínima
  (`inicio_pulsos mod 1`). Suposição declarada: uso o pulso e não o compasso,
  porque anacruse e compasso 3/4 deslocariam o compasso sem que o ritmo mudasse.
- **altura**: pares com a mesma altura / notas da referência.
- **digitação**: pares tocados na mesma corda / pares em que as duas têm corda.
  A corda é identificada pela altura solta, o que permite comparar baixo de 4
  cordas com o de 5.

- [x] 1. Testes vermelhos em `test_avaliacao_ritmica.py`: posição no pulso,
      digitação e `boletim`.
- [x] 2. Implementar em `avaliacao_ritmica.py`: `EventoRitmico.corda` opcional,
      contagens novas e a função `boletim`.
- [x] 3. `_ler` do script lê a corda via `_tablatura`, e o resultado ganha o
      boletim, com teste real em `test_corpus_ritmico.py`.
- [x] 4. Medir nos GP5 atuais (Você, Gesu, Fear, Plague com 20 s/2000; Dance
      ainda com o GP5 antigo) e registrar a tabela aqui.
- [x] 5. Suíte, Ruff e mypy: 778 passed, Ruff e mypy limpos.

Boletim medido em 2026-10-30 (manifesto e saída no scratchpad, `boletim/`).
Dance e Eyrie usam GP5 antigos. Eyrie tem afinação de 4 cordas contra 6 da
humana e velocidade 0,485, então não decide:

| música | andamento | figuras | posição no pulso | altura | digitação |
| --- | --- | --- | --- | --- | --- |
| Você | 0,92 | 0,95 | **0,43** | 0,93 | 0,74 |
| Gesu | 1,00 | 0,91 | **0,04** | 0,87 | 0,42 |
| Fear | 0,87 | 0,84 | **0,27** | 0,72 | 0,44 |
| Plague | 0,31 | 0,96 | **0,27** | 0,79 | 0,43 |
| Dance | 0,19 | 0,71 | **0,24** | 0,55 | 0,24 |

A maior distância é a **posição no pulso**: as figuras acertam e as notas caem
na semicolcheia errada do tempo. Deslocamento (gerada − humana) mod 1 pulso,
nos pares alinhados por altura (`boletim/fases.py`):

- Gesu: 580 de 668 pares com exatamente −1 semicolcheia (0,75), constante do
  começo ao fim.
- Plague: +0,25 no primeiro terço e 0 no último.
- Você: 0,75 no primeiro terço e 0 no último.

Plague e Você mudam de deslocamento ao longo da música, junto com a deriva de
andamento.

Causa provável, conferida no código: `ajustar` e `recuo_de_fase` encontram a
fase só dentro de uma semicolcheia (`grade = 60/bpm/4`). O resíduo é o mesmo
para as 4 semicolcheias, e nada escolhe qual delas é a cabeça do tempo. O
começo do tempo fica onde o primeiro tique cair. Próximo passo: escolher a
semicolcheia do tempo por medição (candidatas: acentos do mix, batidas do
Beat This!, densidade de notas por posição), com validação deixando uma
música de fora. É mudança de comportamento do pipeline, então exige plano,
ADR e revisão.

### Cabeça do tempo — plano (2026-10-30) ✅ **FECHADO** (`d4944f1`)

Medição prévia (`boletim/cabeca.py` no scratchpad). Janelas de 30 s em que um
deslocamento domina pelo menos 60% dos pares, contando quantas vezes cada regra
acerta a semicolcheia da cabeça do tempo indicada pela humana. Nenhuma regra tem
parâmetro ajustado, então não há vazamento entre músicas:

| música | janelas | atual (fase 0) | densidade | Beat This! | acentos do mix | **batidas do librosa** |
| --- | --- | --- | --- | --- | --- | --- |
| Você | 5 | 3 | 0 | 3 | 1 | **4** |
| Gesu | 8 | 0 | 1 | 8 | 7 | **8** |
| Fear | 2 | 0 | 2 | 1 | 1 | **1** |
| Plague | 17 | 5 | 5 | 7 | 6 | **13** |
| total | 32 | 8 | 8 | 19 | 15 | **26** |

As batidas do `librosa.beat.beat_track` já são calculadas em `estimar_andamento`
(`tempo.py:106`) e descartadas. Elas venceram o Beat This! sem dependência nova,
sem rede e sem mudar o `models.lock.toml`. **O Beat This! sai do plano**: só volta
se, numa etapa futura, superar o librosa fora da amostra.

Revisões independentes (fable e Codex, ambas "aprovar com ajustes"), já
incorporadas abaixo:

- A causa raiz está certa: `ajustar` só busca fase dentro de uma semicolcheia, e
  `recuo_de_fase` escolhe entre `fase` e `fase - grade`. Nada escolhe qual das 4
  semicolcheias é a cabeça do tempo.
- O deslocamento precisa entrar **antes** de `_nas_barras`, como parâmetro de
  `mapa_de_andamento`. Somado ao recuo depois, ele tira as trocas da barra
  (`marcas()`, `rhythm.py:131-143`; `gp5.py:125-130`).
- 32 janelas sustentam um experimento, não uma adoção. A régua precisa ser
  congelada antes da rodada que decide.

Etapas:

0. **Régua congelada, antes de qualquer código** (scratchpad). Janela, limiar de
   dominância e critério ficam escritos aqui antes da rodada:
   - Janela de 15 s, dominância ≥ 60%, mapa exato (não interpolação entre ataques
     do baixo).
   - Dance regerada com o pipeline atual; Eyrie segue fora (afinação errada).
   - Relatar a cobertura (janelas excluídas e por quê) e a ambiguidade do
     `_alinhar`.
   - Decisão **global por música** (uma fase só), comparada com a humana; quando a
     moda por trecho discorda da global, isso é relatado.
   - Batidas em dobro ou metade: dobradas para a semínima. Se a paridade não
     decidir (empate entre duas fases a meio tempo), o serviço se abstém e mantém
     a fase atual.

   Critério para seguir: nenhuma música pior que a fase atual e o total melhor.
   Se surgir parâmetro, ele é escolhido deixando uma música de fora.

   **Régua congelada (2026-10-30, aprovada: "pode"), escrita antes da rodada**
   (`regua/medir.py` no scratchpad):
   - Mapa exato: o `Resultado.mapa` (bpm, recuo, trocas) de cada rodada vai para
     `mapa.json`. O tempo no áudio de uma nota é `mapa.para_audio(pulsos·60/bpm)`,
     e o pulso de uma batida é `mapa.para_partitura(t)·bpm/60`. Sanidade: mediana
     da distância entre a nota assim reconstruída e o ataque mais próximo do cache.
   - Gabarito por janela de 15 s: moda de `(pulsos Thoth − pulsos humana) mod 1`,
     arredondada à semicolcheia, nos pares do `_alinhar`. Uma janela conta com pelo
     menos 12 pares e moda com pelo menos 60% deles.
   - Candidata: **uma** fase por música, a moda da fração das batidas do librosa
     (`beat_track` no `mix.wav`, como em `estimar_andamento`). Abstém-se, e fica
     a fase 0, quando a segunda fração mais votada tem pelo menos 80% dos votos
     da primeira (batidas em dobro sem paridade decidida).
   - Medidas por música: (a) janelas dominantes acertadas pela fase global, contra
     a fase 0; (b) **posição no pulso prevista**, a fração dos pares cujo
     deslocamento é igual à fase escolhida (o `_alinhar` casa por altura, então
     deslocar a grade não muda os pares nem as figuras); (c) teto: a melhor fase
     global possível; (d) cobertura (janelas descartadas por poucos pares ou sem
     dominância), altura (pares/notas da humana) e janelas cuja moda local das
     batidas discorda da global.
   - Músicas: Você, Gesu, Fear, Plague e Dance regerados agora (20 s, λ 2000).
     Eyrie fica fora (afinação errada).
   - Passa se, em (b), nenhuma música cai e a soma sobe, e se, em (a), o total
     sobe. O 0,8 da abstenção e o 12/60% das janelas foram fixados aqui, sem rodar.

   **Resultado da régua (2026-10-30)** (`regua/resultado.jsonl`). Sanidade do mapa
   exato: 6,5 a 22,7 ms de mediana entre a nota reconstruída e o ataque do cache.

   | música | trocas | votos das batidas (0 / ¼ / ½ / ¾) | fase | posição: fase 0 → escolhida (teto) | janelas: 0 → escolhida (teto) / dominantes |
   | --- | --- | --- | --- | --- | --- |
   | Você | 2 | 118 / 73 / 115 / 137 | abstém | 0,434 → 0,434 (0,434) | 5 → 5 (5) / 10 |
   | Gesu | 0 | 53 / 33 / 2 / 424 | ¾ | **0,043 → 0,868** (0,868) | **0 → 14** (14) / 14 |
   | Fear | 2 | 147 / 175 / 72 / 115 | abstém | 0,267 → 0,267 (0,307) | 1 → 1 (3) / 6 |
   | Plague | 6 | 469 / 440 / 76 / 146 | abstém | 0,299 → 0,299 (0,456) | 10 → 10 (18) / 33 |
   | Dance | 3 | 278 / 289 / 273 / 272 | abstém | 0,245 → 0,245 (0,285) | 0 / 0 dominantes |
   | total | | | | pares 1801 → 2352 de 6577 | 16 → 30 (40) / 63 |

   O critério congelado passa: nenhuma música cai, e as duas somas sobem. A
   leitura honesta é mais estreita:
   - Todo o ganho vem de Gesu, a única música sem troca de andamento. Nas quatro
     com trocas, as batidas votam quase por igual nas quatro frações, e a regra se
     abstém. As batidas não discordam da fase: o mapa é que deriva entre elas.
   - Você se abstém por pouco (0,86 contra o limiar de 0,8), e escolheria ¾, fora
     do teto 0. A abstenção é a salvaguarda que sustenta o "nenhuma pior".
   - Em Plague, Fear e Dance, o teto global ganharia pouco (até +0,16). O ganho
     maior está na fase por trecho, que depende de corrigir a deriva do mapa.

   **Etapas 1 a 5 feitas (2026-10-30).** `services/cabeca_do_tempo.py`,
   `Andamento.batidas`, `mapa_de_andamento(..., cabeca=)`, `Resultado.cabeca_do_tempo`
   e aviso de abstenção na CLI, tudo por TDD.

   Medição de ponta a ponta (scratchpad `etapa5/`):
   - As 5 músicas foram regeneradas com o pipeline novo. A régua confirma a
     previsão: Gesu sai com recuo 0,104 → 0,435 s (+3 semicolcheias), posição no
     pulso 0,043 → 0,868 e janelas 0 → 14 de 14. As outras quatro se abstêm e
     saem idênticas (BPM, recuo e trocas). Total de pares na posição certa:
     1801 → 2352 de 6577.
   - Nas 18 fontes do cache (notas do stem antigo):
     - 7 decidem sem troca: Gesu, A Resposta, Sou Eu, Smooth Operator, Arde Outra
       Vez, Se Eu Cair e O Sol. Nelas só o recuo muda; o BPM fica igual.
     - 5 com troca escolhem 0 e não mudam. 5 se abstêm.
     - Plague (com troca) decide ¼: as 6 trocas ficam iguais, mas o primeiro trecho
       vai de 104,88 para 104,94 BPM, porque a primeira troca cai em outra barra
       (16,1 → 18,6 s). É desvio da letra do critério "BPM igual", e não é defeito.
     - Todas as trocas ficam na barra.
   - Sem tab humana, as 6 fontes decididas sem troca não têm gabarito. A mudança
     delas é aposta na mesma regra que acertou Gesu, e não um resultado medido.

   **Etapa 6 feita (2026-10-30).** README, AGENTS e ADR-054 atualizados; sem lição,
   porque não houve correção do usuário. Verificação: suíte padrão 798 passed;
   `-m "slow and not network"` 51 passed e 1 skipped com `-n 2`. Com `-n auto`,
   `test_caminho_real_ate_o_arquivo_baixado` falhou duas vezes, provavelmente por disputa de
   memória, o que agora está documentado em AGENTS e `/verificacao` (`9f0790a`).
   Ruff e mypy limpos.
1. **ADR-054**: a cabeça do tempo é escolhida pelas batidas do librosa; o mapa
   continua decidindo andamento e trocas (ADR-053 intacto). O ADR registra o
   Beat This! medido e descartado.
2. **Serviço puro `services/cabeca_do_tempo.py`**: dado o mapa e as batidas,
   devolve o deslocamento em semicolcheias (0 a 3) ou abstenção. Moda da fração
   do pulso onde as batidas caem, com tempo negativo (anacruse) dobrado para o
   intervalo do pulso. TDD com dados sintéticos.
3. **`estimar_andamento` devolve as batidas** que hoje descarta. Teste real num
   WAV (barato: librosa já roda na suíte padrão).
4. **Pipeline**:
   - `mapa_de_andamento` recebe o deslocamento e o aplica antes de `_nas_barras`;
     `recuo_de_fase` não é reaplicado por cima.
   - Com BPM informado, as batidas são dobradas para o pulso dado.
   - Na multifaixa, as batidas vêm do `mix.wav` e a mesma fase vai às três
     chamadas de `_medir_grade` (`pipeline.py:731, 801, 856`).
   - Abstenção ou falha → fase atual, com um campo legível por máquina em
     `Resultado` e aviso no relatório.
5. **Medição de ponta a ponta**:
   - Boletim nas 5 músicas: posição no pulso precisa subir; andamento e figuras
     não podem cair.
   - Nas 18 fontes: BPM e número de trocas iguais; as trocas continuam na barra.
     A fase pode mudar (o critério "mapa idêntico" da versão anterior estava
     errado).
   - Reler o GP5 gerado e conferir pela reprodução independente
     (`test_gp5_reproducao_midi`).
   - Hashes de `test_gp5_saida_estavel` atualizados só com justificativa.
6. **Documentação**: README e AGENTS, lição e todo; verificação com a suíte
   padrão, `-m "slow and not network"`, Ruff e mypy.

Riscos:

- Evidência curta: 32 janelas, e Gesu decide boa parte. A etapa 0 pode reprovar
  a adoção; nesse caso nada é implementado e o resultado fica registrado.
- Você e Plague mudam de deslocamento ao longo da faixa por deriva do mapa. Uma
  fase global corrige só parte delas; a fase por trecho fica para depois.
- Mudar a fase muda todos os GP5 gerados (hashes de saída estável).
- O teto de 4/4 continua: compasso composto ou 3/4 não é tratado aqui.

Sucesso desta etapa: uma base de avaliação que detecte as divergências audíveis
e impeça promover outra candidata por F1 de cache ou ganho em uma única música.
Uma melhoria local não encerra a tarefa de igualdade com a versão humana.
Riscos: versões distintas da gravação, afinações incorretas em saídas antigas,
compassos 3/4 e compostos contra o 4/4 fixo, articulação do player MIDI e
arredondamento de BPM. Testes usam recursos reais; sem mocks de formato/leitor.
Revisão de exploração: `diagnosticar_ritmo_notas` (corpus) e
`explorar_comparacao` (reprodução independente). Não há revisor específico de
áudio no harness; decisões de arquitetura, se necessárias, terão ADR próprio.

## Você igual à tab humana por aprendizado, com Você fora (aprovado: "pode seguir", 2026-10-30)

Meta: a saída de _Você_ igual à tab humana em nota, corda/casa e duração, das 846 notas. O caminho é só aprender com
as outras tabs: Gesu, Dance of Death, Fear Is the Key, Plague, Eyrie e Fear of the Dark. _Você_ fica fora de todo
ajuste, calibração e escolha de opção. O placar é `avaliar_tablatura` (ataque 0,1 s, duração 0,05 s), com o mesmo
relógio do relatório de `out/Você/analise-algoritmo-2026-10-30`. As fontes sem tab humana não podem piorar.

1. [ ] **Linha de base honesta.** Toda opção (modelo, digitação, alcance) é escolhida só pelas seis tabs de treino.
   A régua, congelada antes de medir:
   - na digitação isolada, cada perfil e alcance (0 a 4) é medido nas seis tabs de treino;
   - vence a maior média por música, e só então _Você_ é medida com o vencedor;
   - o `medium` não foi validado fora de _Você_ (ADR-009 o mediu só em fixtures), então a linha de base informa
     `small` e `medium` lado a lado, sem escolher entre eles;
   - a candidata de 687 notas fica registrada como contaminada, porque o alcance 3 foi escolhido olhando _Você_.

   **Resultado: feito.** As seis tabs de treino escolhem `experiente` com alcance 0, média de 0,570 na digitação
   isolada. _Você_, medida só depois, fica em **0,738**. O alcance 3 tem média de treino de 0,537 e só subia _Você_
   para 0,936: foi escolha olhando a música de teste. O placar completo usa os GP5 regenerados do áudio, em
   `small` e `medium`, com `experiente` e alcance 0. O relógio é o recuo que maximiza os ataques pareados, na grade
   de 2 ms. Esse é um método novo, que dá à candidata 696 completas em vez das 687 do relatório; os números abaixo
   usam todos o mesmo método.

   | versão (846 notas humanas)                 | ataques | alturas | posições | durações | completas | faltam | sobram |
   | ------------------------------------------ | ------: | ------: | -------: | -------: | --------: | -----: | -----: |
   | `small`, experiente, alcance 0             |     779 |     746 |      549 |      732 |   **519** |     67 |     43 |
   | `medium`, experiente, alcance 0            |     807 |     789 |      585 |      761 |   **557** |     39 |     27 |
   | candidata `medium`, alcance 3 (contaminada) |     807 |     789 |      735 |      761 |       696 |     39 |     27 |

   A diferença entre `medium` e a candidata é só a digitação: 150 posições. A escolha do `medium` continua validada
   só em _Você_, porque não há inferência `medium` das seis tabs de treino.
2. [ ] Corda/casa aprendida das tabs de treino (plano detalhado e revisão Fable + Codex antes do código).

   **Plano detalhado, revisado por Fable e Codex (2026-10-30), aguardando confirmação.**

   As revisões apontaram quatro problemas no rascunho anterior:
   - logit local com Viterbi é um MEMM, com viés de rótulo, e foi treinado só com o contexto humano;
   - a regularização era escolhida na mesma validação que aprova o modelo;
   - _Você_ já está contaminada pelo ADR-050 e pelo alcance 3, então não serve como teste independente;
   - a régua aceitava ganho mínimo com perda grande.

   Desenho revisado:
   - **Conjuntos.** O treino são cinco tabs: Gesu, Dance of Death, Fear Is the Key, Plague e Eyrie. O teste limpo é
     _Fear of the Dark_, que nunca orientou decisão de digitação. A aceitação é _Você_, conhecida e contaminada.
     A base `experiente` com alcance 0 fica em 0,605 de média no treino, 0,395 em _Fear of the Dark_ e 0,738 em
     _Você_.
   - **Modelo.** Perceptron estruturado com média, treinado sobre o próprio Viterbi, com normalização global e
     decodificação igual à da inferência. As features são os termos do custo atual (casa, corda solta, Δmão,
     Δcorda), mais |Δcasa| em faixas, região da casa e Δmão × intervalo curto/longo, com corte em 0,25 s. Esse
     conjunto fica congelado agora. Ele nasceu em parte do diagnóstico de _Você_, o que fica registrado, e não muda
     depois de medir.
   - **Hiperparâmetros fixos antes de medir.** São 10 épocas, sem busca. Cada época tem o mesmo número de frases
     por música, para a música longa não pesar mais.
   - **Passo 0, barato.** Decompor os erros do `experiente` nas cinco tabs de treino: corda solta contra pisada,
     salto de região, troca de corda. Se a classe dominante não couber nas features, a 2a para aqui.

   Régua 2a, congelada:
   1. Na validação deixando uma de fora entre as cinco de treino, a média por música sobe pelo menos 0,02 sobre
      0,605. Nenhuma música perde mais de 0,03. Pelo menos 3 das 5 melhoram, e diferença menor que 0,005 conta como
      empate. Os resultados saem também por número de cordas.
   2. Com o modelo treinado nas cinco, _Fear of the Dark_ sobe acima de 0,395 + 0,02, medida uma vez.
   3. Aceitação em _Você_: a digitação isolada fica acima de 0,738, e o placar completo melhora as posições em
      `small` (acima de 549) e em `medium` (acima de 585), com o relógio e o cache da etapa 1.

   **Resultado 2a (2026-10-30): reprovado no item 1.** O passo 0 passou: 84% dos erros do `experiente` são "Thoth
   mais grave no braço, uma corda" (42,5%) e "Thoth solta, humano pisada" (41,3%). O Viterbi do script com os pesos
   iniciais reproduz o `experiente` nas cinco tabs. Na validação deixando uma de fora:

   | tab fora do treino | cordas | `experiente` | aprendida |      Δ |
   | ------------------ | -----: | -----------: | --------: | -----: |
   | Gesu               |      4 |        0,582 |     0,661 | +0,079 |
   | Dance of Death     |      4 |        0,387 |     0,479 | +0,092 |
   | Fear Is the Key    |      4 |        0,633 |     0,734 | +0,100 |
   | Plague             |      5 |        0,677 |     0,618 | −0,059 |
   | Eyrie              |      6 |        0,745 |     0,652 | −0,093 |
   | média              |        |        0,605 |     0,629 | +0,024 |

   A média sobe 0,024 e 3 de 5 melhoram, mas Plague e Eyrie perdem mais que 0,03. As três de 4 cordas ganham
   de 0,08 a 0,10; as duas de 5 e 6 cordas, do mesmo baixista, perdem. _Fear of the Dark_ e _Você_ não foram
   medidas. Scripts: `scratchpad/aprender/perceptron.py`, `loo.json`.

   **2a′ — só para baixo de 4 cordas (aprovado: "pode seguir", 2026-10-30).** A ideia nasceu de olhar a validação
   acima, não os testes; por isso a régua é nova e congelada antes de medir. O modelo é o mesmo `pesos.json`,
   treinado nas cinco tabs, sem novo treino nem ajuste. Ele vale só com afinação de 4 cordas; com 5 ou 6, a
   digitação continua `experiente`, igual por construção.
   1. Validação: cada tab de 4 cordas melhora pelo menos 0,02 fora do treino. Já cumprido pela tabela acima
      (+0,079, +0,092, +0,100) — não é evidência nova.
   2. _Fear of the Dark_ (4 cordas, faixa 4), medida uma vez: digitação isolada acima de 0,395 + 0,02 = 0,415.
   3. _Você_, só depois do item 2: digitação isolada acima de 0,738 e posições no placar completo acima de 549
      (`small`) e de 585 (`medium`).
   Falhou um item: registra e encerra a linha de digitação, sem nova tentativa.

   **Resultado 2a′ (2026-10-30): aprovado nos três itens**, cada teste medido uma vez.

   | medida                                   | `experiente` | aprendida |   piso |
   | ---------------------------------------- | -----------: | --------: | -----: |
   | _Fear of the Dark_, isolada (2297 notas) |        0,395 |     0,800 |  0,415 |
   | _Você_, isolada (846 notas)              |        0,738 |     0,858 |  0,738 |
   | _Você_ `small`, posições no placar       |          549 |       618 |    549 |
   | _Você_ `medium`, posições no placar      |          585 |       633 |    585 |

   No placar, só posições e completas mudam (`small` 519 → 581, `medium` 557 → 597); ataques, alturas, durações,
   faltam e sobram são idênticos, como devem ser. A candidata contaminada tinha 735 posições: a diferença para 633
   é o que a digitação aprendida ainda não alcança. Scripts: `item2.py`, `item3.py`, `gerar.py` (troca o assigner
   da CLI) no scratchpad; GP5 em `scratchpad/aprender/aprendida-{small,medium}/Você/`.

   Se qualquer item falhar, o resultado é registrado sem nova tentativa olhando os testes. Passar na régua não
   entrega as 846 notas: a digitação não corrige notas que faltam, alturas ou durações.

   2b, só se a 2a passar: ADR-055, TDD e um `FretAssigner` novo atrás do `Protocol` (`--digitacao aprendida`).
   Os pesos ficam versionados com os hashes do corpus, as features e os hiperparâmetros. O treino é reproduzível por
   script e conferido por teste `slow`; o default só muda com ADR próprio. A evidência acústica de corda (piloto
   SVM: 745 contra 728 em _Você_, regressão em Plague) fica para depois, como custo de emissão atrás de um `Protocol`
   e com a mesma régua.

   **2b feita (2026-10-30, ADR-055):** `services/digitacao_aprendida.py` + `digitacao_aprendida.json` (pesos, sha256
   das 5 tabs, hiperparâmetros), `--digitacao aprendida` na CLI. O treino pelo código de produção reproduz os pesos da
   régua bit a bit. `-m slow` do módulo: 4 passaram (hashes, retreino, _Fear of the Dark_ 0,800, _Você_ 0,858). A CLI
   real gera o mesmo GP5 do script (633 posições, 597 completas). 18 fontes sem tab: nenhuma falha, ≤ 0,14 s. Suíte
   padrão 807 passaram; ruff e mypy limpos. Falta a API oferecer `aprendida`.
3. [ ] Notas que faltam e sobram: filtro aprendido nas tabs de treino.
4. [ ] Duração: figura escrita aprendida nas tabs de treino.
5. [ ] Em cada etapa, conferir as fontes sem tab e gerar a nova _Você_ para abrir no Guitar Pro.

## Transcrição de Você igual à referência humana — objetivo corrigido (2026-10-30)

O usuário esclareceu que a tarefa exige modificar o programa para obter o
resultado humano a partir do áudio. A derivação `.referencia` entregue antes
não atende ao pedido. Assumir `samples/catedral-voce_build.gp5` correto, inclusive
ritmos e corda/casa; não aceitar apenas altura MIDI ou F1 alto como igualdade.
O trabalho de correção do programa continua autorizado; não repetir a aprovação
do escopo. Não usar a tab como entrada da inferência nem codificar exceções por
título, tempo da música ou notas copiadas. Manter os arquivos existentes.

Origem: serviços e medições locais (ADR-021, 032, 033, 041, 042, 050, 053).
Banco de soluções consultado; não há solução de transcrição musical entre os
projetos catalogados. Hipótese inicial: a política de digitação para iniciante
favorece corda solta e mede só altura; avaliar antes de alterar.

1. [x] Estabelecer diagnóstico por alturas, ataques, durações e corda/casa, com
   referência humana e recursos reais; conferir numeração de cordas.
2. [ ] Reproduzir causas em testes e corrigir o algoritmo, sem memorizar a música.
3. [ ] Regenerar do áudio, medir igualdade e verificar regressões nas outras tabs,
   pytest, Ruff e mypy. Registrar qualquer diferença restante explicitamente.

Riscos: o modelo não fornece corda/traste e preenche durações até o ataque
seguinte (ADR-033); inferir execução exata pode exigir informação adicional ou
outro método. Não prometer igualdade sem verificá-la. Mudanças de arquitetura,
se necessárias, exigem ADR. Exploração/revisão do plano: `explorar_comparacao`
e `diagnosticar_ritmo_notas`, somente leitura, antes de escolher alterações.

Progresso do programa, sem copiar a tab: leitor preserva corda/casa e afinação;
`avaliar_tablatura` mede ataques, alturas, posições, durações, omissões e extras,
sem reutilizar pares. Viterbi aceita alcance da mão (CLI `--alcance-mao`), com
janela preservada nas cordas soltas. CLI aceita `--modelo medium` para o baixo,
com cache por identidade e sem mudar os defaults dos outros instrumentos.

O teste do caso Sol3/Ré5/Sol3 voltou a falhar ao reverter somente a janela:
escolheu Ré solto e o GP5 relido teve 2/3 notas completas. Restaurada a correção,
o caso passa com 3/3. Alcance 3 melhora a digitação isolada de Você de 0,738 para
0,936, mas piora três outras tabs; permanece opcional, não padrão.

Execução real via CLI, sem referência como entrada: medium, experiente, alcance
3 → 834 notas após três descartes (837 brutas). Candidata em
`out/Você/analise-algoritmo-2026-10-30/candidata/Você/`. Avaliação no mesmo
relógio (fase da partitura devolvida), tolerância de ataque 100 ms e duração
50 ms: 687 eventos completos contra 517 da small/iniciante anterior, sobre 846
referências. **Não coincide com o gabarito**: ainda há 29 Ré gerados em corda
solta, notas ausentes/extras e figuras rítmicas divergentes. As etapas 2 e 3
permanecem abertas; 755 testes de software passando não encerram o objetivo.

Experimentos rejeitados para produção: preencher buracos com detector de ataques
(5 candidatos corretos/35); mapa curto, mais largo e menos penalizado (fabrica
35 trocas no controle Equus); correção YIN+harmônicos (três semitons corrigidos
em Você, ainda sem validação nas outras músicas). Não aplicar regras por título
nem substituir eventos da inferência pelos da tab para fazer o teste passar.

Verificação desta etapa: 755 testes padrão passaram, Ruff zero diagnósticos,
mypy zero erros em 46 arquivos. MuScriptor medium real executado em CPU e
pipeline real gerou GP5/MusicXML/WAVs e auralização. Relatório e scripts de
medição ficam em `out/Você/analise-algoritmo-2026-10-30/`; a tarefa geral não
está concluída. Não há revisor arquitetural específico de áudio no harness;
o plano e a hipótese da janela foram conferidos pelo `explorar_comparacao`.

Critério estrito agora reproduzido em cinco testes privados de GP5 real:
quantidade, sequência de alturas, corda/casa, figuras/durações e andamento
inicial. **Os cinco falharam**: 834/846 notas, divergências de altura e posição,
terceira figura 0,75/0,5 semínima e andamento 116/106. O teste está em
`out/Você/analise-algoritmo-2026-10-30/scripts/test_fidelidade_voce.py` e não
confunde igualdade da tab com tolerância de áudio. Não declarar o objetivo
concluído porque a suíte portável passou.

Piloto adicional executado por `piloto_corda_acustica`, sem produção: alinhamentos
independentes das quatro outras tabs, features de harmônicos/envelope, SVM fixo
e validação deixando uma música fora. Você não entrou no treino. Na inferência
dos 834 eventos MuScriptor, sem consultar gabarito, 789 tiveram previsão e 45
ficaram sem evidência. Avaliação posterior: nas mesmas 765 notas com altura e
ataque pareados e cobertura acústica, posição correta 745 no SVM contra 728 no
Viterbi3. Entre 135 Ré2 pareados: 133 Lá/5 e dois Ré/0 no SVM, contra 108 e 27
no Viterbi3. Não integrado: cobertura incompleta, regressão em Plague na
validação e nenhuma correção das notas e ritmos restantes. Dados e relatório
reproduzíveis em `out/Você/analise-algoritmo-2026-10-30/corda-acustica/`.

## Correção de Você contra a tab humana (2026-10-30)

Plano aprovado pelo usuário. Referência: `samples/catedral-voce_build.gp5`;
saída antiga de 30/09: 802 notas, 120 BPM fixos. A referência contém 846
notas executadas, repetições e mudanças de andamento. Reaproveitar ADR-041/042
para comparar e ADR-053 para regenerar, sem presumir que 44 notas de diferença
na contagem sejam exatamente 44 omissões.

1. [x] Preservar a saída antiga e regenerar com o pipeline atual e caches compatíveis.
2. [x] Medir a saída relida contra a referência; corrigir somente defeitos comprovados,
   com teste antes de qualquer alteração de código.
3. [x] Validar GP5/MusicXML e executar pytest, Ruff e mypy; registrar os limites.

Dependências reais: GP5 via PyGuitarPro, MusicXML via music21 e áudio local.
Não usar mocks na medição. O cache Demucs antigo (`4.1.0`) não corresponde ao
atual (`4.1.0-shifts0`); preservar ambos e gerar o atual quando necessário.
Subagente: `explorar_comparacao` (`explorer`, leitura das decisões e métodos).

Diagnóstico durante a execução: as 802 alturas do GP5 antigo são idênticas às
do cache, na ordem; o arquivo relido antecipa ataques em 30–420 ms. O GP5 grava
119,86 como 120 BPM, conforme a limitação do ADR-021. O MusicXML também era
arredondado sem necessidade: `sound@tempo` aceita decimal na especificação W3C.
Corrigir esse arredondamento após reproduzir a deriva em teste de arquivo real;
preservar a quantização e o contrato do GP5. Mudança de uma camada, sem decisão
arquitetural nova; emendar o ADR-021 para corrigir a premissa sobre MusicXML.

Resultado: saída automática regenerada e publicada em `out/Você`, com 822 notas
(antes: 802), mapa com dois pontos de troca e auralização real sem falha. O F1 de
altura + ataque no tempo do áudio foi de 0,915 para 0,926; no MusicXML relido,
de 0,178 para 0,885. Não são porcentagens de alturas corretas. O GP5 continua
limitado ao BPM inteiro e a transcrição automática ainda difere da referência.

Entrega corrigida supervisionada: `Você.referencia.gp5` e
`Você.referencia.musicxml`, ambos com as 846 notas humanas, mantendo cordas e
casas. O GP5 mantém as repetições; o MusicXML as escreve por extenso. Dois testes
locais de arquivo real confirmaram alturas, ataques, durações e digitação.
Não afirmar que essa derivação é melhoria do modelo nem sincronismo com a gravação.

Código: MusicXML preserva andamento decimal nos exportadores de cordas, piano
e bateria. TDD: seis falhas antes, seis testes passando depois; retirar apenas o
fix reproduziu cinco falhas. Verificação: 730 testes padrão passaram; Ruff zero
diagnósticos; mypy zero erros em 46 arquivos. Cinco testes do MuseScore real
passaram. Demucs e MuScriptor reais executados separadamente, em CPU. Backups,
medições, scripts e relatório estão em `out/Você/comparacao-2026-10-30/`.

## Alinhamento das configurações locais aos globais (2026-10-30)

Plano aprovado pelo usuário: manter a herança dos globais do Claude Code e do Codex,
preservando as exceções do Thoth (projeto pessoal, sem Django ou Infisical).
Origem conferida: regras e configurações instaladas dos dois harnesses e
`claude-md/installer/rules.py`. Sucesso: instruções locais coerentes com os globais,
permissões locais específicas e verificação de entrega passando.

1. [x] Conferir a herança e registrar o plano. Subagente `conferir_heranca`
   (`explorer`, `gpt-6-luna`, esforço `high`): auditoria somente de leitura.
2. [x] Atualizar `AGENTS.md` e `CLAUDE.md`: herança, leitura prévia e exemplos
   headless com modelo/esforço explícitos. Preservar os detalhes do projeto.
3. [x] Conferir permissões locais, validar os arquivos e executar pytest, Ruff e mypy.

Verificação: JSON válido, herança global e restrição de leitura de áudio preservadas;
`git diff --check` sem erros. `uv run pytest -n auto`: **725 passaram**, 40 avisos de
depreciação de dependências, em 28,93 s. `uv run ruff check src/ tests/`: **0 erros**.
`uv run mypy src/`: **0 erros em 46 arquivos**. A suíte padrão exclui `slow`,
`network` e `navegador`; essas camadas não foram alteradas nesta tarefa.

Trade-off: manter modelos, esforço, subagentes e hooks nos globais evita cópias que
ficariam desatualizadas. Remover a autorização genérica de `uv run python` faz esse
comando voltar ao fluxo normal de aprovação. Nenhuma alteração de arquitetura.

## Backlog aberto, com Codex e subagentes (2026-10-23)

Pedido do usuário: "pode fazer tudo", usando o Codex e os agentes, depois de alinhar a configuração dos dois
harnesses ao `CLAUDE.md` global. Escrita sequencial no repositório; medições em paralelo, com script em scratchpad e
número impresso ao lado do piso.

0. [x] Configuração: `AGENTS.md` com o mapa de módulos atual e a consulta entre agentes; skill `verificacao` para o
   Codex em `.agents/skills/`, espelho do `/verificacao`.
1. [x] Mapa de andamento, etapa 1b (Claude): resíduo do mapa **contínuo** (fase herdada, troca de andamento só quando
   paga) nas 15 músicas do cache, e quantas trocas ele escreve nas planas. Emenda ao ADR-034; sem código de produto.
   **Resultado:** com λ pequeno o mapa sobreajusta (fora da amostra, pior que o andamento único em 3 músicas). Com
   λ = 2000 ms·nota, nenhuma piora, zero trocas nas planas e ganho de até 41% fora da amostra em 12 das 21 fontes.
   A etapa 2 (produto) depende de decisão.
2. [x] Demucs `--shifts 0` (Codex, worktree): o stem do baixo fica idêntico entre duas rodadas? Os pisos do baixo e
   o F1 se mantêm? Adotar só se a medição sustentar; senão, registrar por quê.
   **Resultado:** WAV byte a byte idêntico no `misto` (antes: pico 0,048, SNR 29,9 dB); 115 métricas de piso iguais
   antes e depois, 48 testes pesados passaram nas duas rodadas. **Adotado**: escopo do cache `4.1.0-shifts0`, stems
   antigos ficam no disco sem reuso. Emendas aos ADR-010, 026 e 044.
3. [x] Discriminador de oitava para baixo (subagente): as tabs de *Você* e *Gesu* (2026-09-30) são posteriores à
   última medição do ADR-030. Remedir o AUC com as seis tabs; candidato novo só se a amostra ampliada o permitir.
   **Resultado:** as duas somam 5 casos "abaixo"; AUC agregado 0,748 (44 casos, 26 numa música só). Nenhum candidato
   testado, veredito igual. Emenda de 2026-10-23 ao ADR-030.
4. [x] *Eyrie*, entrada e saída de cada stem (subagente): energia por stem no tempo, como audibilidade — não é
   veredito musical (ADR-048). Referência humana por parte continua inexistente; o item 6 de lá depende dela.
   **Resultado:** intervalos por stem estáveis entre 20 e 50 dB abaixo do pico; eventos do pipeline dentro da presença
   (bass 99,9%, bateria 100%, vocais 78,1%). Por parte continua pendente. Emenda de 2026-10-23 ao ADR-048.
5. [x] Verificação de entrega e registro de cada resultado aqui e no ADR da área.
   pytest padrão 709 passaram; ruff limpo; mypy sem erros (46 arquivos); Demucs real em develop: 4 passaram.
6. [x] Conferir as trocas de ~10 bpm do mapa contra a tab humana de *Dance of Death*.
   **Resultado:** as três trocas escritas são reais (mediana de 2 bpm da gravação entre 220 e 460 s). O que falta é o
   trecho lento (83 a 90 bpm) e os de 150, fora da faixa de ±10% (116 a 142). Emenda ao ADR-034.

## Mapa de andamento, etapa 2 (aprovada em 2026-10-23)

1. [x] Medir a largura da faixa (só medição): ±10% atual, faixa larga (±40%) e ±10% com metade/dobro como candidatos,
   nas 21 fontes, com o controle fora da amostra da etapa 1b. Critério: nenhuma música pior que o andamento único,
   nenhuma troca nas planas e o trecho lento de *Dance of Death* alcançado. Se nenhuma opção cumprir, fica ±10%.
   **Resultado:** nenhuma cumpriu (±40% alcança o trecho lento piorando 4 músicas; ±40% sem troca piora 9). Fica
   ±10% com custo em ms e λ = 2000. Emenda ao ADR-034.
2. [x] `services/tempo`: `mapa_de_andamento(onsets, bpm, λ)` → trechos `(início, bpm)`, trocas puxadas para a barra de
   compasso mais próxima. TDD, com estímulo sintético de andamento conhecido. O primeiro trecho é reajustado e o BPM
   depois da troca é refinado junto com a barra: sem isso, a troca saía um compasso antes (ADR-053).
3. [x] `rhythm` quantiza cada trecho no próprio andamento; música plana sai idêntica à de hoje (teste de regressão).
   Fora da amostra: nenhuma música pior que +0,2%, planas sem troca, *And Plague Flowers* −45%.
4. [x] Exportadores: andamento por compasso no GP5 (`mixTableChange`) e no MusicXML (`<sound tempo>` + metrônomo).
   Round-trip afirmando estrutura (em que compasso troca, para qual BPM).
5. [x] Auralização e cursor da página de estudo seguindo o mapa (`-m navegador`).
6. [x] ADR novo (ADR-053), verificação de entrega e seleções `slow` e `navegador`.

## Eficiência: revisão conjunta Claude + Codex (2026-10-23)

Revisão somente leitura: Claude (`fable`) e Codex (`gpt-6.1-sol`, `high`). Os achados principais foram conferidos na
fonte. Linha de base: suíte padrão em 39 s de relógio (487 s de CPU em 20 workers). [M] = medido pelo revisor, [E] =
estimado. Cada mudança começa por um teste de equivalência com a versão atual (saída idêntica), não só pelo teste
existente.

### Lote A — risco baixo, sem ADR

1. [x] MusicXML: `makeNotation(inPlace=True)` nos três exportadores (`musicxml.py:114, 439` e piano). [M] 3.000
   notas: 17,4 s → 11,5 s, saída idêntica. `write(makeNotation=False)` muda a saída: não usar.
2. [x] `tempo.ajustar`: vetorizar as 120 fases por BPM (mediana em `axis=1`, primeiro mínimo no desempate). [M] 64
   onsets: 1,9 s → 0,1 s; 3.000: 12,7 s → 4,7 s. A grade do ADR-021 não muda.
3. [x] Imports leves: `TOLERANCIA_S` sai de `evaluation` (que puxa `mir_eval`/`scipy`/`pretty_midi`) para o
   domínio; `fastapi`/`uvicorn` importados só no `serve`. [M] ~1,6 s a cada processo da CLI e worker do xdist.
4. [x] `test_trecho_denso_fecha_beams_e_so_encolhe_duracao`: 60 sementes parametrizadas. É a cauda da suíte (25 s).
5. [-] Fixtures caras compartilhadas por worker (`tests/conftest.py` novo): MIDI renderizado, MP3 de
   `test_local_source`, auralização de `test_auralizacao`. Cópia para `tmp_path`, bytes idênticos (a fixture é
   **copiada**, não reescrita; `lessons/workflow.md`).
   Medido, não compensa: o setup mais caro dessas fixtures é ≤ 0,33 s; a cauda era o item 4.
6. [x] Modo `todos`: `fetch` uma vez, o `AudioAsset` passa às partes (hoje são 5 hashes e 5 `ffprobe`).
7. [x] MuScriptor: o silêncio inicial da bateria (ADR-045) é escrito em blocos, sem duas cópias do stem na memória.
8. [x] Ganhos pequenos, mesma natureza: eventos do GP5 indexados por compasso (O(c×e) → O(c+e)); média do caminho do
   DTW por `bincount`; `octave_check` com frequências e índices de banda pré-calculados; `tempo.residuo` sem
   reconverter a lista de onsets.

### Lote B — ganho grande, pede ADR ou emenda antes

9. [x] Cache em disco da transcrição bruta do MuScriptor, chave = sha256 do stem + identidade dos pesos
   (`models.lock.toml`) + versão do adapter, escrita atômica (ADR-026). Hoje mudar só `--bpm` ou a digitação
   retranscreve a música (minutos de CPU); `notas.jsonl` (ADR-020) guarda as notas já processadas e não evita isso.
   ADR-052. Real: `escala` 5,7 s no modelo, 0,006 s do disco, saída igual.
10. [-] Modo `todos` roda o Demucs duas vezes (two-stems do baixo + separação completa). Duplicação deliberada na
    emenda de 2026-09-27 ao ADR-047; só muda se o `bass.wav` das duas for medido idêntico ou equivalente.
    Medido, não muda: nos 15 pares do cache, nenhum byte a byte igual; SNR de 19,4 a 31,8 dB, pico da diferença até
    0,31. Trocar a fonte do stem mudaria a entrada medida do baixo — equivalência exigiria remedir F1, não compensa.

### Aberto

- [x] `test_mede_perfil[piano-acustico-mix]` e `[piano-eletrico-mix]` falhavam ("mão esquerda regrediu", 1 < 3)
  desde o `1c91fcf`. Não era o modelo nem o fluidsynth (2.6.0 falha igual): o piso foi medido quando o transcritor
  devolvia `drums` como nota, e a `Transcricao` passou a pô-los em `ataques`, fora de "qualquer rótulo". Com os
  ataques de volta, 3/8 exatos nos dois pianos. Causa confirmada pelo Codex (`gpt-6.1-sol`, leitura).
- [x] `test_mede_perfil[guitarra-acustica-mix-stem]` intermitente nos acordes de seis notas (21 < 22): três rodadas
  sem mudança deram 23, 21 e 21 — variação do Demucs. Folga dos acordes de seis no `mix-stem` passou a 2 notas,
  como a `FOLGA_DEMUCS` do F1 já absorvia (emenda do ADR-044, 2026-10-23).
- [x] Demucs determinístico (`--shifts 0`): adotado em 2026-10-23 (item 2 do backlog do topo).
- [ ] Tirar as folgas do `mix-stem` (`FOLGA_DEMUCS`, `FOLGA_DEMUCS_SEIS_NOTAS`): só depois de rodadas repetidas com
  `shifts 0` mostrarem a contagem estável.

### Fora, por ora

- Segunda passada do MuScriptor só nos buracos: mexe em comportamento medido (F1).
- DTW em banda sem matriz densa (ADR-042): risco alto, só se a memória virar problema.
- Espectrograma compartilhado entre os estimadores de andamento (ADR-019), cache da auralização (ADR-037), busca
  grossa → fina na comparação: ganho incerto para o risco.

## Revisão conjunta Claude + Codex do código inteiro (2026-10-22)

Revisão somente leitura: Claude (`fable`) e Codex (`gpt-6.1-sol`, `high`). Os achados foram conferidos na fonte antes de
entrar aqui; cada correção nasce de um teste vermelho.

1. [x] `transcribe --tom` validado e descartado: encaminhar ao pipeline (ADR-031).
2. [x] `todos`: grade e recuo de fase comuns a todas as partes — a mesma nota cai no mesmo tick em toda faixa.
3. [x] `todos`: parte sem evento exportável é relatada como ausente, não derruba a música (ADR-014); sem decidir
   por prefixo de mensagem.
4. [x] `todos`: diagnósticos de guitarra e bateria chegam ao resultado; histograma de `other` contado uma vez.
5. [x] Baixo com todas as notas fora do braço: erro claro antes de exportar.
6. [x] yt-dlp: só hosts do YouTube; o downloader recebe a URL canônica montada do ID.
7. [x] `/uploads`: leitura em blocos com teto, hash incremental, escrita fora do event loop; `escrita_atomica` com
   temporário exclusivo (upload `foo.parcial.wav` não pode apagar outro).
8. [x] Jobs: uma thread trabalhadora com fila FIFO (ADR-027) e o dicionário de jobs sob trava.
9. [x] `POST /jobs`: `ref` local restrita; `TrustedHostMiddleware` contra DNS rebinding.
10. [x] Nome de saída limitado em bytes, com espaço para o maior sufixo.
11. [x] `comparar` usa o escopo de stem do `DemucsSeparator` (ADR-026). `escopo` ficou público; stem de outra
   versão do demucs dá "sem stem do baixo".
12. [x] Upload chamado `mix.wav` mantém o título: a pasta passou a ser o sha256 inteiro, que `LocalFileSource` não
   confunde com cache (emenda ao ADR-051).
13. [x] Ligaduras rastreadas por voz e corda em `tab_referencia` e `guia_estudo`; fixture GP5 de duas vozes.
14. [x] MuScriptor: energia por segundo lida em blocos (`sf.blocks`); teste prova que `sf.read` não é chamado.
15. [x] Página: `Paused → Stopped` do MPRIS volta o cursor ao início (ADR-046); teste `navegador` com player falso.
16. [x] Arquitetura: `PECAS_DA_BATERIA` e `PECAS_POR_ATAQUE` em `domain/instrumentos.py`, seguidas pelos
   exportadores; `ROTULOS_DE_BAIXO` é `PERFIS["baixo"].rotulos`. Avaliadas e mantidas: `pipeline`/`vocais`
   importando adapters (são a raiz de composição) e `gp5`/`musicxml` importando `services.rhythm`/`notas` (lógica
   pura, sem I/O).
17. [x] Docstrings e comentários conferidos contra os ADRs (`instrumentos`, `pipeline`, `auralizacao`, `demucs`,
   página). `ExportadorDePiano` mantido: tem uso planejado no M3 do ADR-044 e implementação testada
   (`MusicXmlPianoExporter`).
18. [x] Teste de upload com WAV real passando por `LocalFileSource` (nome acentuado e `mix.wav`).
19. [x] Verificação de entrega (`pytest -n auto`, `-m navegador`, `-m "slow and not network"`, `ruff`, `mypy`),
   emendas aos ADR-026, 027, 047 e 051, e README.

## Página de estudo: abrir arquivo e tocar com WAV (2026-10-22)

Abrir arquivo pelo seletor do sistema (`.mp3`, `.wav`, `.gp5`, `.musicxml`). O áudio é transcrito; GP5 e MusicXML só
abrem na tela. Um WAV escolhido toca sincronizado com a pauta (ADR-051).

1. [x] `POST /uploads`: recebe o áudio, recusa extensão fora da lista, devolve a `ref` (teste de API real).
2. [x] Página: botão "Abrir arquivo…" — áudio vira upload + job; GP5/MusicXML abrem direto no alphaTab (teste
   `navegador`).
3. [x] Página: "Tocar com WAV…" — `<audio>` local no modo *external media*, cursor segue o áudio (teste `navegador`).
4. [x] Verificação de entrega (`pytest -n auto`, `-m navegador`, `ruff`, `mypy`) e README.
   **Resultado:** suíte padrão 575 passed; `-m navegador` 19 passed (numa primeira rodada,
   `test_o_formulario_manda_afinacao_e_digitacao_por_nome` falhou uma vez e passou isolado e na repetição);
   ruff e mypy limpos. O alphaTab encaixa a posição no início do tempo ao pausar e repassava isso como `seekTo`,
   puxando o WAV para trás; a pausa vinda do áudio agora ignora esse eco (teste cobre).

## Tabs humanas como referência: digitação, andamento e nota errada (2026-09-30)

Comparação de _Você_ (Catedral) e _Watashi Igai Watashi Ja Nai No_ (Gesu) com tabs humanas de `samples/`: nota certa
95,6% e 82,0%; corda/casa iguais em 74% e 43%; andamento de _Você_ 120 contra 106 da tab humana.

1. [x] Digitação: medir os perfis contra as 6 tabs de baixo de `samples/` (alturas humanas → Viterbi → corda humana);
   recalibrar só o `experiente` (o default `iniciante` é do ADR-006), com teste de frase real e ADR.
   **Resultado:** concordância de corda média 0,521 → 0,627, sem piorar nenhuma tab (ADR-050).
2. [x] Andamento de _Você_: achar a causa do 120 contra 106 antes de propor correção.
   **Resultado:** não é erro. A tab humana acelera de 106 a 124 (média 116,2); o Thoth escreve um BPM só (119,86).
   Limite já conhecido do ADR-034, registrado como emenda; nenhum código mudou.
3. [x] Nota errada em _Gesu_: localizar onde se concentram os 15,6% (registro, trecho, tipo de erro).
   **Resultado:** 78 de 103 erradas são a altura da nota vizinha. A causa é o DTW, que deixava a tab 18 a 50 ms
   atrasada. Ajuste fino pelos ataques do stem (emenda ao ADR-042): errada de _Gesu_ 15,6% → 9,1%, melhora em
   quatro de cinco tabs, nenhum piso subiu.
4. [x] Verificação de entrega e registro dos resultados.
5. [x] Mapa de andamento por trecho, etapa 1 (medir): por janela de 20 s acompanha a tab humana de _Você_ (erro
   mediano 0,3 contra 2,7 BPM do global) e nunca erra mais que o global nas cinco tabs; a razão do ADR-034 não
   separa; resíduo da grade cai 35–73% no acervo inteiro, com fase livre (teto otimista). Emenda ao ADR-034.
6. [x] Mapa de andamento, etapa 1b: resíduo de um mapa contínuo (fase herdada, mudança só quando paga) e quantas
   mudanças ele escreve nas músicas planas. Só depois decidir exportadores e pipeline.
   **Resultado (2026-10-23):** candidato λ = 2000 ms·nota; ver a emenda do ADR-034 e o item 1 do backlog do topo.

## Conformidade Markdown do repositório (2026-09-29)

1. [x] Aplicar correções automáticas seguras com `.markdownlint-cli2.jsonc`.
2. [x] Corrigir manualmente os diagnósticos restantes sem alterar o sentido.
3. [x] Rodar o lint em todos os Markdown selecionados e revisar o diff completo.

## Reprocessamento multifaixa do acervo (2026-09-28)

**Plano (execução não interativa):** reprocessar as músicas reais do acervo com o perfil `todos`, começando por _Thalles
Roberto - A Resposta (vídeo oficial)_. Usar os URLs correspondentes aos IDs já registrados em `cache/` para aproveitar a
mix e as notas de baixo existentes. Preservar a afinação de cinco ou seis cordas das músicas que a usam. Deixar _Eyrie_
fora do lote por já ter sido concluída, e ignorar a fixture `misto` e a cópia técnica `.aural`.

1. [x] Reprocessar e conferir _A Resposta_: GP5/MusicXML multifaixa com Baixo e Bateria; as três categorias de guitarra
   não tiveram eventos válidos. Os dois guias de estudo foram regenerados e a afinação de quatro cordas foi preservada.
2. [x] Reprocessar as outras 12 músicas e comunicar cada conclusão: _Dance of Death_, _Fear Is the Key_, _Fear of the
   Dark_, _Feel Like Makin' Love_, _Hallowed Be Thy Name_, _And Plague Flowers the Kaleidoscope_, _Equus_, _Everything
   Changes_, _SOU EU_, _Is It A Crime_, _Smooth Operator_ e _Tive Razão_. Todos os GP5/MusicXML multifaixa e os guias
   solo/multifaixa foram gerados e conferidos; os perfis sem eventos válidos foram relatados e as afinações de quatro,
   cinco ou seis cordas foram preservadas.
3. [x] Conferir cobertura: 13 músicas do acervo reprocessadas, _Eyrie_ excluída por já estar concluída; GP5 e MusicXML
   com faixas disponíveis, guias solo e multifaixa presentes, sem falhas finais. As faixas incluídas dependem dos
   eventos válidos encontrados nos stems; o processamento em CPU não garante que cada música tenha eventos em todas as
   categorias de guitarra.

### Resultado por música (GP5/MusicXML `todos`)

| Música | Afinação do baixo | Faixas presentes |
| --- | ---: | --- |
| _A Resposta_ | 4 cordas | Baixo, Bateria |
| _Dance of Death_ | 4 cordas | Baixo, Guitarra distorcida, Guitarra acústica, Bateria |
| _Fear Is the Key_ | 4 cordas | Baixo, Guitarra distorcida, Bateria |
| _Fear of the Dark_ | 4 cordas | Baixo, Guitarra distorcida, Bateria |
| _Feel Like Makin' Love_ | 4 cordas | Baixo, Guitarra limpa, Bateria |
| _Hallowed Be Thy Name_ | 4 cordas | Baixo, Guitarra distorcida, Guitarra acústica, Bateria |
| _And Plague Flowers the Kaleidoscope_ | 6 cordas | Baixo, Guitarra acústica, Bateria |
| _Equus_ | 5 cordas | Baixo, Guitarra limpa, Guitarra distorcida, Guitarra acústica, Bateria |
| _Everything Changes_ | 4 cordas | Baixo, Guitarra limpa, Guitarra acústica, Bateria |
| _SOU EU_ | 4 cordas | Baixo, Guitarra distorcida, Guitarra acústica, Bateria |
| _Is It A Crime_ | 4 cordas | Baixo, Guitarra limpa, Guitarra distorcida, Bateria |
| _Smooth Operator_ | 4 cordas | Baixo, Guitarra limpa, Bateria |
| _Tive Razão_ | 4 cordas | Baixo, Guitarra acústica, Bateria |

_Eyrie_ já tinha sido processada separadamente e não integra as 13 acima.

## Guias de estudo das músicas do acervo, exceto _Eyrie_ (2026-09-28)

**Plano (execução não interativa):** gerar os guias Markdown com `thoth estudar` para os GP5 musicais já presentes em
`out/`, começando por _Thalles Roberto - A Resposta (vídeo oficial)_. Incluir as versões solo e multifaixa quando houver
baixo em ambas. Excluir _Eyrie_, a fixture sintética `misto` e a cópia técnica `.aural`; arquivos sem faixa de baixo
serão relatados.

1. [x] Gerar e conferir os dois guias de _Thalles Roberto - A Resposta (vídeo oficial)_: 431 ataques, primeiro ataque no
   compasso 23 e tom candidato F# menor (margem 0,28) em ambos.
2. [x] Gerar e conferir os guias das outras 12 músicas com faixa de baixo, informando a conclusão de cada música.
3. [x] Conferir a cobertura: 14 GP5 musicais alvo, 14 guias presentes e completos, sem falhas; os dois guias
   preexistentes de _Eyrie_ ficaram fora do lote. O tom de cada guia é candidato inferido da linha de baixo, sujeito a
   conferência harmônica.

## Publicação do guia didático (2026-09-28)

1. [x] Revisar o diff e executar a verificação de entrega antes do commit: 561 testes padrão, Ruff e mypy passaram.
2. [x] Criar o commit `4bceeb5` da implementação e publicar `develop` em `origin`.
3. [x] Integrar `develop` em `main` pelo merge `710b978` e publicar o branch de produção em `origin`.

## Teste do guia com _Eyrie_ (2026-09-28)

1. [x] Gerar Markdown a partir dos GP5 de baixo solo e multifaixa já existentes em `out/Ne Obliviscaris - Eyrie/`.
2. [x] Conferir as saídas: ambas selecionam `Baixo`, apresentam 1.578 ataques, primeiro ataque no compasso 23, afinação
   E1-A1-D2-G2 e tom candidato A menor (margem de grafia 0,37). A comparação de altura, corda, casa, compasso, posição e
   duração encontrou zero diferenças entre os ataques. As pausas escritas são 154 na tab solo e 163 na multifaixa.
3. [x] Corrigir o título `mix` herdado dos GP5 antigos, explicar a entrada tardia do baixo e verificar: 561 testes
   padrão, Ruff e mypy passaram. Os dois guias finais estão ao lado dos respectivos GP5.

## Guia didático de tablatura de baixo (2026-09-28)

**Plano (execução não interativa):** criar `thoth estudar <arquivo.gp5>` para ler uma tablatura local já produzida e
gerar Markdown em português, sem repetir a transcrição. O relatório distinguirá observações da tab, conceitos gerais e
hipóteses musicais. Técnicas de execução e intenção harmônica não serão apresentadas como fatos quando não estiverem
codificadas no arquivo.

1. [x] Pesquisar teoria e técnica de baixo; conferir as limitações do GP5 e os ADRs.
2. [x] Escrever testes de leitura real do GP5 e das explicações por nota, inclusive intervalos, oitavas, quintas, ritmo
   e incerteza de técnica.
3. [x] Implementar o gerador Markdown e o comando CLI com seleção de faixa e caminho de saída.
4. [x] Documentar uso, registrar decisão arquitetural e verificar: 557 testes padrão, Ruff e mypy passaram; `thoth
   estudar` gerou Markdown de `out/misto/misto.gp5`.

### Emenda — estimar o tom a partir da tablatura

1. [x] Testar com GP5 real a estimativa automática, a indicação de incerteza e a precedência de `--tom`.
2. [x] Reutilizar `estimar_tom` sobre as notas lidas do GP5; mostrar origem e margem no guia sem tratar a margem como
   confirmação de tônica/modo.
3. [x] Atualizar README, ADR e lição; 559 testes padrão, Ruff e mypy passaram; comando real gerou o guia de
   `out/misto/misto.gp5`.

## Contrato livre do transcritor e metadados MusicXML (2026-09-28)

**Plano (execução não interativa):** ignorar suporte a piano conforme orientação do usuário; registrar MPRIS como aceito
conforme confirmação do usuário; generalizar a saída do transcritor para notas e ataques de bateria, remover o seletor
de instrumento do contrato e corrigir nomes/título das partes no MusicXML multifaixa.

1. [x] Escrever testes de regressão primeiro para o parsing completo do JSONL, o contrato e a passagem da transcrição
   estruturada pelo pipeline.
2. [x] Implementar o retorno `Transcricao` e adaptar filtros/consumidores preservando comportamento de baixo, guitarra e
   bateria.
3. [x] Escrever testes primeiro para metadados corretos de baixo/guitarras e título de fonte local no MusicXML composto;
   corrigir a origem dos metadados.
4. [x] Marcar MPRIS como aceito e piano como fora da prioridade atual; revisar diff e rodar verificações aplicáveis.

## WAVs publicados por padrão e perfis adiados (2026-09-28)

**Escopo:** manter somente os perfis já cobertos pelo trabalho e adiar novas famílias sem inventário/validação
independente,
incluindo violino e cello. Todo WAV entregue ao usuário deve ter cópia padrão sob `out/`; cópias técnicas para cache e
processamento continuam em `cache/`. `fetch` publicará a mix normalizada em `out/<música>/`, além de preservá-la no
cache.

1. [x] Registrar o adiamento das famílias não cobertas sem remover perfis ou medições existentes.
2. [x] Escrever teste de regressão para `fetch` publicar a mix WAV por padrão e respeitar `--out`.
3. [x] Implementar a publicação e atualizar documentação/ajuda da CLI.
4. [x] Rodar testes focados, suíte padrão, Ruff e mypy: 543 testes passaram; Ruff e mypy limpos.

## Laboratório multifaixa real — _Eyrie_ (2026-09-28)

**Plano (execução não interativa):** usar _Ne Obliviscaris — Eyrie_ (`yt__RMax1LS3pM`, versão de estúdio, 711 s) como
teste de estresse para aprender a extrair cada parte musical. A escolha e a régua estão no ADR-048. A música não vira
o único gate: sua complexidade serve para revelar limites; fixtures sintéticas e referências humanas independentes
decidem se cada instrumento está correto.

### Etapas

1. [x] Escolher a gravação sem viés de instrumento e registrar por que _Eyrie_ vence _Equus_ e os covers do acervo.
2. [x] Confirmar disponibilidade técnica dos quatro stems em `_Eyrie_`, todos com a duração da mix; inventário musical
   por escuta e intervalos ainda pendente.
3. [x] Manter o trabalho nos perfis já cobertos pelo pipeline e suas medições. Não adicionar perfis para violino,
   viola ou cello nesta etapa; ficam adiados. O inventário de _Eyrie_ pode continuar como pesquisa, sem virar
   compromisso
   de suporte ou mudança de código.
   - [x] Consultar créditos do encarte de `Urn`: baixo, bateria, duas guitarras, violino, viola, cello e vozes são
     candidatos confirmados para `Eyrie`; não há crédito de piano/teclado ou coro confirmado para esta faixa.
   - [ ] Mapear timestamps de entrada/saída no áudio local; os créditos não substituem escuta nem anotação de
     referência. Por stem, feito em 2026-10-23 (emenda ao ADR-048); por parte, depende de anotação humana.
4. [ ] Obter referência humana independente por parte quando existir e registrar cobertura temporal, afinação e
   confiabilidade. Sem referência, limitar o veredito a separação/audibilidade e marcar a transcrição como
   inconclusiva.
   - [x] Procurar referência local de `Eyrie` em GP5/MIDI/MusicXML/PDF e consultar canais oficiais; nenhuma partitura
     licenciada foi localizada nesta busca inicial. Não tratar isso como prova de inexistência.
5. [x] Congelar uma linha de base exploratória por família, antes de ajustes; durações de eventos e contagens estão na
   emenda do ADR-048. Sem referência humana independente, não há métrica de acerto. As entradas mix/stem seguem o
   ADR-044.
6. [ ] Tratar apenas perfis existentes e já cobertos, uma família por vez, por TDD; não ampliar a matriz nesta etapa.
   Preservar o baixo como controle de regressão. Qualquer família nova exige retomada explícita e teste real com
   veredito.
7. [x] Exportar a partitura multifaixa apenas com os perfis existentes. A guitarra distorcida não gerou eventos e não
   foi incluída; violino, viola, cello e melodia vocal não foram inferidos.
8. [x] Execução real do pipeline concluída e resultados por parte registrados na emenda do ADR-048; 543 testes,
   Ruff e mypy passaram no checkpoint do commit. Isso valida a execução, não a exatidão musical sem referência.
9. [x] Corrigir e testar os nomes vazios de baixo/guitarras nas partes
   multifaixa e evitar o título interno `mix` quando a fonte for um WAV já normalizado em cache.
10. [x] Registrar o veredito do usuário de que GP5 do baixo solo e GP5 multifaixa estão perfeitos no uso observado;
    manter esse resultado separado do aviso ainda não diagnosticado do MusicXML no MuseScore.

### Benchmark GPU nesta estação — suspenso por decisão do usuário (2026-09-28)

- [x] Registrar que a RX 5500 XT (`gfx1012`) tem caminho experimental via wheels ROCm/TheRock, sem suporte equivalente
  na distribuição ROCm estável; ver emenda do ADR-002.
- [x] Manter a configuração CPU-only: não instalar/configurar ROCm, não alterar dependências e não iniciar benchmark
  GPU.
- [ ] Se o usuário reabrir esta investigação, começar por preflight no host (`/dev/kfd`, `/dev/dri`, permissões),
  virtualenv descartável com versão noturna fixada, teste de kernel GPU e só depois comparação curta CPU/GPU.

### Incremento V1 — stem vocal auditável

1. [x] Escrever primeiro os testes do serviço e da CLI para entregar mix, vocal e playback sem vocal.
2. [x] Implementar `separar-vocais` atrás do `Separator`, sem perfil instrumental ou partitura fictícia.
3. [x] Adicionar teste real `slow` com Demucs sobre fixture local e documentar uso e limites.
4. [x] Executar suíte padrão, seleção real aplicável, Ruff e mypy: 542 testes passaram; canário real, 1 teste em
   43,84 s; Ruff e mypy limpos.
5. [x] Reexecutar `_Eyrie_` e registrar a linha de base observável. O primeiro wrapper desapareceu sem core dump nem
   evento OOM; a repetição acompanhada ficou ativa por 17min17s e concluiu. Todos os stems têm 711,088 s, 44,1 kHz,
   estéreo e PCM 16-bit. RMS: baixo 0,0788; bateria 0,1092; `other` 0,1534; vocais 0,0725; mix 0,2713.
6. [x] Fazer uma passada livre do MuScriptor no stem vocal: 288 eventos (286 `voice`, 2 `drums`), 111,24–593,64 s;
   guardar JSONL no cache ignorado. Resultado exploratório, sem referência para julgar acerto.
7. [x] Fazer passadas livres em `other` e `drums`: `other` devolveu 14.639 eventos (incluindo 1.872 `drums` e 12.478
   `acoustic_guitar`); o stem de bateria, 2.451 `drums`. Guardar JSONL e registrar como distribuição bruta de rótulos,
   não como qualidade medida.

### Riscos e trade-offs

- `htdemucs_ft` entrega `bass`, `drums`, `vocals` e `other`, não uma faixa por instrumento; `other` é o principal
  gargalo para guitarra, teclas e violino.
- O MuScriptor conhece baixo, bateria, piano e guitarra, mas não oferece contrato já validado para violino ou voz.
- _Eyrie_ já revelou silêncio indevido do transcritor entre 557 e 671 s; a segunda passada corrige cobertura, mas a
  qualidade desse trecho continua sem referência conclusiva.
- Uma faixa extrema é ótima para achar falhas e ruim para calibrar sozinha. Nenhum ajuste entra se melhorar _Eyrie_ e
  regredir as fixtures ou o corpus já medido.

## Documentação arquitetural completa (2026-09-26)

- [x] Inventariar módulos, contratos, dependências, fluxos, testes e ADRs do estado atual.
- [x] Escrever `docs/arquitetura.md` em linguagem progressiva para júnior e revisão por arquitetos.
- [x] Criar e validar diagrama de componentes da arquitetura.
- [x] Criar e validar diagrama de fluxo de dados do pipeline.
- [x] Criar e validar diagrama de sequência entre usuário, CLI/API e pipeline.
- [x] Aplicar o patch obrigatório de hover e realizar validação visual dos HTMLs entregues.
- [x] Vincular a documentação no README e executar a verificação final.

## Detalhamento dos comandos no README (2026-09-26)

- [x] Conferir comportamento, argumentos e opções de cada subcomando contra `src/thoth/cli.py` e a ajuda real.
- [x] Reestruturar a seção `Uso` por comando, explicando pré-requisitos, processamento, saídas e exemplos.
- [x] Validar o diff e todas as ajudas da CLI documentadas.

## Documentação detalhada de instalação (2026-09-26)

- [x] Conferir requisitos e ferramentas externas contra o código, o contêiner e os ADRs.
- [x] Reestruturar o `README.md` com instalação nativa, pesos, alphaTab, validação, primeiro uso e contêiner.
- [x] Fechar a verificação da entrega:
  - [x] `git diff --check`, `thoth --help`, Ruff e mypy.
  - [x] Suíte padrão: 530 testes passaram em 26,87 s na repetição de 2026-09-26.

## Continuidade — backlog ativo (revisado em 2026-09-26)

### Partitura multifaixa com WAV focado no baixo (2026-09-27)

- [x] Registrar a decisão arquitetural e o limite temporário do piano em GP5.
- [x] Escrever primeiro testes estruturais para combinar baixo, guitarras e bateria em GP5 e MusicXML.
- [x] Implementar compositores multifaixa preservando ritmo, nomes, programas e percussão.
- [x] Adicionar o modo `todos` ao pipeline sem copiar nem auralizar WAVs das outras famílias.
- [x] Expor `todos` na CLI, API e página e relatar partes ausentes sem perder as demais.
- [x] Provar que o modo `baixo` preserva seus artefatos e que os WAVs do modo `todos` continuam focados no baixo.
- [x] Executar testes reais aplicáveis, navegador, suíte padrão, Ruff e mypy.

### Animação no player interno da web (2026-09-27)

- [x] Ampliar primeiro o teste de navegador para reprodução, pausa e parada do alphaTab.
- [x] Observar o estado real pelo evento `playerStateChanged`, inclusive encerramento automático.
- [x] Compartilhar o destaque visual entre reprodução interna e externa, preservando redução de movimento.
- [x] Executar navegador (14 passaram), suíte padrão (535 passaram), Ruff e mypy.

### Salvar a transcrição pela página (2026-09-27)

- [x] Escrever primeiro o teste de navegador para os downloads disponíveis no job concluído.
- [x] Exibir uma área de salvamento criada a partir dos formatos realmente produzidos.
- [x] Manter os downloads disponíveis mesmo quando o alphaTab não puder exibir o formato.
- [x] Documentar o uso e executar navegador (14 passaram), suíte padrão (535 passaram), Ruff e mypy.

### Animação do cursor no player externo (2026-09-27)

- [x] Escrever primeiro o teste de navegador para a animação ativa e sua remoção ao voltar ao player local.
- [x] Aplicar brilho pulsante ao cursor em `Playing`, manter destaque estático em `Paused` e remover em `Stopped`.
- [x] Respeitar `prefers-reduced-motion` e não alterar o comportamento do cursor ou do áudio.
- [x] Executar teste de navegador (13 passaram), suíte padrão (535 passaram), Ruff e mypy.

### Implementação — acompanhar player MPRIS (2026-09-26)

**Plano (execução não interativa):** 1) confirmar contrato AlphaTab/MPRIS e limites de correspondência; 2) registrar a
decisão arquitetural; 3) escrever testes primeiro para consulta real ao barramento e transições/ausência de player; 4)
implementar adaptador MPRIS opcional, endpoint local e controles na página; 5) documentar instalação/uso Linux e
executar suíte, lint, tipagem e teste com barramento D-Bus isolado.

- [x] Pesquisa de MPRIS e AlphaTab concluída; solução restrita a players locais compatíveis no Linux, com Spotify
  excluído e sem OAuth/Web API.
- [x] ADR da leitura MPRIS, isolamento local e sincronização manual registrados (ADR-046).
- [x] Testes escritos antes do adaptador e da interface; inclui teste D-Bus real em sessão isolada.
- [x] Endpoint lista players e informa estado, faixa e posição; barramento/players ausentes não derrubam a aplicação.
- [x] Página permite escolher um player, iniciar/parar acompanhamento e observar o cursor sem áudio local do AlphaTab.
- [x] README e arquitetura explicam compatibilidade, instalação no Linux, uso e limites de alinhamento.
- [x] Suíte padrão (535 testes), navegador (13 testes), D-Bus real (1 teste), Ruff e mypy executados.

**Estado:** implementação e testes automatizados concluídos; o usuário confirmou a aceitação de MPRIS em 2026-09-28.

#### Aceitação

- [x] O usuário confirmou que MPRIS está OK (2026-09-28); encerrado sem acrescentar resultado manual não informado.

O projeto está funcional para baixo, guitarra e bateria. O transcritor agora devolve a transcrição livre, e os nomes das
partes e o título da fonte são preservados na exportação MusicXML multifaixa. O piano acústico permanece fora da
prioridade por orientação do usuário (2026-09-28); o piano elétrico segue fora do escopo conforme ADR-044.

### Itens do plano ADR-044

1. [x] Generalizar o contrato do transcritor (ADR-044, M1), mantendo notas e ataques de bateria separados no domínio.
2. [x] Corrigir os nomes das partes e o título de origem na exportação MusicXML multifaixa.
3. [x] ~~Spike e integração do piano acústico (ADR-044, M3)~~ — fora da prioridade por orientação do usuário; não
   agendado.

O caminho do baixo é uma restrição permanente: qualquer mudança compartilhada precisa preservar os pisos, descartes e
artefatos existentes.

### Aguardando dados ou decisão — não bloqueia o trabalho acima

- **Discriminador de erro de oitava para baixo (ADR-030):** o atual tem AUC 0,75 e é apenas diagnóstico. Candidatos
  adicionais já foram descartados; faltam tablaturas humanas conclusivas em mais músicas. Retomar quando houver novas
  referências, sem reabrir os candidatos medidos por diferença pequena em amostra insuficiente.
- **Integração Spotify/Web API (ADR-043):** não adotada devido à restrição oficial de sincronização com conteúdo visual.
  O recurso desejado foi implementado com outra fonte — MPRIS local, excluindo Spotify — no ADR-046.

### Itens encerrados ou condicionais

- **Contrato de acordes do M1:** já implementado como `AtribuidorDeAcordes`, independente do `FretAssigner`, com
  `ViterbiAcordes` e testes de posicionamento/integração. A caixa aberta na seção M1 era registro desatualizado e foi
  fechada abaixo.
- **Tabs humanas adicionais:** não há ação automática prevista; se o usuário fornecer uma tab clássica válida, ela
  pode alimentar a validação de oitava. Automatizar a coleta do Songsterr está descartado pelo ADR-007.
- **MusicXML fora de 4/4 e anacruse:** fora do contrato atual do ADR-039; só reabrir se fórmulas variáveis entrarem no
  escopo.
- **Auralização como métrica:** encerrada como requisito inválido; não há ground truth para calcular F1 a partir dela.

### Verificação padrão de entrega

```bash
uv run pytest -n auto
uv run ruff check src/ tests/
uv run mypy src/
```

Rodar também a seleção da integração tocada: `uv run pytest -m "slow and not network"` para modelos/ferramentas reais,
`uv run pytest -m ""` para testes pesados como MuseScore e `uv run pytest -m navegador` quando a UI mudar. Registrar
resultados e não atribuir à suíte padrão cobertura das camadas excluídas pelos marcadores.

## Fase 0 — Spike de viabilidade ✅ **CONCLUÍDA (2026-09-22) — veredito: SEGUIR**

Sem escrever código do pipeline. Medir se a qualidade justifica o projeto. A avaliação **não depende de saber tocar**
(ADR-006).

### Preparo

- [x] `uvx muscriptor transcribe --help` → flags verificadas na v0.3.0 (2026-09-21): `-f midi|json|jsonl` ·
  `-m small|medium|large` · `-d auto|cpu|cuda|mps` · `--instruments` · `--auralize` + `--soundfont` ·
  `--detect-tempo     true|false|best-effort` · `--sampling/-t` · `--cfg-coef` · `--notes` · `-o -` Nomes de
  instrumento (`list-instruments`): `electric_bass`, `acoustic_bass`, `contrabass`, `clean_electric_guitar`,
  `distorted_electric_guitar`, `drums`… **Sem MusicXML/PDF/tab** — ver correção no ADR-003.
- [x] Aceitar a licença CC BY-NC 4.0 no HuggingFace + `hf auth login` na estação

### Camada 1 — objetiva (critério principal)

- [x] Fixtures: 6 linhas de baixo em MIDI (`tests/sintetico.py`) → fluidsynth + soundfont → WAV normalizado a −1 dBFS
- [x] **Onset F1** com `mir_eval` (`services/evaluation.py`), travado por fixture como teste de regressão em
  `tests/integration/test_regressao_fase0.py`
- [x] Medir o **pipeline completo** (com separação) contra ground truth: no `misto`, nota F1 0,682 → **0,968** com
  separação, onset inalterado em 0,938 (ADR-010, emenda de 2026-09-22). Separar recupera altura, não tempo
- [x] Repetir com `small` vs `medium`, cronometrando em CPU — feito em 2026-09-24, emenda do ADR-009: com separação o
  `medium` não degenera, mas não ganha em nenhuma fixture, custa ~2× e em `escala` rotula o baixo como
  `acoustic_guitar`. A comparação em áudio real fica com a Camada 3 (precisa de tab humana)

### Camada 2 — perceptual assistida (dispensa treino)

- [x] Auralização: original em um canal, MIDI no outro (`thoth auralizar`, ADR-020). Se descolar, qualquer ouvido
  percebe
- [x] ~~Rodar a auralização sobre o corpus e reportar F1 por grupo~~ — auditoria encerrada em 2026-09-25: 2/4 arquivos
  validados no Grupo A, 2/2 no B e 2/2 no C; F1 não é definido em nenhum grupo porque o corpus tem zero referências.
  Não foi agregado nem substituído por zero (emenda do ADR-020)

### Camada 3 — referência externa (ADR-007)

- [x] Tabs humanas escolhidas: três `.gp5` da comunidade do UG, baixados à mão pelo usuário para `samples/` (ignorada
  pelo git): _Fear Is the Key_, _Dance of Death_, _And Plague Flowers_. O Songsterr ficou fora (emenda do ADR-007)
- [x] `thoth comparar <tab.gp5> <fonte>` (ADR-041):
  - [x] leitor da tab → `NoteEvent` em segundos: faixa de baixo, andamento de **todas** as faixas na posição exata,
      repetições com finais alternativos, ligaduras, compasso que não é 4/4. D.S./coda fora, declarado
  - [x] ~~alinhamento só por ataque~~ — medido e derrubado: a tab deslocada casava quase tanto quanto a alinhada.
      Alinhamento pelo nome da nota (sem oitava), escala + deslocamento globais, correção por trecho de ±80 ms
  - [x] relatório: mesma oitava / acima / abaixo nos pares de mesmo nome, com o piso de acaso (tab deslocada) ao lado;
      escala na borda da grade é recusada
  - [x] subcomando na CLI, lendo `notas.jsonl` do cache como o `auralizar`
  - [x] rodar nas três músicas → ADR-041
- [x] Conferir oitava contra essa tab: duas oitavas quase nunca (6 de 1266 pares, só em _And Plague Flowers_); 5–15% a
  uma. _Dance of Death_ ficou no piso de acaso — não confirma nada; _And Plague Flowers_ só alinhou em 60–300 s
- [x] "Nota errada" contra tab: exige alinhar a tab ao stem do baixo (DTW), não à transcrição (ADR-041, consequência) →
  ADR-042
  - [x] medir: DTW sobre croma do stem nas três tabs (78/≤64, 79/≤45, 60/≤55); porta só de áudio não separa da música
      errada — descartada
  - [x] `services/alinhamento_audio.py`: tab → tempo do stem por DTW (porte literal do script de medição), teste com
      áudio sintético
  - [x] `comparacao.veredito_de_nota`: certa/oitava/errada por janela de 60 s, piso ao lado, janela conclusiva só com
      certa ≥ piso + 10 pontos; o resto "inconclusivo"
  - [x] CLI `comparar`: tabela por janela quando há stem em cache; sem stem, recado
  - [x] rodar nas três músicas, conferir contra a medição → ADR-042: errada 14,1% / 15,4% nas janelas conclusivas de
      _Fear_ e _And Plague Flowers_; _Dance_ 1 de 9
- [x] Refazer _And Plague Flowers_ com `--afinacao 5` (emenda do ADR-041): 89,3% contra piso de 71,9%, alinhamento igual
  — a afinação não mudava o quadro
- [x] **Transcrição some depois de 511 s** em _And Plague Flowers_ (`yt_ArBcOGvMvGU`): era o filtro de rótulo — o baixo
  vira `clean_electric_guitar`. Trechos sem baixo agora são relatados e readmitidos (emenda do ADR-008); vai até
  654,9 s, 1558 pares, 89,5% na mesma oitava contra piso de 75,2%

### Comparações a fazer

- [x] **mix direto** vs **stem do Demucs** → decidido no ADR-010 (separar sempre)
- [x] **com** vs **sem** `--instruments` → decidido no ADR-008 (sem; filtrar por conjunto de rótulos)

**Pronto quando:** planilha com F1 por condição + tempo em CPU + decisão **seguir / ajustar / abortar**. **Cuidado:** F1
sintético é métrica de regressão, não de qualidade real.

## Fase 1 — Esqueleto e domínio ✅ **CONCLUÍDA (2026-09-21)**

- [x] `uv init` com Python 3.12 fixo (ADR-004)
- [x] `domain/models.py` — `AudioAsset`, `NoteEvent`, `TabNote`, afinações
- [x] `domain/ports.py` — `AudioSource`, `Transcriber`, `Separator`, `FretAssigner`, `Exporter`
- [x] `LocalFileSource` — ffmpeg → WAV 44.1 kHz estéreo, `source_id` = SHA-256 do conteúdo
- [x] Cache por `source_id`: cache hit não reconverte
- [x] `YtDlpSource` + `resolver_fonte()` — URL do YouTube ou caminho local (ADR-005)
- [x] `cli.py` (Typer): `thoth fetch <arquivo|URL>`
- [x] 6 testes contra **ffmpeg real** (sem mock — Regra 3); ruff + mypy strict limpos

## Fase 2 — MuScriptor + ground truth

- [x] **Verificador de oitava** (`services/octave_check.py`) — razão `f0 / 2·f0` por nota, limiar 0,40, 7 testes contra
  WAV real gerado pelo ffmpeg. Roda sobre o **stem**, não sobre a mix: validado nos dois, pega 12/12 no stem e só
  6/12 na mix (bumbo e guitarra enchem a banda de 30,9 Hz).
- Mais um dado para essa validação (2026-09-22, primeira execução da CLI ponta a ponta): no stem do Demucs da fixture
  `walking` o limiar sinaliza **4 de 15 notas** (27%), todas G2/A2 — bem acima dos 8,7% medidos em material real.
  Fixture sintética passada pelo Demucs não é material real, então isto não condena o limiar; é mais uma amostra de que
  a taxa de alarme depende forte do material
- [x] Validar o limiar **fora do Equus** — ele foi calibrado nas mesmas 12 notas em que foi medido. Feito com as três
  tabs alinhadas ao stem (emenda do ADR-030): **não se sustenta** — alarma 31–39% das notas que a tab confirma (8,7%
  no Equus), 4–5% dos avisos são erro real, e nenhum limiar de 0,2 a 1,0 separa. O limiar fica; o aviso deixa de
  valer como lista curta
- [x] **A janela do ADR-029 tinha quebrado a detecção** (emenda do ADR-029): no Equus caiu de 12 para 2 das 12, e o pico
  zero (faixa de 41 Hz entre dois pontos da FFT) virava nota certa em suspeita. FFT completada com zeros + janela
  com piso de 0,3 s: 8 de 12, 4 de 127 alarmes. Calibração travada em `tests/integration/test_oitava_equus.py`
  (`slow`, pula sem `~/thoth-fase0`). Remedido nas tabs: segunda emenda do ADR-030
- [x] Erro de oitava **para cima** — não é do Thoth: em 91 dos 95 casos medidos o áudio desmente a tab (terceira emenda
  do ADR-030). Nada a detectar
- [ ] Discriminador do erro **para baixo** que separe melhor que o `f0 / 2·f0` (AUC 0,75, segunda emenda do ADR-030).
  Candidatos já medidos e descartados: ímpares/pares, `3f0/(2f0+4f0)`, meios-harmônicos. Com 84 casos em duas
  músicas, diferença pequena entre candidatos não se distingue de acaso: esperar mais tabs. _Eyrie_ acrescentou só 2
  (quarta emenda do ADR-030): linha repetitiva demais para as janelas serem conclusivas. _Você_ e _Gesu_, mais 5
  (emenda de 2026-10-23): falta tab de música com **mais erro de oitava**, não só mais tabs
  - Tentativa de escolher a próxima tab pelo próprio aviso (2026-10-30, só medição, script `oitava/ranking.py` no
    scratchpad): `verificar_oitavas` no stem em cache de cada uma das 18 fontes. **Não serve para escolher.** O
    aviso não acompanha o erro real que as tabs confirmam. Gesu alarma 41,9% das notas, com poucos casos reais;
    Fear, 26,7% com 13; Plague, 10,9% com 26, o maior número; Dance, 24,3% sem nenhum caso conclusivo. A
    sugestão `pitch + 12` sai em quase todos os avisos e não filtra nada. O topo da lista (Hallowed Be Thy
    Name 36%, Feel Like Makin' Love 20%) não indica mais erro de oitava. A próxima tab continua dependendo de
    escolha externa
  - Tab nova: _Fear of the Dark_ (`samples/Iron Maiden - Fear Of The Dark.gp5`, faixa 4 "Steve Harris", 4 cordas;
    cache `yt_bePCRKGUwAY`). Método da emenda de 2026-10-23 do ADR-030: `alinhar_ao_stem`, `veredito_de_nota`, e
    `verificar_oitavas(limiar=1e300)` sobre o `bass.wav`, só em janelas conclusivas. O script é conferido antes
    reproduzindo os 13 casos de _Fear Is the Key_ e os 26 de _Plague_. Régua congelada antes de medir: a tab
    **amplia a amostra** se render pelo menos 10 casos "abaixo" em janelas conclusivas, porque aí _Plague_ deixa
    de ter metade dos positivos. Nesse caso, os candidatos a discriminador são comparados num plano próprio. Se
    render menos, entra como a quinta tab que não amplia
  - Resultado (2026-10-30): **não amplia**. Foram 3 casos "abaixo" contra 786 notas concordantes, em 4 janelas
    conclusivas. A conferência reproduziu _Fear Is the Key_ (13 casos, AUC 0,70) e _Plague_ (27 casos, AUC 0,76).
    O agregado passa a 47 casos, 27 deles em _Plague_. Registrado na emenda de 2026-10-30 do ADR-030. A próxima
    tab continua dependendo de escolha externa
- [x] MuScriptor silencioso no fim de _Eyrie_ (`_RMax1LS3pM`): o _prelude forcing_ trava o modelo em vazio de 557 a 671
  s. Segunda passada sem ele, só quando há buraco, só dentro do buraco (emenda do ADR-008). 0 → 382 notas no trecho,
  travado em `tests/integration/test_prelude_eyrie.py`
- [x] _Eyrie_ de novo com a segunda passada: 1507 → 1809 notas, a última em 659 s (antes 555 s); 136 e 192 notas nas
  janelas de 540 e 600 s, antes 25 e 0. **Qualidade não medida:** contra a tab, as duas janelas saem inconclusivas (600
  s: certa 20% contra piso 25%), como as do meio da música. A tab de _Eyrie_ não serve para julgar o trecho.
  Casos de oitava para baixo continuam 2
- [x] `MuscriptorTranscriber` atrás do `Protocol Transcriber` — subprocesso via `uvx` (torch fora do projeto), `small` +
  livre + `--detect-tempo false`. 7 testes: 6 de parsing puro + 1 contra o modelo real (`slow`).
- [x] **Não fatiar áudio antes de transcrever** — o rótulo do instrumento depende de contexto (emenda do ADR-008): 2,9 s
  viram `acoustic_piano`, 8 s viram `electric_bass`. Vale como restrição ao montar o serviço de pipeline.
- [x] `models.lock.toml` com SHA-256 dos pesos — `small` e `medium`, com revisão do HF e licença. Conferido contra o
  cache real da estação por teste `slow` (1,6 GB em ~5 s). Pesos seguem fora do versionamento (ADR-005); o lock
  guarda só a identidade deles.
- [x] Promover as fixtures da Fase 0 a **gate de regressão** — `tests/sintetico.py` (regera as seis fixtures; áudio
  nunca versionado, ADR-005) + `tests/integration/test_regressao_fase0.py`. Válido só para o `small` (ADR-009) sobre
  o checkpoint de `models.lock.toml`, conferido por hash antes de medir. Sem folga: renderização byte-idêntica e
  `muscriptor@0.3.0` pregado. Cobre também o avaliador, agora em `thoth.services.evaluation` com 8 testes contra o
  mir_eval real.
- [x] ~~Travar o gate no CI~~ — **descartado** (2026-09-22, decisão do Welington): projeto pessoal, sem necessidade de
  CI. O teste de regressão roda localmente sob demanda: `uv run pytest -m slow`. Consequência aceita: ele só protege
  quando alguém o roda — não há nada impedindo um commit de regredir.
- [x] `@pytest.mark.slow` para o que carrega modelo

**Pronto quando:** o F1 estiver documentado e travado. **Cuidado:** F1 sintético é métrica de regressão, não de
qualidade real.

## Fase 3 — Motor de tablatura (Viterbi/DP)

- [x] Estados (corda, traste) válidos por afinação — qualquer tupla de afinação; EADG, BEADG e Drop D já em
  `thoth.domain.models`
- [x] Custo: traste alto, corda solta, deslocamento, troca de corda e janela da mão (ADR-012). A janela é **absoluta**
  (trastes 0–5), não móvel — ver ADR-012
- [x] **Modo iniciante** (ADR-006) — preset `INICIANTE`. Nasceu idêntico ao `PADRAO`: custo linear por traste não separa
  os modos. Quem separa é a penalidade fora da primeira posição (ADR-012)
- [x] Hypothesis: pitch (corda,traste) == pitch original; nenhum traste > `max_fret`
- [x] **Acordes / notas simultâneas** — resolvido na borda do pipeline, não no motor: `monofonizar` reduz o grupo à nota
  mais grave e relata o descarte (ADR-014). `assign` continua monofônico de propósito

**Medido:** as seis fixtures caem em primeira posição sob os **dois** presets — o corpus sintético vive no grave, onde
tocável e ótimo coincidem, e portanto **não** valida o modo iniciante. A distinção se apoia no teste de contraste e na
varredura de 400 linhas aleatórias (170 divergem).

**Pronto quando:** as tabs das fixtures couberem na primeira posição quando a linha permitir, verificado por propriedade
— não por execução no instrumento.

## Fase 4 — Exportadores

- [x] GP5 via PyGuitarPro (afinação, corda/traste, tempo) — `Gp5Exporter`
- [x] MusicXML via music21 (clave de Fá 8vb, compasso, corda/traste como indicações) — `MusicXmlExporter`
- [x] Round-trip: grava → relê → mesmas cordas e trastes. 16 testes contra as bibliotecas reais (Regra 3), nenhum mock
- [x] **Abrir no TuxGuitar** — verificado pelo Welington em 2026-09-22: os quatro GP5 e os quatro MusicXML (incluindo
  `graves`, de 5 cordas) abriram corretamente. É o único leitor independente disponível — o round-trip sozinho prova
  consistência com quem escreveu, não validade do formato
- [x] Ligaduras no GP5 — feito pelo ADR-022 (`NoteType.tie`, fatiado nas barras); o item ficou aberto por engano até
  2026-09-24

**Pronto quando:** abrir sem erro no TuxGuitar.

## Condicionais — só com evidência da Fase 0

- [x] **C1** `DemucsSeparator` (`htdemucs_ft`) — **aprovada** e promovida a etapa fixa do pipeline (ADR-010). Custo
  conhecido: erra a oitava em 7% das notas no material grave e denso — mitigação na Fase 2, não motivo para
  reverter.
- [x] **C2** quantizador próprio — o Beat This! é dependência dura do MuScriptor (ADR-003 corrigido), não condicional.
  Resolvido pelo segundo caminho: o transcritor roda sempre com `--detect-tempo false` e a quantização é nossa
  (`services/rhythm.py`).

## Fase 4.5 — Pipeline ponta a ponta ✅ **CONCLUÍDA (2026-09-22)**

Pré-requisito invisível até agora: a Fase 5 só existe se houver o que o `POST /jobs` chame. Hoje os estágios existem
isolados e nada os liga.

- [x] `DemucsSeparator` atrás do `Separator` (ADR-010) — `htdemucs_ft`, `--two-stems=bass`, `uvx --with "numpy<2"` (o
  demucs declara mal suas dependências). Stem descoberto por glob, não por caminho reconstruído
- [x] `services/pipeline.py` — `ref → artefatos`, uma função, sem fila nem estado
- [x] **Política de simultaneidade** (ADR-014) — decidir na borda do pipeline, não descobrir no meio de uma música:
  `assign` é monofônico e `rhythm.eventos` levanta erro. Deixa de ser latente no primeiro áudio real
- [x] Rótulo do instrumento por **conjunto** (`electric_bass`, `acoustic_bass`, `contrabass`), nunca literal — o rótulo
  depende de contexto (emenda do ADR-008) e não foi medido sobre stem do Demucs. `Counter` dos rótulos no resultado,
  como no gate de regressão
- [x] **Nota fora do braço não é fatal** (ADR-014) — apareceu no primeiro teste: é a assinatura do erro de oitava do
  Demucs, e `assign` levantava `AlturaImpossivelError` matando a música inteira por causa de uma nota
- [x] BPM plumbado ponta a ponta (entrada, não estimativa — ADR-013)
- [x] `thoth transcribe <ref> --out <dir> --bpm` na CLI

**Pronto quando:** `thoth transcribe` sobre um áudio real produzir `.gp5` e `.musicxml` que abram, com o rótulo e os
avisos de oitava no relatório.

## Fase 5 — API e UI

- [x] FastAPI: `POST /jobs`, `GET /jobs`, `GET /jobs/{id}`, `GET /jobs/{id}/artifacts/{fmt}`. Jobs em memória e falha de
  pipeline como estado do job, não 500 (ADR-015). O resumo devolve descartes, notas fora do braço e avisos de oitava
  — a tablatura sozinha não conta o que foi perdido
- [x] alphaTab servido localmente (sem CDN): renderiza, toca e **controla andamento (estudar a 50–70%)** — ferramenta de
  estudo central para iniciante (ADR-006). `scripts/vendor_alphatab.py` resolve os `import` em vez de listar
  arquivos; a lista fixa trazia só a fachada de 4 KB e deixava a página em branco
- [x] `thoth serve` — sobe API e página em `127.0.0.1` por padrão
- [x] **Abrir a página no navegador** — não renderizava. Causa: `scrollElement` apontando para o próprio `#tab`, que faz
  o lazy loading do alphaTab achar que nada está visível (ADR-016). Fechado com teste de navegador de verdade
  (`tests/navegador/`, marcador `navegador`), verificado nos dois sentidos
- [x] Reabrir job pronto por `?job=<id>`, com guarda para id inexistente
- [x] **Tocar e cursor** — medido, não ouvido (2026-09-25): `test_tocar_faz_sair_som_e_andar_o_cursor_e_parar_cala`. Um
  analisador preso a toda ligação com a saída de som mede o volume: 0 antes, ≈ 0,094 tocando, 0 depois de Parar; o
  cursor anda (x 198 → 235 px em 1 s). Provado nos dois sentidos: `enablePlayer: false` e `enableCursor: false` o
  fazem falhar. Limite: o autoplay é liberado por flag, então a política de gesto do navegador real não é exercitada

## Fase 6 — Opcionais

- [x] Avaliar sync do cursor via Spotify `currently-playing` (ADR-043): não seguir com a Web API, pois a referência
  oficial proíbe sincronizar gravações do Spotify com conteúdo visual.
- [x] Implementar player externo via MPRIS (ADR-046): somente Linux, somente leitura e com Spotify excluído; manter a
  reprodução local do alphaTab. VLC/Strawberry ainda precisam de validação manual na estação do usuário.
- [x] Containerfile + compose (CPU) — ADR-040, job real verificado dentro do contêiner

### Multi-instrumento: guitarra polifônica, piano e bateria — plano (ADR-044)

> Uma parte-alvo por execução; o baixo continua sendo o padrão. Ordem **revista pelo veredito** (ADR-044, 2026-09-25):
> contrato e medição comum → **guitarra (M4)** → bateria (M2) → piano acústico (M3). Só a guitarra tem `seguir`; bateria
> e piano acústico estão em `ajustar`; piano elétrico fora de escopo. Nenhuma etapa autoriza áudio ou tablatura de
> terceiros no repositório.

#### M0 — aceitar o recorte antes de implementar

- [x] Aceitar ou rejeitar o ADR-044 (aceito em 2026-09-25, com emenda no ADR-011); pronto quando o status deixar de ser
  `Proposto` e estiver decidido se piano sem GP5 nativo ainda conta como suporte completo.
- [x] Congelar em teste a taxonomia do MuScriptor 0.3.0 (`slow`, via `list-instruments`) para o escopo: piano
  (`acoustic_piano`, `electric_piano`), guitarra (`acoustic_guitar`, `clean_electric_guitar`,
  `distorted_electric_guitar`) e `drums`; pronto quando uma mudança de nome no motor falhar com a lista observada
  impressa.
- [x] Criar perfis de instrumento no domínio (`domain/instrumentos.py`) sem misturar rótulos por conveniência; pronto
  quando cada perfil declarar família, rótulos aceitos, stem, programa GM e afinação opcional, e guitarra
  limpa/acústica/distorcida puderem ser selecionadas separadamente.

#### M1 — contrato de domínio e régua comum, por TDD

> Ordem ajustada na aceitação (ADR-044, decisão do usuário): tipos, fixtures e avaliador, depois a medição e o veredito.
> Os itens que mudam `Transcriber`, `Separator`, `FretAssigner` e `Exporter`, e a `ParteMusical`, que só tem consumidor
> nos exportadores, esperam um `seguir`. Critério do veredito fixado no ADR-044.

- [x] Testar primeiro e introduzir `EventoPercussivo` e `Transcricao` (`ParteMusical` espera o primeiro exportador
  novo): nota com altura continua sendo `NoteEvent`; ataque de bateria guarda instante e peça GM, sem fingir altura
  ou sustentação; pronto com testes de igualdade, ordenação e validação de cada modelo.
- [x] Generalizar `Transcriber` para devolver a transcrição livre completa e remover o seletor opcional do contrato;
  pronto quando nenhum caminho usar `--instruments` e notas mais ataques de bateria sobreviverem ao parsing real do
  JSONL.
- [x] Manter `Separator.separate()` retornando stems nomeados, mas retirar do contrato a suposição de “baixo”; pronto
  quando os perfis resolverem `bass`, `drums` ou `other` e um stem ausente produzir erro explícito antes da
  transcrição.
- [x] Preservar o `FretAssigner` monofônico do baixo e criar um contrato distinto para acordes de guitarra; pronto
  quando o tipo impedir piano e bateria de passarem por atribuição de corda e impedir o baixo de herdar polifonia
  por acidente. → `AtribuidorDeAcordes` em `domain/ports.py`, `ViterbiAcordes` em `services/acordes.py` e cobertura
  em `tests/unit/test_acordes.py`, `test_pipeline_guitarra.py` e testes de exportação.
- [x] Generalizar `Exporter` para receber uma `ParteMusical`, não apenas `list[TabNote] + tuning`; pronto quando
  exportadores falsos provarem por teste que piano e bateria não exigem afinação e que baixo/guitarra não perdem
  posições. → Bateria resolvida com `ExportadorDePercussao` à parte (emenda do ADR-044, 2026-09-25); a
  `ParteMusical` fica para o piano, se ele não couber. → Não foi preciso: o piano também ganhou contrato próprio,
  `ExportadorDePiano` (decisão do usuário, emenda do ADR-044 de 2026-09-25). Item encerrado sem a `ParteMusical`.
- [x] Gerar, em código versionado (`tests/sintetico_multi.py`), fixtures MIDI de pelo menos 8 s, isoladas e em mix, para
  cada instrumento; pronto quando `fluidsynth` real renderizar WAVs normalizados, os MIDI forem a referência e
  nenhum `.mid`, `.wav`, `.gp5` ou `.musicxml` gerado aparecer no índice do Git.
- [x] Estender o avaliador (`avaliar_polifonico`, `avaliar_bateria`): piano/guitarra com precisão, revocação e F1 de
  ataque e de nota sem cobrar offset; bateria com F1 micro e macro por peça GM a 50 ms, sem métrica de duração;
  pronto com testes contra `mir_eval` real e casos que demonstrem erro de altura, troca de peça e ataque deslocado.
- [x] Medir cada fixture em três condições — isolada, mix direta e stem do Demucs (`drums` para bateria; `other` para
  piano/guitarra) — com decodificação livre; pronto com tabela de tempo de CPU, contagem por rótulo, precisão,
  revocação e F1, sempre imprimindo medido e piso lado a lado. → `tests/integration/test_multi_instrumento.py`
  (2026-09-25).
- [x] Registrar o veredito por instrumento antes do respectivo exportador; pronto quando a medição disser `seguir`,
  `ajustar` ou `manter fora de escopo`, sem usar avaliação auditiva do usuário e sem promover a primeira rodada a
  piso por simples conveniência. → ADR-044, Veredito: bateria e piano acústico `ajustar`, piano elétrico fora de
  escopo, as três guitarras `seguir`.

#### M2 — bateria primeiro

- [x] Medir bumbo, caixa, chimbal, tons e prato, incluindo ataques simultâneos; pronto quando o teste `slow` contra o
  MuScriptor e o Demucs reais publicar F1 micro/macro por peça e matriz de confusão GM, ou encerrar bateria com
  veredito negativo documentado. → `confusao_bateria`; tons trocam de número; revocação perdida na borda dos pedaços
  de 5 s do MuScriptor (emenda do ADR-044 de 2026-09-25). → Borda medida (ADR-045): 0,1 s de silêncio na frente leva
  a bateria de 0,529 a 0,901, mas troca o rótulo de baixo, guitarra e piano; fica só na bateria (`silencio_inicial_s`,
  padrão 0). → Fixture só de tons: 45 de 48 ataques achados, quase todos como 43 ou 36; o
  modelo não separa os tons (emenda do ADR-044, F1 micro 0,109).
- [x] Implementar quantização de ataques sem inventar sustain; pronto quando dois hits no mesmo tique virarem um acorde
  percussivo e peças diferentes não forem descartadas pela `monofonizar` do baixo. → `ataques_em_ticks` em
  `services/rhythm.py`: peças do mesmo tique viram um grupo, a mesma peça repetida no tique é devolvida para relato,
  duração gráfica até o grupo seguinte e no máximo uma semínima. A bateria no pipeline (item 5) passa por ela, nunca
  pelo `monofonizar`.
- [x] GP5: escrever faixa nativa de percussão (`isPercussionTrack`, canal MIDI 10) e peças simultâneas no mesmo beat;
  pronto com gravação → releitura preservando peça, tique e simultaneidade, além de abertura por leitor
  independente. → `Gp5PercussaoExporter` atrás de `ExportadorDePercussao` (Protocol próprio, decisão do usuário;
  emenda do ADR-044). MuseScore lê as 32 figuras e as peças.
- [x] MusicXML: escrever pauta não afinada, clave de percussão e `Unpitched`/`PercussionChord` com mapa GM explícito;
  pronto quando XML cru, round-trip do music21 e importação real no MuseScore preservarem peça, tique e
  simultaneidade. → `MusicXmlPercussaoExporter` e `MAPA_PERCUSSAO` (GM 35–59, drumset do MuseScore), com
  `<instrument id>` por nota; sem ele o MuseScore confunde 38 com 40 (emenda do ADR-044).
- [x] Integrar `--instrumento bateria` na CLI/API sem alterar o default; pronto com teste ponta a ponta que usa o stem
  `drums`, entrega os dois formatos e não gera tablatura de cordas. O transcritor da bateria usa
  `silencio_inicial_s=0.1` (ADR-045); o dos outros perfis, não. → `_parte_de_bateria`, descartes por motivo em
  `ataques_descartados`, opção na página. Pipeline inteiro na `bateria-mix`: F1 micro 0,901, igual ao stem cru (emenda
  do ADR-044).

#### M3 — piano depois

- [x] Medir piano acústico e elétrico separadamente, com acordes de duas mãos, inversões, notas repetidas e extremos
  A0/C8; pronto com teste `slow` e tabela por rótulo/condição, ou veredito negativo documentado. → Tabela por parte
  no `test_mede_perfil` e fixture `piano-*-extremos` (emenda do ADR-044): A0/C8 nunca saem, nem no meio do áudio; a
  mix perde a mão esquerda e o stem a devolve; inversões perdem a nota de cima; o elétrico acerta as notas com o
  rótulo de outro instrumento.
- [x] MusicXML: escrever piano em sistema de duas pautas, acordes verdadeiros e vozes quando as durações sobrepuserem;
  pronto quando round-trip e MuseScore real preservarem todas as alturas, ataques, durações quantizadas, clave e
  pauta. → `MusicXmlPianoExporter` (emenda do ADR-044): no máximo 4 vozes por pauta, porque o MuseScore descarta a
  5ª; acima disso a duração encolhe (decisão do usuário), altura e ataque não. Beams consertados voz a voz (ADR-038).
- [x] ~~Spike de GP5 e integração do piano acústico~~ — fora da prioridade por orientação do usuário (2026-09-28).

#### M4 — guitarra polifônica por último

- [x] Medir separadamente guitarra acústica, elétrica limpa e distorcida, com notas simples, díades e acordes de até
  seis notas; pronto com teste `slow`, tabela por condição e comparação explícita com o teto do ADR-011, ou veredito
  negativo. → `revocacao_por_acorde`; acordes de 6 notas em 21–24 de 24, 23–24 no stem (emenda do ADR-044 de
  2026-09-25, comparação com o ADR-011).
- [x] Implementar atribuição de acordes ao braço por teste de propriedade (`services/acordes.py`, emenda do ADR-044 de
  2026-09-25); pronto quando toda nota preservar a altura, cada acorde usar cordas distintas, nenhum traste exceder
  o máximo e a falha em acorde impossível for relatada, não monofonizada.
- [x] GP5: emitir acordes no mesmo beat, afinação de guitarra e programa GM do perfil; pronto quando gravação →
  releitura preservar alturas, cordas, trastes, ataques e simultaneidade, com abertura por leitor independente.
- [x] MusicXML: emitir partitura + tablatura de guitarra, clave correta, afinação e acordes; pronto quando XML cru,
  round-trip e MuseScore real preservarem as posições escolhidas, inclusive uma digitação válida alternativa.
- [x] Integrar os três perfis de guitarra na CLI/API pelo stem `other`; pronto quando o relatório separar erro de
  rótulo, contaminação do stem e acorde impossível, sem fundir os três rótulos numa única parte. - [x] Pipeline:
  `instrumento` (padrão `baixo`, caminho intacto); guitarra pelo stem do perfil, filtro pelos rótulos do perfil,
  notas do mesmo tique unidas antes do `ViterbiAcordes` (senão o exportador recusa depois dos minutos de CPU),
  andamento pelo primeiro ataque de cada acorde, sem readmissão, monofonização nem conferência de oitava. - [x]
  Relatório: `erro_de_rotulo` (outras guitarras), `contaminacao` (outras famílias no stem) e `acordes_impossiveis`,
  vazios no baixo. - [x] Nada do baixo é sobrescrito: arquivos e cache de notas levam o perfil no nome
  (`<nome>.guitarra-limpa.gp5`, `notas.guitarra-limpa.jsonl`); chaves de `artefatos` continuam `gp5`/`musicxml`;
  stem e playback como `outros` e `sem-outros`. Auralização com o programa GM do perfil. - [x] CLI `--instrumento` e
  API `instrumento`; `--afinacao` só vale para o baixo; perfis sem exportador (bateria, piano) recusados antes do
  download. - [x] Ponta a ponta `slow` com `guitarra-limpa-mix`, Demucs e MuScriptor reais.

#### M5 — compatibilidade e verificação de entrega

- [x] Preservar o caminho atual do baixo byte a byte nas fixtures existentes; pronto quando os pisos atuais, contagens
  de descarte e artefatos de round-trip não mudarem ao deixar `--instrumento` ausente. Verificado em 2026-09-25:
  `d0d7015` (antes do `instrumento`) contra `8703c25`, fixtures `walking`, `misto`, `graves` e `oitavas`, com `bpm`
  90 e estimado, a mesma transcrição real do MuScriptor nas duas e o separador dublado (o Demucs não se repete entre
  rodadas). GP5, WAVs, cache de notas, contagens, andamento e tom idênticos byte a byte. O MusicXML só difere nos
  ids `P…`/`I…` que o music21 sorteia a cada gravação — a versão antiga rodada duas vezes também difere de si mesma
  —; com eles normalizados, os 8 arquivos são idênticos.
- [x] Adaptar a página apenas para formatos realmente suportados; pronto com teste `navegador` verificando seleção,
  artefatos e mensagem explícita quando o alvo não tiver GP5 — sem exigir julgamento musical. - [x]
  `<select id="instrumento">` com baixo e as três guitarras; afinação desabilitada fora do baixo e enviada como
  `null`. - [x] Relato de `erro_de_rotulo`, `contaminacao` e `acordes_impossiveis`. - [x] Job sem `gp5` em
  `formatos`: mensagem explícita, sem carregar. - [x] GP5 de guitarra (6 cordas, acorde) renderizado no Chromium
  real.
- [x] Rodar `uv run pytest -n auto`, `uv run ruff check src/ tests/`, `uv run mypy src/`,
  `uv run pytest -m "slow and not network"` e, se a página mudar, `uv run pytest -m navegador`; pronto somente com
  saídas e números registrados, sem afirmar que a suíte padrão exercitou modelo, Demucs ou navegador. Verificado em
  2026-09-25 em `8703c25`: suíte padrão 458 passando; ruff e mypy limpos; `-m "slow and not network"` 38 passando em
  13 min, nenhum abaixo do piso (ponta a ponta da guitarra: nota F1 0,990, margem +0,030; `misto` do baixo com
  separação: nota 0,968, margem +0,000). A página não mudou; `navegador` não se aplica ainda.

## Pendências para o Welington

- [x] ~~Aval para `omarchy-pkg-install musescore`~~ — já instalado (MuseScore 4.7.4, conferido em 2026-09-24)

## ✅ Resolvido — GP5 gravado perdia beats no round-trip (2026-09-22)

Achado ao verificar o ADR-018 com o CLI real, **não introduzido por ele** (o mesmo resultado aparecia com as mudanças em
`git stash`).

- **Sintoma:** `out/escala.gp5` relido com PyGuitarPro trazia 4 beats com nota em vez de 15; cada compasso virava **um**
  beat com todas as notas empilhadas dentro.
- **Causa raiz:** `gp.Beat.status` nasce `BeatStatus.empty` no PyGuitarPro, e o exportador só ajustava o das pausas
  (`rest`). Na leitura, `gp3.readBeat` devolve `0` para beat `empty` em vez da duração, então o cursor `start` não
  avança e `getBeat(voice, start)` devolve o beat anterior — as notas seguintes entram todas nele. Reproduzido com
  PyGuitarPro puro, sem nada do Thoth: 4 beats escritos com `empty` → `[4]` na leitura; com `normal` → `[1, 1, 1, 1]`.
- **Correção:** `beat.status = gp.BeatStatus.normal` em `Gp5Exporter._nota`.
- **Por que a suíte não pegava:** os asserts liam as notas achatadas sobre todos os beats (`_lidas`), o que sobrevive à
  fusão. `test_cada_nota_ocupa_um_beat_proprio` agora afirma a estrutura, e
  `test_silencio_vira_pausa_e_nao_desloca_a_nota` passou a cobrar o ataque em ticks em vez da sequência de beats que o
  bug produzia.

## Fase 7 — Configuração de agentes (2026-09-23)

Contrato de projeto para os agentes que trabalham neste repositório. `AGENTS.md` é o canônico (o Codex só lê esse);
`CLAUDE.md` importa com `@AGENTS.md` e acrescenta a cauda que só o Claude Code entende — o `@import` é resolução
exclusiva do Claude, e inverter a direção faria o Codex ler um ponteiro vazio **sem erro visível**.

- [x] `AGENTS.md` — só os _deltas_ que um agente novo erraria: pt-BR no código, teto do Python, o que `pytest` **não**
  roda por padrão, repositório público
- [x] `CLAUDE.md` — `@AGENTS.md` + skills e fluxo `tasks/`
- [x] `.claude/settings.json` — allowlist estreita, nada específico da estação (o repositório é público); o que for
  local vai em `.claude/settings.local.json`, agora no `.gitignore`
- [x] `.claude/commands/verificacao.md` — os três comandos da verificação de entrega
- [x] Revisão do `AGENTS.md` pelo Codex contra o repositório

**Suposição declarada:** `install.py` (`~/workspace/claude-md`) gerencia o `~/.claude` global. O `.claude/` deste
repositório é versionado aqui e não entra no instalador.

- [x] Três docstrings realinhados aos ADRs (2026-09-23): `services/rhythm.py` e `adapters/export/gp5.py` tratavam o BPM
  como obrigatório (ADR-019/021) e `domain/ports.py` chamava a separação de opcional (ADR-010). Achado pela revisão
  do Codex sobre o `AGENTS.md`.

## Fase 8 — Análise conjunta Claude + Codex (2026-09-23)

Revisão de projeto inteiro feita em paralelo por Claude Opus 5 e Codex `gpt-5.6-sol`, com os achados cruzados e
verificados um a um contra o código. Ordem de execução abaixo é por impacto, com dependência declarada onde existe.

**Decisão do usuário nesta rodada:** executar tudo, inclusive os itens de pesquisa (B2/B3/B7/B9), cada um com ADR e
medição antes do código. A modelagem de A1 foi decidida na conversa: **decompor no exportador**, não partir o evento no
pipeline.

### Defeitos com correção definida

- [x] **A1 — nota que cruza a barra é truncada, em GP5 e MusicXML.** (ADR-022) `eventos()` devolve a duração real; o GP5
  fatia nas barras e liga com `NoteType.tie`, o MusicXML não precisou mudar — o `makeNotation` já ligava. Censo do
  acervo: em Is It A Crime, 26,3% das notas saíam encurtadas e só 74,2% da duração soava. Verificado ponta a ponta
  nessa música: 778 ataques para 778 notas de entrada, 215 compassos e nenhum fora de 4/4.
- [x] **B6 — teste de quantização ponta a ponta.** (ADR-023) `tests/integration/test_quantizacao_ponta_a_ponta.py`:
  referência sintética em código (não em `cache/`, que é gitignorado) → rítmica → GP5 → releitura → `avaliar`. 2,9
  s, na suíte padrão. Conferido: com o `rhythm.py` antigo, 3 dos 5 testes reprovam.
- [x] **A2 — dobrar o andamento para 70–160 descarta metade das notas.** (ADR-024) `desdobrar()` em `tempo.py`, chamada
  entre transcrever e `ajustar`, só no caminho estimado. Critério: colisão na grade acima de 10%, no máximo duas
  dobras. Medido: colisão de 0,0–2,8% no BPM certo contra 20–37% na grade pela metade. `Resultado.desdobrado` +
  linha na CLI. Limite declarado: música sem semicolcheia (0,0–4,5%) não é resgatável — é limite do sinal.
- [x] **A11 — `--bpm 0` colapsa a música em uma nota.** (ADR-025) `BPM_MINIMO/MAXIMO` (20–300) em `tempo.py`, uma fonte
  para CLI, API e pipeline; `transcrever` valida antes do download. `AFINACOES` na CLI com `typer.BadParameter` —
  nome fora do catálogo não vira mais a afinação padrão calado (a chave virou nome no ADR-028).
- [x] **A3 — piso do teste da separação era 0,682 e o ADR-010 mediu 0,968.** (ADR-010, emenda 2026-09-23)
  `COM_SEPARACAO_NOTA_F1 = 0.968`, exato — o F1 é discreto (~0,03 por nota em 16). O piso antigo fica com mensagem
  própria: abaixo de 0,682 é o ADR desmentido, não regressão. Medido 2x: 0,968, margem +0,000, `ref=16 est=15`.
- [x] **A4 — cache do Demucs não pertencia ao modelo** que o produziu. (ADR-026) `separate` procura em
  `out_dir / self.model`; os dois modelos convivem no mesmo cache. Medido: stem de `mdx_extra` passava por
  `htdemucs_ft`.
- [x] **A5 — nenhuma escrita de cache era atômica.** (ADR-026) `thoth/arquivos.py` com `escrita_atomica` e
  `diretorio_atomico`, vizinhos do destino (o `/tmp` desta estação é outro ponto de montagem). Quatro sítios: notas,
  WAV local, WAV do YouTube, stems. Três testes vermelhos antes de verdes.
- [x] **A7 — `stderr` dos subprocessos era descartado** nos 6 pontos. (ADR-026) `thoth/processos.py` com `rodar` e
  `ErroDeProcesso`; cada módulo mantém o próprio tipo de erro na fronteira. `FileNotFoundError` continua passando
  direto.
- [x] **A6 — jobs concorrentes dividem arquivos**; dict `jobs` sem limite. ADR-027: execução serializada por
  `threading.Lock`, `status` nasce `na fila`, histórico com teto de 50 descartando os concluídos mais antigos — e
  nunca o que ainda não terminou. Teste de concorrência com threads reais, verificado vermelho (o segundo job
  entrava no pipeline com o primeiro dentro).
- [x] **A9 — `pipeline.py` instancia adapters**; `AudioSource` não é injetável. `transcrever(source=...)` como os outros
  quatro estágios: `source or resolver_fonte(ref)`. Sem ele, todo teste do pipeline arrastava ffmpeg ou rede.
- [x] **A10/B4 — `PADRAO` e `TUNING_BASS_DROP_D` existem e não têm porta de entrada.** (ADR-028) Catálogos nomeados:
  `AFINACOES` (`4`/`5`/`drop-d`) em `models.py` e `DIGITACOES` (`iniciante`/`experiente`) em `fretboard.py`.
  `--afinacao`/`--digitacao` na CLI, campos no `Pedido`, dois `<select>` na página; `--cordas` sai (drop D tem
  quatro cordas — contar cordas não a nomeia). O JS perdeu o `Number()`, e o formulário ganhou teste de navegador
  que o dirige: `-m navegador` 3 passed.
- [x] **A8 — `octave_check` ignora `offset_s`** e analisa 0,6 s fixos. (ADR-029) `janela_s` virou teto: a janela é
  `min(teto, offset - onset)`. Teste vermelho antes: nota de 0,3 s seguida de 30,9 Hz forte passava calada.
- [x] **A12 — `octave_check` lê o stem inteiro na memória.** (ADR-029) `setpos` + `readframes` por nota, arquivo aberto
  uma vez. Medido com `tracemalloc` em 30 s de WAV: pico de 26,5 MB → menos de 2 MB.
- [x] **B5 — nenhuma métrica de offset.** (ADR-023) `nota_offset_f1` e `duracao_ratio` em `Scores`, informativas e fora
  de qualquer piso. Medido: com o corte na barra ativo, as duas métricas antigas dão 1,000 com 3 de 13 notas
  encurtadas.
- [x] **B8 — oitava é diagnóstico, não sugestão.** (ADR-030) `pitch + 12` deixou de ser afirmado: a mesma razão é medida
  para a candidata e a sugestão só sai quando ela explica melhor — senão `suggested_pitch` é `None`. A comparação é
  entre as duas razões, não um segundo corte pelo `limiar` (calibrado só na original). O gatilho não mudou, então os
  testes com modelo real seguem valendo. Exposto na CLI, no `_resumo` e na página; `inf` vira `null` (`Infinity`
  quebra o `JSON.parse`). `-m navegador` 4 passed.

### Pesquisa — ADR e medição antes do código

- [x] **B9 — grafia sempre com sustenido.** (ADR-031) `services/tonalidade.py`: estimativa via music21 com **margem
  contra a melhor interpretação de sinal oposto** (o sinal é o que muda a grafia; relativas escrevem igual), teto
  0,05. Medido no acervo: 3 de 7 músicas são tom bemol (~476 notas mal escritas) e uma é empate exato — o único caso
  recusado pela margem. Armadura errada imprime mais acidente que armadura nenhuma (11 contra 9 em 12 notas), então
  abaixo da margem nada muda. `--tom`/campo na página/`Pedido.tom`; exportadores com `armadura`. `-m navegador` 5
  passed.
- [x] **B7 — digitação otimiza posição, não técnica.** (ADR-032) O estado do Viterbi virou `(corda, traste, mão)`: o
  deslocamento é cobrado contra o último traste **pisado**, e mão ainda não posicionada não paga nada. O
  `3 → 0 → 15` do enunciado não reproduz — a emissão limita o braço ao traste ≤10, e o pior salto escondido medido
  é 8. No acervo (7924 notas): experiente 27 → 8 saltos acima de 4 trastes (os 8 restantes são genuínos, lidos um a
  um), iniciante 19 → 17 (o `acima_da_janela` já prendia a mão). Posição muda em 0,28% das notas; custo de tempo
  abaixo do ruído. Sem peso novo em `Custos`. A leitura ampla de "técnica" (articulação, dinâmica) é o B3.
- [x] **B3 — nada de dinâmica nem articulação.** (ADR-033) **Resultado negativo: pesquisa feita, nenhum código.** As
  três hipóteses foram medidas e as três falham. Articulação é impossível: `offset_s` é preenchimento — provado
  contra fixture de duração conhecida (notas de 0,45 s com 0,10 s de silêncio voltaram contíguas) e 83%–99,7% de
  lacuna zero no acervo. Dinâmica não existe na saída do modelo (velocidade 120 contra 40 descartada) e, do áudio, é
  IQR de 2,4–5,6 dB sem rótulo para calibrar corte. Deslize: o discriminador dispara igual ou mais no controle (pares
  com silêncio, que não podem ser deslize). Reabre com tablatura de referência (Camada 3, ADR-007). O achado
  sobre `offset_s` foi para `NoteEvent.duration_s`, `tonalidade.py` e uma emenda ao ADR-022.
- [x] **B2 — representação rítmica estreita.** ADR-034. **Resultado negativo: pesquisa feita, nenhum código.** A
  premissa do item caiu: a semicolcheia ganha da tercina e das duas grades de swing nas sete músicas (10,4–30,8 ms
  contra 27,2–58,6 e 23,9–88,4), e a fusa quase não melhora (0,1–2,9 ms em quatro) — o resíduo é jitter de ataque do
  transcritor, não erro de quantização, então **grade mais fina não reabre o item**. Tercina some contra controle
  interno em seis das sete. Andamento variável é real em 1 de 7 (degrau 103,0 → ~105), e a medida barata acusaria
  primeiro a música errada: limiar de n=1, reprovado no mesmo piso do ADR-033.

### Verificado e descartado

- A suíte **não** trava: `-n auto` 174 passed em 16,1 s, `-n 0` 174 passed em 29,3 s. O travamento que o Codex relatou é
  do sandbox dele.
- MusicXML com `Bass8vb` e sem `<transpose>` **não** é defeito: o round-trip devolve C2 / MIDI 36, correto, e a posição
  na pauta é a usual do baixo.
- `astype(np.float64)` em `_ler_mono` **não** é redundante — o buffer vem `<i2`.

## Fase 9 — tablatura dentro do MusicXML (ADR-035)

> Origem: o MuseScore abria os nossos arquivos só em notação. O `.gp5` já declara `tablature=True` e o importador de
> Guitar Pro do MuseScore ignora a flag — não há o que corrigir lá. O MusicXML, esse sim, não dizia nada sobre
> tablatura.

Sondado antes de escrever código, com `mscore` de verdade:

- `<staff-details number="2">` depois dos `<clef>` monta a pauta de tablatura;
- `<staff-tuning line="N">` com **linha 1 = corda mais grave** devolve `StringData [28, 33, 38, 43]` no MuseScore — a
  nossa afinação, na ordem certa;
- na volta pelo music21 10.5 o arquivo vira 2 `PartStaff`: `parts[0]` notação, `parts[1]` tablatura;
- o MuseScore **honra** o nosso `<technical>`: mandei 8-10-12-13 na corda grave, digitação que algoritmo nenhum
  escolheria, e foi exatamente o que voltou.

- [x] Testes primeiro: estrutura de duas pautas, linhas e afinação no XML cru, afinação de 5 cordas inteira, nome da
  nota só na partitura, corda/traste só na tablatura, e um teste contra o `mscore` real (pulado se ausente).
- [x] `MusicXmlExporter` passa a montar `PartStaff` de notação + `PartStaff` de tablatura sob um `StaffGroup`, e injeta
  `<staff-details>` após a escrita — o music21 10.5 emite `<staves>`, `<staff>` e a clave TAB, mas não o
  `staff-details`.
- [x] Testes existentes ancorados em `parts[0]` — sem isso passam a contar cada nota duas vezes e a asserção muda de
  significado em silêncio.
- [x] ADR-035 em `tasks/decisions.md`.

### Fechada

Verificação de entrega: `pytest -n auto` 279 passando; `-m slow` do exportador passando com o `mscore` 4.7.4 instalado;
`ruff` e `mypy --strict` limpos.

Uma asserção fora do exportador precisou de âncora:
`test_pipeline.py:: test_o_tom_informado_chega_a_armadura_da_partitura` lia a armadura pela partitura toda e passou a
ver duas. O arquivo grava **uma** — o `<attributes>` é da parte inteira e o music21 dá uma cópia a cada pauta na
leitura. Ancorada em `parts[0]`.

Os sete artefatos em `out/` são anteriores a isto: ainda de uma pauta. Reexportar é rodar o pipeline de novo nas sete.

## Fase 10 — o áudio junto da partitura (ADR-036)

> Origem: pedido direto — "quero os arquivos wav, gp5 e musicxml na mesma pasta". Mix e baixo isolado; sem `.mscz`, que
> o MuseScore não precisa desde o ADR-035.

- [x] Teste primeiro: nomes, mesma pasta dos exportadores, bytes iguais à origem, e não-symlink. No `slow` real, mix e
  baixo diferentes entre si — asserção que o dublê não permite, porque lá o stem é o próprio mix.
- [x] `transcrever` copia os dois para `out_dir` e os devolve em `artefatos`.
- [x] ADR-036 em `tasks/decisions.md`.
- [x] Oito músicas já processadas preenchidas sem reprocessar, e os sete `.mscz` apagados.

## Fase 11 — pasta por música e CLI que mostra os estágios (ADR-037)

> Origem: pedido direto — "cli colorido que mostra todas as etapas do processo", "salve os arquivos em pastas separadas
> com o nome da musica", "todos os wavs que você produzir". Decidido junto: nomes repetem o da música dentro da pasta, e
> os wavs são mix, baixo, sem-baixo e a auralização.

- [x] Teste primeiro: um dublê de `Progresso` coletando os nomes dos estágios na ordem; caminhos dentro de
  `out/<nome>/`; os quatro wavs presentes e com os bytes da origem.
- [x] `Progresso` como `Protocol` em `domain/ports.py` — o pipeline anuncia o estágio, quem desenha é o CLI. Sem isso o
  `rich` entraria num service.
- [x] `transcrever` grava numa pasta por música e copia os quatro wavs.
- [x] Auralização dentro do pipeline, e falha dela **não** mata a corrida: o soundfont é opcional e são minutos de CPU
  em jogo (ADR-014).
- [x] `transcribe` com `rich`: um estágio por linha, tempo decorrido, ✓ ao fechar.
- [x] ADR-037 em `tasks/decisions.md`, emendando o ADR-036 no que muda.
- [x] As oito músicas já em `out/` movidas para o formato novo.

### Fechada

Verificação de entrega: `pytest -n auto` 289 passando; `ruff check` e `mypy --strict` limpos.

Conferido rodando de verdade, e não só pelo teste: `thoth transcribe` numa música cacheada imprimiu os dez estágios com
o tempo de cada um — `obtendo o áudio` 0:00, `estimando o andamento` 0:05, `separando o baixo` 0:00 (cache),
`transcrevendo as notas` **2:36**, `ajustando a grade rítmica` 0:05, `conferindo as oitavas` 0:01,
`posicionando no braço` 0:00, `exportando a partitura` 0:03, `copiando os áudios` 0:00, `auralizando` 0:06. Total 3m15
de parede, 25m53 de CPU.

As oito pastas em `out/` conferidas com 6 arquivos cada e nada solto em `out/` (`find out -maxdepth 1 -type f` vazio).
Os quatro WAVs de uma delas conferidos por hash: distintos, e o RMS do playback (0,0896) fica entre o do mix (0,1215) e
o do baixo (0,0290), como se espera de um mix sem o baixo.

Achado que virou a Fase 12: o music21 cospe `beam: WARNING: Found a messed up beam pair` ao gravar o MusicXML. Não foi
silenciado — o aviso é sinal real, e investigar mostrou que ele **subnotifica** o problema. Números medidos abaixo.

## Fase 12 — beams mal-formados no MusicXML ✅ **FECHADA (2026-09-24)**

> Origem: o aviso `beam: WARNING: Found a messed up beam pair` que a Fase 11 deixou anotado. Investigado em 2026-09-23.
> **São dois defeitos, não um**, e o aviso só cobre o menor dos dois.

### O defeito, medido nos oito arquivos já entregues

**208 beams mal-formados** — `end` ou `continue` num nível de beam sem `begin` aberto, o que o MusicXML não admite. De 8
a 52 por música, metade em cada pauta (as duas compartilham o ritmo). Nenhum `begin` pendurado.

O aviso do music21 aparece de 0 a 6 vezes por música: ele só dispara no subcaso que `mergeConnectingPartialBeams`
examina. **O resto sai calado.**

| forma                        | quantos | causa                              | quem tem culpa |
|------------------------------|---------|------------------------------------|----------------|
| (A) há pausa dentro do grupo | 46      | entregamos um stream com buracos   | nossa          |
| (B) grupo contíguo           | 162     | nota cruzando a fronteira de tempo | music21 10.5   |

> Este split vem do classificador por proximidade de pausa, que **superestima (A)**: `end@1` solto perto de uma pausa
> era contado como (A) sem estar dentro de grupo nenhum. A medição controlada mais abaixo o supera; o total (208) segue
> valendo.

### (A) — nossa: o stream vai com buracos para o `makeNotation`

`_pauta` faz `parte.insert(offset, nota)` e nunca preenche as pausas. O beam é calculado antes de elas existirem, e duas
notas a meio compasso de distância se veem como vizinhas. Medido:

```python
ts.getBeams([Note(0.25), Rest(2.25), Note(0.25), Rest(1.25)])  # [None,None,None,None] ✅
# mas o mesmo ritmo inserido com buracos: 1/begin + 2/forward hook … 1/end + 2/end ❌
```

Com `parte.makeRests(fillGaps=True, inPlace=True)` antes do `makeNotation`, o music21 acerta sozinho: nenhum beam, que é
o certo para semicolcheia isolada. **A forma (A) é uma linha.**

### (B) — do music21: nota que cruza a fronteira de tempo

Sobrevive ao `makeRests` — é ritmo contíguo, sem pausa nenhuma. O mínimo é quatro notas: `(2, 8, 3, 3)` semicolcheias
(colcheia, mínima, colcheia pontuada, colcheia pontuada) sai `1/begin, 1/continue, 1/end, 1/end` — dois `end`. **O
music21 não avisa em nenhum dos 18 ritmos mínimos encontrados.**

Varredura de todas as composições contíguas de um compasso 4/4 na grade de semicolcheia, com 2 a 5 notas:

- nenhuma nota cruzando a fronteira de semínima: **0 mal-formados em 13**
- alguma nota cruzando: **132 mal-formados em 1535**

A amostra negativa é pequena (13), então isso é compatível com "cruzar o tempo é condição necessária", não prova dela.
10.5.0 é a versão mais nova que existe no PyPI: não há correção a montar.

### O que já foi descartado como saída

- **Não emitir beams.** Conferido: o MuseScore 4.7.4 **não** beameia sozinho quando o arquivo não traz beam nenhum —
  cada semicolcheia sai com bandeirola solta.
- **Deixar o leitor consertar.** O MuseScore não recusa o arquivo, mas o conserto é visível e errado: no caso mínimo de
  (A) ele tira a primeira nota do grupo e pendura o beam numa **pausa**.

### O que falta

- [x] Teste de gramática sobre o XML escrito, por (pauta, voz, nível), incluindo `begin` que fica aberto. É o teste que
  faltava: o round-trip pelo music21 não pega nada disso, porque ele relê o que escreveu.
- [x] (A): `makeRests(fillGaps=True)` antes do `makeNotation` em `_pauta`.
- [x] (B): refazer por tempo só o compasso quebrado — ADR-039, 2496 → 0 nos 32767 compassos contíguos; nas nove músicas,
  ver o fim desta seção. Era: decidir a abordagem — nenhuma foi escolhida ainda. Quebrar o grupo na fronteira de
  tempo é o candidato, mas não está verificado que resolve, e não há botão para isso (conferido em
  `meter/base.py::getBeams` e `stream/makeNotation.py::makeBeams`).
- [x] Reexportar as músicas depois da correção — são **nove**, não oito; a conta anterior estava errada. Resultado
  abaixo.
- [x] ADR-038 com a medição. — escrito para (A); a parte (B) fica registrada como aberta.

### (A) fechada — medição controlada

O mesmo conjunto de notas de sete músicas do cache, exportado com e sem a linha do `makeRests` (comparar com os arquivos
entregues não isola nada: sem o recuo de fase do pipeline o conjunto de notas muda — daí 248 aqui contra os 208 medidos
sobre a base entregue):

| base           | mal-formados | (A) | (B) |
|----------------|--------------|-----|-----|
| sem a correção | 248          | 48  | 200 |
| com a correção | 200          | 0   | 200 |

Queda monotônica nas sete, nenhuma piora. Os 14 que a primeira conta ainda punha em (A) são (B) disfarçados: `end@1`
solto numa colcheia pontuada, sem `begin` em lugar nenhum.

Verificação de entrega: 291 passed + 1 xfailed (era 289), ruff e mypy limpos. O `xfail(strict=True)` de (B) é de
propósito — fica vermelho no dia em que (B) for corrigido.

O conteúdo não mudou com a correção: nos sete pares antes/depois, notas, compassos e pausas batem exatamente — o
`makeNotation` já produzia as mesmas pausas, e a correção só muda **quando** elas existem. Nenhum `begin` aninhado nem
pendurado em nenhuma das bases.

### Reexportadas e validadas — 2026-09-23

As nove pelo caminho de verdade (`thoth transcribe`, com stems e download em cache; 34 min de relógio no total, 2m03 a
8m11 por música, todas com saída 0). O validador de gramática sobre `out/*/*.musicxml`:

| música                    | mal-formados |
|---------------------------|--------------|
| Dance of Death            | 50           |
| Smooth Operator           | 24           |
| Seu Jorge — Tive Razão    | 22           |
| SOU EU                    | 38           |
| Feel Like Makin' Love     | 28           |
| Sade — Is It A Crime      | 14           |
| Hallowed Be Thy Name      | 10           |
| SOJA — Everything Changes | 2            |
| Ne Obliviscaris — Equus   | **0**        |
| **total**                 | **188**      |

Nenhum `begin` pendurado, nenhum `begin` aninhado. E a asserção que importa: **0 grupos de beam abraçando pausa** nos
nove arquivos — a assinatura da forma (A) desapareceu.

Os 16 que o classificador ainda põe em "(A)" são (B) com pausa por perto: a heurística de proximidade deixa de valer
quando as pausas passam a existir em todo compasso, e a conta estrutural acima é a que decide. Os 188 são todos (B), o
defeito aberto do music21 10.5.

Os artefatos não entram no repositório (`out/` no `.gitignore`, ADR-005): o que fica versionado é a correção que os gera
e esta medição.

### (B) fechada — 2026-09-24 (ADR-039)

Só o compasso quebrado é refeito, por tempo, com o `getBeams` do music21. Varredura de todos os 32767 compassos 4/4
contíguos: music21 sozinho 2496, primeira versão do conserto 80 (achados pelo Codex: `measureStartOffset` do tempo, não
da primeira nota), esta **0**.

Nove músicas reexportadas pelo `thoth transcribe` real, todas com saída 0: **188 → 0**. Nas oito comparáveis, 0 dos 2998
pares (compasso, pauta) válidos mudaram e as notas batem exatamente; só os 94 compassos quebrados foram refeitos.

**Achado de passagem:** a reexportação de 2026-09-23 do _Equus_ saiu com **4 cordas** — o `--afinacao 5` que
`tasks/corpus.md` manda usar ficou de fora, e ~444 notas abaixo do E1 foram descartadas (ADR-014) calado. A tabela de
2026-09-23 acima (Equus: 0) mediu esse arquivo. Refeito com 5 cordas: 3251 elementos de nota, 0 mal-formados.
