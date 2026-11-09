# CLAUDE.md — Thoth

O contrato do projeto é comum a todos os agentes e vive em `AGENTS.md`:

@AGENTS.md

O que segue vale só para o Claude Code.

## Skills

- `superpowers:test-driven-development` — antes de qualquer implementação
- `superpowers:systematic-debugging` — qualquer bug ou teste falhando; o Iron Law vale
- `verification-before-completion` — antes de dizer que passou; aqui isso significa
  rodar o marcador certo, porque a suíte padrão pula `slow`, `network` e `navegador`
- `python-django` — só os padrões de Python/uv/ruff/mypy; **não há Django neste projeto**
- `diagramas` + `archify` — qualquer diagrama, sempre

Sem `infisical-secrets`, `keycloak`, `openshift`, `gitlab-ci`: não se aplicam.

## Herança do global

`~/.claude/CLAUDE.md` continua valendo, incluindo planejamento, delegação e revisão
de planos complexos. A leitura prévia comum aos dois harnesses está em `AGENTS.md`.
As exceções locais são:

- **Secrets/Infisical** — não há secrets aqui; a Regra 4 fica sem objeto.
- **Testes Django** — não há Django nem banco; as regras anti-mutação não se aplicam.
- **`install.py`** — mudanças nas configurações globais pertencem ao repositório
  `claude-md` e são aplicadas pelo instalador. Como exceção de escopo do projeto,
  o `.claude/settings.json`, os comandos e as instruções do Thoth são mantidos
  neste repositório e não entram no instalador global.

## Configuração local

`.claude/settings.json` é versionado e público: sem caminho absoluto, sem nome de
máquina. Ajuste de estação vai em `.claude/settings.local.json`, que está ignorado.

Modelo, `advisorModel`, `effortLevel`, `env.CLAUDE_CODE_SUBAGENT_MODEL`, hooks e MCPs
são herdados das configurações globais, sem cópia local. As permissões locais
complementam as globais com comandos específicos do Thoth e a restrição de leitura
de `audio/`. Comandos Python arbitrários não recebem autorização genérica local.
