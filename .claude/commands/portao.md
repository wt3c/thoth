---
description: Roda o portão de entrega do Thoth — testes, lint e tipos
allowed-tools: Bash(uv run pytest:*), Bash(uv run ruff:*), Bash(uv run mypy:*)
---

Rode os três comandos do portão, nesta ordem, e **não pare no primeiro que falhar** —
o relatório precisa dizer o estado dos três:

```bash
uv run pytest -n auto
uv run ruff check src/ tests/
uv run mypy src/
```

Depois relate, em uma linha por comando, o resultado com o número medido (quantos
testes passaram, quantos diagnósticos do ruff, quantos erros do mypy). Nada de "tudo
certo" sem o número ao lado.

Lembre do que a suíte padrão **não** roda: `addopts` exclui `slow`, `network` e
`navegador`. Se a tarefa tocou o MuScriptor, o Demucs, o yt-dlp ou a página
de estudo, o portão acima não a cobre — diga isso explicitamente e rode também a
seleção correspondente: `uv run pytest -m "slow and not network"` (modelos locais),
`-m network` (canário do yt-dlp) ou `-m navegador`. Atenção: `-m slow` sozinho inclui
o teste de rede.

Se algum dos três falhar: pare, não proponha correção sem causa raiz confirmada
(`superpowers:systematic-debugging`).

$ARGUMENTS
