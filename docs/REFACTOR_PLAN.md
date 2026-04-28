# agent-notes — Refactor Plan

**Status:** ✅ COMPLETE (Phases 0–3 shipped in PRs #1–#6). Superseded by `docs/ENGINE_PLAN.md` for further work. · **Target version:** 0.5.0 · **Date:** 2026-04-22

Vision: **agent-notes is a hub for installing AI best-practices across any AI model and any AI CLI tool.** Each CLI is a plugin-like module, not a hardcoded branch in the code.

---

## Problem statement

The current codebase has accumulated three structural problems:

1. **No installation state.** The tool is stateless — it reconstructs "what is installed" from filesystem probes in `doctor.py`. There is no manifest, no record of prior selections, no source-of-truth for uninstall/update operations.
2. **CLI-specific logic is hardcoded everywhere.** ~80+ hardcoded strings for CLI names, paths, filenames, subdirectory layouts, skill groups, rule targets. `if/elif` on `"claude"` / `"opencode"` in 6 files. Copilot is a second-class citizen (not even offered in the wizard).
3. **Claude-specific concepts leak into "generic" code.** `MEMORY_DIR = CLAUDE_HOME / "agent-memory"` in `config.py`. Rules install only to Claude. `color`/`effort` fields in `agents.yaml` are Claude-only. Frontmatter generation is dispatched via `if cli == "claude"` branches.

As a result:
- `agent-notes update` cannot report what changed — it blindly reinstalls everything.
- Uninstall relies on guesswork, not a manifest.
- Adding a new CLI (Cursor, Aider, Gemini CLI) requires editing multiple files.
- The wizard hardcodes CLI names, skill groups, and skill descriptions in Python strings.
- The source tree has `agent_notes/data/` buried inside the Python package — code and content are conflated.

---

## Target architecture

### 1. CLI backends as plugins

One YAML file per supported CLI, dropped into `content/cli/`. The tool auto-discovers them. Adding a new CLI is a 1-file PR.

```yaml
# content/cli/claude.yaml
name: claude
label: Claude Code
global_home: ~/.claude
local_dir: .claude
layout:
  agents:  agents/
  skills:  skills/
  rules:   rules/
  commands: commands/
  config:  CLAUDE.md
  memory:  agent-memory/
  settings: settings.json
features:
  agents: true
  skills: true
  rules: true
  commands: true
  memory: true
  frontmatter: claude        # which frontmatter generator to use
  config_style: imports      # @-imports vs inline
  settings_template: true
  supports_symlink: true
global_template: globals/claude.md
settings_template: cli/claude/settings.json.template
model_map:
  opus-4.7: claude-opus-4-7
  sonnet:   sonnet
  haiku:    haiku
exclude_flag: claude_exclude
```

A new `cli_backend.py` module loads all YAMLs into a registry. Every existing `if/elif` branch in `build.py`, `install.py`, `doctor.py`, `wizard.py` collapses to `for backend in registry.enabled():` or `registry.get(name)`.

### 2. Local state file

Single source of truth for what is installed:

**Path:** `~/.config/agent-notes/state.json` (respects `$XDG_CONFIG_HOME`)

```json
{
  "schema": 1,
  "version": "0.5.0",
  "installed_at": "2026-04-22T13:05:00Z",
  "updated_at": "2026-04-22T13:05:00Z",
  "source_commit": "abc1234",
  "source_path": "/Users/me/agent-notes",
  "mode": "symlink",
  "scope": "global",
  "cli_backends": ["claude", "opencode"],
  "selections": {
    "skill_groups": ["rails", "docker", "git"],
    "agents": ["lead", "coder", "reviewer"],
    "rules": ["code-quality", "safety"],
    "commands": ["plan", "review", "commit", "doctor"]
  },
  "installed": {
    "claude": {
      "agents":   { "lead.md":   { "sha": "abc…", "target": "~/.claude/agents/lead.md" } },
      "skills":   { "rails-models": { "sha": "abc…", "target": "~/.claude/skills/rails-models" } },
      "rules":    { "safety.md":    { "sha": "abc…", "target": "~/.claude/rules/safety.md" } },
      "commands": { "plan.md":      { "sha": "abc…", "target": "~/.claude/commands/plan.md" } },
      "config":   { "CLAUDE.md":    { "sha": "abc…", "target": "~/.claude/CLAUDE.md" } },
      "settings": { "settings.json": { "sha": "abc…", "target": "~/.claude/settings.json", "merged": true } }
    }
  }
}
```

Used by:
- `install` — writes it; respects prior selections on re-run
- `update` — reads it for diff; produces change report
- `uninstall` — removes exactly what is listed
- `doctor` — validates state vs. filesystem; flags drift
- `info` / `list` — reads from state (fast, honest)

Module: `state.py` — owns load/save/migrate. Schema versioning from day one.

### 3. Smart update with diff

```
agent-notes update
  1. git pull --ff-only
  2. Load state.json (prior install)
  3. Rebuild dist/
  4. Compute SHA diff: new source vs. state.installed
  5. Print report:
       + 2 new agents:  analyst, devil
       ~ 1 agent updated: coder (prompt changed)
       + 3 new skills:  rails-solid-queue, …
       ~ 1 rule updated: safety.md
       - 1 skill removed: rails-legacy
  6. Prompt: Apply all? [Y/n/select]
  7. Reinstall only changed items
  8. Update state.json
```

Flags: `--dry-run`, `--yes`, `--only agents|skills|rules|commands`, `--since <commit>`.

### 4. Dynamic wizard (fully data-driven)

No hardcoded lists in `wizard.py`. Every list is auto-discovered from content + registry:

- **CLIs** — from `content/cli/*.yaml`
- **Skill groups** — from `SKILL.md` frontmatter `group:` field
- **Agents** — from `agents.yaml` (with `presets:` section for quick selections)
- **Rules** — from `content/rules/*.md`
- **Commands** — from `content/commands/*.md`
- **Install mode** — only shows "Symlink" option if any selected CLI declares `supports_symlink: true`
- **Prior selections** — pre-checked from `state.json` on re-runs
- **Dry-run preview** — `show-diff` option prints exactly what files will change

### 5. Flatten source tree

```
agent-notes/
├── src/agent_notes/            # Python package (pure code)
│   ├── cli.py, install.py, build.py, state.py, cli_backend.py, …
├── content/                    # single source of truth (was agent_notes/data/)
│   ├── cli/                    # per-CLI descriptors
│   ├── agents/
│   ├── skills/
│   ├── rules/
│   ├── commands/               # NEW: slash commands
│   ├── scripts/
│   └── globals/                # global templates (was global-*.md)
├── build/                      # generated dist (was agent_notes/dist/, gitignored)
├── tests/
└── pyproject.toml
```

### 6. Decouple Claude-specific concepts

- **Memory**: driven by `features.memory` + `layout.memory` per CLI. `memory.py` becomes multi-CLI.
- **Rules**: driven by `features.rules`. Today only Claude gets them — arbitrarily.
- **Frontmatter generators**: dispatch table `{"claude": gen_claude, "opencode": gen_opencode}`.
- **Agent exclusions**: replace `claude_exclude`/`opencode_exclude` with a single `exclude_from: [copilot]` list.
- **`color` / `effort` fields**: move to a Claude-specific section of `agents.yaml` or to the CLI descriptor.

---

## Execution phases

Each phase is independently shippable and each ends with a green test suite.

### Phase 0 — Content improvements (no code changes, ship first)

1. **Tighten `tools:` per agent in `agents.yaml`** — enforce least-privilege.
   Read-only agents (reviewer, security-auditor, explorer, performance-profiler, api-reviewer, system-auditor, database-specialist) → `[Read, Glob, Grep, WebFetch]` only.
   Writer agents (coder, test-writer, test-runner, devops, tech-writer) → add `Edit, Write, Bash`.
   Lead → restricted per new HARD LIMITS.
2. **Add trigger keywords** to every agent `description:` field (EN only by default).
3. **Rewrite `lead.md` with HARD LIMITS** — forbid reading project code, restrict orchestrator to dispatch/synthesis. Add concrete Feature / Bugfix / Audit / Infra pipeline diagrams.
4. **Add 6 new generic agents:** `analyst`, `architect`, `devil`, `debugger`, `integrations`, `refactorer`.

### Phase 1 — Foundation (state + CLI registry)

5. `state.py` module. `~/.config/agent-notes/state.json` schema v1. Full test coverage.
6. `content/cli/claude.yaml`, `opencode.yaml`, `copilot.yaml` descriptors (parallel to existing code, no behavior change yet).
7. `cli_backend.py` registry loader. Tests.

### Phase 2 — Refactor install/doctor/wizard around registry

8. Rewrite `install.py` around `for backend in registry.enabled():`. Write `state.json` on every install/uninstall.
9. Rewrite `doctor.py` around registry (replaces 30+ hardcoded checks). Validate against `state.json`.
10. Rewrite `wizard.py` — auto-discover CLIs, agents, rules, commands, skill groups. Pre-fill from prior `state.json`.
11. Delete hardcoded path constants from `config.py`.

### Phase 3 — Smart update

12. SHA tracking in `state.json` per source file.
13. `update.py` diff engine (added/removed/modified per component type).
14. CLI flags: `--dry-run`, `--yes`, `--only`, `--since`.
15. Rich change report printed to user.

### Phase 4 — New component: commands

16. `content/commands/` directory. Generic commands: `/plan`, `/review`, `/commit`, `/doctor`, `/audit`.
17. Wire into CLI descriptors (`features.commands: true` for Claude).
18. Wizard gains commands section.

### Phase 5 — settings.json templates + @-imports

19. `content/cli/claude/settings.json.template` with generic `permissions.deny` for secrets. No Laravel-specific hooks.
20. Install step: if template exists and no user settings, write template. If exists, merge non-destructively.
21. For Claude Code, generate `CLAUDE.md` with `@`-imports to shipped rules instead of inlining.
22. CLI descriptor field: `config_style: imports | inline`.

### Phase 6 — Decouple Claude-isms

23. Memory multi-CLI via registry.
24. Rules multi-CLI via `features.rules`.
25. Frontmatter dispatch table.
26. Replace `claude_exclude`/`opencode_exclude` with `exclude_from: [...]` list.

### Phase 7 — Dynamic skill groups

27. `SKILL.md` frontmatter with `group:` field.
28. Wizard auto-discovery by group.
29. Remove hardcoded group lists from `wizard.py`.
30. Add `presets:` section to `agents.yaml`.

### Phase 8 — Source tree flatten

31. Move `agent_notes/data/` → `content/`, `agent_notes/dist/` → `build/`.
32. Move package to `src/agent_notes/`.
33. Update `pyproject.toml` package-data + entry points.
34. Migration helper: `agent-notes migrate-repo`.

### Phase 9 — Polish

35. Update README with new architecture + "how to add a CLI backend".
36. CHANGELOG, deprecation notes.
37. `agent-notes doctor --migrate` to upgrade old installs to state.json.

---

## Ship order

PRs #1–3 are pure content, ship immediately. PRs #4–6 deliver ~70% of the architectural value. PRs #7+ follow.

| PR | Phase | Scope | Risk |
|----|-------|-------|------|
| #1 | 0 | `agents.yaml` — tools tightening + trigger keywords | low (content only) |
| #2 | 0 | `lead.md` HARD LIMITS + pipelines | low (content only) |
| #3 | 0 | 6 new agents | low (content only) |
| #4 | 1 | `state.py` + `content/cli/*.yaml` + `cli_backend.py` | medium (new code, no behavior change) |
| #5 | 2 | Registry-driven install/doctor/wizard + state.json | medium (rewrites ~3 modules) |
| #6 | 3 | Smart update with diff | medium |
| #7 | 4 | Commands component | low |
| #8 | 5 | settings.json templates + @-imports | low |
| #9 | 6 | Decouple Claude-isms | medium |
| #10 | 7 | Dynamic skill groups | low |
| #11 | 8 | Source tree flatten | high (disruptive) |
| #12 | 9 | Polish, docs, migration | low |

---

## Design principles

1. **Every CLI is a plugin.** No `if cli == "claude"` branches in application code. All CLI-specific behavior lives in descriptor YAML + dispatch tables.
2. **State is explicit.** Nothing is reconstructed from filesystem probes. `state.json` is the authority.
3. **Content and code are separated.** `content/` has no Python. `src/agent_notes/` has no markdown.
4. **The wizard is a thin shell.** It discovers everything from content/registry. No hardcoded lists.
5. **Updates report before they act.** No blind reinstalls. User sees the diff, approves, applies.
6. **Backward compatibility by migration.** Old installs get auto-upgraded to `state.json` on first run of the new version.
7. **Generic by default, specific by opt-in.** Laravel, Rails, Vue, Python — those are skills, not core. The core is CLI-agnostic and framework-agnostic.

---

## Influences

Patterns borrowed and generalized from [AratKruglik/claude-laravel](https://github.com/AratKruglik/claude-laravel):

- Explicit per-agent `tools:` (least-privilege) — Phase 0
- Orchestrator HARD LIMITS — Phase 0
- Pipeline diagrams per task type — Phase 0
- Agent team composition (ba, devil, debugger, architect, integrations) — Phase 0, generalized
- Trigger keywords in agent descriptions — Phase 0
- `settings.json` with `permissions.deny` for secrets — Phase 5
- `@`-imports in CLAUDE.md — Phase 5
- Slash commands in `.claude/commands/` — Phase 4
- Max 2 retry cycles for quality gate — already present in our lead prompt

Explicitly **not** borrowed (too Laravel-specific):

- Laravel Actions pattern, Filament, Inertia.js references
- `laravel-boost` MCP server
- `docker compose exec app composer run pint:fix` hooks
- Experimental `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` flag (documented as optional)
- Superpowers plugin dependency
