# CLAUDE.md — Thoth

O contrato do projeto é comum a todos os agentes e vive em `AGENTS.md`:

@AGENTS.md

O que segue vale só para o Claude Code.

## Leitura prévia

1. `tasks/todo.md` — fase ativa e o que falta
2. `tasks/decisions.md` — ADR da área que vai tocar
3. `tasks/lessons/<domínio>.md` — só o domínio da tarefa (`audio`, `exportadores`,
   `navegador`, `workflow`); `workflow.md` sempre

## Skills

- `superpowers:test-driven-development` — antes de qualquer implementação
- `superpowers:systematic-debugging` — qualquer bug ou teste falhando; o Iron Law vale
- `verification-before-completion` — antes de dizer que passou; aqui isso significa
  rodar o marcador certo, porque a suíte padrão pula `slow`, `network` e `navegador`
- `python-django` — só os padrões de Python/uv/ruff/mypy; **não há Django neste projeto**
- `diagramas` + `archify` — qualquer diagrama, sempre

Sem `infisical-secrets`, `keycloak`, `openshift`, `gitlab-ci`: não se aplicam.

## Herança do global

`~/.claude/CLAUDE.md` continua valendo. Este arquivo **substitui** o global apenas em:

- **Secrets/Infisical** — não há secrets aqui; a Regra 4 fica sem objeto.
- **Testes Django** — não há Django nem banco; as regras anti-mutação não se aplicam.
- **`install.py`** — gerencia o `~/.claude` global. O `.claude/` deste repositório é
  versionado aqui e não entra no instalador.

## Configuração local

`.claude/settings.json` é versionado e público: sem caminho absoluto, sem nome de
máquina. Ajuste de estação vai em `.claude/settings.local.json`, que está ignorado.
