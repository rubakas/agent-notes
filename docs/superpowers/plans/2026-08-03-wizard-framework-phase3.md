# Wizard Framework Phase 3 — Backend Selection Slot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate the wizard's AI-provider backend-selection step (step 1) into the capability framework as a `KIND_BACKEND` capability, mirroring how Phase 2 migrated memory as a `KIND_PROVIDER`.

**Architecture:** Register a single `backends` capability of kind `backend` whose `view` wraps the existing `_select_cli` (left byte-for-byte unchanged; it already enumerates the CLI registry via `registry.available()`, the stability-filtered pattern the spec requires). Add a `collect_backend_selections` collector mirroring `collect_provider_selections` / `collect_toggle_selections`. Rewire orchestrator step 1 to call the collector. No behavior change: identical user choices yield the identical `clis: Set[str]` into `_execute_install`, so `dist/` stays byte-identical.

**Tech Stack:** Python 3.14, pytest, existing wizard package (`agent_notes/commands/wizard/`), `agent_notes/domain/capability.py`, `agent_notes/registries/cli_registry.py`.

## Global Constraints

- **Byte-identity gate:** `scripts/dev/verify_dist_equiv.sh a8ff35d` MUST report BYTE-IDENTICAL at the end of the phase. `a8ff35d` is the Phase 2 tip and this phase's baseline. Never `git diff` the gitignored `agent_notes/dist/`.
- **Full suite green:** `uv run pytest tests/` MUST pass (Phase 2 baseline 1904 passed); no reduction in count.
- **`_select_cli` stays untouched:** do not change its signature, its `registry.available()` enumeration, or its `Set[str]` return. Its existing tests must keep passing unchanged.
- **Scope = selection only.** Do NOT migrate per-backend model/effort config (`_select_models_per_role`, step 2) — that moves to Phase 4 with the dynamic config-step composition. Do NOT touch `execute.py`, `install_plan.py`, or the intentional claude-specific overrides (orchestrator-role skip, profile `global_home` override).
- **`TOTAL_STEPS` stays 9:** dynamic numbering is Phase 4. Backend selection remains step 1; the console header must still read "Step 1 of 9".
- **Kind semantics:** `backends` is `KIND_BACKEND` — a multi-select selection step; the CLI options themselves live in `cli_registry`, not the capability registry. The capability routes the *step*, not the per-CLI options.
- **Lazy import rule:** the backend view imports the wizard package lazily (function-body import) to avoid a circular import between the wizard package `__init__` and `capabilities`.

---

### Task 1: Register `backends` as a backend capability + add `collect_backend_selections`

**Files:**
- Modify: `agent_notes/commands/wizard/capabilities.py`
- Test: `tests/unit/commands/test_wizard_backend_step.py` (create)

**Interfaces:**
- Consumes (from Phase 1): `Capability(name, kind, default, order)` and `KIND_BACKEND` from `agent_notes/domain/capability.py`; `CapabilityRegistry.register(capability, *, view, process=None)`, `.by_kind(kind)`, `.get(name)`; the existing `_build_registry()` / `default_capability_registry()` in `capabilities.py`.
- Consumes (existing wizard): `_select_cli(step=0, total=0, version='') -> Set[str]` (returns the set of chosen backend names), defined in `agent_notes/commands/wizard/__init__.py`.
- Produces (for Task 2): `collect_backend_selections(step: int, total: int, version: str, registry: CapabilityRegistry | None = None) -> set`, the union of every `KIND_BACKEND` capability's view result. Also `BACKENDS: Capability` and `_backends_view(step, total, version) -> set` registered into the default registry.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/commands/test_wizard_backend_step.py`:

```python
from agent_notes.domain.capability import Capability, KIND_BACKEND
from agent_notes.commands.wizard.capability_registry import CapabilityRegistry
from agent_notes.commands.wizard.capabilities import (
    default_capability_registry,
    collect_backend_selections,
)


def test_backends_registered_as_backend_kind():
    reg = default_capability_registry()
    assert [c.name for c in reg.by_kind(KIND_BACKEND)] == ["backends"]


def test_collect_backend_selections_returns_union_of_views():
    reg = CapabilityRegistry()
    reg.register(
        Capability(name="backends", kind=KIND_BACKEND, default=True, order=0),
        view=lambda step, total, version: {"claude", "codex"},
    )
    result = collect_backend_selections(step=1, total=9, version="x", registry=reg)
    assert result == {"claude", "codex"}


def test_collect_backend_selections_passes_step_args_to_view():
    seen = {}
    reg = CapabilityRegistry()

    def _view(step, total, version):
        seen.update(step=step, total=total, version=version)
        return {"claude"}

    reg.register(
        Capability(name="backends", kind=KIND_BACKEND, default=True, order=0),
        view=_view,
    )
    collect_backend_selections(step=1, total=9, version="2.34", registry=reg)
    assert seen == {"step": 1, "total": 9, "version": "2.34"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/commands/test_wizard_backend_step.py -v`
Expected: FAIL — `ImportError: cannot import name 'collect_backend_selections'`.

- [ ] **Step 3: Implement the backend capability + collector**

In `agent_notes/commands/wizard/capabilities.py`:

1. Add `KIND_BACKEND` to the existing domain-capability import (the line that already imports `KIND_TOGGLE, KIND_PROVIDER`). Only add the name.

2. Declare the capability and its view (place near the `MEMORY` declaration):

```python
# backend slot: always present (the CLI-selection step); options come from cli_registry.available(),
# default=True means "step always runs", not "pre-select every backend"
BACKENDS = Capability(name="backends", kind=KIND_BACKEND, default=True, order=0)


def _backends_view(step, total, version="") -> set:
    # lazy import: avoids a circular import between wizard.__init__ and capabilities
    from agent_notes.commands import wizard as _wiz

    return _wiz._select_cli(step=step, total=total, version=version)
```

3. Register `BACKENDS` in `_build_registry()` (before the `COST_REPORT` / `MEMORY` registrations, so backend is first by insertion for readability — order within a kind is by `.order`):

```python
    reg.register(BACKENDS, view=_backends_view)
```

4. Add the collector (mirror `collect_provider_selections`, but union the sets since backend selection is multi-select):

```python
def collect_backend_selections(step, total, version, registry=None) -> set:
    """Run every registered backend capability's view; return the union of selected names."""
    reg = registry if registry is not None else default_capability_registry()
    selected: set = set()
    for cap in reg.by_kind(KIND_BACKEND):
        selected |= reg.get(cap.name).view(step, total, version)
    return selected
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/commands/test_wizard_backend_step.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add agent_notes/commands/wizard/capabilities.py tests/unit/commands/test_wizard_backend_step.py
git commit -m "#40 feat(wizard): register backend selection as a backend capability and add backend collector"
```

---

### Task 2: Route orchestrator step 1 through `collect_backend_selections`

**Files:**
- Modify: `agent_notes/commands/wizard/orchestrator.py` (step 1 `_select_cli` call ~line 62; the module-scope `from .capabilities import ...` line)
- Test: `tests/unit/commands/test_wizard_backend_step.py` (extend)

**Interfaces:**
- Consumes (from Task 1): `collect_backend_selections(step, total, version, registry=None) -> set`.
- Produces: no new public interface; `clis` is still a `Set[str]` passed to `_execute_install`, identical values for identical choices.

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/commands/test_wizard_backend_step.py`:

```python
def test_collect_backend_selections_importable_at_orchestrator_module_scope():
    from agent_notes.commands.wizard import orchestrator as orch

    assert hasattr(orch, "collect_backend_selections")
    assert orch.TOTAL_STEPS == 9
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/commands/test_wizard_backend_step.py::test_collect_backend_selections_importable_at_orchestrator_module_scope -v`
Expected: FAIL — `AttributeError: module '...orchestrator' has no attribute 'collect_backend_selections'`.

- [ ] **Step 3: Rewire the orchestrator**

In `agent_notes/commands/wizard/orchestrator.py`:

1. Extend the existing module-scope capabilities import to include the new name:

```python
from .capabilities import (
    collect_toggle_selections,
    collect_provider_selections,
    collect_backend_selections,
)
```

(Match the file's current import form — if it is a single line, keep it a single line with the third name appended.)

2. Replace the step-1 call `clis = _wiz._select_cli(step=1, total=TOTAL_STEPS, version=version)` with:

```python
    clis = collect_backend_selections(step=1, total=TOTAL_STEPS, version=version)
```

Leave the `_execute_install(...)` call and its `clis=clis` argument exactly as they are.

- [ ] **Step 4: Run the targeted + wizard test suites**

Run: `uv run pytest tests/unit/commands/test_wizard_backend_step.py tests/unit/commands/ -k wizard tests/functional/commands/test_wizard_happy_path.py -v`
Expected: PASS, including the happy-path functional test (step 1 sequence and prompts unchanged).

- [ ] **Step 5: Run the full suite + byte-identity gate**

Run: `uv run pytest tests/`
Expected: PASS, count ≥ Phase 2 baseline (1904) + the new backend tests.

Run: `scripts/dev/verify_dist_equiv.sh a8ff35d`
Expected: **BYTE-IDENTICAL**. If DRIFT, stop — the `clis` value or enumeration changed; the rewire must be pure plumbing.

- [ ] **Step 6: Commit**

```bash
git add agent_notes/commands/wizard/orchestrator.py tests/unit/commands/test_wizard_backend_step.py
git commit -m "#40 refactor(wizard): route backend selection through the backend capability runner"
```

---

## Self-Review

**1. Spec coverage.** Spec phase 4 has two halves — "backend selection" (this plan) and "per-backend config" (deferred to Phase 4). The deferral is a deliberate refinement: the spec defines config steps as "built dynamically from the selections above, in order," which is Phase 4's dynamic-composition deliverable; migrating per-backend config in Phase 3 would require either a throwaway hardcoded route or building Phase 4's machinery early (speculative). Selection is migrated here via a `KIND_BACKEND` capability whose view is `_select_cli`; the stability `available()` constraint (spec line 115) is already satisfied because `_select_cli` enumerates via `registry.available()` and stays untouched.

**2. Placeholder scan.** No TBD/TODO; every code step has concrete code. Byte-identity and suite gates use exact commands with baseline `a8ff35d`.

**3. Type consistency.** `_select_cli` returns `Set[str]`; `_backends_view` returns that set unchanged; `collect_backend_selections` unions the `KIND_BACKEND` views into a `set` and returns it; orchestrator assigns it to `clis` (still `Set[str]`) → `_execute_install(clis=...)` unchanged. `collect_backend_selections` signature shape matches `collect_provider_selections`/`collect_toggle_selections` (`step, total, version, registry=None`). `KIND_BACKEND` is the exact constant from `domain/capability.py`.

**Risk note.** Same circular-import shape as Phase 2, mitigated identically by the lazy import in `_backends_view`. The union in `collect_backend_selections` is defensive (there is exactly one `KIND_BACKEND` capability today, so the union equals its single view's set); it degrades correctly if a second backend capability is ever added. If Task 1 Step 4 raises `ImportError`/`AttributeError` on `_wiz._select_cli`, match the attribute path against `orchestrator.py`'s existing `_wiz._select_cli` usage rather than changing `_select_cli`.

## Execution Handoff

Executing **subagent-driven** (per the established per-phase workflow): one fresh coder subagent per task, review after Task 2, byte-identity gate on Task 2. No sandbox rebuild needed — the byte-identity gate builds into its own worktree.
