# agent-notes

Multi-agent development team with cost-optimized model routing for Claude Code.

## What this plugin installs

**18 specialized agents** with automatic model routing:
- Opus — architect, debugger, devil (complex reasoning tasks)
- Sonnet — coder, reviewer, security-auditor, devops, integrations, refactorer, and more
- Haiku — explorer, analyst, api-reviewer, tech-writer (fast read-only work)

**11 process discipline skills** (available as `/skill` immediately after install):

Recent additions inspired by [mattpocock/skills](https://github.com/mattpocock/skills):
- `grill-me` — interview the user relentlessly until the plan is fully resolved
- `grill-with-docs` — same, but cross-references CONTEXT.md and ADRs; updates docs inline
- `caveman` — ultra-compressed reply mode (~75% token savings) for rapid iteration
- `setup-project-context` — bootstraps a CONTEXT.md domain glossary (ubiquitous language)
- `improve-codebase-architecture` — deletion test to find shallow modules; surfaces deepening opportunities
- `zoom-out` — quick orientation map of an unfamiliar code area

Core skills:
- `tdd` — RED-GREEN-REFACTOR with tracer-bullet vertical slices; horizontal-slicing anti-pattern added
- `debugging-protocol` — build a feedback loop first; 9 strategies across 4 phases
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
(Rails, Docker, Git), slash commands (/review /debug /brainstorm), and
the interactive setup wizard:

```bash
pip install agent-notes
agent-notes install
```

## What's in the full install

| Feature | Plugin | Full install |
|---|---|---|
| 18 specialized agents | ✓ | ✓ |
| Process skills (11) | ✓ | ✓ |
| Session context hook | ✓ | ✓ |
| Domain skills (Rails, Docker, Git) | — | ✓ |
| Slash commands (/review /debug /brainstorm) | — | ✓ |
| User config overrides | — | ✓ |
| Doctor / health checks | — | ✓ |
