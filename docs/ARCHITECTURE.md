# Architecture — AgentNotes Engine v1.1.0

## Overview

AgentNotes is a **hub** that registers and installs AI agent configurations across multiple CLIs (Claude Code, OpenCode, GitHub Copilot, etc.). At its core, the engine reads declarative YAML files from three registries — **CLIs, Models, and Roles** — and orchestrates the build-and-install pipeline. The engine's promise: **adding a new CLI, model, role, agent, skill, or rule requires zero Python changes** — only drop a YAML file in the right data directory.

This document describes the 4-layer architecture that enforces this promise.

---

## The 4-Layer Architecture

AgentNotes is organized into four strictly layered packages. Dependencies flow **downward only** — lower layers never import from upper layers.

```
┌─────────────────────────────────────────────────────┐
│ Layer 4: commands/                                  │ CLI orchestrators (13 modules)
│ • Thin command modules (≤600 lines, target ≤300)   │ May import everything below
│ • Routes user input to services                     │
└────────────────┬────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────┐
│ Layer 3: services/                                  │ Technical concerns (9 modules)
│ • fs, ui, state_store, installer, rendering, etc.  │ May import domain + registries + config
│ • Reusable business logic across commands          │ Forbidden: commands/, top-level modules
└────────────────┬────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────┐
│ Layer 2: registries/                                │ YAML loaders (7 registries)
│ • cli_registry, model_registry, role_registry, etc. │ May import domain + config
│ • Hydrate domain types from agent_notes/data/      │ Forbidden: services/, commands/
└────────────────┬────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────┐
│ Layer 1: domain/                                    │ Pure dataclasses/types (10 modules)
│ • AgentSpec, CLIBackend, Model, Role, State, etc.  │ Only sibling domain.* imports allowed
│ • Zero imports from registries/services/commands   │ No I/O, no side effects
└─────────────────────────────────────────────────────┘
```

**Enforcement:** `tests/test_package_layout.py` contains 6 tests that validate this hierarchy at test time:

- `test_domain_has_no_internal_imports()` — domain must not import from registries/services/commands
- `test_registries_dont_import_services_or_commands()` — registries must not import from services/commands
- `test_services_dont_import_commands()` — services must not import from commands
- `test_commands_are_thin_orchestrators()` — commands ≤600 lines
- `test_top_level_shims_are_short()` — shims ≤150 lines
- `test_no_circular_imports_at_module_load()` — config loads cleanly without circular imports

---

## Layer Responsibilities

### Layer 1: Domain (`agent_notes/domain/`)

**What it contains:**
- Dataclasses: `AgentSpec`, `CLIBackend`, `Model`, `Role`, `State`, `InstallState`, `Skill`, `Rule`, `Diff`, `Diagnostics`
- Types that represent the problem domain, not the solution

**Rules:**
- Pure dataclasses with no I/O, no mutable state, no external dependencies
- May only import sibling `domain.*` modules
- Frozen dataclasses where appropriate to enforce immutability

**Examples:**
```
agent_notes/domain/
├── agent.py          # AgentSpec
├── cli_backend.py    # CLIBackend (carries metadata from CLI descriptors)
├── model.py          # Model
├── role.py           # Role
├── state.py          # State, InstallState (schema for state.json)
├── skill.py          # Skill
├── rule.py           # Rule
├── diff.py           # Diff (output type)
├── diagnostics.py    # Diagnostics (output type)
└── __init__.py       # Public exports
```

---

### Layer 2: Registries (`agent_notes/registries/`)

**What it contains:**
- YAML loaders that hydrate domain types from `agent_notes/data/`
- Registry classes that provide lookup by ID

**Rules:**
- May import `domain` + `config`
- Forbidden: `services/`, `commands/`, top-level command modules (`install`, `doctor`, etc.)
- Each registry has a loader function (e.g., `load_cli_registry()`, `default_model_registry()`)

**Examples:**
```
agent_notes/registries/
├── cli_registry.py          # CLIBackend loader from data/cli/*.yaml
├── model_registry.py        # Model loader from data/models/*.yaml
├── role_registry.py         # Role loader from data/roles/*.yaml
├── agent_registry.py        # AgentSpec loader from data/agents/agents.yaml
├── skill_registry.py        # Skill loader from data/skills/*/SKILL.md
├── rule_registry.py         # Rule loader from data/rules/*/RULE.md
├── _base.py                 # Base loader utilities
└── __init__.py              # Public loader exports
```

**Usage example:**
```python
from agent_notes.registries import load_cli_registry

registry = load_cli_registry()
claude_backend = registry.get("claude")
print(claude_backend.label)  # "Claude Code"
```

---

### Layer 3: Services (`agent_notes/services/`)

**What it contains:**
- Reusable business logic: filesystem operations, UI rendering, state persistence, installation engine, diagnostics, validation
- Functions that do work for the engine (but don't know about CLI commands)

**Rules:**
- May import `domain` + `registries` + `config` + sibling `services.*`
- Forbidden: `commands/`, top-level command modules (`install`, `doctor`, etc.)
- Stateless or immutable state (services don't hold mutable singletons)

**Examples:**
```
agent_notes/services/
├── fs.py                      # place_file, remove_symlink, etc. (I/O)
├── ui.py                      # Color, ok(), warn(), fail(), etc. (console output)
├── state_store.py             # load_state, save_state (JSON I/O)
├── installer.py               # install_all, uninstall_all (orchestration)
├── install_state_builder.py   # build_install_state (prepare state for install)
├── rendering.py               # render_agent_files, build_artifacts (code generation)
├── diff.py                    # compute_diff (state comparison)
├── diagnostics.py             # check_health, identify_issues (validation)
├── validation.py              # validate_yaml (linting)
└── __init__.py                # Public service exports
```

**Usage example:**
```python
from agent_notes.services import installer
from agent_notes.registries import load_cli_registry

registry = load_cli_registry()
installer.install_all(backends=registry.all(), scope="global")
```

---

### Layer 4: Commands (`agent_notes/commands/`)

**What it contains:**
- Thin CLI command implementations that route user input to services
- Each command module is a single verb (install, doctor, list, etc.)
- Orchestrators, not implementations

**Rules:**
- May import everything below (domain, registries, services, config)
- Maximum 600 lines per file (target ≤300 for most)
- Name `foo.py` for the `agent-notes foo` command

**Examples:**
```
agent_notes/commands/
├── install.py         # install command — calls services.installer.install_all()
├── doctor.py          # doctor command — calls services.diagnostics.check_health()
├── list.py            # list command — queries registries
├── wizard.py          # install wizard — calls services.install_state_builder
├── update.py          # update command — calls services.diff, services.installer
├── build.py           # build command — calls services.rendering
├── validate.py        # validate command — calls services.validation
├── memory.py          # memory command — calls services for state manipulation
├── regenerate.py      # regenerate command — rebuilds agents from state
├── set_role.py        # set role command — updates state, calls services
├── uninstall.py       # uninstall command
├── info.py            # info command
├── _install_helpers.py # Shared helpers for install/uninstall/verify
└── __init__.py         # Public command exports
```

**Usage example (inside a command module):**
```python
# agent_notes/commands/install.py
def install(local: bool = False, copy: bool = False) -> None:
    from ..services import installer
    from ..registries import load_cli_registry
    
    registry = load_cli_registry()
    scope = "local" if local else "global"
    installer.install_all(backends=registry.all(), scope=scope)
```

---

## Top-Level Shims

**What are they?**

`agent_notes/install.py`, `agent_notes/doctor.py`, `agent_notes/wizard.py`, etc. are thin re-export files that maintain backward compatibility with old test code that patches `agent_notes.install.install`.

**Why they exist:**

Before Phase 13, commands lived at the top level:
```python
# Old code (Phase 12):
from agent_notes.install import install

# New code (Phase 13+):
from agent_notes.commands.install import install
```

Tests that patch the old path still need to work:
```python
# Old test code (still works because of shims):
@mock.patch("agent_notes.install.install")
def test_install(mock_install):
    pass
```

**How they stay thin:**

Each shim ≤150 lines. They only re-export:
- Command functions (`from agent_notes.commands.install import install`)
- Helper functions used by tests
- Config constants that tests patch

**Example:** `agent_notes/install.py`
```python
"""DEPRECATED shim. Import from agent_notes.commands.install instead."""

from agent_notes.commands.install import install
from agent_notes.commands.uninstall import uninstall
from agent_notes.commands.info import show_info
from agent_notes.services.fs import place_file, remove_symlink
from agent_notes.config import DIST_DIR, BIN_HOME
```

**The rule:** services never import from top-level shims. Only the shims import from commands/services, never the reverse.

---

## Circular-Import Safety: `config.py`

`agent_notes/config.py` is imported early by many modules, but it needs paths controlled by `cli_backend.py` (which lives in the domain layer). To avoid circular imports, `config.py` uses **named fallback helpers**:

```python
# agent_notes/config.py
def _fb_home() -> Path:
    """Fallback: compute CLAUDE_HOME if cli_backend not yet available."""
    return Path.home() / ".claude"

def _fb_dist() -> Path:
    """Fallback: compute DIST_CLAUDE_DIR if cli_backend not yet available."""
    return PKG_DIR / "dist" / "claude"

# Use lazy evaluation with fallback
CLAUDE_HOME = _lazy_backend_attr("CLAUDE_HOME", _fb_home)
```

When a module first imports `config`, these fallback helpers ensure `CLAUDE_HOME` is always truthy, even if `cli_backend` hasn't been imported yet. Tests can patch both the config constants and the shim module constants, and either will work.

---

## Runtime Flow: `agent-notes install`

Here's a 10-line walk-through of how a single command executes:

```
1. bin/agent-notes (wrapper)
   ↓ executes: python3 -m agent_notes
   ↓
2. agent_notes/__main__.py → agent_notes.cli.main()
   ↓
3. cli.py → argparse dispatches to shim module
   ↓
4. agent_notes/install.py (shim) → agent_notes.commands.install.install()
   ↓
5. commands/install.py → load registries, prepare state
   ↓
6. commands/install.py → services.installer.install_all()
   ↓
7. services/installer.py → for each backend, call services.fs.place_file()
   ↓
8. services/fs.py → symlink or copy files to disk
   ↓
9. services/state_store.py → save state.json
   ↓
10. Return to user with summary
```

**Key insight:** Each layer only calls into the layer below. Commands orchestrate services, services use domain types and registries, registries load from YAML, all the way down.

---

## Where New Code Goes: Decision Tree

**Adding a new CLI verb (e.g., `agent-notes foo`)?**
→ Create `agent_notes/commands/foo.py` (≤600 lines)

**Adding a new YAML-loaded concept (e.g., `data/platforms/`)?**
→ Create `agent_notes/registries/platform_registry.py` + `agent_notes/domain/platform.py`

**Adding filesystem, UI, or state logic?**
→ Create a new service in `agent_notes/services/` or add to an existing one

**Adding a dataclass for a domain concept?**
→ Create `agent_notes/domain/my_type.py`

**Adding a new CLI, model, role, agent, skill, or rule?**
→ Drop a YAML file in `agent_notes/data/{cli,models,roles,agents,skills,rules}/` — zero Python changes

---

## Test Layout

### `tests/test_package_layout.py`

6 tests that enforce the 4-layer architecture:

```python
def test_domain_has_no_internal_imports():
    """Domain imports only from domain.*"""
    
def test_registries_dont_import_services_or_commands():
    """Registries don't import services/commands"""
    
def test_services_dont_import_commands():
    """Services don't import commands"""
    
def test_commands_are_thin_orchestrators():
    """Commands ≤600 lines"""
    
def test_top_level_shims_are_short():
    """Shims ≤150 lines"""
    
def test_no_circular_imports_at_module_load():
    """Package loads without circular imports"""
```

### Other tests

- Per-module tests in `tests/test_*.py` (not constrained by layer rules)
- Fixture `mock_paths` in `tests/conftest.py` patches `agent_notes.config` constants and all shim module constants, so tests can mock paths via either module

---

## Anti-Patterns to Avoid

### ❌ Don't import from top-level shims inside services

**Bad:**
```python
# agent_notes/services/my_service.py
from agent_notes import install  # WRONG

def my_service():
    return install.CLAUDE_HOME
```

**Good:**
```python
# agent_notes/services/my_service.py
from agent_notes import config

def my_service():
    return config.CLAUDE_HOME
```

### ❌ Don't add `if backend.name == "claude"` branches

The whole point of registries is to avoid hardcoding backend names. If you need backend-specific logic, put it in the backend descriptor (YAML) or create a new registry type.

**Bad:**
```python
if backend.name == "claude":
    install_claude_specific_thing()
```

**Good:**
```yaml
# data/cli/claude.yaml
features:
  some_custom_flag: true
```

Then in the service, read the flag and dispatch:
```python
if backend.features.get("some_custom_flag"):
    do_thing()
```

### ❌ Don't hardcode model IDs

Model IDs should come from state.json or be declared in YAML. Never `id = "claude-opus-4-7"` in Python.

**Bad:**
```python
# agent_notes/services/rendering.py
model_id = "claude-opus-4-7"  # WRONG
```

**Good:**
```python
# Load from state or registry
model = model_registry.get(role_model_id)
```

---

## Data-First Extensibility

The engine's promise is enforced by putting all extensible data in `agent_notes/data/` as YAML files. Adding a new X does not require touching Python.

| To add… | Create… | Zero Python changes? |
|---------|---------|----------------------|
| CLI (e.g., Cursor) | `data/cli/cursor.yaml` + optional `data/templates/frontmatter/cursor.py` | ✅ Yes |
| Model (e.g., Kimi) | `data/models/kimi-k2.yaml` | ✅ Yes |
| Role (e.g., Specialist) | `data/roles/specialist.yaml` | ✅ Yes |
| Agent | Add to `data/agents/agents.yaml` + `data/agents/my-agent.md` | ✅ Yes |
| Skill | New directory `data/skills/my-skill/` with `SKILL.md` | ✅ Yes |
| Rule | New directory `data/rules/my-rule/` with `RULE.md` | ✅ Yes |

For step-by-step guides, see:
- `docs/ADD_CLI.md`
- `docs/ADD_MODEL.md`
- `docs/ADD_ROLE.md`

---

## References

- **Phases 1–13:** See `docs/ENGINE_PLAN.md` for history, rationale, and phase-by-phase breakdown
- **CLI capabilities:** `docs/CLI_CAPABILITIES.md` documents every Claude Code + OpenCode feature the engine must support
- **Test suite:** 502 tests; 6 in `tests/test_package_layout.py` enforce architecture
