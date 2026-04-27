# agent-notes

Multi-agent development team with cost-optimized model routing for Claude Code.

## What this plugin installs

**Process discipline skills** (available immediately after plugin install):
- `plan-first` — decompose and plan before coding
- `test-driven` — RED-GREEN-REFACTOR TDD methodology
- `debugging-protocol` — 4-phase systematic debugging
- `brainstorming` — explore approaches before committing
- `code-review` — correctness, safety, clarity, consistency checklist

**Session context** — a brief team roster injected at every session start
via the SessionStart hook.

## Full install (recommended)

The plugin delivers process skills only. For the full agent team (18 specialized
agents with Opus/Sonnet/Haiku cost routing, domain skills for Rails/Docker/Git,
slash commands, and the interactive setup wizard):

```bash
pip install agent-notes
agent-notes install
```

## What's in the full install

| Feature | Plugin | Full install |
|---|---|---|
| Process skills | ✓ | ✓ |
| Session context hook | ✓ | ✓ |
| Domain skills (Rails, Docker, Git) | — | ✓ |
| 18 specialized agent personas | — | ✓ |
| Model cost routing (Opus/Sonnet/Haiku) | — | ✓ |
| Slash commands (/plan /review /debug) | — | ✓ |

## Schema verification note

The `plugin.json` format is based on the Claude Code plugin specification as of
April 2026. Verify against the official Claude Code plugin schema before
submitting to the marketplace, particularly:
- The `hooks.SessionStart` structure
- Whether `matcher: ""` is the correct wildcard for all sessions
- Whether skills are loaded from `.claude-plugin/skills/` automatically or
  require explicit registration in `plugin.json`
