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

## Teste que afirma o invólucro não diz nada sobre o conteúdo

As sete partituras do acervo saíram com o título errado por meses. No GP5 liam
`Thoth`, o default do exportador; no MusicXML, `Music21 Fragment` — o placeholder da
própria biblioteca, porque `score.metadata = None` descartava a metadata e o music21
imprimia o dele. Quem abrisse no MuseScore via o nome da biblioteca, não o da música.

O `asset.title` existia e estava correto: alimentava `nome_de_arquivo`. Faltava um
argumento em `pipeline.py`, onde os dois exportadores eram construídos com `bpm` e
`armadura` e ficavam no `titulo` default.

**O que deixou passar:** havia teste, e ele se chamava
`test_gera_os_dois_artefatos_nomeados_pelo_titulo`. Ele afirmava
`caminho.stem == resultado.asset.title` — o **nome do arquivo**. E o nome do arquivo
sempre esteve certo, porque vinha do caminho que funcionava. O teste verificava o
invólucro e nunca abriu o que estava dentro.

Mesma família do antipadrão do `Beat.status` acima: asserção que passa por acidente
porque mede o lado certo do defeito. Exportador entrega **arquivo**; o teste dele
abre o arquivo e lê o campo, sempre.

**Armadilha de leitor ao testar isto:** o music21 10.5 grava o título em
`<work-title>` e `<movement-title>`, mas na releitura não o devolve em
`metadata.title` (fica `None`) — aparece em `movementName`/`bestTitle`. Um teste
escrito contra `metadata.title` falha com o arquivo correto. Afirmar o XML cru é o
que mais se aproxima do que MuseScore e TuxGuitar leem.
