# Plugin System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make agent-notes' own subsystems (cost-report, credential-guard, memory) enable/disable-able like oh-my-zsh plugins, via a `plugin.yaml` manifest + a registry + an `agent-notes plugins` command.

**Architecture:** A plugin is a directory with a `plugin.yaml` manifest declaring what it contributes across eight surfaces (skills, agents, rules, includes, hooks, allow-entries — agents/rules unused at first). A registry loads enabled manifests; the existing installer and renderer consume merged contributions. Enable/disable is a `{name: bool}` map in user config; **disable actively uninstalls**, it does not no-op. Plugin *code* stays where it already lives (`agent_notes/cost/`, `agent_notes/memory/`); only the manifest and any escape-hatch install hook are new.

**Tech Stack:** Python 3.11+, PyYAML, argparse, pytest. No new dependencies.

## Scope

This plan covers epic #32's first five sub-issues — the mechanism plus the first, easiest conversion:

- **#33** — manifest format, `Plugin` domain type, `plugin_registry.py`, enabled-plugins config
- **#34** — `agent-notes plugins list | enable | disable | info`
- **#35** — route the declarative surfaces (skills, includes) through the registry, additive model + equivalence gate
- **#36** — route hooks + allow-entries through the registry, composed with `backend.supports(...)`, disable-uninstalls
- **#37** — convert cost-report to a plugin

This is a complete, working, testable increment on its own: plugins can be declared, listed, toggled, and cost-report is the first real one whose disable strips its Stop hook. The remaining conversions — **#38** (cred-guard), **#39** (memory), **#40** (wizard), **#41** (docs) — follow the pattern this plan establishes and get their own plan once the mechanism is proven under review.

### Correction to the tickets (surfaced while planning)

Sub-issue **#35** says "delete `requires_memory` parsing and `include_skip()`." That is mis-sequenced: a gate cannot be deleted until the subsystem it gates is a plugin. So:

- `include_skip()` (gates the `cost_reporting` include) is deleted in **Task 5 / #37**, when cost-report becomes a plugin that owns that include.
- `requires_memory` frontmatter parsing (gates memory skills) is deleted in **#39**, out of this plan.

Task 3 therefore establishes the additive registry-driven surface set *with a temporary legacy bridge* for subsystems not yet converted, and the equivalence gate proves it stays byte-identical. This is honest sequencing; the deletions still happen, just in the ticket that can safely make them.

### Path refinement

Manifests live at `agent_notes/data/plugins/<name>/plugin.yaml`, not `agent_notes/plugins/` as sub-issue #33 tentatively wrote. Rationale: every other data-driven registry loads from `DATA_DIR` (`SKILLS_DIR`, `RULES_DIR`, `AGENTS_DIR`); manifests are data, so they belong there for consistency. Plugin *code* is unaffected — it stays in `agent_notes/cost/`, `agent_notes/memory/`.

## Global Constraints

Copied verbatim from epic #32 and the project's standing rules. Every task's requirements implicitly include these.

- **Dist equivalence is the safety mechanism — but `git diff agent_notes/dist/` is a NO-TEETH GATE. Never use it.** `agent_notes/dist/` is gitignored (`.gitignore:30`, zero tracked files), so `git diff`/`git status` on it is ALWAYS empty and will report "byte-identical" even when the build output changed. This trap already bit this epic once (the first #35 gate). Two real ways to verify, in order of preference:
  1. **Additive unit gate (fast, CI-safe, committed):** assert the plugin wiring equals the legacy path when no manifest owns the surface — `rendering._plugin_include_skip(cfg) == cost.render.include_skip(cfg)`, and the installer skill filter drops nothing. This is `tests/unit/registries/test_plugin_equivalence.py`. A gate must be proven capable of failing (perturb → red → revert) before it is trusted.
  2. **End-to-end checksum vs. baseline (manual, at task boundaries):** run `scripts/dev/verify_dist_equiv.sh` — it builds dist from HEAD and from the branch point `7af1310` into a worktree (forcing each source via `PYTHONPATH`), wipes dist and excludes `*.bak*` (install artifacts, not build output), then sha256-compares the trees. Byte-identity = identical checksums. `git diff` is never the check.
  - An unpinned comparison is also noise for a different reason (`services/rendering.py` reads the developer's live `state.json`); the checksum script pins `XDG_CONFIG_HOME` for both builds.
- **Installed-contract invariant.** Hook command strings come from `constants.py` (`Hooks.COST_REPORT`, `Hooks.MEMORY_BRIDGE`, `Hooks.GUARD_CREDENTIALS`) — byte-identical. `remove_hook` matches these exact strings in every existing user's `settings.json`; a changed string orphans hooks on upgrade.
- **Composed capability gate.** A hook/allow-entry installs iff `plugin_enabled AND backend.supports(requires)`. Never replace the `backend.supports(...)` axis — compose with it.
- **Disable uninstalls.** A disabled plugin's hooks and allow-entries are actively removed from `settings.json`, not skipped.
- **No new dependencies.** stdlib + existing (PyYAML) only.
- **Built-in plugins only.** No user drop-in directory, no versioning, no trust boundary. The config format must not preclude adding those later.
- **No AI attribution** in any commit message or committed text.
- **Branch:** `refactor/plugin-system` (already cut from `refactor/model-catalog-and-mission-trim`). Commit format `#<issue> type(scope): desc`, title only.
- **TDD:** every behavior change is a failing test first, then minimal code, then green, then commit.

---

### Task 1: Plugin domain type, manifest loader, and registry (#33)

**Files:**
- Create: `agent_notes/domain/plugin.py`
- Create: `agent_notes/registries/plugin_registry.py`
- Modify: `agent_notes/config.py:18-22` (add `PLUGINS_DIR = DATA_DIR / "plugins"` next to `SKILLS_DIR`)
- Create: `agent_notes/data/plugins/.gitkeep` (empty dir must exist so the loader finds it; real manifests arrive in Task 5)
- Test: `tests/unit/registries/test_plugin_registry.py`

**Interfaces:**
- Consumes: `registries/_base.py` → `load_yaml_file(path)`, `require_fields(data, required, source)`; `config.PLUGINS_DIR`.
- Produces:
  - `domain/plugin.py` → `PluginHook(event: str, command: str, matcher: Optional[str], requires: Optional[str])`, `PluginAllow(value: str, requires: Optional[str])`, `Plugin(name: str, description: str, default: bool, path: Path, skills: tuple[str,...], agents: tuple[str,...], rules: tuple[str,...], includes: tuple[str,...], hooks: tuple[PluginHook,...], allow: tuple[PluginAllow,...])` — all `@dataclass(frozen=True)`.
  - `registries/plugin_registry.py` → `PluginRegistry` with `.all() -> list[Plugin]`, `.get(name) -> Plugin`, `.names() -> list[str]`, `.enabled(config: dict) -> list[Plugin]`; module fns `load_plugin_registry(plugins_dir: Optional[Path] = None) -> PluginRegistry`, `default_plugin_registry() -> PluginRegistry` (`@lru_cache(maxsize=1)`).
  - Resolution rule: `enabled(config)` returns each plugin for which `config.get("enabled_plugins", {}).get(p.name, p.default)` is truthy.

- [ ] **Step 1: Write the failing test for manifest parsing + default resolution**

```python
# tests/unit/registries/test_plugin_registry.py
from pathlib import Path
import textwrap
from agent_notes.registries.plugin_registry import load_plugin_registry


def _write_manifest(root: Path, name: str, body: str) -> None:
    d = root / name
    d.mkdir(parents=True)
    (d / "plugin.yaml").write_text(textwrap.dedent(body))


def test_loads_manifest_fields(tmp_path):
    _write_manifest(tmp_path, "cost-report", """
        name: cost-report
        description: Per-session token cost reporting
        default: off
        includes: [cost_reporting]
        hooks:
          - {event: Stop, command: "agent-notes cost-report", requires: stop_hook}
        allow:
          - {value: "Bash(agent-notes cost-report)", requires: allow_entries}
    """)
    reg = load_plugin_registry(tmp_path)
    p = reg.get("cost-report")
    assert p.default is False
    assert p.includes == ("cost_reporting",)
    assert p.hooks[0].event == "Stop"
    assert p.hooks[0].command == "agent-notes cost-report"
    assert p.hooks[0].requires == "stop_hook"
    assert p.allow[0].value == "Bash(agent-notes cost-report)"


def test_enabled_uses_default_then_override(tmp_path):
    _write_manifest(tmp_path, "on-plugin", "name: on-plugin\ndescription: x\ndefault: on\n")
    _write_manifest(tmp_path, "off-plugin", "name: off-plugin\ndescription: y\ndefault: off\n")
    reg = load_plugin_registry(tmp_path)
    assert {p.name for p in reg.enabled({})} == {"on-plugin"}
    assert {p.name for p in reg.enabled({"enabled_plugins": {"off-plugin": True, "on-plugin": False}})} == {"off-plugin"}


def test_rejects_name_directory_mismatch(tmp_path):
    _write_manifest(tmp_path, "dirname", "name: other\ndescription: x\ndefault: on\n")
    try:
        load_plugin_registry(tmp_path)
        assert False, "expected ValueError"
    except ValueError as e:
        assert "dirname" in str(e)


def test_missing_required_field_raises(tmp_path):
    _write_manifest(tmp_path, "bad", "name: bad\ndefault: on\n")  # no description
    try:
        load_plugin_registry(tmp_path)
        assert False, "expected ValueError"
    except ValueError as e:
        assert "description" in str(e)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/registries/test_plugin_registry.py -v`
Expected: FAIL with `ModuleNotFoundError: agent_notes.registries.plugin_registry`.

- [ ] **Step 3: Write the domain type**

```python
# agent_notes/domain/plugin.py
"""Plugin domain types — a toggleable agent-notes subsystem."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class PluginHook:
    event: str                       # SessionStart / Stop / PreToolUse / PreCompact
    command: str                     # exact string from constants.Hooks — installed contract
    matcher: Optional[str] = None    # PreToolUse tool matcher, e.g. "Read|Bash|Grep"
    requires: Optional[str] = None   # backend.supports(...) capability gate


@dataclass(frozen=True)
class PluginAllow:
    value: str                       # settings.json allow entry, e.g. "Bash(agent-notes cost-report)"
    requires: Optional[str] = None


@dataclass(frozen=True)
class Plugin:
    name: str
    description: str
    default: bool
    path: Path
    skills: tuple[str, ...] = ()
    agents: tuple[str, ...] = ()
    rules: tuple[str, ...] = ()
    includes: tuple[str, ...] = ()
    hooks: tuple[PluginHook, ...] = ()
    allow: tuple[PluginAllow, ...] = ()
```

- [ ] **Step 4: Write the registry + loader**

```python
# agent_notes/registries/plugin_registry.py
"""Registry of agent-notes plugins from data/plugins/*/plugin.yaml."""
from __future__ import annotations
from pathlib import Path
from typing import Optional
from functools import lru_cache

from ..config import PLUGINS_DIR
from ..domain.plugin import Plugin, PluginHook, PluginAllow
from ._base import load_yaml_file, require_fields


class PluginRegistry:
    def __init__(self, plugins: list[Plugin]):
        self._plugins = plugins
        self._by_name = {p.name: p for p in plugins}

    def all(self) -> list[Plugin]:
        return list(self._plugins)

    def get(self, name: str) -> Plugin:
        if name not in self._by_name:
            raise KeyError(f"Plugin '{name}' not found in registry")
        return self._by_name[name]

    def names(self) -> list[str]:
        return sorted(self._by_name)

    def enabled(self, config: dict) -> list[Plugin]:
        chosen = config.get("enabled_plugins") or {}
        return [p for p in self._plugins if chosen.get(p.name, p.default)]


def _parse_bool_default(value, source: Path) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip().lower() in ("on", "off"):
        return value.strip().lower() == "on"
    raise ValueError(f"'default' must be on/off in {source}, got {value!r}")


def _plugin_from(path: Path, data: dict) -> Plugin:
    require_fields(data, ["name", "description", "default"], path)
    name = data["name"]
    if name != path.parent.name:
        raise ValueError(f"Plugin name '{name}' != directory '{path.parent.name}' in {path}")
    hooks = tuple(
        PluginHook(event=h["event"], command=h["command"],
                   matcher=h.get("matcher"), requires=h.get("requires"))
        for h in (data.get("hooks") or [])
    )
    allow = tuple(
        PluginAllow(value=a["value"], requires=a.get("requires"))
        for a in (data.get("allow") or [])
    )
    return Plugin(
        name=name,
        description=data["description"],
        default=_parse_bool_default(data["default"], path),
        path=path.parent,
        skills=tuple(data.get("skills") or ()),
        agents=tuple(data.get("agents") or ()),
        rules=tuple(data.get("rules") or ()),
        includes=tuple(data.get("includes") or ()),
        hooks=hooks,
        allow=allow,
    )


def load_plugin_registry(plugins_dir: Optional[Path] = None) -> PluginRegistry:
    root = plugins_dir if plugins_dir is not None else PLUGINS_DIR
    if not root.exists():
        return PluginRegistry([])
    plugins = []
    for d in sorted(root.iterdir()):
        manifest = d / "plugin.yaml"
        if d.is_dir() and manifest.exists():
            plugins.append(_plugin_from(manifest, load_yaml_file(manifest)))
    return PluginRegistry(plugins)


@lru_cache(maxsize=1)
def default_plugin_registry() -> PluginRegistry:
    return load_plugin_registry()
```

- [ ] **Step 5: Add `PLUGINS_DIR` to config and the `.gitkeep`**

In `agent_notes/config.py`, after `SKILLS_DIR = DATA_DIR / "skills"` add:
```python
PLUGINS_DIR = DATA_DIR / "plugins"
```
Create empty `agent_notes/data/plugins/.gitkeep`.

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/unit/registries/test_plugin_registry.py -v`
Expected: PASS (4 tests).

- [ ] **Step 7: Run the full suite (nothing consumes the registry yet — must stay green)**

Run: `uv run pytest tests/ -q`
Expected: prior count + 4 passed, 0 failures.

- [ ] **Step 8: Verify dist unchanged**

Run: `bash scripts/dev/verify_dist_equiv.sh   # REAL checksum gate vs branch point — NEVER `git diff` dist/ (gitignored, always empty)`
Expected: no output (byte-identical — nothing wired yet).

- [ ] **Step 9: Commit**

```bash
git add agent_notes/domain/plugin.py agent_notes/registries/plugin_registry.py \
        agent_notes/config.py agent_notes/data/plugins/.gitkeep \
        tests/unit/registries/test_plugin_registry.py
git commit -m "#33 feat(plugins): add plugin manifest domain type and registry"
```

---

### Task 2: `agent-notes plugins` command (#34)

**Files:**
- Create: `agent_notes/commands/plugins.py`
- Modify: `agent_notes/cli.py` (register subparser near the `models` block ~L303-311; dispatch in `main()` near the `models` elif ~L377-389)
- Test: `tests/unit/commands/test_plugins_command.py`

**Interfaces:**
- Consumes: `plugin_registry.default_plugin_registry()`, `Plugin`, `user_config.load_user_config`, `user_config.save_user_config`.
- Produces: `commands/plugins.py` → `plugins(action: str, name: Optional[str] = None) -> None`, dispatching `list` / `enable` / `disable` / `info`.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/commands/test_plugins_command.py
import agent_notes.commands.plugins as plugins_cmd
from agent_notes.domain.plugin import Plugin
from agent_notes.registries.plugin_registry import PluginRegistry
from pathlib import Path


def _reg():
    return PluginRegistry([
        Plugin(name="cost-report", description="cost", default=False, path=Path(".")),
        Plugin(name="memory", description="mem", default=True, path=Path(".")),
    ])


def test_enable_writes_config(tmp_path, monkeypatch):
    cfg = tmp_path / "config.yaml"
    monkeypatch.setattr(plugins_cmd, "default_plugin_registry", _reg)
    monkeypatch.setattr(plugins_cmd, "config_path", lambda: cfg)
    plugins_cmd.plugins("enable", "cost-report")
    import yaml
    assert yaml.safe_load(cfg.read_text())["enabled_plugins"]["cost-report"] is True


def test_disable_writes_config(tmp_path, monkeypatch):
    cfg = tmp_path / "config.yaml"
    monkeypatch.setattr(plugins_cmd, "default_plugin_registry", _reg)
    monkeypatch.setattr(plugins_cmd, "config_path", lambda: cfg)
    plugins_cmd.plugins("disable", "memory")
    import yaml
    assert yaml.safe_load(cfg.read_text())["enabled_plugins"]["memory"] is False


def test_enable_unknown_plugin_errors(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(plugins_cmd, "default_plugin_registry", _reg)
    monkeypatch.setattr(plugins_cmd, "config_path", lambda: tmp_path / "config.yaml")
    plugins_cmd.plugins("enable", "nope")
    assert "nope" in capsys.readouterr().out.lower()


def test_list_marks_enabled(monkeypatch, capsys):
    monkeypatch.setattr(plugins_cmd, "default_plugin_registry", _reg)
    monkeypatch.setattr(plugins_cmd, "load_user_config", lambda: {})
    plugins_cmd.plugins("list")
    out = capsys.readouterr().out
    assert "cost-report" in out and "memory" in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/commands/test_plugins_command.py -v`
Expected: FAIL with `ModuleNotFoundError: agent_notes.commands.plugins`.

- [ ] **Step 3: Write the command**

```python
# agent_notes/commands/plugins.py
"""`agent-notes plugins` — list, enable, disable, and inspect plugins."""
from __future__ import annotations
from typing import Optional

from ..registries.plugin_registry import default_plugin_registry
from ..services.user_config import load_user_config, save_user_config, config_path


def _resolve_enabled(config: dict, plugin) -> bool:
    return (config.get("enabled_plugins") or {}).get(plugin.name, plugin.default)


def _set_enabled(name: str, value: bool) -> None:
    reg = default_plugin_registry()
    if name not in reg.names():
        print(f"Unknown plugin: {name!r}. Known: {', '.join(reg.names())}")
        return
    cfg = load_user_config(config_path())
    cfg.setdefault("enabled_plugins", {})[name] = value
    save_user_config(cfg, config_path())
    verb = "enabled" if value else "disabled"
    print(f"Plugin {name} {verb}. Run 'agent-notes install' to apply.")


def _list() -> None:
    reg = default_plugin_registry()
    cfg = load_user_config()
    for p in reg.all():
        on = _resolve_enabled(cfg, p)
        mark = "●" if on else "○"
        default_note = "" if _resolve_enabled({}, p) == on else f"  (default: {'on' if p.default else 'off'})"
        print(f"  {mark} {p.name:<16} {p.description}{default_note}")


def _info(name: str) -> None:
    reg = default_plugin_registry()
    if name not in reg.names():
        print(f"Unknown plugin: {name!r}. Known: {', '.join(reg.names())}")
        return
    p = reg.get(name)
    print(f"{p.name} — {p.description}")
    print(f"  default:  {'on' if p.default else 'off'}")
    print(f"  skills:   {', '.join(p.skills) or '—'}")
    print(f"  includes: {', '.join(p.includes) or '—'}")
    print(f"  hooks:    {', '.join(h.event for h in p.hooks) or '—'}")
    print(f"  allow:    {', '.join(a.value for a in p.allow) or '—'}")


def plugins(action: str, name: Optional[str] = None) -> None:
    if action == "list":
        _list()
    elif action == "enable" and name:
        _set_enabled(name, True)
    elif action == "disable" and name:
        _set_enabled(name, False)
    elif action == "info" and name:
        _info(name)
    else:
        print("usage: agent-notes plugins {list | enable <name> | disable <name> | info <name>}")
```

- [ ] **Step 4: Register in `cli.py`**

After the `models` subparser block (~L311), add:
```python
    p_plugins = subparsers.add_parser("plugins", help="Enable or disable agent-notes plugins")
    p_plugins.add_argument("action", nargs="?", default="list",
        choices=["list", "enable", "disable", "info"], help="Action (default: list)")
    p_plugins.add_argument("name", nargs="?", help="Plugin name (for enable/disable/info)")
```
In `main()`, after the `models` elif (~L389), add:
```python
    elif args.command == "plugins":
        from .commands.plugins import plugins
        plugins(args.action, getattr(args, "name", None))
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/unit/commands/test_plugins_command.py -v`
Expected: PASS (4 tests).

- [ ] **Step 6: Smoke-test the CLI + full suite + dist**

Run:
```bash
agent-notes plugins list          # empty until Task 5 ships a manifest — prints nothing, exit 0
uv run pytest tests/ -q
bash scripts/dev/verify_dist_equiv.sh   # REAL checksum gate vs branch point — NEVER `git diff` dist/ (gitignored, always empty)
```
Expected: suite green; dist byte-identical.

- [ ] **Step 7: Commit**

```bash
git add agent_notes/commands/plugins.py agent_notes/cli.py tests/unit/commands/test_plugins_command.py
git commit -m "#34 feat(plugins): add plugins list/enable/disable/info command"
```

---

### Task 3: Route declarative surfaces through the registry (#35)

Route **skills** and **includes** through `registry.enabled(config)`, additively, while keeping a temporary bridge for subsystems not yet converted (cost-report include, memory skills). The equivalence gate is the proof.

**Files:**
- Modify: `agent_notes/services/installer.py:172` (skill filter → registry-aware)
- Modify: `agent_notes/services/rendering.py:329-330,449-450` (include skip-set → registry-aware, bridged)
- Create: `agent_notes/registries/plugin_registry.py` — add `contributed_includes(config)` helper (see below)
- Test: `tests/unit/registries/test_plugin_equivalence.py`

**Interfaces:**
- Consumes: `default_plugin_registry()`, `Plugin.skills`, `Plugin.includes`, existing `memory.install.filter_skills_by_backend`, existing `cost.render.include_skip`.
- Produces: `plugin_registry.py` → `PluginRegistry.owned_includes() -> set[str]` (every include named by any plugin) and `.active_includes(config) -> set[str]` (includes named by *enabled* plugins). The render skip-set becomes `owned_includes() - active_includes(config)` **unioned with** the legacy bridge set, until each subsystem converts.

- [ ] **Step 1: Write the equivalence gate test first**

```python
# tests/unit/registries/test_plugin_equivalence.py
import subprocess, os, sys
from pathlib import Path


def test_default_build_is_byte_identical_to_branch_point(tmp_path):
    """Building with the default plugin set must not change dist.

    Builds into a worktree at the merge-base and diffs. Skips cleanly if the
    repo has uncommitted dist churn from an in-progress task.
    """
    repo = Path(__file__).resolve().parents[3]
    env = dict(os.environ, XDG_CONFIG_HOME=str(repo / "tests/fixtures/state-local"))
    subprocess.run([sys.executable, "-m", "agent_notes", "build"], cwd=repo, env=env, check=True)
    diff = subprocess.run(["git", "diff", "--stat", "agent_notes/dist/"],
                          cwd=repo, capture_output=True, text=True)
    assert diff.stdout.strip() == "", f"dist drifted:\n{diff.stdout}"
```

(If the suite already has a dist-equivalence check with a pinned fixture, extend that instead of duplicating; keep one canonical gate.)

- [ ] **Step 2: Run it — should pass now (baseline), and must keep passing after the wiring change**

Run: `uv run pytest tests/unit/registries/test_plugin_equivalence.py -v`
Expected: PASS against current dist.

- [ ] **Step 3: Add the include helpers to the registry**

```python
    # in PluginRegistry
    def owned_includes(self) -> set:
        out = set()
        for p in self._plugins:
            out.update(p.includes)
        return out

    def active_includes(self, config: dict) -> set:
        out = set()
        for p in self.enabled(config):
            out.update(p.includes)
        return out
```

- [ ] **Step 4: Bridge the render skip-set**

In `agent_notes/services/rendering.py`, replace both `include_skip(user_config)` call sites (~L329-330 and ~L449-450) with a single local helper that composes plugin ownership with the legacy cost bridge:

```python
def _plugin_include_skip(user_config: dict) -> set:
    from ..registries.plugin_registry import default_plugin_registry
    from ..cost.render import include_skip as _legacy_cost_skip
    reg = default_plugin_registry()
    # additive: skip any owned include that no enabled plugin activates
    skip = reg.owned_includes() - reg.active_includes(user_config)
    # legacy bridge — cost-report is not a plugin yet (#37); honor the old flag
    # so `cost_reporting` stays skipped by default. Removed in #37.
    skip |= _legacy_cost_skip(user_config)
    return skip
```

Use `_plugin_include_skip(user_config)` / `_plugin_include_skip(_ucfg)` in place of the two `_cost_include_skip(...)` calls. Leave `cost.render.include_skip` in place — Task 5 removes it.

- [ ] **Step 5: Bridge the skill filter**

In `agent_notes/services/installer.py:172`, keep `filter_skills_by_backend` (memory conversion is #39) but additionally drop any skill *owned by a disabled plugin*. Since no plugin owns a skill yet, this is a no-op today but establishes the path:

```python
    skills = _filter_skills_by_backend(default_skill_registry().all(), memory_backend)
    from ..registries.plugin_registry import default_plugin_registry
    _preg = default_plugin_registry()
    _disabled_owned = set()
    for _p in _preg.all():
        if _p not in _preg.enabled(load_user_config()):
            _disabled_owned.update(_p.skills)
    skills = [s for s in skills if s.name not in _disabled_owned]
```
(Import `load_user_config` at the call site if not already in scope.)

- [ ] **Step 6: Run the equivalence gate + full suite**

Run:
```bash
uv run pytest tests/unit/registries/test_plugin_equivalence.py -v
uv run pytest tests/ -q
bash scripts/dev/verify_dist_equiv.sh   # REAL checksum gate vs branch point — NEVER `git diff` dist/ (gitignored, always empty)
# (the checksum script above already pins XDG_CONFIG_HOME for both builds)
```
Expected: all green; both dist builds byte-identical. **If dist drifts, stop** — the additive/bridge logic is wrong; do not suppress the diff.

- [ ] **Step 7: Commit**

```bash
git add agent_notes/registries/plugin_registry.py agent_notes/services/rendering.py \
        agent_notes/services/installer.py tests/unit/registries/test_plugin_equivalence.py
git commit -m "#35 refactor(plugins): route skills and includes through the plugin registry"
```

---

### Task 4: Route hooks and allow-entries through the registry (#36)

Replace the hardcoded per-subsystem hook installs with one loop over resolved plugin state, composed with `backend.supports(...)`. **Disable uninstalls.** cost-report's Stop hook still installs the same way today because cost-report becomes a plugin in Task 5 — until then this task changes structure, not the installed set, so dist and settings stay identical.

**Files:**
- Modify: `agent_notes/services/installer.py:180-202` (`_install_session_hook`) and `:223-235` (`_uninstall_session_hook`)
- Test: `tests/unit/services/test_plugin_install.py`

**Interfaces:**
- Consumes: `default_plugin_registry()`, `Plugin.hooks`, `Plugin.allow`, `PluginHook.{event,command,matcher,requires}`, `PluginAllow.{value,requires}`, existing `install_hook/remove_hook/install_allow_entry/remove_allow_entry`, `backend.supports(cap)`.
- Produces: a module-level helper `_apply_plugin_settings(settings_path, backend, config)` in `installer.py` that installs enabled plugins' hooks/allow and removes disabled ones, both gated by `backend.supports(requires)`.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/services/test_plugin_install.py
from pathlib import Path
import json
import agent_notes.services.installer as installer
from agent_notes.domain.plugin import Plugin, PluginHook, PluginAllow
from agent_notes.registries.plugin_registry import PluginRegistry


class _Backend:
    def supports(self, cap): return cap in {"stop_hook", "allow_entries"}


def _reg():
    return PluginRegistry([
        Plugin(name="cost-report", description="c", default=False, path=Path("."),
               hooks=(PluginHook(event="Stop", command="agent-notes cost-report", requires="stop_hook"),),
               allow=(PluginAllow(value="Bash(agent-notes cost-report)", requires="allow_entries"),)),
    ])


def test_enabled_plugin_installs_hook(tmp_path, monkeypatch):
    settings = tmp_path / "settings.json"; settings.write_text("{}")
    monkeypatch.setattr(installer, "default_plugin_registry", _reg)
    installer._apply_plugin_settings(settings, _Backend(), {"enabled_plugins": {"cost-report": True}})
    data = json.loads(settings.read_text())
    assert any("cost-report" in json.dumps(h) for h in data.get("hooks", {}).get("Stop", []))


def test_disabled_plugin_removes_hook(tmp_path, monkeypatch):
    settings = tmp_path / "settings.json"
    monkeypatch.setattr(installer, "default_plugin_registry", _reg)
    installer._apply_plugin_settings(settings, _Backend(), {"enabled_plugins": {"cost-report": True}})
    installer._apply_plugin_settings(settings, _Backend(), {"enabled_plugins": {"cost-report": False}})
    data = json.loads(settings.read_text())
    assert not any("cost-report" in json.dumps(h) for h in data.get("hooks", {}).get("Stop", []))
```

(Match the exact `settings.json` hook shape `install_hook` writes — read `services/settings_writer.py` for the schema and adjust the assertion accordingly. The behavioral contract is: enabled → present, disabled → absent.)

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/services/test_plugin_install.py -v`
Expected: FAIL — `_apply_plugin_settings` does not exist.

- [ ] **Step 3: Write `_apply_plugin_settings` and call it**

```python
def _apply_plugin_settings(settings_path, backend, config) -> None:
    from .settings_writer import (
        install_hook, remove_hook, install_allow_entry, remove_allow_entry,
    )
    from ..registries.plugin_registry import default_plugin_registry
    reg = default_plugin_registry()
    enabled = set(p.name for p in reg.enabled(config))
    for p in reg.all():
        on = p.name in enabled
        for h in p.hooks:
            if h.requires and not backend.supports(h.requires):
                continue
            if on:
                install_hook(settings_path, h.event, h.command, matcher=h.matcher)
            else:
                remove_hook(settings_path, h.event, h.command)
        for a in p.allow:
            if a.requires and not backend.supports(a.requires):
                continue
            (install_allow_entry if on else remove_allow_entry)(settings_path, a.value)
```

Call `_apply_plugin_settings(settings_path, backend, load_user_config())` inside `_install_session_hook` right after the existing hook installs, and inside `_uninstall_session_hook` remove all plugin contributions (call with an all-disabled view, or a dedicated `_remove_all_plugin_settings`). **Do not yet delete** the hardcoded `install_hook(..., "Stop", Hooks.COST_REPORT)` — Task 5 moves it into cost-report's manifest and deletes the hardcoded line in the same commit, so the two never both install it. To avoid a double-install in this task, guard the hardcoded line behind `if not _preg.get_if_exists("cost-report")` — simplest is: Task 4 adds the loop but cost-report has no manifest yet (arrives in Task 5), so the loop installs nothing and the hardcoded line still owns the Stop hook. Confirm no double-install by asserting the Stop hook appears exactly once after a normal install.

- [ ] **Step 4: Run tests + confirm single-install**

Run:
```bash
uv run pytest tests/unit/services/test_plugin_install.py -v
uv run pytest tests/ -q
```
Expected: green. Manually assert the Stop hook count is 1 after `_install_session_hook` on a scratch settings file.

- [ ] **Step 5: Commit**

```bash
git add agent_notes/services/installer.py tests/unit/services/test_plugin_install.py
git commit -m "#36 refactor(plugins): install and uninstall plugin hooks and allow-entries via registry"
```

---

### Task 5: Convert cost-report to a plugin (#37)

Ship the first real manifest. cost-report now *owns* the `cost_reporting` include and the Stop hook. Delete the legacy bridges. Migrate the old `cost_report_enabled` config key.

**Files:**
- Create: `agent_notes/data/plugins/cost-report/plugin.yaml`
- Modify: `agent_notes/services/installer.py` (delete the hardcoded `install_hook(..., "Stop", Hooks.COST_REPORT)` and its uninstall/allow counterparts — now driven by the manifest via Task 4's loop)
- Modify: `agent_notes/services/rendering.py` (drop the legacy cost bridge from `_plugin_include_skip`)
- Modify: `agent_notes/cost/cost_report.py:67` (read plugin state, not `cost_report_enabled`)
- Modify: `agent_notes/commands/config.py:625-635` (`cost_report_toggle` delegates to plugin enable/disable, or is removed with a pointer)
- Delete: `agent_notes/cost/render.py` (its only fn `include_skip` is now unused)
- Modify: `agent_notes/services/user_config.py` (one-shot migration `cost_report_enabled` → `enabled_plugins.cost-report`)
- Test: update `tests/unit/cost/` and add a migration test

**Interfaces:**
- Consumes: everything from Tasks 1–4.
- Produces: `user_config.load_user_config` transparently migrates the legacy key on read; `cost_report.main` gates on `enabled_plugins.cost-report`.

- [ ] **Step 1: Write the manifest**

```yaml
# agent_notes/data/plugins/cost-report/plugin.yaml
name: cost-report
description: Emit a per-session token cost report at the Stop hook
default: off
includes: [cost_reporting]
hooks:
  - {event: Stop, command: "agent-notes cost-report", requires: stop_hook}
allow:
  - {value: "Bash(agent-notes cost-report)", requires: allow_entries}
```

- [ ] **Step 2: Write the migration test (failing)**

```python
# tests/unit/services/test_cost_report_plugin_migration.py
from agent_notes.services.user_config import load_user_config


def test_legacy_flag_migrates_to_plugin(tmp_path):
    cfg = tmp_path / "config.yaml"
    cfg.write_text("cost_report_enabled: true\n")
    data = load_user_config(cfg)
    assert data["enabled_plugins"]["cost-report"] is True
    assert "cost_report_enabled" not in data
```

- [ ] **Step 3: Run it — fails**

Run: `uv run pytest tests/unit/services/test_cost_report_plugin_migration.py -v`
Expected: FAIL (no migration yet).

- [ ] **Step 4: Add the one-shot migration in `load_user_config`**

After parsing `data` in `load_user_config`, before returning:
```python
    if "cost_report_enabled" in data:
        data.setdefault("enabled_plugins", {}).setdefault(
            "cost-report", bool(data.pop("cost_report_enabled")))
```
(In-memory migration on read; the file is rewritten in the new form the next time `save_user_config` runs — e.g. via `plugins enable/disable` or the wizard.)

- [ ] **Step 5: Remove the bridges and hardcoded Stop hook**

- In `rendering.py` `_plugin_include_skip`, delete the two legacy-cost-bridge lines and the `_legacy_cost_skip` import. The skip-set is now purely `owned_includes() - active_includes(config)`.
- In `installer.py`, delete the hardcoded `install_hook(settings_path, "Stop", Hooks.COST_REPORT)`, its `remove_hook` counterpart, and the `Bash(agent-notes cost-report)` allow lines — Task 4's loop now installs them from the manifest.
- In `cost/cost_report.py:67`, replace `load_user_config().get("cost_report_enabled", False)` with a plugin check:
  ```python
  from ..registries.plugin_registry import default_plugin_registry
  cfg = load_user_config()
  if not any(p.name == "cost-report" for p in default_plugin_registry().enabled(cfg)):
      print("Cost reporting is disabled. Enable with: agent-notes plugins enable cost-report")
      return 0
  ```
- In `config.py` `cost_report_toggle`, delegate: `from .plugins import plugins; plugins("enable" if value == "on" else "disable", "cost-report")` (or remove the action and update the `config` choices list + help to point at `agent-notes plugins`).
- Delete `agent_notes/cost/render.py` and update any import of `include_skip`.

- [ ] **Step 6: Update cost tests to assert via plugin state**

In `tests/unit/cost/`, replace assertions that set `cost_report_enabled` with `enabled_plugins: {cost-report: true/false}`. Keep `Hooks.COST_REPORT` byte-identical assertions.

- [ ] **Step 7: Run everything + both dist expectations**

Run:
```bash
uv run pytest tests/ -q
# default (cost-report off) → byte-identical to today
bash scripts/dev/verify_dist_equiv.sh   # REAL checksum gate vs branch point — NEVER `git diff` dist/ (gitignored, always empty)
```
Expected: suite green; **dist byte-identical with cost-report disabled** (today's default — the checksum script compares HEAD-with-cost-report-disabled against the `7af1310` baseline and must report BYTE-IDENTICAL). Then verify the *enabled* path deliberately changes output. `git diff` cannot show it (dist is gitignored), so grep the built artifact for the include's content:
```bash
agent-notes plugins enable cost-report
agent-notes build
grep -rl "cost" agent_notes/dist/claude/agents/ | head   # cost_reporting include now present in built agents — expected
agent-notes plugins disable cost-report && agent-notes build   # restore default output
```

- [ ] **Step 8: Verify disable uninstalls the Stop hook (the headline fix)**

```bash
# on a scratch settings file via the install path, enable then disable, assert the
# Stop hook 'agent-notes cost-report' is absent afterward.
uv run pytest tests/unit/services/test_plugin_install.py -v
```

- [ ] **Step 9: Commit**

```bash
git add agent_notes/data/plugins/cost-report/ agent_notes/services/installer.py \
        agent_notes/services/rendering.py agent_notes/cost/cost_report.py \
        agent_notes/commands/config.py agent_notes/services/user_config.py \
        tests/unit/cost/ tests/unit/services/test_cost_report_plugin_migration.py
git rm agent_notes/cost/render.py
git commit -m "#37 refactor(cost): make cost-report a plugin; disable now uninstalls its hook"
```

---

## Self-Review

**1. Spec coverage.** #33 → Task 1 (+ config resolution). #34 → Task 2. #35 → Task 3 (skills + includes routed; deletions correctly deferred to #37/#39 per the noted correction). #36 → Task 4 (hooks + allow, disable-uninstalls). #37 → Task 5 (manifest, bridge removal, migration, both dist expectations). #38/#39/#40/#41 explicitly out of scope, deferred to a follow-up plan — stated in Scope.

**2. Placeholder scan.** No "TBD"/"handle edge cases"/"similar to Task N". Two intentional read-and-match instructions (Task 4 Step 1: match the `settings.json` hook schema in `settings_writer.py`; Task 3 Step 1: reuse an existing dist gate if present) are pointers to real code the engineer must read, not placeholders — the behavioral contract is stated regardless.

**3. Type consistency.** `Plugin` / `PluginHook` / `PluginAllow` field names identical across Tasks 1, 2, 4, 5. `enabled(config)`, `owned_includes()`, `active_includes(config)` used consistently. `_apply_plugin_settings(settings_path, backend, config)` signature matches between definition (Task 4) and callers. `default_plugin_registry` monkeypatched at the module where it's imported in each test.

**Known risk carried into execution:** the exact `settings.json` hook JSON shape (Task 4) and the precise current default skill/include set (Task 3 equivalence) are verified empirically by the equivalence gate and the install tests, not asserted blind here. If either drifts, the gate fails loudly — which is the intended safety behavior, not a plan gap.
