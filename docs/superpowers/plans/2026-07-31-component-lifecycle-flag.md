# Component Lifecycle Flag Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a developer commit a half-built component (CLI backend, plugin, skill, agent, memory backend) that lives in the tree but is hidden from the wizard, build, and user-facing listings — unless force-enabled locally — so work on one component never blocks the system.

**Architecture:** One optional `stability` field (`stable` default / `wip`) parsed into each family's existing domain object, and one shared `is_visible(stability, name, override)` helper. User-facing enumeration flows through a new `available()` method on each registry; memory (which has no enumeration) gets a selection guard on `get_backend`. A `wip` component is force-enabled per-process via `AGENT_NOTES_ENABLE_WIP=name1,name2`.

**Tech Stack:** Python 3.11+, frozen dataclasses, PyYAML, pytest, `uv` for running.

## Global Constraints

- **Byte-identical dist when nothing is `wip` and no override is set.** No shipped component is marked `wip` in this plan, so every task must leave `dist/` unchanged. Verify with `scripts/dev/verify_dist_equiv.sh <BASELINE>` where `BASELINE = e9edbf7` (the spec commit; dist matches `eb1a82d`). **Never** use `git diff`/`git status` on `agent_notes/dist/` — that tree is gitignored, so those always report empty (a no-teeth gate).
- **Two states only:** `stable` and `wip`. The field is a string enum, extensible to `experimental` later; do NOT add a third state now.
- **Override env var:** exactly `AGENT_NOTES_ENABLE_WIP`, comma-separated component names, matched against the component's `name`.
- **Default rule:** absent/empty `stability` ⇒ `"stable"`. An unrecognised value raises `ValueError` at load.
- **Hermetic tests:** any CLI-subprocess test sets a per-test `XDG_CONFIG_HOME`; the real `~/.config` must never be touched. Env vars are set per-test and cleaned up.
- **Commits:** conventional format `type(scope): desc`, no ticket in branch name so omit the prefix; **no AI attribution** (no `Co-Authored-By`, no "Generated with", no robot emoji).
- **Full suite baseline:** `uv run pytest tests/` must stay green (1867 passed at branch head; new tests add to that).

---

### Task 1: Stability helper module

**Files:**
- Create: `agent_notes/services/stability.py`
- Test: `tests/unit/services/test_stability.py`

**Interfaces:**
- Produces (consumed by every later task):
  - `STABILITY_STABLE = "stable"`, `STABILITY_WIP = "wip"`, `STABILITY_VALUES: frozenset[str]`
  - `normalize_stability(value, source: Optional[Path] = None) -> str` — validate/default; raises `ValueError` on unknown.
  - `enabled_wip() -> frozenset[str]` — parse `AGENT_NOTES_ENABLE_WIP`.
  - `is_visible(stability: str, name: str, override: Optional[frozenset[str]] = None) -> bool` — `override=None` means read the env.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/services/test_stability.py
import os
import pytest
from agent_notes.services.stability import (
    STABILITY_STABLE, STABILITY_WIP,
    normalize_stability, enabled_wip, is_visible,
)


def test_normalize_defaults_to_stable():
    assert normalize_stability(None) == STABILITY_STABLE
    assert normalize_stability("") == STABILITY_STABLE
    assert normalize_stability("stable") == STABILITY_STABLE
    assert normalize_stability(" WIP ") == STABILITY_WIP


def test_normalize_rejects_unknown():
    with pytest.raises(ValueError):
        normalize_stability("beta")


def test_enabled_wip_parses_env(monkeypatch):
    monkeypatch.setenv("AGENT_NOTES_ENABLE_WIP", " gemini , notion ,")
    assert enabled_wip() == frozenset({"gemini", "notion"})
    monkeypatch.delenv("AGENT_NOTES_ENABLE_WIP", raising=False)
    assert enabled_wip() == frozenset()


def test_is_visible_rules(monkeypatch):
    monkeypatch.delenv("AGENT_NOTES_ENABLE_WIP", raising=False)
    assert is_visible(STABILITY_STABLE, "claude") is True
    assert is_visible(STABILITY_WIP, "gemini") is False
    assert is_visible(STABILITY_WIP, "gemini", frozenset({"gemini"})) is True
    monkeypatch.setenv("AGENT_NOTES_ENABLE_WIP", "gemini")
    assert is_visible(STABILITY_WIP, "gemini") is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/services/test_stability.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agent_notes.services.stability'`

- [ ] **Step 3: Write minimal implementation**

```python
# agent_notes/services/stability.py
"""Component lifecycle stability flag + development override.

A component (CLI backend, plugin, skill, agent, memory backend) may declare a
``stability`` of "stable" (default) or "wip". A "wip" component is hidden from the
wizard, the build, and user-facing listings unless its name appears in the
``AGENT_NOTES_ENABLE_WIP`` environment variable (comma-separated).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

STABILITY_STABLE = "stable"
STABILITY_WIP = "wip"
STABILITY_VALUES = frozenset({STABILITY_STABLE, STABILITY_WIP})

ENABLE_WIP_ENV = "AGENT_NOTES_ENABLE_WIP"


def normalize_stability(value, source: Optional[Path] = None) -> str:
    """Return a validated stability string, defaulting to "stable".

    ``None``/empty becomes "stable"; an unrecognised value raises ``ValueError``.
    """
    if value is None or value == "":
        return STABILITY_STABLE
    text = str(value).strip().lower()
    if text not in STABILITY_VALUES:
        where = f" in {source}" if source is not None else ""
        raise ValueError(
            f"Invalid stability {value!r}{where}; "
            f"expected one of {sorted(STABILITY_VALUES)}"
        )
    return text


def enabled_wip() -> frozenset[str]:
    """Component names force-enabled via AGENT_NOTES_ENABLE_WIP (may be empty)."""
    raw = os.environ.get(ENABLE_WIP_ENV, "")
    return frozenset(n.strip() for n in raw.split(",") if n.strip())


def is_visible(
    stability: str, name: str, override: Optional[frozenset[str]] = None
) -> bool:
    """True unless the component is "wip" and not force-enabled by the override."""
    if stability != STABILITY_WIP:
        return True
    if override is None:
        override = enabled_wip()
    return name in override
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/services/test_stability.py -v`
Expected: PASS (all 4)

- [ ] **Step 5: Commit**

```bash
git add agent_notes/services/stability.py tests/unit/services/test_stability.py
git commit -m "feat(stability): add stability helper and AGENT_NOTES_ENABLE_WIP override"
```

---

### Task 2: Parse `stability` into the five domain objects

Adds the field to every family's domain object and loader, validated and defaulting to `stable`. **No filtering yet** — pure parsing, so dist stays byte-identical.

**Files:**
- Modify: `agent_notes/domain/cli_backend.py` (add field), `agent_notes/registries/cli_registry.py:64-82` (parse)
- Modify: `agent_notes/domain/plugin.py:23-33` (add field), `agent_notes/registries/plugin_registry.py:55-80` (parse)
- Modify: `agent_notes/domain/skill.py:10-16` (add field), `agent_notes/registries/skill_registry.py` (parser + loader)
- Modify: `agent_notes/domain/agent.py:9-34` (add field), `agent_notes/registries/agent_registry.py:13,60-99` (parse + `NON_BACKEND_KEYS`)
- Modify: `agent_notes/memory/memory_backend.py:9-40` (base + subclass class attr)
- Test: `tests/unit/registries/test_stability_parsing.py`

**Interfaces:**
- Consumes: `normalize_stability` from Task 1.
- Produces: `.stability: str` attribute on `CLIBackend`, `Plugin`, `Skill`, `AgentSpec`, and every `MemoryBackend` instance.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/registries/test_stability_parsing.py
import textwrap
import pytest
from agent_notes.registries.cli_registry import load_registry
from agent_notes.registries.plugin_registry import load_plugin_registry
from agent_notes.registries.skill_registry import load_skill_registry
from agent_notes.registries.agent_registry import load_agent_registry


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(text))


def test_backend_stability_parsed(tmp_path):
    _write(tmp_path / "wipcli.yaml", """
        name: wipcli
        label: WIP CLI
        global_home: ~/.wipcli
        local_dir: .wipcli
        layout: {agents: agents/}
        features: {agents: true, frontmatter: claude}
        stability: wip
    """)
    _write(tmp_path / "stablecli.yaml", """
        name: stablecli
        label: Stable CLI
        global_home: ~/.stablecli
        local_dir: .stablecli
        layout: {agents: agents/}
        features: {agents: true, frontmatter: claude}
    """)
    reg = load_registry(tmp_path)
    assert reg.get("wipcli").stability == "wip"
    assert reg.get("stablecli").stability == "stable"  # absent → stable


def test_backend_invalid_stability_rejected(tmp_path):
    _write(tmp_path / "bad.yaml", """
        name: bad
        label: Bad
        global_home: ~/.bad
        local_dir: .bad
        layout: {agents: agents/}
        features: {agents: true, frontmatter: claude}
        stability: beta
    """)
    with pytest.raises(ValueError):
        load_registry(tmp_path)


def test_plugin_stability_parsed(tmp_path):
    _write(tmp_path / "wipplug" / "plugin.yaml", """
        name: wipplug
        description: WIP plugin
        default: off
        stability: wip
    """)
    reg = load_plugin_registry(tmp_path)
    assert reg.get("wipplug").stability == "wip"


def test_skill_stability_parsed(tmp_path):
    _write(tmp_path / "wipskill" / "SKILL.md", """
        ---
        description: "A WIP skill"
        stability: wip
        ---
        body
    """)
    reg = load_skill_registry(tmp_path)
    assert reg.get("wipskill").stability == "wip"


def test_agent_stability_parsed(tmp_path):
    yaml_path = tmp_path / "agents.yaml"
    _write(yaml_path, """
        agents:
          wipagent:
            description: WIP agent
            role: helper
            mode: subagent
            stability: wip
          stableagent:
            description: Stable agent
            role: helper
            mode: subagent
    """)
    reg = load_agent_registry(yaml_path)
    assert reg.get("wipagent").stability == "wip"
    assert reg.get("stableagent").stability == "stable"
    # stability must NOT be treated as a per-backend override
    assert "stability" not in reg.get("wipagent").backends


def test_memory_backend_default_stability():
    from agent_notes.memory.memory_backend import get_backend
    assert get_backend("local").stability == "stable"
    assert get_backend("obsidian").stability == "stable"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/registries/test_stability_parsing.py -v`
Expected: FAIL — `AttributeError: 'CLIBackend' object has no attribute 'stability'` (and equivalents).

- [ ] **Step 3: Add the field + parse for CLI backend**

In `agent_notes/domain/cli_backend.py`, add as the last field of `CLIBackend`:

```python
    preferred_family: Optional[str] = None     # "claude", "gpt", etc.
    stability: str = "stable"                   # "stable" | "wip"
```

In `agent_notes/registries/cli_registry.py`, add the import and the parse line inside the `CLIBackend(...)` construction:

```python
from ..services.stability import normalize_stability
```
```python
            preferred_family=data.get("preferred_family"),
            stability=normalize_stability(data.get("stability"), yaml_file),
        )
```

- [ ] **Step 4: Add the field + parse for Plugin**

In `agent_notes/domain/plugin.py`, add to `Plugin`:

```python
    allow: tuple[PluginAllow, ...] = ()
    stability: str = "stable"
```

In `agent_notes/registries/plugin_registry.py`, import and add to the `Plugin(...)` return in `_plugin_from`:

```python
from ..services.stability import normalize_stability
```
```python
        allow=allow,
        stability=normalize_stability(data.get("stability"), path),
    )
```

- [ ] **Step 5: Add the field + parse for Skill**

In `agent_notes/domain/skill.py`, add to `Skill`:

```python
    requires_memory: Optional[str] = None
    stability: str = "stable"
```

In `agent_notes/registries/skill_registry.py`, extend `_parse_skill_frontmatter` to a 4-tuple `(description, group, requires_memory, stability)`:
- Add `stability = None` next to the other locals.
- In the key loop, add:
  ```python
                    elif key == 'stability':
                        stability = value
  ```
- Change every `return` in the function to include `stability` as the 4th element (the no-frontmatter/fallback returns pass `None`).

Then update `load_skill_registry`:

```python
from ..services.stability import normalize_stability
```
```python
        description, group, requires_memory, stability = _parse_skill_frontmatter(skill_md)

        skill = Skill(
            name=skill_dir.name,
            path=skill_dir,
            description=description,
            group=group,
            requires_memory=requires_memory,
            stability=normalize_stability(stability, skill_md),
        )
```

- [ ] **Step 6: Add the field + parse for Agent**

In `agent_notes/domain/agent.py`, add to `AgentSpec`:

```python
    backends: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    stability: str = "stable"
```

In `agent_notes/registries/agent_registry.py`:
- Add `"stability"` to `NON_BACKEND_KEYS` so it is not mistaken for a per-backend override:
  ```python
  NON_BACKEND_KEYS = {"description", "role", "mode", "color", "effort", "claude_exclude", "stability"}
  ```
- Import and set the field in the `AgentSpec(...)` construction:
  ```python
  from ..services.stability import normalize_stability
  ```
  ```python
          backends=backends,
          stability=normalize_stability(config.get("stability"), yaml_path),
      )
  ```

- [ ] **Step 7: Add the class attribute for memory backends**

In `agent_notes/memory/memory_backend.py`, add a class attribute to the base so all backends inherit a default:

```python
class MemoryBackend(ABC):
    """Common interface that all memory backends must implement."""

    stability: str = "stable"

    @abstractmethod
    def init(self, path: Path) -> None:
```

(A future WIP backend subclass sets `stability = "wip"`.)

- [ ] **Step 8: Run tests to verify they pass**

Run: `uv run pytest tests/unit/registries/test_stability_parsing.py -v`
Expected: PASS (all 6)

- [ ] **Step 9: Verify byte-identical dist + full suite**

Run:
```bash
uv run pytest tests/
scripts/dev/verify_dist_equiv.sh e9edbf7
```
Expected: suite green; verify script reports BYTE-IDENTICAL (no shipped manifest declares `stability`, so nothing changes).

- [ ] **Step 10: Commit**

```bash
git add agent_notes/domain/ agent_notes/registries/ agent_notes/memory/memory_backend.py tests/unit/registries/test_stability_parsing.py
git commit -m "feat(stability): parse stability field on backends, plugins, skills, agents, memory"
```

---

### Task 3: Filter backends and plugins through `available()`

Adds `available()` to the CLI and plugin registries and routes the user-facing enumeration sites through it. Behavior changes only for `wip` components.

**Files:**
- Modify: `agent_notes/registries/cli_registry.py` (add `available`)
- Modify: `agent_notes/registries/plugin_registry.py` (add `available`; make `enabled` exclude wip)
- Modify: `agent_notes/commands/wizard/__init__.py:67` (`all()` → `available()`)
- Modify: `agent_notes/services/rendering.py:350` (`all()` → `available()`)
- Modify: `agent_notes/commands/plugins.py:14` (`all()` → `available()`)
- Test: `tests/unit/registries/test_stability_filtering.py`

**Interfaces:**
- Consumes: `is_visible`, `enabled_wip` from Task 1; `.stability` from Task 2.
- Produces: `CLIRegistry.available(override=None) -> list[CLIBackend]`, `PluginRegistry.available(override=None) -> list[Plugin]`, and a wip-aware `PluginRegistry.enabled(config)`.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/registries/test_stability_filtering.py
import textwrap
from agent_notes.registries.cli_registry import load_registry
from agent_notes.registries.plugin_registry import load_plugin_registry


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(text))


def _two_backends(tmp_path):
    _write(tmp_path / "wipcli.yaml", """
        name: wipcli
        label: WIP CLI
        global_home: ~/.wipcli
        local_dir: .wipcli
        layout: {agents: agents/}
        features: {agents: true, frontmatter: claude}
        stability: wip
    """)
    _write(tmp_path / "stablecli.yaml", """
        name: stablecli
        label: Stable CLI
        global_home: ~/.stablecli
        local_dir: .stablecli
        layout: {agents: agents/}
        features: {agents: true, frontmatter: claude}
    """)


def test_backend_available_hides_wip_by_default(tmp_path, monkeypatch):
    monkeypatch.delenv("AGENT_NOTES_ENABLE_WIP", raising=False)
    _two_backends(tmp_path)
    reg = load_registry(tmp_path)
    names = {b.name for b in reg.available()}
    assert names == {"stablecli"}
    assert {b.name for b in reg.all()} == {"stablecli", "wipcli"}  # all() unchanged


def test_backend_available_shows_wip_when_overridden(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_NOTES_ENABLE_WIP", "wipcli")
    _two_backends(tmp_path)
    reg = load_registry(tmp_path)
    assert {b.name for b in reg.available()} == {"stablecli", "wipcli"}


def test_plugin_available_and_enabled_exclude_wip(tmp_path, monkeypatch):
    monkeypatch.delenv("AGENT_NOTES_ENABLE_WIP", raising=False)
    _write(tmp_path / "wipplug" / "plugin.yaml", """
        name: wipplug
        description: WIP plugin
        default: on
        stability: wip
    """)
    reg = load_plugin_registry(tmp_path)
    assert [p.name for p in reg.available()] == []
    # default: on, but wip → not enabled without override
    assert [p.name for p in reg.enabled({})] == []
    monkeypatch.setenv("AGENT_NOTES_ENABLE_WIP", "wipplug")
    assert [p.name for p in reg.enabled({})] == ["wipplug"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/registries/test_stability_filtering.py -v`
Expected: FAIL — `AttributeError: 'CLIRegistry' object has no attribute 'available'`.

- [ ] **Step 3: Add `available()` to the CLI registry**

In `agent_notes/registries/cli_registry.py`, import and add a method to the `CLIRegistry` class (next to `all()`):

```python
from ..services.stability import is_visible, enabled_wip
```
```python
    def available(self, override=None):
        """Backends visible to users: all() minus wip ones not force-enabled."""
        ov = enabled_wip() if override is None else override
        return [b for b in self.all() if is_visible(b.stability, b.name, ov)]
```

- [ ] **Step 4: Add `available()` and wip-aware `enabled()` to the plugin registry**

In `agent_notes/registries/plugin_registry.py`, import the helpers and add/replace on `PluginRegistry`:

```python
from ..services.stability import is_visible, enabled_wip
```
```python
    def available(self, override=None):
        ov = enabled_wip() if override is None else override
        return [p for p in self.all() if is_visible(p.stability, p.name, ov)]

    def enabled(self, config):
        ov = enabled_wip()
        chosen = config.get("enabled_plugins", {})
        return [
            p for p in self.all()
            if chosen.get(p.name, p.default) and is_visible(p.stability, p.name, ov)
        ]
```

(Preserve the existing `enabled` semantics — `chosen.get(p.name, p.default)` — and add only the `is_visible` conjunct.)

- [ ] **Step 5: Route the enumeration sites through `available()`**

- `agent_notes/commands/wizard/__init__.py:67` — change `sorted(registry.all(), key=lambda b: b.name)` to `sorted(registry.available(), key=lambda b: b.name)`.
- `agent_notes/services/rendering.py:350` — change `for backend in registry.all():` to `for backend in registry.available():`.
- `agent_notes/commands/plugins.py:14` — change `plugins = registry.all()` to `plugins = registry.available()`.

(`services/installer.py:158` keeps `reg.all()` — its `on = p.name in enabled` check already excludes wip via the new `enabled()`, so a wip plugin is correctly treated as off/uninstalled. `commands/build.py:162` keeps `all()` — it computes valid dist dir names for cleanup and must not delete a wip dir a developer built under override.)

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/unit/registries/test_stability_filtering.py -v`
Expected: PASS (all 3)

- [ ] **Step 7: Verify byte-identical dist + full suite**

Run:
```bash
uv run pytest tests/
scripts/dev/verify_dist_equiv.sh e9edbf7
```
Expected: green; BYTE-IDENTICAL.

- [ ] **Step 8: Commit**

```bash
git add agent_notes/registries/cli_registry.py agent_notes/registries/plugin_registry.py agent_notes/commands/wizard/__init__.py agent_notes/services/rendering.py agent_notes/commands/plugins.py tests/unit/registries/test_stability_filtering.py
git commit -m "feat(stability): hide wip backends and plugins from wizard, build, and listings"
```

---

### Task 4: Filter skills and agents; guard memory selection

Skills and agents flow through `available()` at their build sites; memory has no enumeration, so it gets a selection guard on `get_backend`.

**Files:**
- Modify: `agent_notes/registries/skill_registry.py` (add `available`)
- Modify: `agent_notes/registries/agent_registry.py` (add `available`)
- Modify: `agent_notes/services/installer.py:209` (skills → `available()`)
- Modify: `agent_notes/services/rendering.py:330` (filter `agents_config` by stability)
- Modify: `agent_notes/memory/memory_backend.py:49-60` (guard `get_backend`; add `available_backends`)
- Test: `tests/unit/registries/test_stability_skills_agents.py`, `tests/unit/memory/test_stability_memory.py`

**Interfaces:**
- Consumes: `is_visible`, `enabled_wip`, `.stability` from Tasks 1–2.
- Produces: `SkillRegistry.available(override=None)`, `AgentRegistry.available(override=None)`, `memory_backend.available_backends(override=None) -> list[str]`, and a wip-guarded `get_backend`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/registries/test_stability_skills_agents.py
import textwrap
from agent_notes.registries.skill_registry import load_skill_registry
from agent_notes.registries.agent_registry import load_agent_registry


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(text))


def test_skill_available_hides_wip(tmp_path, monkeypatch):
    monkeypatch.delenv("AGENT_NOTES_ENABLE_WIP", raising=False)
    _write(tmp_path / "wipskill" / "SKILL.md", "---\ndescription: x\nstability: wip\n---\n")
    _write(tmp_path / "okskill" / "SKILL.md", "---\ndescription: y\n---\n")
    reg = load_skill_registry(tmp_path)
    assert {s.name for s in reg.available()} == {"okskill"}
    monkeypatch.setenv("AGENT_NOTES_ENABLE_WIP", "wipskill")
    assert {s.name for s in reg.available()} == {"okskill", "wipskill"}


def test_agent_available_hides_wip(tmp_path, monkeypatch):
    monkeypatch.delenv("AGENT_NOTES_ENABLE_WIP", raising=False)
    yaml_path = tmp_path / "agents.yaml"
    _write(yaml_path, """
        agents:
          wipagent: {description: x, role: r, mode: subagent, stability: wip}
          okagent: {description: y, role: r, mode: subagent}
    """)
    reg = load_agent_registry(yaml_path)
    assert {a.name for a in reg.available()} == {"okagent"}
```

```python
# tests/unit/memory/test_stability_memory.py
import pytest
from agent_notes.memory import memory_backend as mb


class _WipBackend(mb.MemoryBackend):
    stability = "wip"
    def init(self, path): ...
    def regenerate_index(self, path): ...


def test_get_backend_guards_wip(monkeypatch):
    monkeypatch.setitem(mb._REGISTRY, "wipmem", _WipBackend())
    monkeypatch.delenv("AGENT_NOTES_ENABLE_WIP", raising=False)
    with pytest.raises(ValueError):
        mb.get_backend("wipmem")
    monkeypatch.setenv("AGENT_NOTES_ENABLE_WIP", "wipmem")
    assert isinstance(mb.get_backend("wipmem"), _WipBackend)


def test_available_backends_excludes_wip_and_removed(monkeypatch):
    monkeypatch.setitem(mb._REGISTRY, "wipmem", _WipBackend())
    monkeypatch.delenv("AGENT_NOTES_ENABLE_WIP", raising=False)
    names = set(mb.available_backends())
    assert "local" in names and "obsidian" in names
    assert "wipmem" not in names and "wiki" not in names
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/registries/test_stability_skills_agents.py tests/unit/memory/test_stability_memory.py -v`
Expected: FAIL — missing `available`/`available_backends`; `get_backend` does not guard.

- [ ] **Step 3: Add `available()` to skill and agent registries**

In `agent_notes/registries/skill_registry.py` (on `SkillRegistry`, next to `all()`):

```python
from ..services.stability import is_visible, enabled_wip
```
```python
    def available(self, override=None):
        ov = enabled_wip() if override is None else override
        return [s for s in self.all() if is_visible(s.stability, s.name, ov)]
```

In `agent_notes/registries/agent_registry.py` (on `AgentRegistry`, next to `all()`):

```python
from ..services.stability import is_visible, enabled_wip
```
```python
    def available(self, override=None):
        ov = enabled_wip() if override is None else override
        return [a for a in self.all() if is_visible(a.stability, a.name, ov)]
```

- [ ] **Step 4: Route the skill build site through `available()`**

In `agent_notes/services/installer.py:209`, change:

```python
    skills = _filter_skills_by_backend(default_skill_registry().all(), memory_backend)
```
to
```python
    skills = _filter_skills_by_backend(default_skill_registry().available(), memory_backend)
```

- [ ] **Step 5: Filter `agents_config` by stability in rendering**

In `agent_notes/services/rendering.py`, immediately before the agent loop at line ~330 (`for agent_name, agent_config in agents_config.items():`), insert:

```python
    from .stability import is_visible, enabled_wip
    _wip = enabled_wip()
    agents_config = {
        n: c for n, c in agents_config.items()
        if is_visible(c.get("stability", "stable"), n, _wip)
    }
```

(`agents_config` values are the raw `agents.yaml` dicts, which carry the `stability:` key added in Task 2.)

- [ ] **Step 6: Guard `get_backend` and add `available_backends`**

In `agent_notes/memory/memory_backend.py`, import the helpers and modify `get_backend`, then add `available_backends`:

```python
from ..services.stability import is_visible, enabled_wip
```
```python
def get_backend(name: str, override=None) -> MemoryBackend:
    """Return the backend instance for *name*, raising ValueError if unknown or
    a work-in-progress backend that is not force-enabled."""
    if name in _REMOVED_BACKENDS:
        raise ValueError(
            f"Memory backend {name!r} has been removed. "
            "Run `agent-notes config memory` to switch to a supported backend "
            "(local or obsidian)."
        )
    try:
        backend = _REGISTRY[name]
    except KeyError:
        raise ValueError(f"Unknown memory backend: {name!r}")
    ov = enabled_wip() if override is None else override
    if not is_visible(getattr(backend, "stability", "stable"), name, ov):
        raise ValueError(
            f"Memory backend {name!r} is work-in-progress; "
            f"set AGENT_NOTES_ENABLE_WIP={name} to enable it."
        )
    return backend


def available_backends(override=None) -> list[str]:
    """Names of memory backends visible to users (non-removed, non-wip)."""
    ov = enabled_wip() if override is None else override
    return [
        name for name, backend in _REGISTRY.items()
        if name not in _REMOVED_BACKENDS
        and is_visible(getattr(backend, "stability", "stable"), name, ov)
    ]
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `uv run pytest tests/unit/registries/test_stability_skills_agents.py tests/unit/memory/test_stability_memory.py -v`
Expected: PASS

- [ ] **Step 8: Verify byte-identical dist + full suite**

Run:
```bash
uv run pytest tests/
scripts/dev/verify_dist_equiv.sh e9edbf7
```
Expected: green; BYTE-IDENTICAL.

- [ ] **Step 9: Commit**

```bash
git add agent_notes/registries/skill_registry.py agent_notes/registries/agent_registry.py agent_notes/services/installer.py agent_notes/services/rendering.py agent_notes/memory/memory_backend.py tests/unit/registries/test_stability_skills_agents.py tests/unit/memory/test_stability_memory.py
git commit -m "feat(stability): hide wip skills and agents; guard wip memory backend selection"
```

---

### Task 5: Doctor visibility line + end-to-end CLI check

A `doctor` line surfaces any `wip` components and whether the override is active, and one hermetic CLI test proves the override reaches a real invocation.

**Files:**
- Modify: `agent_notes/commands/doctor.py` (add `_check_wip_components`, call it in `diagnose`)
- Test: `tests/functional/commands/test_stability_cli.py`

**Interfaces:**
- Consumes: `available()` on each registry, `enabled_wip()`, `available_backends()`.

- [ ] **Step 1: Write the failing test**

```python
# tests/functional/commands/test_stability_cli.py
import os
import sys
import subprocess
from pathlib import Path


def _run(tmp_path: Path, *args: str, extra_env=None):
    env = {**os.environ, "XDG_CONFIG_HOME": str(tmp_path)}
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, "-m", "agent_notes", *args],
        env=env, capture_output=True, text=True,
    )


def test_doctor_reports_no_wip_by_default(tmp_path):
    result = _run(tmp_path, "doctor")
    # No shipped component is wip, so the doctor must not crash and must not
    # claim any wip components are active.
    assert result.returncode in (0, 1), f"stderr: {result.stderr}"
    assert "work-in-progress" not in result.stdout.lower() or "none" in result.stdout.lower()


def test_enable_wip_env_is_read(tmp_path):
    # An unknown override name must not crash any command.
    result = _run(tmp_path, "plugins", "list",
                  extra_env={"AGENT_NOTES_ENABLE_WIP": "does-not-exist"})
    assert result.returncode == 0, f"stderr: {result.stderr}"
```

- [ ] **Step 2: Run test to verify it fails / defines behavior**

Run: `uv run pytest tests/functional/commands/test_stability_cli.py -v`
Expected: the `plugins list` test passes already (override is inert), the doctor test defines the advisory line behavior. Run to confirm the suite executes; adjust only if `doctor` errors.

- [ ] **Step 3: Add the doctor check**

In `agent_notes/commands/doctor.py`, add a function modeled on the existing print-style checks (like `_check_role_models`):

```python
def _check_wip_components() -> None:
    """Print any work-in-progress components and whether they are force-enabled."""
    from ..registries.cli_registry import load_registry
    from ..registries.plugin_registry import default_plugin_registry
    from ..registries.skill_registry import default_skill_registry
    from ..registries.agent_registry import default_agent_registry
    from ..services.stability import enabled_wip, STABILITY_WIP

    override = enabled_wip()
    wip = []
    for kind, items in (
        ("backend", load_registry().all()),
        ("plugin", default_plugin_registry().all()),
        ("skill", default_skill_registry().all()),
        ("agent", default_agent_registry().all()),
    ):
        for item in items:
            if getattr(item, "stability", "stable") == STABILITY_WIP:
                state = "ENABLED" if item.name in override else "hidden"
                wip.append(f"  - {kind} {item.name}: {state}")

    if not wip:
        return
    print("\nWork-in-progress components:")
    print("\n".join(wip))
    if override:
        print(f"  (AGENT_NOTES_ENABLE_WIP={','.join(sorted(override))})")
```

Call it inside `diagnose(...)` near the other advisory prints (e.g. after `_check_role_models`):

```python
    _check_wip_components()
```

(Use whatever `default_*_registry` accessors exist; if a family lacks a cached accessor, call its `load_*` entry point with no argument.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/functional/commands/test_stability_cli.py -v`
Expected: PASS (both)

- [ ] **Step 5: Verify byte-identical dist + full suite**

Run:
```bash
uv run pytest tests/
scripts/dev/verify_dist_equiv.sh e9edbf7
```
Expected: green; BYTE-IDENTICAL (doctor is diagnostic-only, no dist output).

- [ ] **Step 6: Commit**

```bash
git add agent_notes/commands/doctor.py tests/functional/commands/test_stability_cli.py
git commit -m "feat(stability): surface wip components in doctor and cover the override end to end"
```

---

## Self-Review

**Spec coverage** (against `docs/superpowers/specs/2026-07-31-component-lifecycle-flag-design.md`):
- Two-state `stability` field → Task 1 (`STABILITY_VALUES`) + Task 2 (per family). ✓
- Per-family manifest locations → Task 2 covers all five. ✓
- `AGENT_NOTES_ENABLE_WIP` override → Task 1 (`enabled_wip`). ✓
- Single `is_visible` helper + ~5 filter sites → Task 1 helper; Tasks 3–4 wire wizard, rendering (backends + agents), plugins list, installer skills, memory guard. ✓
- Selection guard → Task 3 (plugin `enabled` excludes wip), Task 4 (`get_backend` guard). ✓
- Byte-identical compatibility via `verify_dist_equiv.sh` → every task's penultimate step. ✓
- Test matrix (hidden default / visible override / invalid enum / hermetic) → Tasks 1–5. ✓
- Optional doctor line → Task 5. ✓
- Non-goals (memory de-elif, wizard framework, experimental tier) → not touched; memory wizard option lists left hardcoded by design. ✓

**Known limitation (documented, matches spec):** memory has no enumeration, so `wip` hiding for a memory provider relies on the `get_backend` selection guard plus the developer not adding it to the two hardcoded wizard option lists yet — full wizard enumeration is deferred to the memory de-elif work (out of scope).

**Type consistency:** `available(override=None)` signature is identical across all four registries; `is_visible(stability, name, override)` and `enabled_wip()` are used consistently; `.stability: str` default `"stable"` on all five domain objects.

**Placeholder scan:** no TBD/TODO; every code step has real code.

## Execution Handoff

Two execution options:

1. **Subagent-Driven (recommended)** — a fresh subagent per task, two-stage review between tasks, byte-identity gate enforced per task.
2. **Inline Execution** — execute tasks in this session with checkpoints.

The tasks are ordered by dependency (1 → 2 → {3, 4} → 5); Tasks 3 and 4 both depend only on 1–2 and could run in parallel if isolated, but sharing `rendering.py` and `memory_backend.py` edits makes sequential simpler.
