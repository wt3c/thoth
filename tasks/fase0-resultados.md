# Fase 0 — resultados medidos

Estação: Pandora · CPU only (ADR-002) · MuScriptor 0.3.0 · 2026-09-21
Amostra: 30s de `4kd_eR4216g` (Giane Rangel — *Sou Eu*), Grupo A, a partir de 1min.

## Desempenho em CPU (`small`)

| condição | computação | × tempo real | extrapolação p/ 5 min |
|---|---|---|---|
| `--instruments electric_bass` | 11,8s / 30s de áudio | 0,39× | ~2,0 min |
| sem `--instruments` (livre) | 31,7s / 30s de áudio | 1,06× | ~5,3 min |

Condicionar o instrumento é **2,7× mais rápido** — o modelo decodifica um
instrumento em vez de todos. Viável sem GPU.

## `--instruments`: o custo do atalho

| | notas de baixo | extensão |
|---|---|---|
| condicionado | 99 | C#1 .. A3 |
| livre | 89 | C#1 .. A3 |

No modo livre o modelo separa `acoustic_guitar` (351 notas, G#2..C5) e `drums`
(133). Condicionar **infla o baixo em ~11%**, dobrando conteúdo alheio para
dentro do canal do baixo, já que os demais rótulos ficam proibidos.

**Trade-off:** 2,7× de velocidade contra ~11% de notas espúrias. Decisão pendente
da medição com ground truth sintético.

## Registro agudo: não é artefato de condicionamento

Hipótese testada: as notas em C#3..A3 seriam conteúdo de outro instrumento
forçado para o baixo pelo `--instruments`.

**Refutada.** Sem condicionamento algum, e com `acoustic_guitar` disponível e
sendo usado para 351 outras notas, o modelo atribui **exatamente as mesmas notas
agudas** ao `electric_bass` (2,26 C#3 · 2,50 G#3 · 2,73 G#3 · 2,96 F#3 · 3,19 F#3
· 3,42 D#3…, timings idênticos nas duas execuções).

Estrutura temporal: o registro agudo aparece em **blocos** (5 blocos, tamanho
médio 3,6, máximo 9), não intercalado nota a nota — padrão de linha melódica, não
de erro de oitava disperso.

**Resolvido pela Camada 2 (2026-09-21).** O Welington ouviu a auralização
(`baixo_aural.wav`, L=original / R=MIDI) e confirmou: "parece estar certo". As
frases agudas são o que o baixista toca de fato — **não há erro de oitava aqui**.

Consequência: o sanity-check de oitava do ADR-003 perde urgência; não há evidência
de que o MuScriptor troque oitava neste material. Fica como verificação barata a
implementar, não como correção de defeito observado. A Camada 2 provou seu valor
já no primeiro uso — respondeu em uma escuta o que a análise estática deixou
ambíguo.

## Notas abaixo de E1

20 das 99 notas estão abaixo de E1 (28) — C#1 (25) e D#1 (27). **Não são erro por
definição:** são 2ª e 4ª casas da corda B de um baixo de 5 cordas, equipamento
padrão em gospel brasileiro. O sanity-check de oitava do ADR-003 **não pode
travar na extensão de 4 cordas**.

## Bloqueio — Beat This! inalcançável

`--detect-tempo` (qualquer valor exceto `false`) baixa `beat_this-final0.ckpt` de
`cloud.cp.jku.at`. Esse host está **inalcançável** desta estação: timeout de
conexão em 0s, enquanto HuggingFace e YouTube funcionam. Não é a nossa rede.

- Só dispara com `-f midi` — `-f jsonl` não precisa de tempo e roda normal.
- **Contorno atual:** `--detect-tempo false`. O MIDI sai com tempos absolutos em
  segundos, sem BPM nem fórmula de compasso.
- Pendência: achar espelho do checkpoint ou aceitar quantização própria.

## Auralização — funciona

`--auralize <path> --soundfont /usr/share/soundfonts/FluidR3_GM.sf2` produz WAV
estéreo (L=original, R=MIDI). 18s no total para 30s de áudio, incluindo
transcrição. Dispensa o soundfont de 215 MB do HuggingFace.

## Camada 1 — ground truth sintético

Seis fixtures MIDI → fluidsynth (`FluidR3_GM.sf2`) → WAV normalizado a −1 dBFS de
pico (o áudio cru saía a −36 dB de média, nível que sabotaria a medição) →
MuScriptor → `mir_eval`, tolerância de onset 50 ms.

### `small` — o que interessa

| fixture | cond | onset F1 | nota F1 | ref | est |
|---|---|---|---|---|---|
| escala | livre | 1,000 | 0,968 | 15 | 16 |
| **graves** (B0..E1) | ambos | **1,000** | **1,000** | 10 | 10 |
| **groove16** (semicolcheias) | ambos | **1,000** | **1,000** | 32 | 32 |
| **oitavas** | livre | **1,000** | **1,000** | 12 | 12 |
| walking | ambos | 0,938 | 0,968 | 16 | 15 |
| misto (baixo+piano) | cond | 0,938 | 0,545 | 16 | **39** |
| misto (baixo+piano) | livre | 0,938 | 0,682 | 16 | 28 |

Três leituras:

1. **A região grave de 5 cordas é perfeita** (B0..E1, F1 1,000). Confirma que não
   se deve clampar em 4 cordas.
2. **Semicolcheias a 90 BPM: perfeito** (32/32). Resolução temporal não é gargalo.
3. **Saltos de oitava: perfeito** em modo livre. Não há tendência a erro de oitava
   — consistente com o que o Welington ouviu no áudio real.

O único caso ruim é `misto`, e ele mede exatamente o efeito do `--instruments`
(ver ADR-008), não uma fraqueza do modelo.

### `medium` — degenera em áudio sintético

`escala` livre → 291 notas (ref: 15), todas rotuladas `acoustic_guitar`, com
repetição da mesma nota a partir de t=4,01s. `oitavas` cond → 304 notas (ref: 12).
Zero notas de baixo em `oitavas`/`walking` livre.

É colapso de decodificação autorregressiva em entrada fora da distribuição: som de
soundfont limpo, um instrumento só, sem ruído nem ambiência. **No áudio real o
`medium` se comporta bem** (94 notas, coerente com as 89 do `small`) — o problema é
a fixture, não o modelo. Ver ADR-009.

## Grupo B — mix real, e a decisão da C1

Trechos de 30s escolhidos por energia em 60–250 Hz (não por chute): Sade em
t=240s, Seu Jorge em t=180s.

### Transcrição da mix direta (`small`, livre)

| | total | baixo | extensão | máx. simultâneas |
|---|---|---|---|---|
| Sade | 456 | 67 | E1..C3 | 1 |
| Seu Jorge | 686 | 63 | E1..**F#4** | **4** |

O Sade sai plausível. O Seu Jorge não: F#4 está fora de qualquer baixo de 4 ou 5
cordas, e quatro notas simultâneas não é linha de contrabaixo.

### Com separação (`htdemucs_ft --two-stems=bass`)

| | baixo | extensão | máx. simultâneas | concordância de onsets |
|---|---|---|---|---|
| Sade | 62 | E1..C3 | 1 | 79% |
| Seu Jorge | 52 | E1..F#3 | 1 | 87% |

Os artefatos do Seu Jorge desaparecem por completo. A escuta confirmou a causa:
**teclado vazando para dentro do canal do baixo** na versão sem separação.

Decisão registrada no ADR-010: Demucs deixa de ser condicional.

## Grupo C — os casos-limite não quebraram como eu previa

### Ne Obliviscaris — *Equus* (prog metal, baixo de extensão estendida)

Trecho de 30s em t=150s. Previsão registrada em `tasks/corpus.md`: **falha
esperada**, por afinação estendida e velocidade.

| | notas de baixo | extensão | máx. simultâneas | densidade |
|---|---|---|---|---|
| mix | 176 | B0..D3 | 1 | 5,9 notas/s |
| stem | 165 | B0..D3 | 1 | 5,5 notas/s |

**A previsão estava errada.** `B0..D3` cabe exatamente num baixo de 5 cordas
(`TUNING_BASS_5` já começa em B0=23), sem nenhuma nota simultânea e com densidade
coerente com o gênero. Mix e stem concordam. Não há evidência de quebra.

Custo: a mix densa levou **106s para 30s de áudio** (3,5× tempo real) por causa
das 1238 notas totais — o `distorted_electric_guitar` sozinho gera 769. Separar
antes derruba para 20s, um ganho de 5×. Reforça o ADR-010 por um segundo motivo,
independente da qualidade: **velocidade**.

### Toshiki Soejima — *Feel Like Makin' Love* (guitarra neo-soul)

| | notas | extensão | máx. simultâneas |
|---|---|---|---|
| mix (`clean_electric_guitar`) | 208 | F2..A#5 | 8 |
| stem `other` (`clean_electric_guitar`) | 188 | A#2..A#6 | 7 |

Sete a oito notas simultâneas é acorde de verdade, não artefato — é o que se
espera de neo-soul. Aqui a fraqueza documentada do MuScriptor (notas sobrepostas
do mesmo instrumento: onset F1 60,4 → 51,8) é a métrica que vale, e ela não se
mede por implausibilidade estrutural como no baixo. Precisa de escuta ou de
referência externa.

Observação lateral: o `htdemucs_ft` não tem stem de guitarra — ela cai em `other`
junto com teclados e sopros. Para o objetivo secundário multi-instrumento isso é
uma limitação a considerar, não resolvida pelo pipeline atual.

## Escuta do Grupo C — e o que a medição diz sobre ela

Veredito do usuário (2026-09-22): `neo_MIX` "muito bom"; `neo_STEM` "as notas
parecem corretas, mas pegou o som da dedilhada"; `soul_GUITARRA` "o som ficou
misturado".

### A dedilhada não está na transcrição — está no canal esquerdo

O arquivo de escuta é L = áudio de referência, R = MIDI sintetizado. No
`neo_STEM` o canal L é o **stem do Demucs**, não a mix. Pareando as duas
transcrições nota a nota (onset ≤50 ms + mesma altura):

| | mix | stem |
|---|---|---|
| notas de baixo | 176 | 165 |
| casadas entre si | 127 (77% do stem) | — |
| onset F1 mix~stem | 0,891 | — |
| notas < 100 ms (candidatas a ruído) | 5 (3%) | **2 (1%)** |

O stem não tem excesso de eventos curtos — tem menos que a mix. Mas **isso não
prova nada sobre a dedilhada**: a premissa de que ruído de ataque vira nota
*curta* é minha, nunca foi verificada, e a duração mediana é 140 ms nos quatro
conjuntos, ou seja, é quantizada demais para discriminar. Descartar a hipótese
com n=5 contra n=2 de um proxy que não mede o mecanismo seria autoengano.

O que é fato: a mix está a −13,0 LUFS e o stem a −16,5, então o `loudnorm`
**atenua** a mix mais do que amplifica o stem — a dedilhada não ficou mais alta,
ficou mais exposta. Se isso é desmascaramento (o ruído sempre esteve lá, coberto
por guitarra e bateria) ou artefato do Demucs, os dados atuais não dizem.
**Fica em aberto.** O que a investigação encontrou foi outra coisa, pior, abaixo.

### O que separar mudou de verdade, por faixa

| faixa | notas só na mix | alturas dessas notas | leitura |
|---|---|---|---|
| jorge | 15 | 28..**66** | F#4 num baixo: **teclado vazando**, exatamente o que o ouvido pegou |
| sade | 15 | 29..37 | dentro do baixo — divergência comum, sem viés detectável |
| neo | 49 | 23..38 | dentro do baixo — sem ground truth, não dá para dizer quem acerta |

Só no `jorge` a separação corrige um erro **identificável sem referência**. Nas
outras duas ela não degrada, e no `neo` economiza 5× de tempo. O ADR-010
(separar sempre) continua de pé, mas por motivos diferentes do que eu supunha:
o ganho de qualidade é específico de mix com vazamento, o ganho de velocidade é
geral.

### Guitarra: onde o sistema quebra

"O som ficou misturado" é o veredito perceptual da fraqueza já documentada do
MuScriptor em notas simultâneas do mesmo instrumento (onset F1 60,4 → 51,8). Com
7–8 vozes de neo-soul, as alturas saem plausíveis e o conjunto não se sustenta.

**Consequência de escopo:** o objetivo secundário (qualquer instrumento) não é
alcançável com este motor para material polifônico denso. O baixo — monofônico,
simultaneidade 1 medida em todas as faixas — é onde o sistema funciona. O
projeto segue baixo-primeiro não por preferência, mas por limite medido.

### O achado que o proxy escondia: a separação erra a oitava

O pareamento por onset **e** altura jogava para fora as notas em que os dois
concordam no tempo e discordam na altura. Casando só por onset:

| faixa | onsets coincidentes | mesma altura | altura divergente |
|---|---|---|---|
| neo | 146 | 127 | **19** |
| jorge | 49 | 48 | 1 |
| sade | 53 | 52 | 1 |

No `neo`, **13 das 19 divergências são de exatamente ±12 semitons** — e 12 delas
no mesmo padrão: mix diz B1 (35), stem diz B0 (23). Não é ruído de altura, é
salto de oitava sistemático, e cai em 7% da linha do stem.

**Qual dos dois acerta?** Três evidências, todas apontando para a mix, nenhuma
conclusiva sozinha:

1. **Continuidade melódica.** Saltos ≥ 12 semitons: mix 10% das transições, stem
   **19%**. Salto mediano: mix 2 semitons, stem 4. A linha da mix é mais suave —
   mas pedal em corda solta grave é idiomático em metal, então o argumento é
   fraco justamente neste gênero.
2. **Espectro nos 12 onsets** (janela de 0,6s, no áudio original *e* no stem): a
   banda de 61,7 Hz (B1) supera a de 30,9 Hz (B0) por 2–6×, e a de 30,9 Hz fica
   no piso de ruído ou abaixo dele em metade dos casos.
3. **Teste do 3º harmônico** (92,6 Hz existe em B0, não em B1): **inconclusivo**
   — ora no piso, ora bem acima dele. E 92,5 Hz é F#2, a quinta que as guitarras
   tocam o tempo todo numa música em B. O teste não separa as fontes.

**Status: em aberto, com suspeita forte sobre o stem.** Gerado A/B focado para
decidir por escuta — `~/thoth-fase0/neo_AB_B1_mix.wav` e `neo_AB_B0_stem.wav`,
com as 12 notas em disputa isoladas no canal direito.

**Por que isto importa além da Fase 0:** oitava errada é corda e casa erradas.
O erro atravessa intacto até a tablatura da Fase 4 e não há etapa posterior que
o detecte. Entra como **primeiro item do portão de regressão da Fase 1**.

**Por que a escuta anterior não pegou:** o Welington ouviu o `neo_STEM` inteiro e
disse *"as notas parecem corretas"*. Doze notas erradas de oitava, numa linha
rápida de metal, soando junto com o original — a Camada 2 não discrimina isso sem
um A/B focado. Limite metodológico da escuta, registrado.

### O ouvido não arbitra oitava no grave — e isso era previsível

Submetido o A/B com a linha completa (112 notas, só as 12 em disputa diferindo),
o veredito foi *"agora as duas ficaram perfeitas"*. Não é indecisão do ouvinte:
medido no FluidR3, o B0 rende −35,3 dBFS com **24% da energia abaixo de 50 Hz**
(fora do alcance de caixa e fone comuns), enquanto o B1 rende −30,4 dBFS com 0%.
O que sobra audível de um B0 são seus harmônicos, e o primeiro deles é 61,7 Hz —
a fundamental do B1. **As duas hipóteses soam quase iguais por construção.**

Registrado como ponto cego da Camada 2 no ADR-006. A questão de oitava é da
Camada 3 (referência externa), como o próprio ADR-006 já antecipava.

**Primeira aplicação concreta do ADR-007:** para fechar isto é preciso uma
tablatura humana de *Equus* em `.gp5`, baixada manualmente (o Welington tem
assinatura do Ultimate Guitar). Sem ela, a divergência fica registrada e o
verificador de oitava da Fase 1 nasce sem caso de teste.

### Nota de método: dois erros meus nesta rodada

1. **A/B sem contexto.** A primeira versão isolava só as 12 notas em disputa —
   tirava justamente a linha melódica que permite julgar oitava. Pedir veredito
   sobre isso teria produzido resposta sem valor.
2. **Bug silencioso no A/B.** A versão "B1" alterou 2 das 12 notas, não 12: o
   pareamento usava o onset da *mix* para localizar a nota do *stem*, que difere
   em até 50 ms. Os dois arquivos eram quase idênticos. Só foi pego porque o
   Welington estranhou a esparsidade e perguntou.

Os dois falham do mesmo jeito: **artefato de avaliação entregue sem verificação
própria**. O portão da Fase 1 precisa valer para o código de avaliação também,
não só para o pipeline — um avaliador quebrado produz decisão errada com a mesma
facilidade com que um transcritor quebrado produz tablatura errada.

## Veredito da Fase 0: **SEGUIR**

O critério era descobrir se a qualidade justifica construir o projeto. Justifica,
para baixo.

**O que sustenta o "seguir":**

- Simultaneidade **1** na linha de baixo em **todas** as faixas medidas — Sade,
  Seu Jorge, Ne Obliviscaris. É a propriedade que torna o baixo verificável sem
  referência externa: linha de baixo com notas simultâneas é erro visível.
- A extensão sai sempre dentro de um baixo real: `E1..C3`, `E1..F#3`, `B0..D3`.
  Nenhuma faixa exigiu vocabulário fora de `TUNING_BASS_5`.
- A previsão de falha no caso extremo (prog metal, baixo estendido) **não se
  confirmou** — e a refutação veio de medição, não de otimismo.
- Separação de fontes resolvida com evidência, não com heurística (ADR-010).

**O que sabemos que está quebrado, e não impede seguir:**

| problema | onde dói | mitigação |
|---|---|---|
| oitava errada em 7% (material grave e denso) | Fase 4 — corda e casa erradas | verificador espectral, primeiro item da Fase 2 |
| polifonia densa ilegível | objetivo secundário | fora de escopo (ADR-011) |
| `beat_this-final0.ckpt` inacessível | andamento | `--detect-tempo false` + quantizador próprio |
| dedilhada exposta pela separação | nada hoje | reavaliar se houver auralização no produto |

**O que a Fase 0 mudou no plano:** a Fase 4 virou caminho crítico (ADR-003 —
o motor não emite partitura), o Demucs virou etapa fixa (ADR-010), o escopo
fechou em baixo (ADR-011) e o portão de regressão passa a cobrir o próprio
código de avaliação, não só o pipeline.

---

## Adendo (2026-09-22): as fixtures viraram portão de regressão

A tabela da Camada 1 saiu do scratchpad e virou teste: `tests/sintetico.py` regera as seis
fixtures (MIDI → fluidsynth → normalização de pico; áudio nunca versionado, ADR-005) e
`tests/integration/test_regressao_fase0.py` cobra os números medidos, com o avaliador
agora dentro do repositório (`thoth.services.evaluation`).

Reprodução das seis, modelo `small`, condição livre — idêntica à Fase 0 na terceira casa:

| fixture | onset F1 | nota F1 | ref | est |
|---|---|---|---|---|
| escala | 1,000 | 0,968 | 15 | 16 |
| graves | 1,000 | 1,000 | 10 | 10 |
| groove16 | 1,000 | 1,000 | 32 | 32 |
| oitavas | 1,000 | 1,000 | 12 | 12 |
| walking | 0,938 | 0,968 | 16 | 15 |
| misto | 0,938 | 0,682 | 16 | 28 |

O portão roda sem folga (`FOLGA = 0.0`): a renderização é byte-idêntica entre execuções
(conferido por SHA-256), o transcritor está pregado em `muscriptor@0.3.0` e os pesos são
conferidos contra `models.lock.toml` antes de medir — medir outro checkpoint torna os
pisos sem sentido. Uma folga uniforme também seria enganosa: 0,03 absorveria uma nota
perdida em `groove16` (32 notas) e nenhuma em `graves` (10).

**Terceiro erro meu, da mesma família dos dois anteriores.** Reescrevi a fixture `misto` de
memória em vez de copiar o gerador: nota F1 deu 0,882 contra a baseline 0,682 — e a
direção do erro (para melhor) é a que menos desperta suspeita. Só apareceu porque imprimi
os valores medidos ao lado das baselines em vez de aceitar o verde do portão. Registrado
em `tasks/lessons/workflow.md`.

**Aberto:** não há CI neste repositório. O portão existe e reproduz localmente, mas
"travado no CI" ainda não é verdade — falta um job que instale fluidsynth + soundfont e
rode `-m slow`, com os dois `skipif` virando falha nesse job (portão que pula em silêncio
é pior que portão nenhum).
