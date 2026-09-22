# Lições — exportadores (GP5, MusicXML)

## PyGuitarPro: `Beat.status` nasce `empty` e isso corrompe o arquivo em silêncio

`gp.Beat(...)` tem `status=BeatStatus.empty` por padrão. O escritor aceita, o arquivo
grava sem erro e a `Song` em memória parece perfeita — mas `gp3.readBeat` devolve
duração `0` para beat `empty`, o cursor `start` não avança e `getBeat` funde todas as
notas seguintes no mesmo beat. Todo beat com nota precisa de
`beat.status = gp.BeatStatus.normal`; pausa, de `rest`.

**Antipadrão que escondeu o bug por semanas:** assertar sobre as notas *achatadas*
(`for beat in voice.beats for nota in beat.notes`). Isso passa igual com o compasso
fundido num beat só. Teste de round-trip de formato rítmico tem que afirmar a
**estrutura** — quantos beats, qual o `start` de cada ataque, se a soma das durações
fecha o compasso —, não só o conjunto de notas.

**Como isolar defeito em biblioteca binária de terceiro:** reproduzir com a biblioteca
pura, sem nada do projeto. Se 4 beats escritos voltam como 1, o problema não está nos
dados do projeto; aí sim vale ler o escritor e o leitor lado a lado.
