# Wizard Framework Phase 4a — Per-Backend Config View Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate the wizard's per-backend model/effort config step (step 2, `_select_models_per_role`) into the capability framework as the backend capability's `config_view`, completing the backend migration deferred from Phase 3.

**Architecture:** Extend `CapabilityBehaviour` with an optional `config_view` (the per-selection follow-up config screen, distinct from the reserved install-time `process`). Register the `backends` capability's `config_view` as a wrapper over the unchanged `_select_models_per_role`. Add a `collect_backend_config` collector. Rewire orchestrator step 2 through it. Byte-identical: identical selections yield identical `(role_models, role_efforts)` into `_execute_install`.

**Tech Stack:** Python 3.14, pytest, `agent_notes/commands/wizard/` (`capabilities.py`, `capability_registry.py`, `orchestrator.py`).

## Global Constraints

- **Byte-identity gate:** `scripts/dev/verify_dist_equiv.sh 7902dff` MUST report BYTE-IDENTICAL at phase end. `7902dff` is the Phase 3 tip and this phase's baseline.
- **Full suite green:** `uv run pytest tests/` MUST pass (Phase 3 baseline 1908 passed); no count reduction.
- **`_select_models_per_role` stays untouched:** do not change its signature, its claude-orchestrator skip, or its `(role_models, role_efforts)` return. Its existing tests must keep passing.
- **`config_view` is new; `process` stays reserved.** Do NOT repurpose the existing `process` field (its docstring reserves it for install-time). Add a separate `config_view` field.
- **`TOTAL_STEPS` stays 9 (constant, this sub-phase):** dynamic computation is Phase 4b. Step 2 stays step 2.
- **Lazy import rule:** the backend config view imports the wizard package lazily (function body) to avoid the `__init__ ↔ capabilities` cycle.

---

### Task 1: Add `config_view` to the framework + register the backend config view + `collect_backend_config`

**Files:**
- Modify: `agent_notes/commands/wizard/capability_registry.py` (add `config_view` field + register param)
- Modify: `agent_notes/commands/wizard/capabilities.py` (backend config view + collector)
- Test: `tests/unit/commands/test_wizard_backend_config.py` (create)

**Interfaces:**
- Consumes: `CapabilityRegistry`, `CapabilityBehaviour`, `KIND_BACKEND`, `by_kind`, `get`; `_select_models_per_role(clis, step, total, version) -> tuple[dict, dict]` from the wizard package.
- Produces (for Task 2): `collect_backend_config(clis, step, total, version, registry=None) -> tuple[dict, dict]` returning merged `(role_models, role_efforts)`. `CapabilityBehaviour` gains `config_view: Optional[Callable] = None`; `CapabilityRegistry.register(..., config_view=None)`.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/commands/test_wizard_backend_config.py`:

```python
from agent_notes.domain.capability import Capability, KIND_BACKEND
from agent_notes.commands.wizard.capability_registry import CapabilityRegistry
from agent_notes.commands.wizard.capabilities import (
    default_capability_registry,
    collect_backend_config,
)


def test_backend_capability_has_a_config_view():
    reg = default_capability_registry()
    assert reg.get("backends").config_view is not None


def test_collect_backend_config_merges_config_views():
    reg = CapabilityRegistry()
    reg.register(
        Capability(name="backends", kind=KIND_BACKEND, default=True, order=0),
        view=lambda step, total, version: {"claude"},
        config_view=lambda clis, step, total, version: (
            {"claude": {"reviewer": "m1"}},
            {"claude": {"reviewer": "high"}},
        ),
    )
    role_models, role_efforts = collect_backend_config(
        {"claude"}, step=2, total=9, version="x", registry=reg
    )
    assert role_models == {"claude": {"reviewer": "m1"}}
    assert role_efforts == {"claude": {"reviewer": "high"}}


def test_collect_backend_config_passes_clis_and_step_args():
    seen = {}
    reg = CapabilityRegistry()

    def _cfg(clis, step, total, version):
        seen.update(clis=clis, step=step, total=total, version=version)
        return {}, {}

    reg.register(
        Capability(name="backends", kind=KIND_BACKEND, default=True, order=0),
        view=lambda step, total, version: {"claude"},
        config_view=_cfg,
    )
    collect_backend_config({"claude", "codex"}, step=2, total=9, version="2.34", registry=reg)
    assert seen == {"clis": {"claude", "codex"}, "step": 2, "total": 9, "version": "2.34"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/commands/test_wizard_backend_config.py -v`
Expected: FAIL — `ImportError: cannot import name 'collect_backend_config'` (and `config_view` attribute missing).

- [ ] **Step 3: Implement**

In `agent_notes/commands/wizard/capability_registry.py`:

1. Add the field to `CapabilityBehaviour`:

```python
@dataclass(frozen=True)
class CapabilityBehaviour:
    view: Callable
    process: Optional[Callable] = None
    config_view: Optional[Callable] = None
```

2. Update `register` to accept and store it:

```python
    def register(self, capability: Capability, *, view, process=None, config_view=None) -> None:
        if capability.name in self._entries:
            raise ValueError(f"Capability {capability.name!r} already registered")
        self._entries[capability.name] = (
            capability,
            CapabilityBehaviour(view, process, config_view),
        )
```

In `agent_notes/commands/wizard/capabilities.py`:

3. Add the backend config view (near `_backends_view`):

```python
def _backends_config_view(clis, step, total, version="") -> tuple:
    # lazy import: avoids a circular import between wizard.__init__ and capabilities
    from agent_notes.commands import wizard as _wiz

    return _wiz._select_models_per_role(clis, step=step, total=total, version=version)
```

4. Register the config view on `BACKENDS` in `_build_registry()`:

```python
    reg.register(BACKENDS, view=_backends_view, config_view=_backends_config_view)
```

5. Add the collector (merges each backend capability's config output):

```python
def collect_backend_config(clis, step, total, version, registry=None) -> tuple:
    """Run each backend capability's config_view; merge into (role_models, role_efforts)."""
    reg = registry if registry is not None else default_capability_registry()
    role_models: dict = {}
    role_efforts: dict = {}
    for cap in reg.by_kind(KIND_BACKEND):
        behaviour = reg.get(cap.name)
        if behaviour.config_view is None:
            continue
        models, efforts = behaviour.config_view(clis, step, total, version)
        role_models.update(models)
        role_efforts.update(efforts)
    return role_models, role_efforts
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/commands/test_wizard_backend_config.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add agent_notes/commands/wizard/capability_registry.py agent_notes/commands/wizard/capabilities.py tests/unit/commands/test_wizard_backend_config.py
git commit -m "#40 feat(wizard): add capability config_view and route per-backend model/effort config"
```

---

### Task 2: Route orchestrator step 2 through `collect_backend_config`

**Files:**
- Modify: `agent_notes/commands/wizard/orchestrator.py` (step 2 call ~line 69; the module-scope capabilities import)
- Test: `tests/unit/commands/test_wizard_backend_config.py` (extend)

**Interfaces:**
- Consumes: `collect_backend_config(clis, step, total, version, registry=None) -> tuple[dict, dict]`.
- Produces: no new public interface; `role_models`, `role_efforts` still passed to `_execute_install`, identical values for identical choices.

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/commands/test_wizard_backend_config.py`:

```python
def test_collect_backend_config_importable_at_orchestrator_module_scope():
    from agent_notes.commands.wizard import orchestrator as orch

    assert hasattr(orch, "collect_backend_config")
    assert orch.TOTAL_STEPS == 9
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/commands/test_wizard_backend_config.py::test_collect_backend_config_importable_at_orchestrator_module_scope -v`
Expected: FAIL — `AttributeError: module '...orchestrator' has no attribute 'collect_backend_config'`.

- [ ] **Step 3: Rewire the orchestrator**

In `agent_notes/commands/wizard/orchestrator.py`:

1. Extend the module-scope capabilities import to add `collect_backend_config`:

```python
from .capabilities import (
    collect_toggle_selections,
    collect_provider_selections,
    collect_backend_selections,
    collect_backend_config,
)
```

2. Replace the step-2 call `role_models, role_efforts = _wiz._select_models_per_role(clis, step=2, total=TOTAL_STEPS, version=version)` with:

```python
    role_models, role_efforts = collect_backend_config(
        clis, step=2, total=TOTAL_STEPS, version=version
    )
```

Leave the `_execute_install(...)` call and its `role_models=`, `role_efforts=` args unchanged.

- [ ] **Step 4: Run the targeted + wizard test suites**

Run: `uv run pytest tests/unit/commands/test_wizard_backend_config.py tests/unit/commands/ -k wizard tests/functional/commands/test_wizard_happy_path.py -v`
Expected: PASS, including the happy-path functional test (step-2 sequence and prompts unchanged).

- [ ] **Step 5: Run the full suite + byte-identity gate**

Run: `uv run pytest tests/`
Expected: PASS, count ≥ 1908 + new tests.

Run: `scripts/dev/verify_dist_equiv.sh 7902dff`
Expected: **BYTE-IDENTICAL**. If DRIFT, stop — `role_models`/`role_efforts` values changed; the rewire must be pure plumbing.

- [ ] **Step 6: Commit**

```bash
git add agent_notes/commands/wizard/orchestrator.py tests/unit/commands/test_wizard_backend_config.py
git commit -m "#40 refactor(wizard): route per-backend config through the backend capability runner"
```

---

## Self-Review

**1. Spec coverage.** Completes spec phase 4's second half ("per-backend config become composed capability steps"), deferred from Phase 3. `config_view` is the mechanism the spec's kinds table implies ("backend … config view: yes"). `_select_models_per_role` is now the backend capability's `config_view`; the claude-orchestrator skip and effort logic stay inside it, untouched.

**2. Placeholder scan.** No TBD/TODO; every code step has concrete code; gates use exact commands with baseline `7902dff`.

**3. Type consistency.** `_select_models_per_role` returns `tuple[dict, dict]`; `_backends_config_view` returns it unchanged; `collect_backend_config` merges into `(role_models, role_efforts)` (both `{cli: {role: value}}`) and returns the tuple; orchestrator unpacks the same pair → `_execute_install(role_models=..., role_efforts=...)`. New field `config_view: Optional[Callable] = None` is backward-compatible (existing `register` calls omit it → None). `process` is left untouched and still reserved.

**Risk note.** Same lazy-import shape as prior phases. `config_view` is a distinct field from `process`, avoiding overload of the reserved install-time hook. The merge in `collect_backend_config` is defensive for the single-backend-capability reality (one cap → its output verbatim). If Task 1 Step 4 fails on `_wiz._select_models_per_role`, match the attribute path against orchestrator's prior `_wiz._select_models_per_role` usage rather than changing the function.

## Execution Handoff

Executing **subagent-driven**: fresh coder per task, review after Task 2, byte-identity gate on Task 2. No sandbox rebuild needed (gate builds into its own worktree).
