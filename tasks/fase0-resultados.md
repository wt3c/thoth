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
