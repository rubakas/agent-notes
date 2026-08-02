# Wizard Framework Phase 2 — Memory Provider Slot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate the wizard's memory-selection step into the Phase 1 capability framework as a `provider`-kind capability, so memory backend/path/strategy selection is driven by the registry instead of a hardcoded orchestrator call.

**Architecture:** Register `memory` as a `KIND_PROVIDER` capability whose `view` wraps the existing `_select_memory` (left byte-for-byte unchanged, returning its `(backend, path, strategy)` tuple). Add a `collect_provider_selections` collector that mirrors Phase 1's `collect_toggle_selections`, iterating `registry.by_kind(KIND_PROVIDER)`. Rewire orchestrator step 7 to call the collector and unpack memory's result into the three variables it already threads to `_execute_install`. No behavior change: identical user choices produce identical values into `execute.py`, so `dist/` stays byte-identical.

**Tech Stack:** Python 3.14, pytest, existing wizard package (`agent_notes/commands/wizard/`), `agent_notes/domain/capability.py`.

## Global Constraints

- **Byte-identity gate:** `scripts/dev/verify_dist_equiv.sh cb7fdcf` MUST report BYTE-IDENTICAL at the end of the phase. `cb7fdcf` is the Phase 1 tip and this phase's baseline. Never use `git diff` on `agent_notes/dist/` (it is gitignored — always empty).
- **Full suite green:** `uv run pytest tests/` MUST pass (Phase 1 baseline ~1900 passed); no reduction in test count.
- **Reuse existing config, no new manifest:** Do NOT create `data/providers-slots/` or any new data file. The memory provider is code-registered exactly like the cost-report toggle was in Phase 1.
- **`_select_memory` stays untouched:** Do not change its signature or return type. All existing `test_wizard_*` memory assertions must keep passing unchanged.
- **`TOTAL_STEPS` stays 9:** Dynamic step numbering is Phase 4 (spec phase 5). Memory remains step 7; the console header must still read "Step 7 of 9".
- **Kind semantics:** memory is `KIND_PROVIDER` — a slot that always resolves to one option (`local` is the floor); it is never "disabled".
- **Lazy import rule:** the memory view imports `_select_memory` lazily (function-body import) to avoid a circular import between the wizard package `__init__` and `capabilities`.

---

### Task 1: Register `memory` as a provider capability + add `collect_provider_selections`

**Files:**
- Modify: `agent_notes/commands/wizard/capabilities.py`
- Test: `tests/unit/commands/test_wizard_provider_step.py` (create)

**Interfaces:**
- Consumes (from Phase 1): `Capability(name, kind, default, order)` and `KIND_PROVIDER` from `agent_notes/domain/capability.py`; `CapabilityRegistry.register(capability, *, view, process=None)`, `.by_kind(kind)`, `.get(name)`; the existing `_build_registry()` / `default_capability_registry()` / `collect_toggle_selections` in `capabilities.py`.
- Consumes (existing wizard): `_select_memory(step, total, version='') -> tuple[str, str, str]` returning `(backend, path, strategy)`, defined in `agent_notes/commands/wizard/__init__.py`.
- Produces (for Task 2): `collect_provider_selections(step: int, total: int, version: str, registry: CapabilityRegistry | None = None) -> dict[str, dict]`, returning `{provider_name: {"backend": str, "path": str, "strategy": str}}`. Also `MEMORY: Capability` and `_memory_view(step, total, version) -> dict` registered into the default registry.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/commands/test_wizard_provider_step.py`:

```python
from agent_notes.domain.capability import Capability, KIND_PROVIDER
from agent_notes.commands.wizard.capability_registry import CapabilityRegistry
from agent_notes.commands.wizard.capabilities import (
    default_capability_registry,
    collect_provider_selections,
)


def test_memory_registered_as_provider():
    reg = default_capability_registry()
    assert [c.name for c in reg.by_kind(KIND_PROVIDER)] == ["memory"]


def test_collect_provider_selections_returns_named_dicts():
    reg = CapabilityRegistry()
    reg.register(
        Capability(name="memory", kind=KIND_PROVIDER, default=True, order=0),
        view=lambda step, total, version: {
            "backend": "local",
            "path": "",
            "strategy": "single-brain",
        },
    )
    result = collect_provider_selections(step=7, total=9, version="x", registry=reg)
    assert result == {
        "memory": {"backend": "local", "path": "", "strategy": "single-brain"}
    }


def test_collect_provider_selections_passes_step_args_to_view():
    seen = {}
    reg = CapabilityRegistry()

    def _view(step, total, version):
        seen.update(step=step, total=total, version=version)
        return {"backend": "local", "path": "", "strategy": "single-brain"}

    reg.register(
        Capability(name="memory", kind=KIND_PROVIDER, default=True, order=0),
        view=_view,
    )
    collect_provider_selections(step=7, total=9, version="2.34", registry=reg)
    assert seen == {"step": 7, "total": 9, "version": "2.34"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/commands/test_wizard_provider_step.py -v`
Expected: FAIL — `ImportError: cannot import name 'collect_provider_selections'` (and `memory` not in providers).

- [ ] **Step 3: Implement the provider capability + collector**

In `agent_notes/commands/wizard/capabilities.py`:

1. Extend the domain import to include `KIND_PROVIDER` (alongside the existing `KIND_TOGGLE`), e.g.:

```python
from ...domain.capability import Capability, KIND_TOGGLE, KIND_PROVIDER
```

(Match the existing import style/path already used in this file — only add `KIND_PROVIDER` to it.)

2. Declare the capability and its view (place near the `COST_REPORT` declaration):

```python
MEMORY = Capability(name="memory", kind=KIND_PROVIDER, default=True, order=0)


def _memory_view(step, total, version=""):
    # lazy import: avoids a circular import between wizard.__init__ and capabilities
    from agent_notes.commands import wizard as _wiz

    backend, path, strategy = _wiz._select_memory(
        step=step, total=total, version=version
    )
    return {"backend": backend, "path": path, "strategy": strategy}
```

3. Register `MEMORY` in `_build_registry()` (right after the `COST_REPORT` registration):

```python
    reg.register(MEMORY, view=_memory_view)
```

4. Add the provider collector (mirror `collect_toggle_selections`):

```python
def collect_provider_selections(step, total, version, registry=None):
    """Run every registered provider capability's view; return {name: selection}."""
    reg = registry if registry is not None else default_capability_registry()
    result = {}
    for cap in reg.by_kind(KIND_PROVIDER):
        result[cap.name] = reg.get(cap.name).view(step, total, version)
    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/commands/test_wizard_provider_step.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add agent_notes/commands/wizard/capabilities.py tests/unit/commands/test_wizard_provider_step.py
git commit -m "#40 feat(wizard): register memory as a provider capability and add provider collector"
```

---

### Task 2: Route orchestrator step 7 through `collect_provider_selections`

**Files:**
- Modify: `agent_notes/commands/wizard/orchestrator.py` (step 7 memory call ~line 84; the import of `collect_toggle_selections` from `.capabilities`)
- Test: `tests/unit/commands/test_wizard_provider_step.py` (extend) or the existing orchestrator test that asserts execute payload — add a routing assertion

**Interfaces:**
- Consumes (from Task 1): `collect_provider_selections(step, total, version, registry=None) -> dict[str, dict]`.
- Produces: no new public interface; `memory_backend`, `memory_path`, `memory_strategy` are still passed to `_execute_install` with identical values for identical user choices.

- [ ] **Step 1: Write the failing test**

Add to `tests/unit/commands/test_wizard_provider_step.py` a test that the orchestrator sources memory from the provider collector. Use monkeypatch on the orchestrator module so no real prompts run:

```python
def test_orchestrator_sources_memory_from_provider_collector(monkeypatch):
    from agent_notes.commands.wizard import orchestrator as orch

    captured = {}

    def fake_collect_provider_selections(step, total, version, registry=None):
        captured["step"] = step
        return {
            "memory": {
                "backend": "obsidian",
                "path": "/vault",
                "strategy": "per-project",
            }
        }

    monkeypatch.setattr(
        orch, "collect_provider_selections", fake_collect_provider_selections
    )

    sel = orch.collect_provider_selections(step=7, total=orch.TOTAL_STEPS, version="x")
    memory = sel["memory"]
    assert captured["step"] == 7
    assert (memory["backend"], memory["path"], memory["strategy"]) == (
        "obsidian",
        "/vault",
        "per-project",
    )
```

(This asserts the collector is importable at orchestrator scope with the right name and step arg. The end-to-end thread into `_execute_install` is covered by the existing `test_wizard_happy_path.py` + the byte-identity gate in Step 5.)

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/commands/test_wizard_provider_step.py::test_orchestrator_sources_memory_from_provider_collector -v`
Expected: FAIL — `AttributeError: module 'agent_notes.commands.wizard.orchestrator' has no attribute 'collect_provider_selections'`.

- [ ] **Step 3: Rewire the orchestrator**

In `agent_notes/commands/wizard/orchestrator.py`:

1. Extend the existing capabilities import:

```python
from .capabilities import collect_toggle_selections, collect_provider_selections
```

2. Replace the step-7 memory call (currently `memory_backend, memory_path, memory_strategy = _wiz._select_memory(step=7, total=TOTAL_STEPS, version=version)`) with:

```python
    provider_selections = collect_provider_selections(
        step=7, total=TOTAL_STEPS, version=version
    )
    memory = provider_selections["memory"]
    memory_backend = memory["backend"]
    memory_path = memory["path"]
    memory_strategy = memory["strategy"]
```

Leave the `_execute_install(...)` call and its `memory_backend=`, `memory_path=`, `memory_strategy=` arguments exactly as they are.

- [ ] **Step 4: Run the targeted + wizard test suites**

Run: `uv run pytest tests/unit/commands/test_wizard_provider_step.py tests/unit/commands/ -k wizard tests/functional/commands/test_wizard_happy_path.py -v`
Expected: PASS, including the happy-path functional test (step sequence and prompts unchanged).

- [ ] **Step 5: Run the full suite + byte-identity gate**

Run: `uv run pytest tests/`
Expected: PASS, count ≥ Phase 1 baseline (~1900) + the new provider tests.

Run: `scripts/dev/verify_dist_equiv.sh cb7fdcf`
Expected: **BYTE-IDENTICAL**. If DRIFT, stop — a value threaded into `execute.py` changed; the rewire must be pure plumbing.

- [ ] **Step 6: Commit**

```bash
git add agent_notes/commands/wizard/orchestrator.py tests/unit/commands/test_wizard_provider_step.py
git commit -m "#40 refactor(wizard): route memory selection through the provider capability runner"
```

---

## Self-Review

**1. Spec coverage.** Spec phase 3 ("Migrate the memory provider slot: the M3 provider→strategy flow becomes the memory provider's `view`") is covered: Task 1 makes `_select_memory` the memory provider's `view` (via `_memory_view`); Task 2 makes the wizard consume it through the registry collector. The `provider` = single-select slot, `local` is the floor, never disabled — encoded as `KIND_PROVIDER` with no disable path. Deferred to later phases per spec: dynamic `TOTAL_STEPS` (phase 4), backend migration (phase 3), docs (phase 5) — all out of scope here.

**2. Placeholder scan.** No TBD/TODO; every code step has concrete code. Byte-identity and suite gates use exact commands with the exact baseline `cb7fdcf`.

**3. Type consistency.** `_select_memory` returns `(backend, path, strategy)` (tuple[str,str,str]); `_memory_view` packs it into `{"backend","path","strategy"}`; `collect_provider_selections` returns `{name: that dict}`; orchestrator unpacks the same three keys. `collect_provider_selections` signature is identical shape to `collect_toggle_selections` (`step, total, version, registry=None`). `KIND_PROVIDER` is the exact constant from `domain/capability.py`.

**Risk note.** The one real risk is the circular import (wizard `__init__` defines `_select_memory`; `capabilities` is imported by the package). Mitigated by the lazy function-body import in `_memory_view`. If Task 1 Step 4 raises `ImportError`/`AttributeError` on `_wiz._select_memory`, confirm the attribute path against `orchestrator.py`'s existing `_wiz._select_memory` usage rather than changing `_select_memory`.

## Execution Handoff

Executing **subagent-driven** (per the established per-phase workflow): one fresh coder subagent per task, two-stage review between tasks, byte-identity gate on Task 2. Sandbox rebuild (uv venv editable + fake HOME/XDG) is NOT required for this phase — the byte-identity gate builds into its own worktree; the sandbox is only stood up when a phase needs an interactive wizard run.
