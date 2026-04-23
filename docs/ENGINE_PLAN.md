# AgentNotes Engine — Phase 2 Plan (Models + Roles + CLIs)

**Status:** In progress · **Target version:** 1.1.0 · **Date:** 2026-04-22

Vision: **agent-notes is a true engine.** Adding a new AI CLI, a new AI model, or a new role is a matter of dropping YAML / template files. Zero Python code changes for the common case.

**Companion docs:**
- `docs/CLI_CAPABILITIES.md` — official-docs catalogue of every Claude Code and OpenCode feature the engine must support. Referenced by Phases 3/4/5/10.
- `docs/REFACTOR_PLAN.md` — superseded predecessor (Phases 0–3 complete).

---

## Current progress

| Phase | Status | Notes |
|---|---|---|
| Phase 1 — Model + Role registries | ✅ DONE | `data/models/` (4 Claude YAMLs w/ anthropic+github-copilot aliases), `data/roles/` (4 roles), `model_registry.py`, `role_registry.py`, `accepted_providers` on CLI YAMLs, `CLIBackend.first_alias_for()`. 35 new tests. |
| Phase 2 — State.json shape | ✅ DONE | Single shape: `global` + `local` keyed by project path, `role_models` + `installed` per CLI. All 429 tests passing. |
| Phase 2.5 — CLI capabilities research | ✅ DONE | `docs/CLI_CAPABILITIES.md` (1,827 lines) — official Claude Code + OpenCode docs catalogued. Source of truth for what each CLI supports (agent frontmatter, skills, commands, plugins, hooks, MCP, settings, providers). Referenced by Phases 3/4/5/10. |
| Phase 3 — Modularity audit & versioning strip | ✅ DONE | Hardcoded CLI branches removed from `install.py`, `build.py`, `wizard.py`, `doctor.py`. Versioning fields stripped from state. |
| Phase 4 — Build engine reads state | ✅ DONE | `generate_agent_files(agents_config, tiers, state=None, scope='global', project_path=None)` — state-driven path activates when an agent has a `role:` field AND state has a matching `role_models` entry for the backend. Otherwise falls back to legacy tiers. `build()` auto-loads state if present. Plumbing is inert until Phase 9 migrates agents.yaml to `role:`. 3 new tests (test_build.py 17→20). |
| Phase 5 — Frontmatter templates per CLI | ✅ DONE | `agent_notes/data/templates/frontmatter/{claude,opencode}.py` with `render(ctx)` + `post_process(prompt, ctx)`. `build._load_frontmatter_template(name)` dynamically imports by `backend.features["frontmatter"]`. OpenCode's memory-strip moved into opencode template's `post_process`. Old top-level `generate_*_frontmatter` / `strip_memory_section` kept as thin wrappers for backward compat with existing tests. Smoke-tested adding a `cursor.py` template (add + invoke + remove) — zero build.py edits required to support a new CLI's frontmatter. |
| Phase 6 — Wizard rewrite | ✅ DONE | New `_select_models_per_role(clis)` step between CLI select and scope select. Per-CLI per-role picker, shows only compatible models (via `backend.first_alias_for(model.aliases)`), defaults to a model whose `model_class == role.typical_class`. Config-only CLIs skipped. `_confirm_install` summary lists role→model map. Wizard now writes state.json via `build_install_state(..., role_models={cli:{role:model_id}})` + `record_install_state()` — previously the wizard never persisted state, that was a pre-existing bug, now closed. 4 new tests (test_wizard.py 51→55). |
| Phase 7 — Duplicate install = verify+exit; `--reconfigure` | ⏳ | |
| Phase 8 — Expanded `list` command | ⏳ | |
| Phase 9 — Dead code removal (tiers, model_map) | ✅ DONE | Removed `model_map` from CLIBackend dataclass and all references. All 441 tests passing. |
| Phase 10 — Post-install reconfiguration | ✅ DONE | `set role`, `regenerate` commands; doctor shows role→model map. State.json hand-edits trigger regeneration. 455 tests (baseline: 441 + 14 new). |
| Phase 11 — Docs | ✅ DONE | `docs/ADD_CLI.md`, `docs/ADD_MODEL.md`, `docs/ADD_ROLE.md`, updated README with architecture section + extending guide. |
| Phase 12 — Directory cleanup (`data/clis/`, `data/globals/`) | ⏳ | Cosmetic, last. |
| Phase 13 — Domain layer consolidation (types + registries + services + commands) | 🟡 13a+13b+13c+13d DONE, 13e pending | Phase 13a complete: 16 dataclasses moved to `domain/` package with backward-compat shims. Phase 13b complete: Created `agent_notes/registries/` package with all YAML-loading registry code consolidated. Added 3 new registries (agent, skill, rule). Phase 13c complete: Created `agent_notes/services/` package with 8 service modules: fs, ui, state_store, install_state_builder, rendering, diff, diagnostics, installer. Major extractions from install.py (568→~400 lines), wizard.py (658→~500 lines), build.py (295→~125 lines), config.py (UI moved out). Phase 13d complete: Created `agent_notes/commands/` package with 15 thin orchestrator modules. All top-level command files reduced to ≤20-line shims. CLI updated to import from commands/. 496 tests passing + 3 new architecture tests. Remaining: 13e (tests+docs). |

**Non-goals for 1.1.0:**
- Plugin installation (Claude Code `/plugins`, OpenCode equivalent). CLI YAMLs gain a `features.supports_plugins: bool` flag in Phase 3 for forward-compat, but no installer code is written.
- Hooks/MCP server generation from YAML (future — CLI_CAPABILITIES.md documents these so we don't paint into a corner).
- Per-agent model override (per-role only for 1.1.0).
- Capability-match filtering (model declares capabilities, CLI requires some). Phase-1-level provider intersection is the only filter.

---

## Phase dependency graph

```
2.5 (research) ─────────────────────┐
                                     ▼
1 ✅ ──▶ 2 ✅ ──▶ 3 ──▶ 4 ──▶ 5 ──▶ 6 ──▶ 7 ──▶ 10
                              └──▶ 8 ──▶ (independent)
                              └──▶ 9 ──▶ (after 5)
                                            └──▶ 11 ──▶ 12 (cosmetic, last)
```

Hard dependencies:
- **Phase 3 must finish before Phase 4** — can't rewrite build engine if it still has hardcoded CLI branches.
- **Phase 4 must finish before Phase 5** — frontmatter templates need a build engine that calls them.
- **Phase 4 must finish before Phase 6** — wizard writes `role_models`, build engine must be able to read them.
- **Phase 5 must finish before Phase 9** — can't delete `generate_claude_frontmatter` from `build.py` until templates replace it.
- **Phases 6, 7 must finish before Phase 10** — reconfiguration commands need the wizard/install flow they extend.

Soft dependencies (nice ordering, not strict):
- **Phase 12** (directory renames) should happen EARLY (right after Phase 3) or LAST (after Phase 11). Doing it mid-refactor means importing from moving targets. **Recommendation: push Phase 12 to after Phase 11 as purely cosmetic polish.** The current `data/cli/` path works fine.
- **Phase 8** (expanded `list`) is independent once Phase 3 is done; can slot in anywhere.

---

## Problem statement

After the phases in `REFACTOR_PLAN.md` (content, state.json, installer engine, wizard registry), plus Phase 1 (model + role registries) and Phase 2 (state shape), `agent-notes` is modular for CLI *data* but still couples runtime logic:

1. **CLI descriptor** (claude.yaml) carries a legacy `model_map` that knows about specific models — will be removed in Phase 9.
2. **Agents** declare `tier: opus-4.7` which assumes Anthropic's model naming — will be replaced by `role: <role-name>` in Phase 6.
3. **Build engine** has hardcoded frontmatter generators per CLI in Python — will be moved to `data/templates/frontmatter/<cli>.py` in Phase 5.
4. **Install/doctor/wizard code** still branches on `"claude"` / `"opencode"` / `"copilot"` string literals in dozens of places — will be eliminated in Phase 3.

To truly be a hub, we need to separate three orthogonal concerns: **CLIs**, **Models**, and **Roles**. And expose the third critical dimension — the user's choice of which model to use for each role per CLI — as declared state, not code.

---

## Target architecture

### Three registries, each a plain YAML directory

```
data/
├── clis/                        # renamed from data/cli/
│   ├── claude.yaml              # where files go, which frontmatter template to use
│   ├── opencode.yaml
│   └── copilot.yaml
├── models/                      # NEW: one file per model
│   ├── claude-opus-4-7.yaml
│   ├── claude-sonnet-4.yaml
│   ├── claude-haiku-4-5.yaml
│   ├── kimi-k2.yaml             # drop to add Kimi support
│   ├── gpt-5.yaml               # drop to add GPT support
│   └── gemini-2-5-pro.yaml      # drop to add Gemini support
├── roles/                       # NEW: abstract roles agents declare
│   ├── orchestrator.yaml
│   ├── reasoner.yaml
│   ├── worker.yaml
│   └── scout.yaml
├── templates/
│   └── frontmatter/             # NEW: pluggable per-CLI frontmatter generators
│       ├── claude.py
│       ├── opencode.py
│       └── copilot.py
├── globals/                     # renamed from data/global-*.md
│   ├── claude.md
│   ├── opencode.md
│   └── copilot.md
├── agents/                      # unchanged
├── skills/
├── rules/
├── scripts/
└── commands/                    # future
```

### CLI descriptor (slimmed)

```yaml
# data/clis/claude.yaml
name: claude
label: Claude Code
global_home: ~/.claude
local_dir: .claude
accepted_providers: [anthropic, bedrock, vertex]   # ORDERED preference
global_template: claude                            # → data/globals/claude.md
layout:
  agents:   agents/
  skills:   skills/
  rules:    rules/
  commands: commands/
  config:   CLAUDE.md
  settings: settings.json
  memory:   agent-memory/
features:
  agents: true
  skills: true
  rules: true
  commands: true
  memory: true
  frontmatter: claude                              # → data/templates/frontmatter/claude.py; null for config-only CLIs
  supports_symlink: true
  supports_plugins: false                          # reserved for future; no installer yet
```

**Important:** `features.frontmatter` is the existing field name used in today's YAMLs — NOT `frontmatter_template` (which was used in an earlier draft of this plan). Keep `features.frontmatter` to avoid a rename churn. When null (e.g. Copilot), no frontmatter generator runs for this CLI.

Removed: `model_map`, `exclude_flag`, `strip_memory_section`. Those are moved into frontmatter templates or handled via state.

**Special case — config-only CLIs** (e.g. Copilot): these declare `features.agents: false`, `features.skills: false`, `features.frontmatter: null`. They ship a single config file (e.g. `copilot-instructions.md`) and nothing else. Such CLIs:
- Do NOT appear in wizard step 2 (no role→model picker; no agents to configure)
- Do NOT get a `role_models` entry in state.json
- DO still get an `installed` entry in state (the config file manifest)
- DO appear in wizard step 1 (user selects them to install the config file)

### Model descriptor

```yaml
# data/models/claude-opus-4-7.yaml
id: claude-opus-4-7
label: Claude Opus 4.7
family: claude
class: opus                     # wizard default hint
aliases:                         # per-provider ID strings
  anthropic:      claude-opus-4-7
  bedrock:        anthropic.claude-opus-4-7-20260101-v1:0
  vertex:         claude-opus-4-7@20260101
  github-copilot: github-copilot/claude-opus-4.7
  openrouter:     anthropic/claude-opus-4.7
pricing:                         # optional, for cost reports
  input:  5.00
  output: 25.00
  cache:  0.50
capabilities:                    # optional, for future agent constraints
  vision: true
  long_context: true
```

```yaml
# data/models/kimi-k2.yaml
id: kimi-k2
label: Moonshot Kimi K2
family: kimi
class: opus
aliases:
  openrouter:     moonshotai/kimi-k2
  moonshot:       moonshot/kimi-k2
```

### Role descriptor

```yaml
# data/roles/orchestrator.yaml
name: orchestrator
label: Orchestrator
description: Plans and delegates complex multi-step tasks. Low volume, high reasoning.
typical_class: opus
color: purple
```

```yaml
# data/roles/worker.yaml
name: worker
label: Worker
description: Implements code, writes tests, does focused analysis.
typical_class: sonnet
color: blue
```

```yaml
# data/roles/scout.yaml
name: scout
label: Scout
description: Fast file discovery, pattern search. High volume, low reasoning.
typical_class: haiku
color: cyan
```

```yaml
# data/roles/reasoner.yaml
name: reasoner
label: Reasoner
description: Deep debugging and architecture analysis. Low volume, max reasoning.
typical_class: opus
color: red
```

### Agent declares role, not tier

```yaml
# data/agents/agents.yaml
lead:
  role: orchestrator           # replaces `tier: opus-4.6`
  description: "..."
  mode: primary
  claude: { tools: "...", memory: user }
  opencode: { permission: {...} }

coder:
  role: worker                 # replaces `tier: sonnet`
  ...

explorer:
  role: scout                  # replaces `tier: haiku`
  ...

debugger:
  role: reasoner               # replaces `tier: opus-4.7`
  ...
```

The `tiers:` section is removed from `agents.yaml` entirely.

### Compatibility (auto-computed, not declared)

A model is "compatible with a CLI" iff `model.aliases.keys() ∩ cli.accepted_providers ≠ ∅`.

The resolved provider is the FIRST element of `cli.accepted_providers` that exists in `model.aliases`. That provider's alias becomes the frontmatter `model:` value.

### Frontmatter template (Python module)

```python
# data/templates/frontmatter/claude.py
"""Claude Code frontmatter generator."""

def render(ctx: dict) -> str:
    """Render YAML frontmatter for a Claude Code agent.

    ctx keys:
      agent_name:  str
      agent:       dict (from agents.yaml entry)
      model_id:    str (resolved per-provider alias)
      cli:         CLIBackend object
      prompt:      str (prompt body)
    """
    lines = ["---"]
    lines.append(f"name: {ctx['agent_name']}")
    lines.append(f"description: {ctx['agent']['description']}")
    lines.append(f"model: {ctx['model_id']}")
    claude_cfg = ctx['agent'].get('claude', {})
    if 'tools' in claude_cfg:
        lines.append(f"tools: {claude_cfg['tools']}")
    if 'disallowedTools' in claude_cfg:
        lines.append(f"disallowedTools: {claude_cfg['disallowedTools']}")
    if 'memory' in claude_cfg:
        lines.append(f"memory: {claude_cfg['memory']}")
    if 'color' in ctx['agent']:
        lines.append(f"color: {ctx['agent']['color']}")
    lines.append("---")
    return "\n".join(lines)


def post_process(prompt: str, ctx: dict) -> str:
    """Optional: transform the prompt body. Return as-is by default."""
    return prompt
```

```python
# data/templates/frontmatter/opencode.py
def render(ctx: dict) -> str:
    ...

def post_process(prompt: str, ctx: dict) -> str:
    """Strip ## Memory section for OpenCode (doesn't support agent memory)."""
    return _strip_memory_section(prompt)
```

Adding a new CLI's frontmatter format = one ~30-line Python file in this folder.

---

## State.json

```json
{
  "source_path": "/Users/en3e/code/rubakas/agent-notes",
  "source_commit": "abc1234",
  "global": {
    "installed_at": "2026-04-22T13:05:00Z",
    "updated_at":   "2026-04-22T13:05:00Z",
    "mode": "symlink",
    "clis": {
      "claude": {
        "role_models": {
          "orchestrator": "claude-opus-4-7",
          "reasoner":     "claude-opus-4-7",
          "worker":       "claude-sonnet-4",
          "scout":        "claude-haiku-4-5"
        },
        "installed": {
          "agents":  { "lead.md": {"sha": "...", "target": "..."} },
          "skills":  {...},
          "rules":   {...},
          "config":  {...}
        }
      },
      "opencode": {
        "role_models": {
          "orchestrator": "kimi-k2",
          "reasoner":     "claude-opus-4-7",
          "worker":       "kimi-k2",
          "scout":        "claude-haiku-4-5"
        },
        "installed": {...}
      },
      "copilot": {
        "installed": {
          "config": {"copilot-instructions.md": {"sha": "...", "target": "..."}}
        }
      }
    }
  },
  "local": {
    "/Users/en3e/code/rubakas/my-app": {
      "installed_at": "...",
      "mode": "copy",
      "clis": {
        "claude": { "role_models": {...}, "installed": {...} }
      }
    }
  }
}
```

Fields and their purposes:
- `source_path` — absolute path to the agent-notes checkout that performed the install. Used by `doctor` / `update` to locate source files. **Kept.**
- `source_commit` — git HEAD short SHA at install time. Used by `update` to compute source-side diffs. **Kept.**
- `installed_at` / `updated_at` — ISO timestamps per scope. **Kept.**
- `mode` — `symlink` or `copy`. **Kept.**
- `clis.<name>.role_models` — user's model choice per role. **Omitted for CLIs where `features.agents == false`** (e.g. Copilot has no agents so no role picker).
- `clis.<name>.installed` — file manifest, always present for any installed CLI.

Design rules:
- **No versioning of any kind in state.** No `schema` counter, no `version` string. We're the only user; if we change the shape, we change it. Old state files that don't match → loader returns None, user re-runs `install`.
- `global` is a single object (max one global install).
- `local` is a dict keyed by absolute project path (many local installs).
- Config-only CLIs (no agents/skills) have an `installed` entry but no `role_models` entry.

---

## Resolution chain (build time)

Given state.json, for each installed (scope, CLI) pair:

```
for agent in agents.yaml:
  role = agent.role                    # e.g. "worker"
  model_id = state[scope].clis[cli].role_models[role]
                                        # e.g. "kimi-k2"
  model = models[model_id]
  provider = first(cli.accepted_providers) where provider in model.aliases
                                        # e.g. "openrouter"
  resolved = model.aliases[provider]   # e.g. "moonshotai/kimi-k2"
  template = load_template(cli.frontmatter_template)
                                        # e.g. data/templates/frontmatter/opencode.py
  frontmatter = template.render({
    'agent_name': agent.name,
    'agent': agent,
    'model_id': resolved,
    'cli': cli,
    ...
  })
  prompt = template.post_process(agent.prompt, ctx)
  write(build/<cli>/agents/<agent.name>.md, frontmatter + prompt)
```

If a CLI has no compatible model for a role (shouldn't happen if wizard validated), surface an error.

---

## Wizard flow

```
Step 1 of 4: Which CLI(s) do you use?
  [✓] Claude Code
  [ ] OpenCode
  [ ] Cursor       (appears if data/clis/cursor.yaml exists)

Step 2 of 4: Models for <CLI>             (repeated per selected CLI)

  For Claude Code:
    Orchestrator (plans, delegates — typical: opus):
      1) [*] Claude Opus 4.7
      2) [ ] Claude Sonnet 4
    Reasoner (debugging, architecture — typical: opus):
      1) [*] Claude Opus 4.7
      2) [ ] Claude Sonnet 4
    Worker (implements — typical: sonnet):
      1) [*] Claude Sonnet 4
      2) [ ] Claude Opus 4.7
      3) [ ] Claude Haiku 4.5
    Scout (searches — typical: haiku):
      1) [*] Claude Haiku 4.5
      2) [ ] Claude Sonnet 4

  For OpenCode:
    Orchestrator:
      1) [*] Claude Opus 4.7       (via github-copilot)
      2) [ ] Kimi K2               (via openrouter)
      3) [ ] GPT-5                 (via openai)           ← only shows if model exists
    ...

Step 3 of 4: Install scope?
  1) [*] Global (~/.claude, ~/.config/opencode)
  2) [ ] Local  (current project: /Users/en3e/code/rubakas/my-app)

Step 4 of 4: Install mode?             (only shown for local scope)
  1) [*] Symlink
  2) [ ] Copy

Ready to install:
  Claude Code:
    orchestrator=claude-opus-4-7 (anthropic)
    reasoner=claude-opus-4-7
    worker=claude-sonnet-4
    scout=claude-haiku-4-5
  OpenCode:
    orchestrator=kimi-k2 (openrouter)
    ...
  Scope: Global
Proceed? [Y/n]
```

---

## Duplicate install behavior

```bash
$ agent-notes install
Found existing global installation at ~/.config/agent-notes/state.json
  Installed: 2026-04-22 13:05 UTC
  CLIs:      Claude Code, OpenCode
  Mode:      symlink

Verifying ...
  ✓ 18 Claude agents present
  ✓ 19 OpenCode agents present
  ✓ 30 skills present
  ✓ 2 rules present
  ✓ global config present

Installation is healthy.

Tip: To reinstall with different choices, run:
       agent-notes uninstall
       agent-notes install

     Or to re-run the wizard and overwrite in place:
       agent-notes install --reconfigure
```

`--reconfigure` = clears state, re-runs wizard, installs. Without it, verify-and-exit.

For local installs, same logic scoped to the current project path in state.local.

---

## `agent-notes list` (expanded)

```bash
agent-notes list             # show everything the engine provides
agent-notes list clis
agent-notes list models
agent-notes list roles
agent-notes list agents
agent-notes list skills
agent-notes list rules
```

Default (`list` with no arg) shows a grouped summary:

```
CLIs (3):
  claude    Claude Code              → ~/.claude
  opencode  OpenCode                  → ~/.config/opencode
  copilot   GitHub Copilot            → ~/.github

Models (5):
  claude-opus-4-7        Claude Opus 4.7         [opus]    compatible: claude, opencode, copilot
  claude-sonnet-4        Claude Sonnet 4         [sonnet]  compatible: claude, opencode, copilot
  claude-haiku-4-5       Claude Haiku 4.5        [haiku]   compatible: claude, opencode, copilot
  kimi-k2                Moonshot Kimi K2        [opus]    compatible: opencode
  gpt-5                  GPT-5                   [opus]    compatible: opencode

Roles (4):
  orchestrator    Plans and delegates       (typical: opus)
  reasoner        Deep debugging           (typical: opus)
  worker          Implements code           (typical: sonnet)
  scout           Fast discovery            (typical: haiku)

Agents (19):
  lead          role: orchestrator
  coder         role: worker
  ...

Skills (30):
  ...

Rules (2):
  code-quality.md
  safety.md
```

---

## Phases

### Phase 1 — Model + Role registries (non-breaking, additive) ✅ DONE

**Scope:** Create new data directories and loaders. No build/install changes yet.

1. ✅ `data/models/` — YAMLs for Claude models (opus-4-6, opus-4-7, sonnet-4, haiku-4-5) with `anthropic` + `github-copilot` aliases.
2. ✅ `data/roles/` — 4 role YAMLs (orchestrator, reasoner, worker, scout).
3. ✅ Added `accepted_providers` to CLI YAMLs. (Note: `model_map` still present; Phase 9 removes it.)
4. ✅ `model_registry.py` — loader, compatibility filter, alias resolver.
5. ✅ `role_registry.py` — loader.
6. ✅ Tests: `test_model_registry.py`, `test_role_registry.py` (35 new tests, all passing).

### Phase 2 — State.json shape ✅ DONE

7. ✅ Rewrote `state.py`: single-shape state with `global` single object, `local` dict keyed by project path. `ScopeState`, `BackendState`, `InstalledItem` dataclasses. Helpers: `get_scope`, `set_scope`, `remove_scope`. Custom JSON (de)serialization due to `global`/`local` Python-keyword mapping.
8. ✅ `install_state.py`: `build_install_state(scope, project_path, role_models=...)`, `remove_install_state()`.
9. ✅ Updated `install.py` (project_path for local, scoped uninstall, global+locals `show_info`), `update.py` (scope-aware), `update_diff.py` (added `diff_scope_states()`), `doctor.py` + `doctor_checks.py` (accept `ScopeState`).
10. ✅ All tests pass (429/429). `test_state.py`, `test_install_state.py`, `test_update_diff.py`, `test_doctor.py` all on the new shape.

### Phase 3 — Modularity audit & versioning strip ✅ DONE

**Goal:** eliminate every hardcoded CLI name from the codebase. After Phase 3, adding a new CLI must be a pure YAML drop (plus a frontmatter template in Phase 5). No more `if cli == "claude"` branches, no more `count_agents_claude()` / `count_agents_opencode()`, no more `"claude"` / `"opencode"` string comparisons in code.

#### 3.1 — Strip versioning from state.py

3.1.1. Remove `STATE_SCHEMA_VERSION` constant from `state.py`.
3.1.2. Remove `schema` field from `State` dataclass.
3.1.3. Remove `version` field from `State` dataclass.
3.1.4. Remove schema check + "stale state" warning from `load()`. If JSON is unparseable or shape doesn't match → return None.
3.1.5. Remove `"schema"` and `"version"` keys from `_state_to_dict` / `_state_from_dict`.
3.1.6. Remove `version` parameter from `install_state.build_install_state()`.
3.1.7. Update callers in `install.py` / `update.py` that pass `version=`.
3.1.8. Update tests: drop `schema=2` / `version="..."` from fixtures, remove `test_load_old_schema_deletes_file` and related assertions.
3.1.9. Remove `STATE_SCHEMA_VERSION` import from `tests/test_state.py`.

**Design rule:** no versioning of data anywhere. App version (VERSION file) is the only version we track. If a state file doesn't match the current loader's expectations, it's stale — return None and let user re-run `install`.

#### 3.2 — Remove hardcoded CLI names from `install.py`

3.2.1. Delete `count_agents_claude()`, `count_agents_opencode()`.
3.2.2. Replace with generic `count_agents(backend: CLIBackend) -> int` that reads from the registry + dist structure.
3.2.3. `show_info()` must iterate `registry.all()` and emit one line per backend — no hardcoded "Agents (Claude)" / "Agents (OpenCode)" / "Copilot" / "Universal" labels.
3.2.4. Install targets section: iterate registry for home paths; drop hardcoded `~/.claude/`, `~/.config/opencode/`, `~/.github/`.
3.2.5. `~/.agents/` (universal skills mirror): keep, but source the path from a single constant, not per-CLI.

#### 3.3 — Remove hardcoded CLI names from `build.py`

3.3.1. The `tiers[tier]['claude']` / `tiers[tier]['opencode']` dict access is two hardcoded branches. Replace with `model = tiers[tier][backend.name]` or, better, scrap tiers entirely (Phase 9) in favor of role→model lookup from state (Phase 4). For Phase 3, just make the dict access data-driven.
3.3.2. No `if cli == "claude"` / `elif cli == "opencode"` anywhere in build pipeline.

#### 3.4 — Remove hardcoded CLI names from `wizard.py`

3.4.1. Final summary currently has branches: `if "claude" in clis and "opencode" in clis: ... elif "claude" in clis: ... else (opencode)`. Replace with loop over selected CLIs, using `backend.label` from registry.
3.4.2. The "install copilot-instructions.md even if only claude selected" carve-out (lines 481–485). Current behavior: if user picks Claude but not Copilot, Copilot's config file still gets installed (because `.github/copilot-instructions.md` is useful alongside Claude Code). This is ad-hoc and confusing. **For Phase 3:** delete this carve-out. Users who want Copilot select Copilot explicitly in step 1. The wizard is now registry-driven, so Copilot appears as its own checkbox.
3.4.3. Backend-specific UI code at lines 433–438 (`if backend.name == "claude": ... elif backend.name == "opencode":`) — move that data to the backend YAML as a `wizard_hint:` or drop it entirely if purely cosmetic.

#### 3.5 — Remove hardcoded CLI names from `doctor.py`

3.5.1. `_cli_base_dir()` returns hardcoded `CLAUDE_HOME` / `OPENCODE_HOME` / `.claude` / `.opencode`. Replace with a helper that reads `backend.global_home` (global) or `Path(backend.local_dir)` (local) from the registry.
3.5.2. `for cli, cli_name in [("claude", "Claude Code"), ("opencode", "OpenCode")]` loop — drive from `registry.all()`, skip CLIs where `features.agents == false`.
3.5.3. `_count_agents`, `_count_skills`, `_count_rules` branches keyed on cli name → iterate registry and use `installer.target_dir_for(backend, component, scope)`.
3.5.4. `_find_dist_source` does **reverse lookup** (given a symlink path, find which dist directory it came from). Refactor to iterate `registry.all()` and try `installer.dist_source_for(backend, component)` for each component type; return the first match. Do NOT assume the symlink names the CLI — the parent directory name (`agents`, `skills`, `rules`) is what maps to the component type.
3.5.5. `check_build_freshness` (doctor.py lines ~216–258) has hardcoded `DIST_CLAUDE_DIR`, `DIST_OPENCODE_DIR`, `GLOBAL_CLAUDE_MD`, `GLOBAL_OPENCODE_MD`, `GLOBAL_COPILOT_MD` references. Rewrite as: iterate `registry.all()`, for each backend with `features.agents`, check its dist/agents/ directory; for each backend with a `global_template`, check that global file. No per-CLI constants remain.

#### 3.6 — Verification

3.6.1. `grep -rnE '"claude"|"opencode"|"copilot"' agent_notes/*.py` should return hits ONLY in:
  - Import lines (e.g. `from .config import DIST_CLAUDE_DIR`) if constants still exist (they can be renamed or removed in Phase 12).
  - Test files (tests may still reference specific CLIs as fixtures — that's fine).
  - String-literal YAML content inside error messages (acceptable).
  Goal: no runtime `if cli == "claude"` branches.
3.6.2. Full test suite passes. Expected test count: **~440–445** (429 current + ~10–15 new tests for generic `count_agents(backend)`, registry-driven `show_info`, etc.). Any number below 429 is a regression.
3.6.3. Smoke test — rename: rename a CLI in `data/cli/*.yaml` (e.g. `opencode.yaml` → `opencode2.yaml`, change `name: opencode` → `name: opencode2`). Run `agent-notes install`. Wizard should show "opencode2" instead of "opencode." Install should work end-to-end. Revert.
3.6.4. Smoke test — new CLI: drop a minimal `data/cli/cursor.yaml` with `features.agents: false, features.frontmatter: null, features.skills: false, features.rules: false`, just a config file template. Run `agent-notes install`. Wizard should offer Cursor as a selectable CLI. Installing it should write Cursor's config file to its declared home. No crash even though no frontmatter template exists (because `features.frontmatter: null` = skip template lookup). Remove the file after testing.

### Phase 4 — Build engine reads from state

11. `build.py`: resolve each agent's role via `state[scope].clis[cli].role_models[role]`.
12. Resolve provider alias, resolve model_id.
13. Call frontmatter template (still hardcoded in `build.py` for now — Phase 5 moves to template files).
14. Tests updated.

### Phase 5 — Frontmatter templates as plugins

15. Move `generate_claude_frontmatter` → `data/templates/frontmatter/claude.py`.
16. Move `generate_opencode_frontmatter` → `data/templates/frontmatter/opencode.py`.
17. `build.py`: import template by name from `data/templates/frontmatter/<cli.frontmatter_template>.py`.
18. Adding a new CLI's frontmatter = adding a new file in `data/templates/frontmatter/`.

### Phase 6 — Wizard rewrite for role-based model selection

19. New wizard step 2: per-CLI model pickers, one picker per role.
20. Show only compatible models (`model.aliases ∩ cli.accepted_providers ≠ ∅`).
21. Default to model with matching `class == role.typical_class`.
22. Multi-CLI = repeat step 2 per CLI.
23. State.json writes `role_models` per CLI.

### Phase 7 — Duplicate install = verify-and-exit

24. `agent-notes install`: if state has an entry for the current scope/path, verify instead of reinstalling.
25. Report verification results + tip about `uninstall && install` or `--reconfigure`.
26. New `--reconfigure` flag: clears the scope's state entry, runs wizard.

### Phase 8 — Expanded `list` command

27. `list clis`, `list models`, `list roles` — new filters.
28. `list` (no arg) shows grouped summary of everything.
29. Include compatibility info: each model shows which CLIs can use it.

### Phase 9 — Remove dead code

33. Remove `tiers:` from `agents.yaml`.
34. Remove `model_map` from CLI YAMLs.
35. Remove `generate_claude_frontmatter` / `generate_opencode_frontmatter` from `build.py`.

### Phase 10 — Post-install reconfiguration

Users must be able to modify an installation after the fact without re-running the full wizard. All changes write back to state.json and trigger regeneration of affected files.

**Commands:**

10.1. ~~`agent-notes set agent <agent-name> <role-name>`~~ — **Dropped from 1.1.0.** Per-agent role overrides require a user-override layer on top of `agents.yaml`, which we're not building. Agents keep the `role:` declared in source (Phase 6). If users want to reassign an individual agent, they can edit `agents.yaml` and run `regenerate`.

10.2. `agent-notes set role <role-name> <model-id> [--cli <cli>] [--scope global|local]`
  - Updates `state[scope].clis[cli].role_models[role]` to new model_id.
  - Validates model is compatible with cli (`model.aliases ∩ cli.accepted_providers ≠ ∅`). Error and abort if not.
  - `--cli` handling:
    - If only ONE CLI in the scope has this role, default to that CLI.
    - If multiple CLIs have this role, `--cli` is **required** (error if omitted — listing candidates).
    - If `--cli all` is given, apply to every CLI where the model is compatible with that CLI; skip (with a per-CLI warning) for CLIs where it's not compatible. Do not partially fail.
  - `--scope` default: `global` if a global install exists, else `local` (current dir). Error if neither.
  - Writes state.json, then calls `regenerate` internally for the affected (scope, CLI) pair(s).

10.3. `agent-notes regenerate [--scope global|local] [--cli <cli>]`
  - Reads current state.json.
  - Rebuilds all agent files / skills / rules / configs for the affected scope+CLI.
  - Updates `installed` manifest in state.
  - Shows diff of what changed vs skipped.
  - Used by `set role` and manually by users who hand-edit state.json.

**State.json is hand-editable.** Users can open `~/.config/agent-notes/state.json`, change a role's model, then run `agent-notes regenerate` — same result as `set role`. `set` commands are convenience wrappers.

**Doctor enhancement (part of Phase 10):** `doctor` output should display role→model assignments per scope per CLI (so users see the current config at a glance) and flag any role assigned a model that's not compatible with its CLI (defensive — shouldn't happen if set-role validated, but catches hand-edit errors).

**Design constraint:** every generated file must be regeneratable from state.json alone. Nothing the user configured (models, scopes, modes) can require the wizard to recover.

### Phase 11 — Docs

36. Update README with engine model.
37. Write "How to add a new CLI" doc.
38. Write "How to add a new model" doc.
39. Keep `docs/CLI_CAPABILITIES.md` current when new CLIs are added; cite it as the source-of-truth for per-CLI behavior.

### Phase 12 — Directory cleanup + globals rename (COSMETIC, LAST)

Pure cosmetic renames. No functional change. Do this AFTER Phase 11 (docs) or skip entirely — the current paths work fine.

40. `data/cli/` → `data/clis/` (plural for consistency with `data/models/`, `data/roles/`).
41. `data/global-claude.md` → `data/globals/claude.md`, etc.
42. Update all references in code (`DATA_DIR / "cli"` → `DATA_DIR / "clis"`, etc.).

---

## Design constraints

- **No new runtime dependencies.** Python stdlib + PyYAML. Frontmatter templates are Python modules, not Jinja.
- **No versioning of data.** No schema numbers, no version strings in state.json, no migration code. If the state file shape doesn't match what the loader expects, return None and let the user re-run `install`. App version (VERSION file) is the only version we track.
- **Tests pass at every phase boundary.** Each phase ships independently.
- **Zero Python edits to add a new CLI/model/role.** Drop YAML (+ Python template for new CLI frontmatter).

---

## What this enables (the user's scenarios)

| User scenario | Work required |
|---|---|
| "Add Claude Code with Anthropic models" | Already shipped; `agent-notes install`, pick Claude Code, pick Claude models for each role |
| "Add OpenCode with Kimi" | Drop `data/models/kimi-k2.yaml`; `agent-notes install`, pick OpenCode, pick Kimi for each role |
| "Add Cursor" | Drop `data/clis/cursor.yaml` + `data/templates/frontmatter/cursor.py` + `data/globals/cursor.md`. Zero Python changes to `install.py` / `build.py`. |
| "Add Gemini" | Drop `data/models/gemini-2-5-pro.yaml` with `aliases.google` entry. Wizard auto-offers it for any CLI with `google` in `accepted_providers`. |
| "Mix: Claude Opus orchestrator + Kimi workers on OpenCode" | During wizard, pick per role: orchestrator=claude-opus-4-7, worker=kimi-k2, scout=kimi-k2. State records it. Build resolves each role's model. |
| "Multiple local installs across projects" | `cd my-project && agent-notes install --local`; `cd other-project && agent-notes install --local`. Each recorded under its own path in state.local. |

---

## Detailed Execution Plans (Phases 9-12)

# Detailed Execution Plans for Remaining Phases

## Phase 9 Completion Plan (PARTIALLY COMPLETE)

### Current Status
- ✅ agents.yaml: `tier:` → `role:` conversion complete
- ✅ agents.yaml: `tiers:` section removed
- ✅ CLI YAMLs: `model_map` removed from claude.yaml, opencode.yaml, copilot.yaml
- ✅ build.py: Removed `strip_memory_section()`, `generate_claude_frontmatter()`, `generate_opencode_frontmatter()`
- ✅ test_build.py: Removed TestStripMemorySection, TestGenerateClaudeFrontmatter, TestGenerateOpencodeFrontmatter classes
- ⏸️ PAUSED at: CLIBackend dataclass still has `model_map` field

### Remaining Steps

#### Step 1: Remove `model_map` from CLIBackend dataclass
**File:** `agent_notes/cli_backend.py`
**Lines:** 25, 109

**Action:**
```python
# Line 25 - Remove from dataclass definition:
# DELETE: model_map: dict[str, str]      # tier -> model id

# Line 109 - Remove from constructor:
# DELETE: model_map=data.get("model_map", {}),
```

#### Step 2: Check conftest.py for model_map references
**File:** `tests/conftest.py`

**Search for:** Any CLIBackend mock fixtures that set `model_map`
**Action:** Remove `model_map` parameter from any mock CLIBackend instances

#### Step 3: Find and update tests referencing `tier`
**Search:** `grep -r "tier.*:" tests/ --include="*.py"`
**Expected locations:**
- Tests that create agent_config dicts with `'tier': 'sonnet'`
- Tests for `generate_agent_files()` that pass `tiers` dict

**Action:** 
- Replace `'tier': 'sonnet'` with `'role': 'worker'` in test fixtures
- For tests of `generate_agent_files()` fallback path (when no state), keep `tiers` param as-is since the function signature still accepts it for legacy fallback

#### Step 4: Verify `generate_agent_files()` signature
**File:** `agent_notes/build.py`
**Current signature:**
```python
def generate_agent_files(agents_config, tiers, state=None, scope='global', project_path=None)
```

**Decision:** KEEP the `tiers` parameter for now as fallback (Phase 4 design). It's only dead code if NO agents use it. Since all agents now have `role:` and state-driven path is active, the tiers fallback won't be used in practice but keeps backward compat.

**Alternative:** If we want to fully remove `tiers`:
1. Change signature to: `generate_agent_files(agents_config, state, scope='global', project_path=None)`
2. Make `state` required (error if None)
3. Update all call sites (build.py's `build()` function, tests)
4. This is more aggressive cleanup

**Recommendation:** Keep `tiers` parameter as deprecated-but-present for Phase 9. Full removal can be Phase 13 if desired.

#### Step 5: Run full test suite
```bash
python3 -m pytest
```

**Expected:** All 452 tests pass (or slightly fewer after removing the 3 test classes, maybe ~442)

**If failures occur:**
- Check error messages for references to `tier`, `model_map`, or removed functions
- Update those tests to use `role` or remove if testing dead code

#### Step 6: Update status table in ENGINE_PLAN.md
Mark Phase 9 as ✅ DONE with note about test count

---

## Phase 10 Detailed Plan: Post-Install Reconfiguration

### Overview
Enable users to modify role→model assignments after installation without re-running the wizard.

### Components

#### 10.1: `agent-notes set role` command

**New file:** `agent_notes/set_role.py` (or add to existing commands file)

**Function signature:**
```python
def set_role(role_name: str, model_id: str, cli: str = None, scope: str = None, local: bool = False) -> None:
    """Update role→model assignment in state.json and regenerate affected files.
    
    Args:
        role_name: Role to update (orchestrator, reasoner, worker, scout)
        model_id: New model ID (must be in model registry)
        cli: Target CLI name (auto-detect if only one CLI has this role in scope)
        scope: 'global' or 'local' (auto: global if exists, else local)
        local: Shortcut for scope='local'
    """
```

**Implementation steps:**

1. **Load state.json**
   ```python
   from . import state as state_mod
   from .state import get_scope
   
   current_state = state_mod.load()
   if current_state is None:
       print("No installation found. Run `agent-notes install` first.")
       sys.exit(1)
   ```

2. **Determine scope**
   ```python
   if local:
       scope = 'local'
   elif scope is None:
       # Auto-detect: prefer global if exists
       if current_state.global_install is not None:
           scope = 'global'
       elif current_state.local_installs:
           scope = 'local'
       else:
           print("No installation found.")
           sys.exit(1)
   
   project_path = Path.cwd() if scope == 'local' else None
   scope_state = get_scope(current_state, scope, project_path)
   
   if scope_state is None:
       print(f"No {scope} installation found.")
       sys.exit(1)
   ```

3. **Validate role exists**
   ```python
   from .role_registry import load_role_registry
   
   role_registry = load_role_registry()
   try:
       role = role_registry.get(role_name)
   except KeyError:
       print(f"Unknown role: {role_name}")
       print(f"Available roles: {', '.join(role_registry.names())}")
       sys.exit(1)
   ```

4. **Validate model exists and get it**
   ```python
   from .model_registry import load_model_registry
   
   model_registry = load_model_registry()
   try:
       model = model_registry.get(model_id)
   except KeyError:
       print(f"Unknown model: {model_id}")
       print(f"Available models: {', '.join(model_registry.ids())}")
       sys.exit(1)
   ```

5. **Determine target CLI(s)**
   ```python
   from .cli_backend import load_registry
   
   registry = load_registry()
   
   if cli == "all":
       # Apply to all CLIs where model is compatible
       target_clis = []
       for cli_name in scope_state.clis.keys():
           backend = registry.get(cli_name)
           if backend.first_alias_for(model.aliases) is not None:
               target_clis.append(cli_name)
           else:
               print(f"Warning: Skipping {backend.label} - model {model_id} not compatible")
       
       if not target_clis:
           print(f"Model {model_id} is not compatible with any installed CLI")
           sys.exit(1)
   
   elif cli is None:
       # Auto-detect: error if ambiguous
       candidates = [name for name in scope_state.clis.keys()]
       if len(candidates) == 0:
           print("No CLIs found in this scope")
           sys.exit(1)
       elif len(candidates) == 1:
           target_clis = candidates
       else:
           print(f"Multiple CLIs found: {', '.join(candidates)}")
           print("Specify --cli <name> or --cli all")
           sys.exit(1)
   else:
       # Explicit CLI specified
       if cli not in scope_state.clis:
           print(f"CLI '{cli}' not found in {scope} installation")
           print(f"Installed CLIs: {', '.join(scope_state.clis.keys())}")
           sys.exit(1)
       
       backend = registry.get(cli)
       if backend.first_alias_for(model.aliases) is None:
           print(f"Model {model_id} is not compatible with {backend.label}")
           print(f"Compatible providers: {', '.join(backend.accepted_providers)}")
           print(f"Model providers: {', '.join(model.aliases.keys())}")
           sys.exit(1)
       
       target_clis = [cli]
   ```

6. **Update state.json**
   ```python
   for cli_name in target_clis:
       backend_state = scope_state.clis[cli_name]
       backend_state.role_models[role_name] = model_id
       print(f"Updated {cli_name}: {role_name} → {model_id}")
   
   # Write back
   from . import install_state
   install_state.record_install_state(current_state)
   print(f"Wrote {state_mod.state_file()}")
   ```

7. **Trigger regenerate**
   ```python
   from .regenerate import regenerate
   
   for cli_name in target_clis:
       print(f"\nRegenerating {cli_name}...")
       regenerate(scope=scope, cli=cli_name, project_path=project_path)
   ```

**CLI integration** (`agent_notes/cli.py`):
```python
# Add subparser
p_set_role = subparsers.add_parser("set", help="Configure installation")
p_set_role.add_argument("entity", choices=["role"], help="What to configure")
p_set_role.add_argument("role_name", help="Role name")
p_set_role.add_argument("model_id", help="Model ID")
p_set_role.add_argument("--cli", help="Target CLI (auto-detect if omitted)")
p_set_role.add_argument("--scope", choices=["global", "local"], help="Install scope")
p_set_role.add_argument("--local", action="store_true", help="Use local scope")

# In main():
elif args.command == "set":
    if args.entity == "role":
        from .set_role import set_role
        set_role(args.role_name, args.model_id, cli=args.cli, scope=args.scope, local=args.local)
```

**Tests** (`tests/test_set_role.py`):
1. `test_set_role_updates_state_and_regenerates` - happy path
2. `test_set_role_validates_role_name` - unknown role errors
3. `test_set_role_validates_model_id` - unknown model errors
4. `test_set_role_validates_compatibility` - incompatible model errors
5. `test_set_role_auto_detects_single_cli` - no --cli needed if only one
6. `test_set_role_requires_cli_when_multiple` - errors if ambiguous
7. `test_set_role_all_skips_incompatible` - --cli all warns and skips
8. `test_set_role_auto_detects_scope` - prefers global
9. `test_set_role_errors_if_no_install` - no state.json

#### 10.2: `agent-notes regenerate` command

**New file:** `agent_notes/regenerate.py`

**Function signature:**
```python
def regenerate(scope: str = None, cli: str = None, local: bool = False, project_path: Path = None) -> None:
    """Rebuild agent/skill/config files from current state.json.
    
    Args:
        scope: 'global' or 'local' (auto-detect if omitted)
        cli: Target CLI (regenerate all if omitted)
        local: Shortcut for scope='local'
        project_path: Explicit project path for local scope
    """
```

**Implementation:**

1. **Load state**
   ```python
   from . import state as state_mod
   from .state import get_scope
   
   current_state = state_mod.load()
   if current_state is None:
       print("No state.json found. Nothing to regenerate.")
       sys.exit(1)
   ```

2. **Determine scope**
   ```python
   if local:
       scope = 'local'
   elif scope is None:
       # Auto-detect
       if current_state.global_install:
           scope = 'global'
       elif current_state.local_installs:
           scope = 'local'
       else:
           print("No installation found in state")
           sys.exit(1)
   
   if project_path is None and scope == 'local':
       project_path = Path.cwd()
   
   scope_state = get_scope(current_state, scope, project_path)
   if scope_state is None:
       print(f"No {scope} installation found")
       sys.exit(1)
   ```

3. **Determine target CLIs**
   ```python
   if cli:
       if cli not in scope_state.clis:
           print(f"CLI '{cli}' not in {scope} installation")
           print(f"Installed: {', '.join(scope_state.clis.keys())}")
           sys.exit(1)
       target_clis = [cli]
   else:
       target_clis = list(scope_state.clis.keys())
   ```

4. **Load agent config**
   ```python
   from .config import DATA_DIR
   import yaml
   
   agents_yaml = DATA_DIR / "agents" / "agents.yaml"
   with open(agents_yaml) as f:
       agents_data = yaml.safe_load(f)
   
   agents_config = agents_data.get('agents', {})
   ```

5. **Regenerate per CLI**
   ```python
   from .build import generate_agent_files
   from .cli_backend import load_registry
   
   registry = load_registry()
   
   print(f"Regenerating {scope} installation...")
   
   for cli_name in target_clis:
       backend = registry.get(cli_name)
       print(f"\n{backend.label}:")
       
       # Generate agents
       if backend.supports("agents"):
           files = generate_agent_files(
               agents_config, 
               {},  # empty tiers - state-driven only
               state=current_state,
               scope=scope,
               project_path=project_path
           )
           print(f"  ✓ {len([f for f in files if cli_name in str(f)])} agents")
       
       # TODO: Regenerate skills, rules, config similarly
       # (reuse logic from installer.py)
   ```

6. **Update installed manifest**
   ```python
   # Re-scan what was generated and update state.installed
   from . import install_state
   
   new_state = install_state.build_install_state(
       mode=scope_state.mode,
       scope=scope,
       repo_root=PKG_DIR.parent,
       project_path=project_path,
       role_models=scope_state.clis  # preserve existing role_models
   )
   
   # Merge back into current_state
   # (preserve other scopes)
   if scope == 'global':
       current_state.global_install = new_state.global_install
   else:
       # Update the specific local install
       # ... (state.py helper needed)
   
   install_state.record_install_state(current_state)
   ```

**CLI integration**:
```python
p_regen = subparsers.add_parser("regenerate", help="Rebuild files from state")
p_regen.add_argument("--scope", choices=["global", "local"])
p_regen.add_argument("--cli", help="Regenerate specific CLI only")
p_regen.add_argument("--local", action="store_true")

# In main():
elif args.command == "regenerate":
    from .regenerate import regenerate
    regenerate(scope=args.scope, cli=args.cli, local=args.local)
```

**Tests** (`tests/test_regenerate.py`):
1. `test_regenerate_rebuilds_from_state`
2. `test_regenerate_single_cli`
3. `test_regenerate_updates_installed_manifest`
4. `test_regenerate_errors_if_no_state`
5. `test_regenerate_auto_detects_scope`

#### 10.3: Doctor enhancement

**File:** `agent_notes/doctor.py`

**Add to `doctor()` function output:**

```python
def _check_role_models(state):
    """Display role→model assignments and check compatibility."""
    from .model_registry import load_model_registry
    from .cli_backend import load_registry
    
    model_registry = load_model_registry()
    cli_registry = load_registry()
    issues = []
    
    print(f"\n{Color.CYAN}Role→Model Assignments:{Color.NC}\n")
    
    # Global
    if state.global_install:
        print("Global:")
        for cli_name, backend_state in state.global_install.clis.items():
            backend = cli_registry.get(cli_name)
            print(f"  {backend.label}:")
            for role, model_id in backend_state.role_models.items():
                try:
                    model = model_registry.get(model_id)
                    # Check compatibility
                    if backend.first_alias_for(model.aliases) is None:
                        print(f"    ✗ {role}: {model_id} (INCOMPATIBLE)")
                        issues.append(f"Global {backend.label}: role '{role}' assigned incompatible model '{model_id}'")
                    else:
                        print(f"    ✓ {role}: {model_id}")
                except KeyError:
                    print(f"    ✗ {role}: {model_id} (NOT FOUND)")
                    issues.append(f"Global {backend.label}: role '{role}' assigned unknown model '{model_id}'")
        print()
    
    # Local installs
    for path, local_state in state.local_installs.items():
        print(f"Local ({path}):")
        for cli_name, backend_state in local_state.clis.items():
            backend = cli_registry.get(cli_name)
            print(f"  {backend.label}:")
            for role, model_id in backend_state.role_models.items():
                # same check as global
                ...
    
    return issues
```

**Call from `doctor()`**:
```python
# After existing checks, add:
if state:
    role_issues = _check_role_models(state)
    all_issues.extend(role_issues)
```

---

## Phase 11 Detailed Plan: Documentation

### 11.1: Update README.md

**Sections to add/update:**

1. **Architecture diagram** showing the three registries (CLIs, Models, Roles)
2. **Installation flow** with model selection per role
3. **Post-install reconfiguration** section explaining `set role` and `regenerate`
4. **Examples:**
   ```bash
   # Install with model selection
   agent-notes install
   
   # Change a role's model after install
   agent-notes set role worker claude-sonnet-4 --cli claude --scope global
   
   # Regenerate files after hand-editing state.json
   agent-notes regenerate
   
   # List available models/roles
   agent-notes list models
   agent-notes list roles
   ```

### 11.2: Write "How to add a new CLI" guide

**New file:** `docs/ADD_CLI.md`

**Contents:**

```markdown
# How to Add a New AI CLI

Adding support for a new AI CLI (like Cursor, Windsurf, Zed, etc.) requires **zero Python code changes** in the common case. You only need to add data files.

## Steps

### 1. Create CLI descriptor

Create `agent_notes/data/cli/<cli-name>.yaml`:

```yaml
name: cursor
label: Cursor
global_home: ~/.cursor
local_dir: .cursor
layout:
  agents: agents/
  skills: skills/
  config: CURSOR.md
features:
  agents: true
  skills: true
  rules: false
  frontmatter: cursor  # name of template
  config_style: inline
  supports_symlink: true
global_template: global-cursor.md
exclude_flag: cursor_exclude
accepted_providers: [openai, anthropic, custom-provider]
```

### 2. Create frontmatter template

Create `agent_notes/data/templates/frontmatter/cursor.py`:

```python
"""Cursor agent frontmatter template."""

def render(ctx):
    """Generate Cursor-format frontmatter.
    
    Args:
        ctx: dict with agent_name, agent_config, model_str, backend
    
    Returns:
        str: YAML frontmatter
    """
    agent_config = ctx['agent_config']
    model_str = ctx['model_str']
    
    lines = ['---']
    lines.append(f'name: {ctx["agent_name"]}')
    lines.append(f'description: {agent_config["description"]}')
    lines.append(f'model: {model_str}')
    
    # Add Cursor-specific fields
    if 'cursor' in agent_config:
        cursor_config = agent_config['cursor']
        for key, value in cursor_config.items():
            lines.append(f'{key}: {value}')
    
    lines.append('---')
    return '\\n'.join(lines)

def post_process(prompt: str, ctx):
    """Post-process prompt content (optional).
    
    Args:
        prompt: The markdown body after frontmatter
        ctx: Same context as render()
    
    Returns:
        str: Processed prompt
    """
    # Remove sections Cursor doesn't support, etc.
    return prompt
```

### 3. Create global config template

Create `agent_notes/data/global-cursor.md`:

```markdown
# Global Cursor Configuration

System-wide instructions for all Cursor agents...
```

### 4. (Optional) Add CLI-specific agent config

In `agents.yaml`, add per-agent Cursor settings:

```yaml
agents:
  coder:
    description: "..."
    role: worker
    cursor:  # CLI-specific config
      permission:
        edit: allow
```

### 5. Test

```bash
agent-notes install
# Select Cursor from the CLI list
# Model selection works automatically if models have matching providers
```

## That's it!

No Python code changes needed. The installer, build engine, and wizard automatically discover and use your new CLI.

## Adding Provider Support

If your CLI uses a provider not yet in any model's `aliases`, add models:

```yaml
# agent_notes/data/models/gpt-5.yaml
id: gpt-5
label: GPT-5
family: gpt
class: opus
aliases:
  openai: gpt-5
  cursor: gpt-5-cursor-alias  # Cursor-specific alias
```

Then your CLI's `accepted_providers: [cursor, openai]` will match.
```

### 11.3: Write "How to add a new model" guide

**New file:** `docs/ADD_MODEL.md`

**Contents:**

```markdown
# How to Add a New AI Model

Adding a new model requires creating a single YAML file. No Python code changes.

## Steps

### 1. Create model descriptor

Create `agent_notes/data/models/<model-id>.yaml`:

```yaml
id: kimi-k2
label: Kimi K2
family: kimi
class: opus  # orchestrator-class
aliases:
  openrouter: moonshot/kimi-k2
  anthropic: kimi-k2  # if Anthropic added Kimi support
  github-copilot: github-copilot/kimi-k2
pricing:
  input: 1.00
  output: 5.00
  cache: 0.10
capabilities:
  vision: true
  long_context: true
  tool_use: true
```

### 2. Choose model class

The `class` field determines default role assignment in the wizard:

- `opus` → defaults for orchestrator, reasoner roles
- `sonnet` → defaults for worker role  
- `haiku` → defaults for scout role
- `flash`, `pro`, etc. → you define the mapping

### 3. Add provider aliases

Each alias maps to a CLI's `accepted_providers`. For example:

- `openrouter: moonshot/kimi-k2` → matches CLIs with `openrouter` in `accepted_providers`
- `github-copilot: ...` → matches OpenCode
- `anthropic: ...` → matches Claude Code

### 4. Test

```bash
agent-notes list models
# Should show your new model with compatible CLIs

agent-notes install
# Select a CLI, wizard offers your model if providers match
```

## Model Compatibility

A model is offered for a CLI if:

```
model.aliases.keys() ∩ cli.accepted_providers ≠ ∅
```

Example:
- Model has `{openrouter: "...", openai: "..."}`
- CLI has `accepted_providers: [openai, anthropic]`
- Match on `openai` → model is offered

## Multi-Provider Models

Some models are available through multiple providers:

```yaml
id: claude-opus-4-7
aliases:
  anthropic: claude-opus-4-7
  bedrock: arn:aws:bedrock:us-east-1::...
  vertex: claude-3-opus@20240514
  github-copilot: github-copilot/claude-opus-4.7
```

The wizard picks the first matching provider from the CLI's `accepted_providers` list.
```

### 11.4: Update CLI_CAPABILITIES.md citation

Add note at top:

```markdown
**This document is the source of truth for CLI-specific behavior.**

When adding a new CLI (see `docs/ADD_CLI.md`), research that CLI's capabilities and document them here. This ensures the frontmatter template and installer generate correct config.
```

---

## Phase 12 Detailed Plan: Directory Cleanup (COSMETIC)

**OPTIONAL - Can skip if current naming is acceptable**

### Changes

1. `data/cli/` → `data/clis/` (plural)
2. `data/global-claude.md` → `data/globals/claude.md`
3. `data/global-opencode.md` → `data/globals/opencode.md`
4. `data/global-copilot.md` → `data/globals/copilot.md`

### Implementation

**Step 1: Create new directories**
```bash
mkdir -p agent_notes/data/clis
mkdir -p agent_notes/data/globals
```

**Step 2: Move files**
```bash
mv agent_notes/data/cli/*.yaml agent_notes/data/clis/
mv agent_notes/data/global-*.md agent_notes/data/globals/
# Rename: global-claude.md → claude.md, etc.
```

**Step 3: Update code references**

Search and replace in all Python files:
- `DATA_DIR / "cli"` → `DATA_DIR / "clis"`
- `DATA_DIR / "global-claude.md"` → `DATA_DIR / "globals" / "claude.md"`

**Files likely affected:**
- `agent_notes/config.py` (DIR constants)
- `agent_notes/cli_backend.py` (load path)
- `agent_notes/install.py` (global template refs)
- `agent_notes/build.py` (global template refs)

**Step 4: Run tests**

Should be no functional change, just path updates.

---

## Summary: Remaining Work Checklist

### Phase 9 Completion (15 minutes)
- [ ] Remove `model_map` from CLIBackend dataclass (cli_backend.py lines 25, 109)
- [ ] Check conftest.py for model_map in mocks
- [ ] Search tests for `'tier':` references, update to `'role':`
- [ ] Run full test suite, verify ~442-445 tests pass
- [ ] Update ENGINE_PLAN.md status table

### Phase 10: Post-Install Reconfiguration (4-6 hours)
- [ ] Implement `agent_notes/set_role.py` (2 hours)
- [ ] Implement `agent_notes/regenerate.py` (1.5 hours)
- [ ] Add CLI integration in `cli.py` (30 min)
- [ ] Enhance `doctor.py` with role→model display (30 min)
- [ ] Write tests for `set_role` (1 hour)
- [ ] Write tests for `regenerate` (1 hour)

### Phase 11: Documentation (2-3 hours)
- [ ] Update README.md with architecture and examples (1 hour)
- [ ] Write `docs/ADD_CLI.md` (45 min)
- [ ] Write `docs/ADD_MODEL.md` (45 min)
- [ ] Update `docs/CLI_CAPABILITIES.md` citation note (15 min)

### Phase 12: Directory Cleanup (1 hour) - OPTIONAL
- [ ] Create new directories
- [ ] Move files and rename
- [ ] Update all code references
- [ ] Run tests

**Total estimated time: 8-11 hours remaining**
**Current test count: ~442-445 (after Phase 9 completion)**
**Target: All tests passing at each phase boundary**

---

## Phase 13 — Domain model consolidation (`agent_notes/domain/` package)

**Status:** ⏳ PLANNED · **Priority:** medium (architectural hygiene) · **Est.:** 3-4 hours · **Risk:** low (pure move + re-export, no behavior change)

### Why

Domain model classes (the data structures that describe *what the system is*, independent of *what it does*) are currently scattered across command/service modules. This conflates two concerns:

1. **Domain models** — dataclasses like `CLIBackend`, `Model`, `Role`, `State`, `BackendState`, `InstalledItem`. They describe the problem space. Stable, small, I/O-free.
2. **Services / commands** — modules like `install.py`, `doctor.py`, `regenerate.py` that *use* those models to do work. Churn-heavy, side-effecting.

Today, a reader looking for "what is a `CLIBackend`?" has to open `cli_backend.py`, which also contains `CLIRegistry`, YAML loading, `lru_cache` wiring, and path-expansion logic. Services importing these types pull in registry-loading machinery as a side effect of an `import`.

The user's request — "we need a folder for its models" — is exactly right. We will call the package **`agent_notes/domain/`** rather than `models/` because "models" collides with the AI-model concept (`data/models/*.yaml`, `model_registry`). `domain` is the standard Python/DDD term for this layer and removes ambiguity.

### Naming decision

- Folder name: **`agent_notes/domain/`**
- Rationale: "models" is overloaded (AI models are a first-class concept in this engine); `domain` unambiguously means "domain entities / value objects".
- Alternative considered: `agent_notes/core/` — rejected because it's vague and doesn't communicate that this is the *type layer* specifically.

### Current scattering (audit)

| Class | Current file | Responsibility |
|---|---|---|
| `CLIBackend` (frozen dataclass) | `cli_backend.py` | Domain — describes a CLI backend |
| `CLIRegistry` | `cli_backend.py` | Service — loads + indexes backends |
| `Model` (frozen dataclass) | `model_registry.py` | Domain — describes an AI model |
| `ModelRegistry` | `model_registry.py` | Service — loads + indexes models |
| `Role` (frozen dataclass) | `role_registry.py` | Domain — describes a role |
| `RoleRegistry` | `role_registry.py` | Service — loads + indexes roles |
| `State` | `state.py` | Domain — root state document |
| `ScopeState` | `state.py` | Domain — per-scope state |
| `BackendState` | `state.py` | Domain — per-CLI state inside a scope |
| `InstalledItem` | `state.py` | Domain — single installed item record |
| `Issue` | `doctor.py` | Domain — a doctor-detected problem |
| `FixAction` | `doctor.py` | Domain — a proposed fix |
| `ValidationError` | `validate.py` | Domain — a validation error |
| `ValidationWarning` | `validate.py` | Domain — a validation warning |
| `ComponentDiff` | `update_diff.py` | Domain — per-component diff record |
| `StateDiff` | `update_diff.py` | Domain — aggregate state diff |

**Observation:** 16 domain classes across 8 files, all mixed with their loaders/services. The registries (`CLIRegistry`, `ModelRegistry`, `RoleRegistry`) are *mostly* service layer — they do I/O (YAML loading) and caching (`lru_cache`). The frozen dataclasses are pure domain.

### Target layout

```
agent_notes/
  domain/
    __init__.py              # re-exports for convenience: from agent_notes.domain import CLIBackend, Model, Role, State
    cli_backend.py           # CLIBackend dataclass ONLY (no registry, no I/O)
    model.py                 # Model dataclass ONLY
    role.py                  # Role dataclass ONLY
    state.py                 # State, ScopeState, BackendState, InstalledItem
    diagnostics.py           # Issue, FixAction, ValidationError, ValidationWarning
    diff.py                  # ComponentDiff, StateDiff

  # Services (loaders, caches, factories) stay at the top level but rename for clarity:
  cli_registry.py            # was cli_backend.py — now loader + registry only
  model_registry.py          # unchanged name — now loader + registry only (dataclass moved out)
  role_registry.py           # unchanged name — now loader + registry only (dataclass moved out)
  state_store.py             # was state.py — now I/O only (load_state, save_state, state_file, get_scope, set_scope)
  # or: keep state.py name, just slim it to I/O functions
```

Service modules import the dataclasses from `agent_notes.domain.*`. Commands (`install.py`, `doctor.py`, etc.) continue to import whichever symbol they need — but semantically they now pull *types* from `domain/` and *operations* from service modules.

### Backward-compat strategy

To avoid breaking every caller and every test in a single pass:

- Keep the original module names (`cli_backend.py`, `state.py`, `model_registry.py`, `role_registry.py`) in place as **re-export shims** for one release:
  ```python
  # agent_notes/cli_backend.py (shim)
  from agent_notes.domain.cli_backend import CLIBackend
  from agent_notes.cli_registry import CLIRegistry, load_registry, default_registry
  __all__ = ["CLIBackend", "CLIRegistry", "load_registry", "default_registry"]
  ```
- All existing imports (`from agent_notes.cli_backend import CLIBackend`) keep working.
- New code and refactored code use the canonical path (`from agent_notes.domain import CLIBackend`).
- Deprecation note added to each shim; removal slated for a future major release.

### Acceptance criteria

1. `agent_notes/domain/` package exists with 6 modules: `cli_backend.py`, `model.py`, `role.py`, `state.py`, `diagnostics.py`, `diff.py`.
2. `agent_notes/domain/__init__.py` re-exports every domain class so `from agent_notes.domain import CLIBackend, Model, Role, State` works.
3. Every frozen dataclass / pure dataclass listed in the audit table above lives in `domain/`. No dataclass definitions remain in `cli_backend.py`, `model_registry.py`, `role_registry.py`, `state.py`, `doctor.py` (for `Issue`/`FixAction`), `validate.py` (for `ValidationError`/`ValidationWarning`), `update_diff.py` (for `ComponentDiff`/`StateDiff`).
4. Backward-compat shims exist at all previous import paths. Running `grep -rn "from agent_notes.cli_backend import CLIBackend" tests/` and similar still works without modification.
5. No new hardcoded CLI/model/role names introduced.
6. All 455+ tests still pass: `python3 -m pytest --tb=short -q` → `>= 455 passed`.
7. Circular-import check: `python3 -c "import agent_notes.domain; import agent_notes.cli_backend; import agent_notes.state; import agent_notes.doctor"` succeeds.
8. `docs/ENGINE_PLAN.md` status table gains a Phase 13 row marked `✅ DONE`.

### Step-by-step execution plan

**Step 1 — Create the package skeleton (15 min)**
- `mkdir agent_notes/domain`
- Create empty `__init__.py`
- Create each of the 6 submodule files, empty except for a docstring.

**Step 2 — Move dataclasses (60 min)**
For each source file, cut the `@dataclass` / `class X:` block and paste into the corresponding `domain/` file. Preserve imports the dataclass needs (`from pathlib import Path`, `from typing import Optional`, etc.). Do not bring service code with it.

Order (start with leaves, end with most-depended-on):
1. `Issue`, `FixAction` → `domain/diagnostics.py`
2. `ValidationError`, `ValidationWarning` → `domain/diagnostics.py` (same file; they're all diagnostics)
3. `ComponentDiff`, `StateDiff` → `domain/diff.py`
4. `Role` → `domain/role.py`
5. `Model` → `domain/model.py`
6. `CLIBackend` → `domain/cli_backend.py`
7. `InstalledItem`, `BackendState`, `ScopeState`, `State` → `domain/state.py`

**Step 3 — Populate `domain/__init__.py` (5 min)**
```python
"""Domain model layer — pure data classes, no I/O."""
from .cli_backend import CLIBackend
from .model import Model
from .role import Role
from .state import State, ScopeState, BackendState, InstalledItem
from .diagnostics import Issue, FixAction, ValidationError, ValidationWarning
from .diff import ComponentDiff, StateDiff

__all__ = [
    "CLIBackend", "Model", "Role",
    "State", "ScopeState", "BackendState", "InstalledItem",
    "Issue", "FixAction", "ValidationError", "ValidationWarning",
    "ComponentDiff", "StateDiff",
]
```

**Step 4 — Turn old files into shims (30 min)**
- `cli_backend.py`: remove the `CLIBackend` class, add `from agent_notes.domain.cli_backend import CLIBackend` at top, keep `CLIRegistry`/`load_registry`/`default_registry` in place (or move them to a new `cli_registry.py` and re-export here — call this optional sub-decision).
- Same pattern for `state.py`, `model_registry.py`, `role_registry.py`, `doctor.py`, `validate.py`, `update_diff.py` — each imports its former dataclass from `domain/` and keeps the rest of the file.

**Step 5 — Run tests (10 min)**
- `python3 -m pytest --tb=short -q`
- If any test fails because of a circular import, break the cycle by having the service module import from `domain/` (which has zero service deps).

**Step 6 — Add one canonical-path test (15 min)**
Create `tests/test_domain_package.py`:
```python
def test_domain_reexports():
    from agent_notes.domain import (
        CLIBackend, Model, Role, State, ScopeState,
        BackendState, InstalledItem, Issue, FixAction,
        ValidationError, ValidationWarning, ComponentDiff, StateDiff,
    )
    # All should be classes/dataclasses
    for cls in [CLIBackend, Model, Role, State, ScopeState, BackendState,
                InstalledItem, Issue, FixAction, ValidationError,
                ValidationWarning, ComponentDiff, StateDiff]:
        assert isinstance(cls, type)

def test_backward_compat_imports_still_work():
    from agent_notes.cli_backend import CLIBackend as CB1
    from agent_notes.domain import CLIBackend as CB2
    assert CB1 is CB2
    from agent_notes.state import State as S1
    from agent_notes.domain import State as S2
    assert S1 is S2
```

**Step 7 — Update `docs/ENGINE_PLAN.md` status table (5 min)**
Add Phase 13 row marked `✅ DONE`.

**Step 8 — Update architecture docs (20 min)**
- `README.md` architecture section: mention the `domain/` layer as the type contract.
- Optionally add a short `docs/ARCHITECTURE.md` describing the three layers: **domain** (types) → **services/registries** (loaders, I/O) → **commands** (`install`, `doctor`, `regenerate`, ...).

### Files modified

- **Created (6):** `agent_notes/domain/__init__.py`, `cli_backend.py`, `model.py`, `role.py`, `state.py`, `diagnostics.py`, `diff.py`
- **Modified as shims (8):** `agent_notes/cli_backend.py`, `state.py`, `model_registry.py`, `role_registry.py`, `doctor.py`, `validate.py`, `update_diff.py`, (and possibly `install_state.py` if it has dataclasses too — audit in Step 2)
- **Created test (1):** `tests/test_domain_package.py`
- **Docs:** `docs/ENGINE_PLAN.md` (status table + this section), optionally `README.md`, optionally new `docs/ARCHITECTURE.md`

### Anti-goals (explicitly out of scope for Phase 13)

- Do **not** merge registries into domain. `CLIRegistry`, `ModelRegistry`, `RoleRegistry` stay as services; they do I/O.
- Do **not** change any public behavior. This is a pure refactor.
- Do **not** rename classes. `CLIBackend` stays `CLIBackend`, not `Backend` or `CLI`.
- Do **not** touch YAML schemas. No data files change.
- Do **not** convert dataclasses to Pydantic or attrs. Stdlib dataclasses are fine.
- Do **not** add new abstractions (Protocols, ABCs). Phase 13 is move-only.

### Verification checklist

- [ ] `agent_notes/domain/` package exists with 6 + __init__ modules
- [ ] All 16 domain classes live under `domain/`
- [ ] Old import paths still work (shims in place)
- [ ] `python3 -m pytest --tb=short -q` → ≥ 455 passed
- [ ] `python3 -c "from agent_notes.domain import CLIBackend, Model, Role, State"` succeeds
- [ ] `grep -rn "^@dataclass\|^class " agent_notes/*.py | grep -v domain/` shows only service/command classes (no domain dataclasses at top level)
- [ ] No circular imports
- [ ] `docs/ENGINE_PLAN.md` Phase 13 row → ✅ DONE

---

## Phase 13 (expanded) — Bounded-context reorganization

The initial Phase 13 spec (above) moves only the **dataclasses**. But the codebase has more extractable subdomains than just types. When we ask *"what clusters of operations share vocabulary, invariants, and reasons to change?"*, we find **six clear bounded contexts** hiding inside today's flat `agent_notes/` directory.

This expanded Phase 13 replaces and supersedes the dataclass-only plan above.

### The six subdomains (bounded contexts)

#### 1. **Domain** — `agent_notes/domain/`
Pure types, zero I/O, zero dependencies on other agent_notes modules. The vocabulary of the system.

- `cli_backend.py` — `CLIBackend`
- `model.py` — `Model`
- `role.py` — `Role`
- `state.py` — `State`, `ScopeState`, `BackendState`, `InstalledItem`
- `diagnostics.py` — `Issue`, `FixAction`, `ValidationError`, `ValidationWarning`
- `diff.py` — `ComponentDiff`, `StateDiff`

#### 2. **Registries** — `agent_notes/registries/`
Load YAML descriptors from `data/` and hand back typed in-memory indexes. All three registries today duplicate the same pattern (YAML glob → validate → dataclass → dict-by-name + list-all + filter helpers). Consolidating them clarifies that pattern.

- `cli_registry.py` — `CLIRegistry`, `load_registry()`, `default_registry()`
- `model_registry.py` — `ModelRegistry`, `load_model_registry()`, `default_model_registry()`
- `role_registry.py` — `RoleRegistry`, `load_role_registry()`, `default_role_registry()`
- `agent_registry.py` — reads `data/agents/agents.yaml` (currently inlined into `build.py` as `load_agents_config`). **New extraction.**
- `skill_registry.py` — reads `data/skills/*/SKILL.md` (currently scattered across `install.py:find_skill_dirs`, `wizard.py:_get_skill_groups`, `list.py:list_skills`). **New extraction.**
- `rule_registry.py` — reads `data/rules/*.md` (currently scattered across `install.py:install_rules_*`, `list.py:list_rules`, `wizard.py:_count_rules`). **New extraction.**
- `_base.py` — shared YAML-loading + validation helpers used by all six registries.

**Why this matters:** today, "what roles exist?" is answered by `role_registry.load_role_registry().all()`, but "what skills exist?" requires walking the filesystem in three different places with slightly different logic. One registry module per concept makes adding a new concept (say, `commands/` or `hooks/`) a mechanical act.

#### 3. **Services** — `agent_notes/services/`
Stateful or side-effecting operations that the commands orchestrate. Each service owns one technical concern.

- `fs.py` — filesystem primitives: `place_file`, `place_dir_contents`, `remove_symlink`, `remove_all_symlinks_in_dir`, `remove_dir_if_empty`, `resolve_symlink`, `symlink_target_exists`, `files_differ`, `_files_identical`, `_handle_existing`. Currently spread across `install.py` (lines 16-95, 195-222) and `doctor.py` (lines 28-54).
- `state_store.py` — state.json I/O: `state_file()`, `load_state()`, `save_state()`, `get_scope()`, `set_scope()`, `clear_state()`. Currently mixed into `state.py` + `install_state.py`.
- `install_state_builder.py` — the pure function `build_install_state(...)` that constructs a `State` from inputs. No I/O. Could even live under `domain/` but keeping it here because it knows about filesystem paths.
- `rendering.py` — frontmatter + agent-file rendering. Today `build.py` is 295 lines mixing: loading agent config, loading frontmatter templates, rendering, writing dist output, copying globals. Split into: `rendering.py` (pure render) + a command (orchestrator).
- `installer.py` — **stays** (already a coherent registry-driven installer service). Move to `services/installer.py` for layout symmetry.
- `diagnostics.py` — the actual check functions that produce `Issue`/`FixAction` lists: `check_stale_files`, `check_broken_symlinks`, `check_shadowed_files`, `check_missing_files`, `check_content_drift`, `check_build_freshness`, `_check_role_models`. Today these are 500+ lines inside `doctor.py`. The `do_fix(...)` function (160 lines) that applies `FixAction`s also belongs here as `apply_fixes()`.
- `diff.py` — state diffing: `diff_states()`, `render_diff_report()`. Move from `update_diff.py`.
- `ui.py` — terminal rendering primitives: `Color`, `ok()`, `warn()`, `fail()`, `info()`, `issue()`, `linked()`, `removed()`, `skipped()`, plus `_read_key`, `_checkbox_select`, `_radio_select` and their fallback variants from `wizard.py`. The wizard TUI is 200+ lines of reusable terminal-interaction primitives that belong in their own module.

**Why this matters:** `doctor.py` is 770 lines today because it's **four things in a trenchcoat**: diagnostic checks + fix applier + summary printer + orchestrator. Once the three non-orchestrator concerns move to services, the `doctor` command becomes ~100 lines of pure orchestration.

#### 4. **Commands** — `agent_notes/commands/`
The user-facing verbs. One module per command. Each is a thin orchestrator: parse args → call registries → call services → print results. This is the layer the CLI parser dispatches to.

Current commands (14) and their homes today:

| Command | Today | Target |
|---|---|---|
| `install` | `install.py:install()` | `commands/install.py` |
| `uninstall` | `install.py:uninstall()` | `commands/uninstall.py` |
| `info` | `install.py:show_info()` | `commands/info.py` |
| `build` | `build.py:build()` | `commands/build.py` |
| `doctor` | `doctor.py:doctor()` | `commands/doctor.py` |
| `validate` | `validate.py:validate()` | `commands/validate.py` |
| `update` | `update.py:update()` | `commands/update.py` |
| `regenerate` | `regenerate.py:regenerate()` | `commands/regenerate.py` |
| `set role` | `set_role.py:set_role()` | `commands/set_role.py` |
| `list clis/models/roles/...` | `list.py:list_*()` | `commands/list.py` (one file, many verbs — they're all thin) |
| `wizard` (interactive install) | `wizard.py:interactive_install()` | `commands/wizard.py` |
| `memory *` | `memory.py` | `commands/memory.py` (or a `commands/memory/` subpackage if it grows) |

**Shape of a command module** (target):
```python
# commands/install.py
from agent_notes.registries import default_registry
from agent_notes.services import installer, state_store, fs
from agent_notes.domain import State

def install(local: bool = False, copy: bool = False, reconfigure: bool = False) -> None:
    """Install agents, skills, rules, globals per active state.json."""
    registry = default_registry()
    state = state_store.load_state() or state_store.default_state()
    # ... orchestrate, no filesystem primitives, no diagnostics, no printing details ...
    installer.install_all(registry, state, scope=..., copy_mode=copy)
```

Command files should stay **under 150 lines each**. If a command grows larger, the logic inside belongs in a service, not the command.

#### 5. **CLI parsing** — `agent_notes/cli.py`
Stays at top level, but slims down. Today it's 346 lines of argparse. Target: ≤ 200 lines. It imports from `commands/` and wires subcommand → handler. Nothing else.

#### 6. **Config / paths** — `agent_notes/config.py`
Stays at top level. Holds only:
- `PKG_DIR`, `DATA_DIR`, `DIST_DIR`, other package-root paths
- `dist_dir_for(backend)`, `global_template_path(backend)`, `global_output_path(backend)` helpers added in Round 1
- Any other registry-free constants (e.g., `BIN_HOME`, `AGENTS_HOME` if they survive)

**No** dataclasses (those moved to `domain/`), **no** terminal colors (those moved to `services/ui.py`), **no** skill-dir enumeration (that moved to `registries/skill_registry.py`).

### Target tree

```
agent_notes/
  __init__.py
  __main__.py
  cli.py                                   # argparse only, ≤200 lines
  config.py                                # paths + helpers, ≤80 lines

  domain/
    __init__.py                            # re-exports all types
    cli_backend.py
    model.py
    role.py
    state.py
    diagnostics.py
    diff.py

  registries/
    __init__.py                            # re-exports load_* + default_*
    _base.py                               # shared YAML-loading helpers
    cli_registry.py
    model_registry.py
    role_registry.py
    agent_registry.py
    skill_registry.py
    rule_registry.py

  services/
    __init__.py
    fs.py                                  # filesystem primitives
    state_store.py                         # state.json I/O
    install_state_builder.py               # build_install_state()
    rendering.py                           # frontmatter + agent rendering
    installer.py                           # moved from top-level
    diagnostics.py                         # doctor's check_* and apply_fixes
    diff.py                                # moved from update_diff.py
    ui.py                                  # Color, ok/warn/fail, TUI prompts

  commands/
    __init__.py
    install.py
    uninstall.py
    info.py
    build.py
    doctor.py
    validate.py
    update.py
    regenerate.py
    set_role.py
    list.py
    wizard.py
    memory.py

  data/                                    # unchanged
    cli/*.yaml
    models/*.yaml
    roles/*.yaml
    agents/*.md + agents.yaml
    skills/**/*
    rules/*.md
    scripts/*
    templates/frontmatter/*.py
```

### Top-level shim files for backward compat

Every file that moves leaves behind a **shim** at the old path. This lets tests and external callers keep working:

```python
# agent_notes/install.py (shim)
"""DEPRECATED: import from agent_notes.commands.install instead."""
from agent_notes.commands.install import install, uninstall
from agent_notes.commands.info import show_info
from agent_notes.services.fs import (
    place_file, place_dir_contents, remove_symlink,
    remove_all_symlinks_in_dir, remove_dir_if_empty,
)
# ... re-export everything that was here ...
```

Shims are deleted in a future major release; they are not forever.

### Impact analysis

| Metric | Today | After Phase 13 |
|---|---|---|
| Files > 500 lines | 3 (doctor 770, wizard 658, install 568) | 0 |
| Files > 300 lines | 6 | 0-1 |
| Avg file size | ~245 lines | ~120 lines |
| `doctor.py` | 770 lines (4 concerns) | ~100 lines (1 concern: orchestration) |
| `wizard.py` | 658 lines (TUI + flow + install) | ~150 lines (flow only); TUI in services/ui.py |
| `install.py` | 568 lines (fs + install + uninstall + info) | ~100 lines as commands/install.py |
| Test files touched by shims | 0 | 0 (shims preserve imports) |
| New test files | 1 (`tests/test_domain_package.py`) | +1 (`tests/test_package_layout.py` — asserts architecture invariants) |

### Architecture invariants (enforceable via test)

Add `tests/test_package_layout.py` with tests like:

```python
def test_domain_has_no_agent_notes_imports():
    """Domain is pure; it must not import from any other agent_notes package."""
    for py_file in Path("agent_notes/domain").rglob("*.py"):
        text = py_file.read_text()
        assert "from agent_notes." not in text or \
               "from agent_notes.domain" in text, \
               f"{py_file} imports non-domain modules"

def test_registries_only_import_domain_and_config():
    """Registries depend on domain (for types) and config (for paths). Nothing else."""
    allowed = {"agent_notes.domain", "agent_notes.config", "agent_notes.registries"}
    for py_file in Path("agent_notes/registries").rglob("*.py"):
        # parse imports, assert all agent_notes.* imports are in `allowed`

def test_commands_do_not_import_other_commands():
    """Commands are peers. One command must not call another directly."""
    for py_file in Path("agent_notes/commands").rglob("*.py"):
        text = py_file.read_text()
        # assert no `from agent_notes.commands.X import` except in __init__.py

def test_services_do_not_import_commands():
    """Services are called by commands, never the reverse."""
    for py_file in Path("agent_notes/services").rglob("*.py"):
        text = py_file.read_text()
        assert "from agent_notes.commands" not in text
```

These tests lock in the layering for the long term.

### Dependency rules (the layering contract)

```
commands/    →  services/, registries/, domain/, config
services/    →  registries/, domain/, config
registries/  →  domain/, config
domain/      →  (nothing from agent_notes)
config       →  (nothing from agent_notes)
cli.py       →  commands/
```

Arrows are "may import from". The inverse is forbidden and enforced by `test_package_layout.py`.

### Execution plan — split into 5 sub-phases

Phase 13 is large. Execute in 5 ordered sub-phases. Each sub-phase ends with `python3 -m pytest --tb=short -q` green.

#### Phase 13a — `domain/` (types only) — 1 hour — ✅ DONE
The original Phase 13 plan (dataclass move + shims). Low risk, unblocks everything.
**Completed 2026-04-23**: 16 dataclasses moved to `domain/` package with backward-compat shims. 458 tests passing (455 baseline + 3 new from `test_domain_package.py`).

#### Phase 13b — `registries/` (consolidate loaders) — 1.5 hours
- Move `cli_backend.py::CLIRegistry+loader` → `registries/cli_registry.py`
- Move `model_registry.py` → `registries/model_registry.py`
- Move `role_registry.py` → `registries/role_registry.py`
- Extract `agent_registry.py` from `build.py::load_agents_config`
- Extract `skill_registry.py` from `install.py:find_skill_dirs` + `wizard.py:_get_skill_groups` + `list.py:list_skills`
- Extract `rule_registry.py` from `install.py:install_rules_*` + `list.py:list_rules`
- Create `_base.py` with shared YAML-glob-load helper; refactor all 6 registries to use it.
- Shims at old paths.

**Completed 2026-04-23**: Created `agent_notes/registries/` package with 6 registries (CLI, model, role, agent, skill, rule). Added domain types: `AgentSpec`, `Skill`, `Rule`. Updated callers to use registries for discovery while maintaining backward compatibility. 490 tests passing (458 baseline + 32 new from registry tests).

#### Phase 13c — `services/` (extract technical concerns) — 2-3 hours
Highest-value sub-phase. Each extraction stands alone; can be done in parallel by multiple coder agents:
- **Parallel group 1:**
  - `services/fs.py` ← `install.py` lines 16-95, 195-222 + `doctor.py` 28-54
  - `services/ui.py` ← `config.py::Color + print helpers` + `wizard.py` TUI primitives 25-210
  - `services/state_store.py` ← `state.py` I/O functions
- **Parallel group 2 (depends on group 1):**
  - `services/diagnostics.py` ← `doctor.py` check_* + `_check_role_models` + `do_fix`
  - `services/rendering.py` ← `build.py` frontmatter loader + render logic
  - `services/diff.py` ← rename of `update_diff.py`
- **Sequential:** move `installer.py` → `services/installer.py` (last, depends on fs + state_store)

#### Phase 13d — `commands/` (thin orchestrators) — 1.5 hours
- Create `commands/` package
- Move each top-level command file into `commands/`, renaming the inner function if needed
- The file that shrinks the most: `doctor.py` 770 → ~100 lines (rest lives in services/diagnostics.py)
- `install.py` 568 → `commands/install.py` ~80 + `commands/uninstall.py` ~40 + `commands/info.py` ~30
- `wizard.py` 658 → `commands/wizard.py` ~150 (rest in services/ui.py)
- Update `cli.py` imports to point at `commands/*`
- Top-level shims

#### Phase 13e — Architecture tests + docs — 30 min
- Add `tests/test_package_layout.py` with the 4 invariant tests above
- Add `tests/test_domain_package.py` (already specified in original Phase 13)
- Update `README.md` architecture section
- Write `docs/ARCHITECTURE.md` describing the 4-layer model (domain → registries → services → commands)
- Status table: Phase 13 → ✅ DONE

### Why this is worth doing

1. **Discoverability.** "Where is the code that detects stale symlinks?" Today: grep through a 770-line doctor.py. After: `services/diagnostics.py::check_stale_files`.
2. **Testability.** Services take typed inputs and return typed outputs. No more mocking a filesystem to test a check function that's buried inside a 770-line file with print statements.
3. **Extensibility.** Adding a new command (say, `agent-notes export`) is a new file in `commands/`. Adding a new registry-backed concept (say, `hooks/`) is a new file in `registries/` + `data/hooks/`. The four-layer contract tells contributors exactly where new code goes.
4. **Forces the Round 1 invariant.** With registries concentrated in one package, it's mechanically obvious when a command does `if backend.name == "claude"` — and equally obvious where to push the branch into a data-driven feature flag on `CLIBackend`.
5. **Unblocks Round 2 decomposition.** Splitting `doctor.py` / `wizard.py` / `install.py` is Round 2's goal. Phase 13c-d **is** that decomposition, done correctly (into services by concern) rather than mechanically (by function count).

### Anti-goals (out of scope for Phase 13)

- Do **not** introduce Protocols, ABCs, or dependency injection frameworks. Plain functions and dataclasses.
- Do **not** rewrite business logic. Move, shim, retest — no behavior change.
- Do **not** change YAML schemas or data file layout.
- Do **not** change any command's CLI surface (flags, args, output format).
- Do **not** add new features. (Phase 14+ is for features.)

### Acceptance criteria (expanded Phase 13)

- [ ] Four packages exist: `domain/`, `registries/`, `services/`, `commands/`
- [ ] All listed modules moved to their target locations
- [ ] Top-level shims at every old path
- [ ] `python3 -m pytest --tb=short -q` → ≥ 456 passed (455 baseline + layout tests)
- [ ] `tests/test_package_layout.py` and `tests/test_domain_package.py` both pass
- [ ] No file in `agent_notes/` exceeds 300 lines (config.py and cli.py included)
- [ ] No circular imports (verified by `python3 -c "import agent_notes"` clean)
- [ ] `docs/ARCHITECTURE.md` exists and describes the 4-layer model
- [ ] `README.md` architecture section updated
- [ ] `docs/ENGINE_PLAN.md` Phase 13 row → ✅ DONE
- [ ] Zero public-API breakage — existing tests pass with no modifications

### Suggested execution order summary

```
Phase 13a (domain/)        ─┐
Phase 13b (registries/)    ─┤→ Phase 13c (services/)  ──→  Phase 13d (commands/)  ──→  Phase 13e (tests+docs)
                            │        ↑
                            │        │ group 1 (parallel: fs, ui, state_store)
                            │        │ group 2 (parallel: diagnostics, rendering, diff)
                            │        │ last:    installer
```

Total estimated time: 6-8 hours. Lead-dispatched, the parallelizable bits in 13c can collapse to 2-3 hours wall-clock.
