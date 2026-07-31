# Wizard Capability Framework — Phase 1 (Capability machinery + cost-report migration)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Introduce the capability abstraction (a `Capability` data type + a code-side view/process registry) and prove it end-to-end by migrating the **cost-report toggle** from its hardcoded wizard step (`_select_cost_report`) to a registry-driven one — with no change in behavior.

**Architecture:** Manifests/kinds stay pure data (`domain/capability.py`); behavior (the wizard screen + install action) is registered in code (`commands/wizard/capability_registry.py`). Phase 1 registers exactly one capability — `cost-report` (kind `toggle`) — and routes the wizard's step 8 through a `collect_toggle_selections` runner that enumerates registered toggle capabilities. The other 8 steps stay imperative; later phases migrate them.

**Tech Stack:** Python 3.11+, frozen dataclasses, pytest, `uv`.

**This is Phase 1 of 6.** Phases 2–6 (memory provider slot, backends, dynamic numbering + confirm, docs) get their own plans, written against the real interfaces this phase produces. Each phase is byte-identical for equivalent selections.

## Global Constraints

- **Byte-identical dist for equivalent selections.** The wizard collects input; it does not change `build`/rendering. Verify with `scripts/dev/verify_dist_equiv.sh 2a2261f` (dist must be unchanged). Never `git diff` on `agent_notes/dist/` (gitignored).
- **The wizard test suite is the behavioral gate.** All existing wizard tests must stay green: `tests/unit/commands/test_wizard_*.py` (10 files) and `tests/functional/commands/test_wizard_happy_path.py`. Full suite baseline: **1888 passed**.
- **Capability kinds are exactly** `backend | provider | toggle | core`. No fifth kind.
- **Kind-jargon stays internal.** The cost-report step keeps its existing user-facing copy ("Enable per-response cost report?") — users never see the word "toggle".
- **Stability integration:** any enumeration of toggle *plugins* goes through `plugin_registry` (already stability-aware); the capability registry is code-side and holds only registered capabilities.
- **Effective-state equivalence for cost-report:** choosing "No" must leave cost-report disabled and "Yes" enabled, producing the same build/dist as today. Persisted config key moves from `cost_report_enabled` to `enabled_plugins["cost-report"]` (the modern key cost-report already uses) — this is an intended config-shape change, not a dist change.
- **Commits:** conventional, ticket `#40`, title-only, **no AI attribution**.
- **Sandbox available** for manual spot-checks: `$SB/an` where `SB=/private/tmp/claude-501/-Users-en3e-code-rubakas-agent-notes/651b6910-57f6-4c05-b90b-85bf32637769/scratchpad/sandbox` (never touches the real environment).

---

### Task 1: `Capability` domain type

**Files:**
- Create: `agent_notes/domain/capability.py`
- Test: `tests/unit/domain/test_capability.py`

**Interfaces:**
- Produces: `Capability(name, kind, default=False, order=0)`; kind constants `KIND_BACKEND/PROVIDER/TOGGLE/CORE`; `CAPABILITY_KINDS`.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/domain/test_capability.py
import pytest
from agent_notes.domain.capability import (
    Capability, KIND_BACKEND, KIND_PROVIDER, KIND_TOGGLE, KIND_CORE,
)


def test_each_kind_constructs():
    for kind in (KIND_BACKEND, KIND_PROVIDER, KIND_TOGGLE, KIND_CORE):
        assert Capability(name="x", kind=kind).kind == kind


def test_defaults():
    c = Capability(name="cost-report", kind=KIND_TOGGLE)
    assert c.default is False and c.order == 0


def test_unknown_kind_rejected():
    with pytest.raises(ValueError):
        Capability(name="x", kind="widget")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/domain/test_capability.py -v`
Expected: FAIL — `ModuleNotFoundError: agent_notes.domain.capability`

- [ ] **Step 3: Implement**

```python
# agent_notes/domain/capability.py
"""Capability: a configurable unit the install wizard composes.

Kinds:
- backend  — multi-select AI-provider (claude/codex/...); generates dist/<name>/
- provider — single-select slot (memory: local/obsidian); exactly one active
- toggle   — on/off subsystem (cost-report); can be disabled
- core     — always installed, never shown (credential guard)

Pure data. Behavior (wizard view + install process) lives in the code-side
capability registry, keyed by capability name.
"""
from __future__ import annotations

from dataclasses import dataclass

KIND_BACKEND = "backend"
KIND_PROVIDER = "provider"
KIND_TOGGLE = "toggle"
KIND_CORE = "core"
CAPABILITY_KINDS = frozenset({KIND_BACKEND, KIND_PROVIDER, KIND_TOGGLE, KIND_CORE})


@dataclass(frozen=True)
class Capability:
    name: str
    kind: str
    default: bool = False   # toggle default-on / backend default-selected
    order: int = 0          # tie-break within a wizard phase

    def __post_init__(self):
        if self.kind not in CAPABILITY_KINDS:
            raise ValueError(
                f"Invalid capability kind {self.kind!r} for {self.name!r}; "
                f"expected one of {sorted(CAPABILITY_KINDS)}"
            )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/domain/test_capability.py -v`
Expected: PASS (3)

- [ ] **Step 5: Commit**

```bash
git add agent_notes/domain/capability.py tests/unit/domain/test_capability.py
git commit -m "#40 feat(wizard): add Capability domain type with four kinds"
```

---

### Task 2: Code-side capability registry

**Files:**
- Create: `agent_notes/commands/wizard/capability_registry.py`
- Test: `tests/unit/commands/test_capability_registry.py`

**Interfaces:**
- Consumes: `Capability` from Task 1.
- Produces: `CapabilityBehaviour(view, process=None)`; `CapabilityRegistry` with `register(capability, *, view, process=None)`, `get(name) -> CapabilityBehaviour`, `capability(name) -> Capability`, `by_kind(kind) -> list[Capability]`, `names() -> list[str]`.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/commands/test_capability_registry.py
import pytest
from agent_notes.domain.capability import Capability, KIND_TOGGLE, KIND_PROVIDER
from agent_notes.commands.wizard.capability_registry import CapabilityRegistry


def _noop_view(step, total, version):
    return None


def test_register_get_and_by_kind():
    reg = CapabilityRegistry()
    cap = Capability(name="cost-report", kind=KIND_TOGGLE)
    reg.register(cap, view=_noop_view)
    assert reg.get("cost-report").view is _noop_view
    assert reg.get("cost-report").process is None
    assert reg.capability("cost-report") is cap
    assert reg.by_kind(KIND_TOGGLE) == [cap]
    assert reg.by_kind(KIND_PROVIDER) == []
    assert reg.names() == ["cost-report"]


def test_duplicate_registration_raises():
    reg = CapabilityRegistry()
    cap = Capability(name="a", kind=KIND_TOGGLE)
    reg.register(cap, view=_noop_view)
    with pytest.raises(ValueError):
        reg.register(cap, view=_noop_view)


def test_unknown_get_raises():
    reg = CapabilityRegistry()
    with pytest.raises(ValueError):
        reg.get("nope")
    with pytest.raises(ValueError):
        reg.capability("nope")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/commands/test_capability_registry.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement**

```python
# agent_notes/commands/wizard/capability_registry.py
"""Code-side registry: capability name -> its wizard view + install process.

Manifests/kinds are pure data (domain.Capability); behavior is registered here
in code. `view(step, total, version)` runs the interactive screen and returns
the collected value. `process` (optional) applies it at install time. Phase 1
uses `view` only; `process` is reserved for later phases.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from ...domain.capability import Capability


@dataclass(frozen=True)
class CapabilityBehaviour:
    view: Callable
    process: Optional[Callable] = None


class CapabilityRegistry:
    def __init__(self) -> None:
        self._entries: dict[str, tuple[Capability, CapabilityBehaviour]] = {}

    def register(self, capability: Capability, *, view, process=None) -> None:
        if capability.name in self._entries:
            raise ValueError(f"Capability {capability.name!r} already registered")
        self._entries[capability.name] = (capability, CapabilityBehaviour(view, process))

    def get(self, name: str) -> CapabilityBehaviour:
        try:
            return self._entries[name][1]
        except KeyError:
            raise ValueError(f"No behaviour registered for capability {name!r}")

    def capability(self, name: str) -> Capability:
        try:
            return self._entries[name][0]
        except KeyError:
            raise ValueError(f"No capability {name!r} registered")

    def by_kind(self, kind: str) -> list[Capability]:
        return [cap for cap, _ in self._entries.values() if cap.kind == kind]

    def names(self) -> list[str]:
        return list(self._entries)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/commands/test_capability_registry.py -v`
Expected: PASS (3)

- [ ] **Step 5: Commit**

```bash
git add agent_notes/commands/wizard/capability_registry.py tests/unit/commands/test_capability_registry.py
git commit -m "#40 feat(wizard): add code-side capability registry (view/process)"
```

---

### Task 3: Register cost-report as a toggle capability + a toggle-selection runner

**Files:**
- Create: `agent_notes/commands/wizard/capabilities.py`
- Test: `tests/unit/commands/test_toggle_capabilities.py`

**Interfaces:**
- Consumes: `Capability`/`KIND_TOGGLE` (Task 1), `CapabilityRegistry` (Task 2), the existing `_select_cost_report` (`commands/wizard/cost_report.py`).
- Produces: `default_capability_registry() -> CapabilityRegistry` (cached, cost-report registered); `collect_toggle_selections(step, total, version, registry=None) -> dict[str, bool]` running each registered toggle capability's view in registration order, returning `{name: bool}`.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/commands/test_toggle_capabilities.py
from agent_notes.domain.capability import Capability, KIND_TOGGLE
from agent_notes.commands.wizard.capability_registry import CapabilityRegistry
from agent_notes.commands.wizard.capabilities import (
    default_capability_registry, collect_toggle_selections,
)


def test_cost_report_registered_as_toggle():
    reg = default_capability_registry()
    names = [c.name for c in reg.by_kind(KIND_TOGGLE)]
    assert "cost-report" in names


def test_collect_runs_each_toggle_view():
    reg = CapabilityRegistry()
    calls = []

    def view_a(step, total, version):
        calls.append(("a", step, total))
        return True

    def view_b(step, total, version):
        calls.append(("b", step, total))
        return False

    reg.register(Capability(name="a", kind=KIND_TOGGLE), view=view_a)
    reg.register(Capability(name="b", kind=KIND_TOGGLE), view=view_b)

    result = collect_toggle_selections(step=8, total=9, version="x", registry=reg)
    assert result == {"a": True, "b": False}
    assert calls == [("a", 8, 9), ("b", 8, 9)]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/commands/test_toggle_capabilities.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement**

```python
# agent_notes/commands/wizard/capabilities.py
"""Registration of the built-in capabilities and the per-kind selection runners.

Phase 1 registers only the cost-report toggle. `collect_toggle_selections`
runs every registered toggle capability's view and returns {name: enabled}.
"""
from __future__ import annotations

from functools import lru_cache

from ...domain.capability import Capability, KIND_TOGGLE
from .capability_registry import CapabilityRegistry
from .cost_report import _select_cost_report

COST_REPORT = Capability(name="cost-report", kind=KIND_TOGGLE, default=False)


def _cost_report_view(step, total, version) -> bool:
    return _select_cost_report(step=step, total=total, version=version)


def _build_registry() -> CapabilityRegistry:
    reg = CapabilityRegistry()
    reg.register(COST_REPORT, view=_cost_report_view)
    return reg


@lru_cache(maxsize=1)
def default_capability_registry() -> CapabilityRegistry:
    return _build_registry()


def collect_toggle_selections(step, total, version, registry=None) -> dict:
    """Run every registered toggle capability's view; return {name: enabled}."""
    reg = registry if registry is not None else default_capability_registry()
    result: dict = {}
    for cap in reg.by_kind(KIND_TOGGLE):
        result[cap.name] = reg.get(cap.name).view(step, total, version)
    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/commands/test_toggle_capabilities.py -v`
Expected: PASS (2)

- [ ] **Step 5: Commit**

```bash
git add agent_notes/commands/wizard/capabilities.py tests/unit/commands/test_toggle_capabilities.py
git commit -m "#40 feat(wizard): register cost-report toggle capability and a toggle runner"
```

---

### Task 4: Route the wizard's step 8 through the toggle runner (byte-identical)

Replace the orchestrator's hardcoded `_select_cost_report` call with `collect_toggle_selections`, thread `enabled_plugins` into `_execute_install`, and persist it under `enabled_plugins["cost-report"]`. Behavior (same prompt at step 8, same effective enable/disable) is unchanged.

**Files:**
- Modify: `agent_notes/commands/wizard/orchestrator.py` (the step-8 block + the `_execute_install(...)` call — see extracted lines ~84–88 and ~118–138)
- Modify: `agent_notes/commands/wizard/execute.py` (`_execute_install` signature + the `cost_report_enabled` persistence block, ~278–285)
- Test: extend `tests/unit/commands/test_wizard_orchestrator_skip.py` or add `tests/unit/commands/test_wizard_toggle_step.py`

**Interfaces:**
- Consumes: `collect_toggle_selections` (Task 3).
- Produces: `_execute_install(..., enabled_plugins: dict = None)` replacing the `cost_report_enabled: bool` parameter.

- [ ] **Step 1: Locate the exact call sites**

Confirm in the working tree (line numbers may have drifted): in `orchestrator.py`, the block
```python
    # Step 8: Cost report
    from .cost_report import _select_cost_report
    cost_report_enabled = _select_cost_report(step=8, total=TOTAL_STEPS, version=version)
```
and the trailing `_execute_install(..., cost_report_enabled=cost_report_enabled,)`. In `execute.py`, the `cost_report_enabled: bool = False` parameter and the persistence block that writes `_ucfg["cost_report_enabled"] = cost_report_enabled`. Find every other caller of `_execute_install` (`grep -rn "_execute_install" agent_notes tests`).

- [ ] **Step 2: Write the failing test**

```python
# tests/unit/commands/test_wizard_toggle_step.py
from agent_notes.commands.wizard import execute as execute_mod
import inspect


def test_execute_install_takes_enabled_plugins_not_cost_report_flag():
    sig = inspect.signature(execute_mod._execute_install)
    assert "enabled_plugins" in sig.parameters
    assert "cost_report_enabled" not in sig.parameters


def test_orchestrator_uses_toggle_runner(monkeypatch):
    # The orchestrator's step 8 must call collect_toggle_selections, not the
    # bespoke _select_cost_report directly.
    import agent_notes.commands.wizard.orchestrator as orch
    src = inspect.getsource(orch._interactive_install)
    assert "collect_toggle_selections" in src
    assert "_select_cost_report" not in src
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/unit/commands/test_wizard_toggle_step.py -v`
Expected: FAIL — `_execute_install` still has `cost_report_enabled`; orchestrator still calls `_select_cost_report`.

- [ ] **Step 4: Rewire the orchestrator step 8**

In `orchestrator.py`, replace the step-8 block with:
```python
    # Step 8: Toggle plugins (cost-report, plus any future toggle) — registry-driven
    from .capabilities import collect_toggle_selections
    enabled_plugins = collect_toggle_selections(step=8, total=TOTAL_STEPS, version=version)
```
and change the final call from `cost_report_enabled=cost_report_enabled,` to `enabled_plugins=enabled_plugins,`.

- [ ] **Step 5: Update `_execute_install`**

In `execute.py`, replace the `cost_report_enabled: bool = False` parameter with `enabled_plugins: dict = None`, and replace the persistence block with:
```python
    # Persist enabled-plugins selections (cost-report and any future toggle)
    if enabled_plugins:
        try:
            from ...services.user_config import load_user_config as _load_user_config, save_user_config as _save_user_config
            _ucfg = _load_user_config()
            _ucfg.setdefault("enabled_plugins", {}).update(
                {name: bool(on) for name, on in enabled_plugins.items()}
            )
            _save_user_config(_ucfg)
        except Exception as e:
            print(f"{Color.YELLOW}Warning: failed to save plugin preferences: {e}{Color.NC}")
```
Update any other `_execute_install` caller found in Step 1 to pass `enabled_plugins` (a non-interactive caller may pass `None` or `{}`).

- [ ] **Step 6: Run the focused test + the whole wizard suite**

Run:
```bash
uv run pytest tests/unit/commands/test_wizard_toggle_step.py -v
uv run pytest tests/unit/commands/test_wizard_*.py tests/functional/commands/test_wizard_happy_path.py -v
```
Expected: PASS. If a wizard test asserted on `cost_report_enabled` plumbing, update it to the `enabled_plugins` shape (the behavior it checks — cost-report on/off — is unchanged).

- [ ] **Step 7: Full suite + byte-identity**

Run:
```bash
uv run pytest tests/
scripts/dev/verify_dist_equiv.sh 2a2261f
```
Expected: green; **BYTE-IDENTICAL** (the wizard change does not touch `build`/rendering).

- [ ] **Step 8: Manual sandbox spot-check (non-blocking evidence)**

The wizard is interactive; the automated gate above is authoritative. Optionally, confirm the toggle path in the sandbox by running a build there and confirming cost-report state round-trips via config:
```bash
$SB/an config cost-report on && $SB/an plugins list | grep cost-report
```
(This exercises the plugin path the wizard now writes to, in isolation.)

- [ ] **Step 9: Commit**

```bash
git add agent_notes/commands/wizard/orchestrator.py agent_notes/commands/wizard/execute.py tests/unit/commands/test_wizard_toggle_step.py
git commit -m "#40 refactor(wizard): route cost-report through the toggle capability runner"
```

---

## Self-Review

**Spec coverage (Phase 1 scope):** introduces the `Capability` type (Task 1), the code-side view/process registry (Task 2), the first registered toggle capability + runner (Task 3), and migrates cost-report off its hardcoded step (Task 4). The spec's "skeleton" is delivered incrementally-with-a-real-consumer rather than as unused scaffolding (avoids the premature-abstraction risk the `devil` flagged) — the `Capability`/registry types arrive with cost-report as their first user.

**Deferred to later phases (documented, not omissions):** `WizardContext`/full composer, memory provider slot migration, backend migration, dynamic `TOTAL_STEPS`, and confirm-screen composition. Phase 1 keeps `TOTAL_STEPS = 9` and all other steps imperative.

**Placeholder scan:** none — every step has real code.

**Type consistency:** `Capability(name, kind, default, order)`, `CapabilityRegistry.register(capability, *, view, process)`, `collect_toggle_selections(step, total, version, registry=None) -> dict`, `_execute_install(..., enabled_plugins: dict = None)` are used consistently across tasks.

**Risk:** the only behavioral touch is Task 4 (execute's persistence key `cost_report_enabled` → `enabled_plugins`). Mitigation: the wizard suite + full suite are the gate, `verify_dist_equiv` confirms dist is untouched, and cost-report's effective on/off is unchanged (same prompt, same resulting plugin state).

## Execution Handoff

Two options — recommend **Subagent-Driven** (fresh subagent per task, two-stage review, byte-identity gate per task), matching how Phase 1's four tasks are structured.
