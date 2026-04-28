# Release Plan — 1.3.0: Role-Model Config & Plugin Agent Routing

**Branch:** `release/1.3.0`
**Goal:** Give users control over which model each agent uses. Pre-build the plugin
with model assignments baked in. Add project-level overrides and agent prompt patches.
**Current version:** 1.2.0
**Target version:** 1.3.0

---

## Background: What already exists

The model resolution pipeline is complete (built in v1.1.0):

```
agents.yaml          data/roles/*.yaml     data/models/*.yaml
-----------          -----------------     ------------------
agent.role           role.typical_class    model.class
  debugger: reasoner   reasoner: opus    →   opus models
  coder: worker        worker: sonnet    →   sonnet models
  explorer: scout      scout: haiku      →   haiku models
```

`rendering.py` resolves: `agent.role → role.typical_class → model.class → model.alias` and injects `model:` into Claude Code agent frontmatter at build time.

`state.clis[backend].role_models` (step 1 resolution) allows a role-level model override — but this is set only via an install wizard step and stored in the install state file.

**What is missing:**

1. Users cannot change which role an individual agent belongs to without editing `agents.yaml`
2. The plugin ships with no agents — model routing is not available via plugin install at all
3. No project-level config to override global assignments
4. No way to patch agent prompts without forking the repo
5. No doctor check if built plugin is stale relative to config

---

## Repo structure additions (1.3.0)

```
agent_notes/
  data/
    roles/                  # existing: orchestrator, worker, scout, reasoner
    models/                 # existing: claude-opus-4-7, claude-sonnet-4, ...
    agents/
      agents.yaml           # existing: role: per agent (source of truth)
      *.md                  # existing: prompts

~/.config/agent-notes/      # NEW: user config location
  config.yaml               # role overrides + model overrides + patches

.claude/agent-notes.yaml    # NEW: project-level config (per-project overrides)

.claude-plugin/
  agents/                   # NEW: pre-built agent .md files with model: injected
    lead.md
    coder.md
    ...
  skills/                   # existing: process discipline skills
  plugin.json               # existing: manifest
```

---

## Tracks

| Track | Description | Priority |
|---|---|---|
| A | Pre-built plugin agents | Must |
| B | User config: agent→role overrides | Must |
| C | User config: role→model overrides | Should |
| D | Project-level overrides | Should |
| E | Agent prompt patches | Could |
| F | Doctor staleness check | Should |
| G | Wizard role assignment UI | Could |

Tracks A and B can proceed in parallel. C depends on B (shares config format).
D depends on B. E depends on B (shares config file). F is independent.

---

## Track A — Pre-built Plugin Agents

### Problem

The plugin currently delivers process skills and a SessionStart hook, but no agents.
The model routing system (role → model → `model:` in frontmatter) only activates
when the user runs `agent-notes install` (the Python CLI). Plugin-only users get no agents.

### What to build

Run `agent-notes build` once, then commit the resulting agent files into `.claude-plugin/agents/`.
The plugin then delivers 18 pre-built agents with `model:` already in their frontmatter.

### File structure

```
.claude-plugin/
  agents/           # committed pre-built output
    coder.md        # model: claude-sonnet-4-6 injected
    reviewer.md     # model: claude-sonnet-4-6
    explorer.md     # model: claude-haiku-4-5-20251001
    architect.md    # model: claude-opus-4-7
    debugger.md     # model: claude-opus-4-7
    ...             # all 18 agents (except lead — primary mode only)
```

### How to maintain

After any change to `agents.yaml`, `data/roles/*.yaml`, `data/models/*.yaml`,
or any agent prompt `.md`:

```bash
agent-notes build
cp -r dist/claude/agents/* .claude-plugin/agents/
git add .claude-plugin/agents/
```

This is a manual step performed by maintainers when releasing a new version.
The `Makefile` or a `scripts/build-plugin.sh` should automate it.

### plugin.json update

Add `agents/` path so Claude Code installs agent files:
```json
{
  "agents": ".claude-plugin/agents"
}
```
(Pending verification of exact schema — check Claude Code plugin docs.)

### Acceptance criteria

- `.claude-plugin/agents/*.md` all contain a `model:` field in frontmatter
- A Claude Code user who installs only the plugin gets 18 agents with model routing
- `lead.md` is excluded (it uses `claude_exclude: true` in `agents.yaml`)

---

## Track B — User Config: Agent→Role Overrides

### Problem

`agent.role` is hardcoded in `agents.yaml`. If a user wants `debugger` to use Sonnet
(the worker model) instead of Opus (the reasoner model), they have no way to express this
without editing the source file.

### Config file

Location: `~/.config/agent-notes/config.yaml`
(Falls back to `~/.agent-notes.yaml` if XDG not supported.)

Schema:

```yaml
# ~/.config/agent-notes/config.yaml

# Override which role an agent belongs to
# Valid roles: orchestrator, reasoner, worker, scout
agent_roles:
  debugger: worker     # use Sonnet instead of default Opus
  devil: worker        # cheaper for adversarial review
  architect: worker    # trust your Sonnet for architecture too

# Override which model a role uses (per provider)
# Overrides the typical_class lookup in data/roles/*.yaml
role_models:
  claude-code:
    reasoner: claude-sonnet-4-6   # downgrade reasoners to Sonnet
  opencode:
    scout: ollama/llama3.3        # local model for fast search

# Append custom context to specific agent prompts
patches:
  coder: |
    This project uses Rails 7.2 with Hotwire. Prefer Stimulus over vanilla JS.
    Always check for N+1 queries when touching ActiveRecord.
```

### Build pipeline integration

In `rendering.py → generate_agent_files()`, before resolving model:

1. Load user config from `~/.config/agent-notes/config.yaml`
2. For each agent, check if `config.agent_roles[agent_name]` overrides the role
3. Use overridden role for model resolution instead of `agents.yaml` value
4. After generating prompt content, append `config.patches[agent_name]` if present

### New service: `agent_notes/services/user_config.py`

```python
"""Load and merge user config for agent role/model overrides."""
from __future__ import annotations
from pathlib import Path
from typing import Optional
import yaml


def config_path() -> Path:
    xdg = Path.home() / ".config" / "agent-notes" / "config.yaml"
    legacy = Path.home() / ".agent-notes.yaml"
    if xdg.exists():
        return xdg
    if legacy.exists():
        return legacy
    return xdg  # canonical location for writes


def load_user_config(path: Optional[Path] = None) -> dict:
    """Return user config dict. Returns empty dict if config doesn't exist."""
    p = path or config_path()
    if not p.exists():
        return {}
    return yaml.safe_load(p.read_text()) or {}


def resolve_agent_role(agent_name: str, default_role: str, config: dict) -> str:
    """Return the effective role, applying user override if present."""
    return config.get("agent_roles", {}).get(agent_name, default_role)


def resolve_role_model(role: str, backend_name: str, config: dict) -> Optional[str]:
    """Return user-specified model ID for a role+backend, or None."""
    return config.get("role_models", {}).get(backend_name, {}).get(role)


def get_patch(agent_name: str, config: dict) -> Optional[str]:
    """Return patch text to append to agent prompt, or None."""
    return config.get("patches", {}).get(agent_name)
```

### Integration point in rendering.py

```python
# Load user config once per build
from ..services.user_config import load_user_config, resolve_agent_role, resolve_role_model, get_patch
user_config = load_user_config()

# Per agent: override role
agent_role = resolve_agent_role(agent_name, agent_config.get('role'), user_config)

# Per agent: override model (inserted before step 2 in current resolution chain)
user_model = resolve_role_model(agent_role, backend.name, user_config)
if user_model:
    model_str = user_model

# After generating content: apply patch
patch = get_patch(agent_name, user_config)
if patch:
    content = content + "\n\n" + patch.strip()
```

### Acceptance criteria

- `~/.config/agent-notes/config.yaml` with `agent_roles: {debugger: worker}` causes
  `debugger.md` to get `model: claude-sonnet-4-6` instead of `claude-opus-4-7` after build
- `patches: {coder: "..."}` appends text to `coder.md` prompt
- Missing config file → no error, defaults apply
- Corrupt config file → clear error message with config path
- Tests: `test_user_config.py` — load, override, patch, missing-file, corrupt-file cases

---

## Track C — Project-Level Overrides

### Config file

`.claude/agent-notes.yaml` in any project directory. Same schema as user config.
Project config is merged on top of user config (project wins).

```yaml
# .claude/agent-notes.yaml
patches:
  coder: |
    This is a fintech project. Never store PII in logs. Always use parameterized queries.
agent_roles:
  security-auditor: reasoner   # upgrade for sensitive codebase
```

### Integration

`generate_agent_files()` accepts an optional `project_config_path` argument.
`build()` passes the local `.claude/agent-notes.yaml` if it exists.

### Acceptance criteria

- Project config merges on top of user config
- Project patch + user patch both apply (concatenated, project first)
- No `.claude/agent-notes.yaml` → user config only, no error

---

## Track D — Doctor Staleness Check

### What to check

After `agent-notes build`, the dist files reflect the current config. If:
- `agents.yaml` is newer than `dist/claude/agents/*.md`
- Any `data/roles/*.yaml` is newer than dist
- Any `data/models/*.yaml` is newer than dist
- User config is newer than dist

→ Doctor warns: "Source files changed since last build. Run `agent-notes build`."

Also check:
- `.claude-plugin/agents/*.md` are older than `dist/claude/agents/*.md` → warn to rebuild plugin

### Implementation

Extend `check_build_freshness()` in `agent_notes/services/diagnostics.py`.

---

## Track E — Wizard Role Assignment UI

### What to build

An interactive step in `agent-notes install` (or a standalone `agent-notes configure`)
that shows agents grouped by current role and lets users reassign.

```
Role assignments (current):
  orchestrator: lead
  reasoner:     architect, debugger
  worker:       coder, reviewer, security-auditor, ...
  scout:        explorer, analyst, api-reviewer, tech-writer

Move an agent to a different role? (leave empty to keep defaults)
  Agent name: debugger
  New role [reasoner]: worker
  Saved to ~/.config/agent-notes/config.yaml
```

### Acceptance criteria

- `agent-notes configure` opens role assignment wizard
- Changes saved to `~/.config/agent-notes/config.yaml`
- Build auto-runs after configure to apply changes

---

## Execution order

```
Parallel group A:
  - Track A (pre-built plugin agents — run build, commit output)
  - Track B (user_config.py service + rendering.py integration)

After group A:
  - Track C (project-level overrides — extends Track B's config loading)
  - Track D (doctor staleness — independent of B/C but useful after A)

After B and C:
  - Track E (wizard UI — requires config schema to be stable)

Final:
  - Run full test suite
  - Rebuild plugin agents with 1.3.0 model IDs
  - Bump VERSION to 1.3.0
```

---

## Files changed summary

| File | Change type | Track |
|---|---|---|
| `.claude-plugin/agents/*.md` | Create (18 files, pre-built) | A |
| `.claude-plugin/plugin.json` | Update (add agents path) | A |
| `scripts/build-plugin.sh` | Create | A |
| `agent_notes/services/user_config.py` | Create | B |
| `agent_notes/services/rendering.py` | Extend (load user config, apply overrides) | B/C |
| `agent_notes/commands/build.py` | Pass project_config_path to rendering | C |
| `agent_notes/services/diagnostics.py` | Extend build freshness check | D |
| `agent_notes/commands/wizard.py` | Add configure step | E |
| `agent_notes/VERSION` | Bump to 1.3.0 | Final |
| `tests/test_user_config.py` | Create | B |
| `tests/test_role_overrides.py` | Create | B/C |
| `tests/test_plugin_agents.py` | Create | A |
