# Corpus de avaliação

Referências fornecidas pelo Welington em 2026-09-21. **Só IDs ficam versionados** —
áudio baixado nunca entra no repositório (ADR-005).

Uso: `uv run thoth fetch https://www.youtube.com/watch?v=<id>`

## Grupo A — baixo em primeiro plano (modo fácil)

Bass covers sobre playback: o baixo está mixado muito acima do natural. Servem para
detectar erro grosseiro (oitava trocada, notas fantasma), **não** para decidir
seguir/abortar — o F1 aqui é otimista em relação a qualquer mix real.

| id | faixa | dur | o que testa |
|---|---|---|---|
| `4kd_eR4216g` | Giane Rangel — *Sou Eu* (Fabiana Anastácio) | 5m16 | linha simples de gospel; o mais fácil do corpus, bom primeiro alvo |
| `74oJcmcsy1o` | juliaplaysgroove — Lola Young, *Conceited* | 3m59 | pop moderno, baixo destacado |
| `dlvxhf2GCA4` | juliaplaysgroove — Korn, *Freak On a Leash* | 4m16 | **slap percussivo e afinação grave** — ataque de clique confunde detector de onset; valida `TUNING_BASS_5` e afinação custom |
| `QTOyeFQgZKk` | SOJA — *Everything Changes* | 5m08 | reggae, baixo repetitivo. Camada 2 apenas — a tab do Songsterr é `aiGenerated` (ADR-007) |

## Grupo B — mix real completo (critério que vale)

Aqui o baixo está no lugar dele dentro da banda. **É este grupo que decide a
condicional C1** (separação com Demucs vale a pena ou não).

| id | faixa | dur | o que testa |
|---|---|---|---|
| `U-SHfpm5Bxk` | Sade — *Is It A Crime* (ao vivo, San Diego) | 7m59 | ao vivo: plateia, reverberação de sala, baixo legato e suave |
| `8m6wrCCRvm8` | Seu Jorge — *Tive Razão* | 9m16 | samba/MPB com percussão densa — transientes de percussão competindo com onsets do baixo |

## Grupo C — casos-limite

| id | faixa | dur | o que testa |
|---|---|---|---|
| `4dJz6U3_Xlk` | Ne Obliviscaris — *Equus* (playthrough, Martino Garattoni) | 12m36 | prog metal com baixo de extensão estendida (Strandberg): rápido, grave abaixo do B0, provável glissando. previsão registrada aqui era **falha esperada** (estouro do vocabulário de afinação). **Medido em 2026-09-22: a previsão estava errada** — saiu `B0..D3`, zero notas simultâneas, 5,5 notas/s, cabendo inteiro em `TUNING_BASS_5`. **Confirmado pelo Welington (2026-09-22): é de 5 cordas** — transcrever sempre com `--afinacao 5`. Ver `fase0-resultados.md` |
| `5zqlgMh4aYs` | Toshiki Soejima — *Feel Like Makin' Love* | 7m47 | **não é baixo, é guitarra neo-soul.** Acordes sobrepostos batem exatamente na fraqueza documentada do MuScriptor (notas simultâneas do mesmo instrumento: onset F1 60,4 → 51,8). Testa o objetivo secundário multi-instrumento e o efeito de `--instruments` |

## Regras de leitura dos resultados

- Nunca reportar um número único de F1 do corpus inteiro — **sempre por grupo**.
  Misturar A e B esconde o que interessa.
- Go/no-go do projeto sai do **Grupo B**. O Grupo A é sanidade; o C é fronteira.
- `4dJz6U3_Xlk` e `5zqlgMh4aYs` podem falhar sem invalidar o projeto. Se falharem,
  vira escopo declarado, não bug.
