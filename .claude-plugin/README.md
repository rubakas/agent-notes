# agent-notes

Multi-agent development team with cost-optimized model routing for Claude Code.

## What this plugin installs

**18 specialized agents** with automatic model routing:
- Opus — architect, debugger, devil (complex reasoning tasks)
- Sonnet — coder, reviewer, security-auditor, devops, integrations, refactorer, and more
- Haiku — explorer, analyst, api-reviewer, tech-writer (fast read-only work)

**6 process discipline skills** (available as `/skill` immediately after install):
- `plan-first` — decompose and plan before coding
- `tdd` — RED-GREEN-REFACTOR methodology with strict anti-patterns
- `debugging-protocol` — 4-phase systematic debugging: instrument → evidence → hypothesis → fix
- `brainstorming` — explore multiple approaches before committing
- `code-review` — 5-lens review: correctness, safety, performance, clarity, consistency
- `refactoring-protocol` — safe incremental refactoring with green-test gates

**Session context** — a brief team roster injected at every session start
via the SessionStart hook.

## Model routing

All agents use class-level model aliases (`opus`, `sonnet`, `haiku`) rather than
pinned model IDs. When Anthropic releases new models, Claude Code automatically
resolves these aliases to the current best model in each class — no plugin update needed.

## Full install (recommended)

The plugin delivers agents, skills, and session context. For domain skills
(Rails, Docker, Git), slash commands (/plan /review /debug /brainstorm), and
the interactive setup wizard:

```bash
pip install agent-notes
agent-notes install
```

## What's in the full install

| Feature | Plugin | Full install |
|---|---|---|
| 18 specialized agents | ✓ | ✓ |
| Process skills (6) | ✓ | ✓ |
| Session context hook | ✓ | ✓ |
| Domain skills (Rails, Docker, Git) | — | ✓ |
| Slash commands (/plan /review /debug) | — | ✓ |
| User config overrides | — | ✓ |
| Doctor / health checks | — | ✓ |
