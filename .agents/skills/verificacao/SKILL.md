---
name: verificacao
description: Roda a verificação de entrega do Thoth — testes, lint e tipos. Usar antes de afirmar que uma tarefa deste repositório está pronta.
---

# Verificação

Cópia do `/verificacao` do Claude Code (`.claude/commands/verificacao.md`); as duas
mudam juntas.

Rode os comandos da verificação, nesta ordem, e **não pare no primeiro que falhar** —
o relatório precisa dizer o estado de todos:

```bash
uv run pytest -n auto
uv run ruff check src/ tests/
uv run mypy src/
npm --prefix braco ci && npm --prefix braco run verificar
```

O quarto comando é o do mapa do braço (`braco/`): tipos, lint, Vitest e build. Se a tarefa não
tocou `braco/`, ele pode ser pulado — diga que pulou.

Depois relate, em uma linha por comando, o resultado com o número medido (quantos
testes passaram, quantos diagnósticos do ruff, quantos erros do mypy). Nada de "tudo
certo" sem o número ao lado.

Lembre do que a suíte padrão **não** roda: `addopts` exclui `slow`, `network` e
`navegador`. Se a tarefa tocou o MuScriptor, o Demucs, o yt-dlp ou a página
de estudo ou o braço, a verificação acima não a cobre — diga isso explicitamente e rode também a
seleção correspondente: `uv run pytest -m "slow and not network"` (modelos locais),
`-m network` (canário do yt-dlp) ou `-m navegador`. Atenção: `-m slow` sozinho inclui
o teste de rede.
Na seleção pesada, no máximo `-n 2`: com `-n auto` os modelos disputam a memória e
o teste do caminho real até o arquivo baixado falha.

Se algum deles falhar: pare e não proponha correção sem causa raiz confirmada.
