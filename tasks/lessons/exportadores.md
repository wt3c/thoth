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

## Leitor que mostra tablatura não prova nada sobre outro leitor (2026-09-23)

Afirmei que o MuseScore importava o nosso `.gp5` com pauta de tablatura. O usuário
corrigiu: *"O TuxGuitar e o Guitar Pro quando eu abro já exibi a tablatura"* — dizendo,
nas entrelinhas, que o MuseScore não. Ele estava certo.

O nosso GP5 declara `TrackSettings.tablature=True` desde sempre, e o TuxGuitar e o
Guitar Pro honram. O **MuseScore 4.7 ignora essa flag** no importador de Guitar Pro e
monta a pauta pelo template `electric-bass` dele: `StaffType group="pitched"`, nome
`stdNormal`, clave de Fá 8vb. Nenhum `StaffType group="tablature"` no arquivo
importado. Não é bug do nosso GP5 — é o importador.

**A lição:** a flag no arquivo é o que escrevemos, não o que o leitor faz. Dois
leitores concordarem não é evidência sobre um terceiro. Para afirmar comportamento de
leitor, rodar o leitor:

```bash
QT_QPA_PLATFORM=offscreen mscore entrada.gp5 -o saida.mscx
grep -c 'StaffType group="tablature"' saida.mscx
```

O `mscore` precisa do ambiente inteiro (`os.environ | {...}`) — com `env` podado a
`PATH` ele morre com SIGABRT, porque quer `HOME` e `XDG_*`.

## Sondagem com digitação inválida mede o leitor errado (2026-09-23)

Testando se o MuseScore preserva a nossa digitação, forcei corda/traste
`(4,15) (3,10) (2,5) (4,12)` nas alturas 36/38/40/41 — combinações que **contradizem**
essas alturas. O MuseScore descartou e recalculou, e eu quase registrei isso como "o
MuseScore recalcula os trastes pela regra dele", que é falso.

Com digitação **válida alternativa** — `{36:(4,8), 38:(4,10), 40:(4,12), 41:(4,13)}`,
tudo na corda grave, escolha que nenhum algoritmo de custo faria — voltou
`[('8','3'), ('10','3'), ('12','3'), ('13','3')]`: preservado.

**A lição:** sondagem que viola a semântica do formato mede a tolerância do leitor a
entrada inválida, não a política dele sobre entrada válida. O contraexemplo precisa
ser legal e improvável, não ilegal.

## PyGuitarPro: `gp.Note` também nasce errado — `NoteType.rest` (2026-09-25)

Mesma família do `Beat.status`: `gp.Note(...)` sem `type` é `NoteType.rest`. O
arquivo grava, e o PyGuitarPro relê a nota como pausa. O exportador de cordas sempre
passou o `type` e nunca viu isso; o de percussão nasceu sem ele. O **MuseScore
importou as peças mesmo assim** — o leitor independente não pegou; quem pegou foi o
round-trip afirmando `note.type`. Todo `gp.Note` leva `type` explícito, e o teste
afirma o tipo relido, não só o `value`.
