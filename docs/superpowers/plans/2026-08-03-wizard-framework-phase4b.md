# Wizard Framework Phase 4b — Registry-Computed TOTAL_STEPS Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the hardcoded `TOTAL_STEPS = 9` magic constant with a value derived from the capability registry, so the wizard's step count auto-adjusts when a capability is added or removed. Computes to 9 for the current registry — console and dist stay byte-identical.

**Architecture:** Add `_compute_total_steps(registry=None) -> int` to `capabilities.py` that models the wizard's step structure: 5 fixed general steps (scope, mode, profile, skills, confirm) + 1 backend-selection step (if any backend capability) + 1 backend-config step (if any backend has a `config_view`) + 1 step per provider slot + 1 combined toggle step (if any toggle). The orchestrator sets `TOTAL_STEPS = _compute_total_steps()` at module load. No step reorder; the confirm screen is unchanged (it already composes from the live selections).

**Tech Stack:** Python 3.14, pytest, `agent_notes/commands/wizard/` (`capabilities.py`, `orchestrator.py`).

**Scope note:** This sub-phase is dynamic `TOTAL_STEPS` ONLY. A per-capability confirm-render hook was deliberately left out as speculative (it would produce byte-identical output for a single consumer; the confirm already enumerates the live selection — selected backends, memory, skills).

## Global Constraints

- **Byte-identity gate:** `scripts/dev/verify_dist_equiv.sh b38852f` MUST report BYTE-IDENTICAL. `b38852f` is the Phase 4a tip and this phase's baseline. (`TOTAL_STEPS` does not affect `dist/`; the gate is a guard against incidental drift.)
- **Full suite green:** `uv run pytest tests/` MUST pass (Phase 4a baseline 1912 passed); no count reduction. In particular the three existing `orch.TOTAL_STEPS == 9` assertions (`test_wizard_backend_step.py`, `test_wizard_provider_step.py`, `test_wizard_backend_config.py`) MUST still pass — the computed value stays 9.
- **`TOTAL_STEPS` value stays 9:** the console header must still read "Step X of 9" for the default registry.
- **No step reorder, no confirm changes:** touch only `capabilities.py` and `orchestrator.py` (plus a new test file).

---

### Task 1: Add `_compute_total_steps` and wire it into the orchestrator

**Files:**
- Modify: `agent_notes/commands/wizard/capabilities.py` (add `_compute_total_steps`)
- Modify: `agent_notes/commands/wizard/orchestrator.py` (compute `TOTAL_STEPS` from the registry)
- Test: `tests/unit/commands/test_wizard_total_steps.py` (create)

**Interfaces:**
- Consumes: `default_capability_registry()`, `by_kind`, `get`, `KIND_BACKEND`, `KIND_PROVIDER`, `KIND_TOGGLE`, and the `config_view` attribute on `CapabilityBehaviour` (from Phase 4a).
- Produces: `_compute_total_steps(registry=None) -> int`. `orchestrator.TOTAL_STEPS` becomes the computed value (== 9 today).

- [ ] **Step 1: Write the failing test**

Create `tests/unit/commands/test_wizard_total_steps.py`:

```python
from agent_notes.domain.capability import (
    Capability,
    KIND_BACKEND,
    KIND_PROVIDER,
    KIND_TOGGLE,
)
from agent_notes.commands.wizard.capability_registry import CapabilityRegistry
from agent_notes.commands.wizard.capabilities import _compute_total_steps


def test_default_registry_computes_to_nine():
    assert _compute_total_steps() == 9


def test_orchestrator_total_steps_is_the_computed_value():
    from agent_notes.commands.wizard import orchestrator as orch

    assert orch.TOTAL_STEPS == _compute_total_steps() == 9


def test_extra_provider_adds_a_step():
    reg = CapabilityRegistry()
    reg.register(
        Capability(name="backends", kind=KIND_BACKEND, default=True, order=0),
        view=lambda step, total, version: set(),
        config_view=lambda clis, step, total, version: ({}, {}),
    )
    reg.register(
        Capability(name="memory", kind=KIND_PROVIDER, default=True, order=0),
        view=lambda step, total, version: {},
    )
    reg.register(
        Capability(name="notes", kind=KIND_PROVIDER, default=True, order=1),
        view=lambda step, total, version: {},
    )
    reg.register(
        Capability(name="cost-report", kind=KIND_TOGGLE, default=False),
        view=lambda step, total, version: False,
    )
    # 5 fixed + 1 backend sel + 1 backend cfg + 2 providers + 1 toggle
    assert _compute_total_steps(reg) == 10


def test_backend_without_config_view_omits_the_config_step():
    reg = CapabilityRegistry()
    reg.register(
        Capability(name="backends", kind=KIND_BACKEND, default=True, order=0),
        view=lambda step, total, version: set(),
    )
    # 5 fixed + 1 backend sel (no config_view, no providers, no toggles)
    assert _compute_total_steps(reg) == 6
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/commands/test_wizard_total_steps.py -v`
Expected: FAIL — `ImportError: cannot import name '_compute_total_steps'`.

- [ ] **Step 3: Implement the helper**

In `agent_notes/commands/wizard/capabilities.py`, add (import `KIND_PROVIDER`/`KIND_TOGGLE`/`KIND_BACKEND` are already imported):

```python
def _compute_total_steps(registry=None) -> int:
    """Derive the wizard step count from the capability registry.

    Fixed general steps: scope, mode, profile, skills, confirm (5).
    Capability steps: one backend-selection step (if any backend), one
    backend-config step (if any backend declares a config_view), one step
    per provider slot, and one combined toggle step (if any toggle).
    """
    reg = registry if registry is not None else default_capability_registry()
    total = 5  # scope, mode, profile, skills, confirm
    backends = reg.by_kind(KIND_BACKEND)
    if backends:
        total += 1
        if any(reg.get(c.name).config_view for c in backends):
            total += 1
    total += len(reg.by_kind(KIND_PROVIDER))
    if reg.by_kind(KIND_TOGGLE):
        total += 1
    return total
```

- [ ] **Step 4: Wire it into the orchestrator**

In `agent_notes/commands/wizard/orchestrator.py`:

1. Add `_compute_total_steps` to the module-scope capabilities import block (alongside the existing collectors).

2. Replace the constant `TOTAL_STEPS = 9` (line 11) with:

```python
TOTAL_STEPS = _compute_total_steps()
```

- [ ] **Step 5: Run the test + full suite + byte-identity gate**

Run: `uv run pytest tests/unit/commands/test_wizard_total_steps.py -v`
Expected: PASS (4 tests).

Run: `uv run pytest tests/`
Expected: PASS, count ≥ 1912 + 4 new tests; the three existing `TOTAL_STEPS == 9` assertions still green.

Run: `scripts/dev/verify_dist_equiv.sh b38852f`
Expected: **BYTE-IDENTICAL**.

- [ ] **Step 6: Commit**

```bash
git add agent_notes/commands/wizard/capabilities.py agent_notes/commands/wizard/orchestrator.py tests/unit/commands/test_wizard_total_steps.py
git commit -m "#40 refactor(wizard): compute TOTAL_STEPS from the capability registry"
```

---

## Self-Review

**1. Spec coverage.** Delivers spec phase 5's "`TOTAL_STEPS` is computed, not a constant" for the current (all-unconditional) step set — it derives to 9 and auto-adjusts as capabilities change. The spec's full per-selection dynamic composer + step reorder was explicitly descoped by the user (a `wip` capability would already be excluded because the collectors enumerate a registry built from `available()`-filtered capabilities). The confirm-render hook was descoped as speculative (documented in the Scope note).

**2. Placeholder scan.** No TBD/TODO; concrete code throughout; gates use exact commands with baseline `b38852f`.

**3. Type consistency.** `_compute_total_steps(registry=None) -> int`; called with no arg in the orchestrator (defaults to `default_capability_registry()`) and with an explicit registry in tests. `config_view` is the Phase 4a `CapabilityBehaviour` attribute (may be `None`). Returns 9 for the default registry, keeping every `total=TOTAL_STEPS` call site and the three `== 9` tests valid.

**Risk note.** `_compute_total_steps()` runs at orchestrator import time; it calls `default_capability_registry()` (lru-cached) which only *registers* view/config_view callables (their bodies — the lazy wizard imports — are not executed), so there is no import cycle. The step-structure model (5 fixed + capability steps) mirrors the current orchestrator exactly; if a future phase reorders or conditionalizes steps, this helper is the single place to update.

## Execution Handoff

Executing **subagent-driven**: one coder for the single task (small, cohesive change), then lead verification + byte-identity gate. No sandbox rebuild needed.
