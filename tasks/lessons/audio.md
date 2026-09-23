# Lições — áudio (ffmpeg, medição de energia)

## `aformat=channel_layouts=stereo` numa entrada mono tira 3 dB do sinal

O upmix mono→estéreo do ffmpeg preserva **energia**, não amplitude: divide cada canal
por √2. Numa cadeia `aformat=channel_layouts=stereo,pan=mono|c0=.5*c0+.5*c1` o `pan`
parece o suspeito e é inocente — medido no mesmo arquivo de 440 Hz:

| cadeia                                   | RMS      | razão  |
|------------------------------------------|----------|--------|
| entrada mono, sem filtro                 | 0,088369 | 1,0000 |
| `aformat=stereo` + `pan` .5c0+.5c1       | 0,062485 | 1,4142 |
| só `aformat=stereo` (média dos 2 canais) | 0,062485 | 1,4142 |
| `pan=mono\|c0=c0` direto                  | 0,088369 | 1,0000 |

O `aformat` tinha entrado justamente para *proteger* a entrada mono de perder
amplitude no `.5*c0+.5*c1`. Ele introduziu a perda que dizia evitar. Quando o downmix
precisa casar com uma medição feita em Python, escreva os pesos à mão a partir do
número real de canais (`sf.info(...).channels`) — conversão implícita de layout tem
ganho embutido que não aparece na linha de comando.

## Ganho calculado numa janela que o `-shortest` não escreve sai errado na mesma razão

Igualar a energia de dois canais medindo os arquivos **inteiros** só funciona se os
dois inteiros forem para o arquivo. Com `-shortest`, o que sai é a janela do mais
curto: a cauda de release do soundfont (4,10 s contra 2,00 s do original) entrava na
média, derrubava o RMS da transcrição e o ganho saía 1,43× alto — exatamente o fator
que sobrava no canal.

**Regra:** meça a energia na mesma janela que vai ser escrita, e divida pelo tamanho
da janela, não pelo número de amostras lidas — o silêncio que o `apad` completa é
parte do canal e tem que puxar a média para baixo junto.

**Como os dois se somaram:** 1,432 × 1,4142 = 2,025, que era o desequilíbrio medido.
Dois defeitos independentes cujo produto parece um único fator plausível. Decompor o
número observado em fatores conhecidos (√2? 2? 1,5?) antes de mexer no código foi o
que separou os dois — cada um sozinho teria "quase" explicado o sintoma.
