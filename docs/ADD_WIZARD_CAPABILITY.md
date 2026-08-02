# Adding a Wizard Capability

This guide shows how to add a new configurable feature to the interactive install wizard. The wizard is **capability-driven**: each feature (backend selection, memory provider, cost-report toggle) is a `Capability` paired with code-side behavior in the registry. Adding a new feature requires no orchestrator edits — the step count and collection logic derive automatically from registered capabilities.

---

## Section 1: What is a Capability?

A **capability** is a two-part abstraction:

1. **Data** — a `Capability` dataclass that names the feature and declares its kind:
   ```python
   from agent_notes.domain.capability import Capability, KIND_TOGGLE
   COST_REPORT = Capability(name="cost-report", kind=KIND_TOGGLE, default=False)
   ```

2. **Behavior** — code-side registration in the capability registry that provides the interactive view, optional per-selection config step, and reserved install-time processing:
   ```python
   reg.register(COST_REPORT, view=_cost_report_view)
   ```

**The mental model:** Capabilities are building blocks. The wizard composes its flow dynamically from the registry — no hardcoded step numbers, no orchestrator edits when adding a feature.

---

## Section 2: The Four Kinds

### KIND_BACKEND — Multi-Select AI Provider

**What it means:** A capability that lets users choose one or more AI integrations. Example: `backends` (Claude Code, OpenCode, Cursor, GitHub Copilot).

**How it's collected:**
- One **selection step** (`view`): returns a `set` of selected names.
- One **config step** (`config_view`, optional): for each selected backend, ask per-role model/effort preferences. Returns `(role_models: dict, role_efforts: dict)`.

**In the wizard:**
- Step 1: `collect_backend_selections()` — display checkboxes, return selected names.
- Step 2: `collect_backend_config()` — for each selected backend, run its `config_view` to collect model/effort per role.

**Example in the codebase:**
```python
# In capabilities.py
BACKENDS = Capability(name="backends", kind=KIND_BACKEND, default=True, order=0)

def _backends_view(step, total, version="") -> set:
    from agent_notes.commands import wizard as _wiz
    return _wiz._select_cli(step=step, total=total, version=version)

def _backends_config_view(clis, step, total, version="") -> tuple:
    from agent_notes.commands import wizard as _wiz
    return _wiz._select_models_per_role(clis, step=step, total=total, version=version)

reg.register(BACKENDS, view=_backends_view, config_view=_backends_config_view)
```

**In the orchestrator:**
```python
# Step 1: Select backends
clis = collect_backend_selections(step=1, total=TOTAL_STEPS, version=version)

# Step 2: Configure models/effort per role for each selected backend
role_models, role_efforts = collect_backend_config(
    clis, step=2, total=TOTAL_STEPS, version=version
)
```

---

### KIND_PROVIDER — Single-Select Slot

**What it means:** A capability that users select once and only one option is active at a time. Example: `memory` (local, obsidian, etc.). The "floor" (default, always resolves) is wired into the view.

**How it's collected:**
- One **selection step** (`view`): returns the selected value (a dict, string, or object — up to the view).
- No `config_view` (inline config is part of the selection screen).

**In the wizard:**
- Step 7: `collect_provider_selections()` — returns `{capability_name: selection}`.

**Example in the codebase:**
```python
# In capabilities.py
MEMORY = Capability(name="memory", kind=KIND_PROVIDER, default=True, order=0)

def _memory_view(step, total, version="") -> dict:
    from agent_notes.commands import wizard as _wiz
    backend, path, strategy = _wiz._select_memory(
        step=step, total=total, version=version
    )
    return {"backend": backend, "path": path, "strategy": strategy}

reg.register(MEMORY, view=_memory_view)
```

**In the orchestrator:**
```python
# Step 7: Select memory provider (returns one choice)
provider_selections = collect_provider_selections(
    step=7, total=TOTAL_STEPS, version=version
)
memory = provider_selections["memory"]
memory_backend = memory["backend"]
memory_path = memory["path"]
memory_strategy = memory["strategy"]
```

---

### KIND_TOGGLE — On/Off Subsystem

**What it means:** A capability that is either enabled or disabled. Example: `cost-report`. Multiple toggles can be enabled/disabled independently.

**How it's collected:**
- One **combined step** (`view`): returns a boolean (True = enabled, False = disabled).
- All toggles are collected in a single step via `collect_toggle_selections()`, which returns `{name: enabled}`.

**In the wizard:**
- Step 8: `collect_toggle_selections()` — run every toggle's view, collect `{name: bool}`.

**Example in the codebase:**
```python
# In capabilities.py
from .cost_report import _select_cost_report

COST_REPORT = Capability(name="cost-report", kind=KIND_TOGGLE, default=False)

def _cost_report_view(step, total, version) -> bool:
    return _select_cost_report(step=step, total=total, version=version)

reg.register(COST_REPORT, view=_cost_report_view)
```

**The view implementation** (`agent_notes/commands/wizard/cost_report.py`):
```python
def _select_cost_report(step: int = 0, total: int = 0, version: str = '') -> bool:
    """Ask whether to enable cost reporting. Returns True to enable, False to disable.

    Default is No (disabled). Non-interactive installs skip the prompt and return False.
    """
    options = [
        ("No  (can enable later with: agent-notes config cost-report on)", "no"),
        ("Yes  (appends a token-usage table to every Claude response)", "yes"),
    ]

    if _can_interactive():
        result = _radio_select(
            "Enable per-response cost report?\n"
            "  (appends a token-usage table to every Claude Code / OpenCode response)",
            options,
            default=0,
            step=step,
            total=total,
            version=version,
        )
    else:
        result = _radio_select_fallback(...)

    enabled = result == "yes"
    label = "enabled" if enabled else "disabled"
    print(f"  {Color.GREEN}✓{Color.NC} Cost report: {label}")
    return enabled
```

**In the orchestrator:**
```python
# Step 8: Collect all toggle states
enabled_plugins = collect_toggle_selections(step=8, total=TOTAL_STEPS, version=version)
# enabled_plugins = {"cost-report": True, ...}
```

---

### KIND_CORE — Reserved for Future Use

**What it means:** A capability that is always installed, never shown to the user, and has no wizard step. Reserved for infrastructure like credential guard.

**How it's collected:** No collection step. Defined in the registry but not called during the wizard.

**Status in current code:** Declared in the domain (`KIND_CORE` constant) but not yet used. Document it so future developers know the slot is reserved.

---

## Section 3: CapabilityBehaviour Fields

When you register a capability, you provide a `CapabilityBehaviour` with these fields:

```python
@dataclass(frozen=True)
class CapabilityBehaviour:
    view: Callable
    process: Optional[Callable] = None
    config_view: Optional[Callable] = None
```

### `view` (required)

A function that runs the interactive selection screen. Signature depends on kind:

```python
# Backend and Provider views
def view(step: int, total: int, version: str = '') -> Union[set, dict, str, ...]:
    """Run the selection screen. Return the user's choice."""
    pass

# Toggle view
def view(step: int, total: int, version: str) -> bool:
    """Run the on/off prompt. Return True (enabled) or False (disabled)."""
    pass
```

**Parameters:**
- `step` (int): Current step number (1-indexed). Used in progress header: `"Step 1 of 9: ..."`.
- `total` (int): Total number of steps. Same as `TOTAL_STEPS` in the orchestrator.
- `version` (str): App version string (e.g., `"v1.1.0"`). Optional for display.

**Return type:** Depends on kind — set (backend), dict/value (provider), bool (toggle).

---

### `config_view` (optional, backends only)

A follow-up screen that collects per-selection configuration. Used only for `KIND_BACKEND`. Signature:

```python
def config_view(selections: set, step: int, total: int, version: str = '') -> tuple:
    """Configure each selected backend. Return (role_models, role_efforts)."""
    role_models: dict = {}  # {role_name: model_id}
    role_efforts: dict = {}  # {role_name: effort_level}
    # ... populate via interactive prompts ...
    return role_models, role_efforts
```

**Parameters:**
- `selections` (set): The backend names selected in the prior step (e.g., `{"claude", "opencode"}`).
- `step`, `total`, `version`: Same as `view`.

**Return type:** A tuple of two dicts: `(role_models, role_efforts)`. These are merged with outputs from other backends' `config_view` functions and passed to the build pipeline.

---

### `process` (reserved)

Reserved for install-time processing. Currently unused — all processing happens in Phase 1 via `view` and `config_view`. The field is documented here for completeness. Future phases may populate this callback to customize file installation, state updates, or post-install hooks per capability.

---

## Section 4: How to Add a Capability of Each Kind

### Recipe 1: Add a New Toggle

**Goal:** Add a feature `my-feature` that users can enable/disable during install.

**Step 1: Define the Capability**

In `agent_notes/commands/wizard/capabilities.py`, add:

```python
from ...domain.capability import Capability, KIND_TOGGLE

MY_FEATURE = Capability(name="my-feature", kind=KIND_TOGGLE, default=False)
```

**Step 2: Implement the View**

Create the interactive screen. Example in `capabilities.py`:

```python
def _my_feature_view(step, total, version) -> bool:
    """Ask whether to enable my-feature."""
    options = [
        ("No  (can enable later)", "no"),
        ("Yes  (enable now)", "yes"),
    ]

    if _can_interactive():
        result = _radio_select(
            "Enable my-feature?",
            options,
            default=0,
            step=step,
            total=total,
            version=version,
        )
    else:
        result = _radio_select_fallback(
            "Enable my-feature?",
            options,
            default=0,
            step=step,
            total=total,
            version=version,
        )

    enabled = result == "yes"
    print(f"  {Color.GREEN}✓{Color.NC} My-feature: {'enabled' if enabled else 'disabled'}")
    return enabled
```

**Why the lazy import pattern?**

Notice the pattern in existing code:
```python
def _memory_view(step, total, version="") -> dict:
    # lazy import: avoids a circular import between wizard.__init__ and capabilities
    from agent_notes.commands import wizard as _wiz
    return _wiz._select_memory(...)
```

This avoids a circular import: `wizard/__init__.py` imports `capabilities.py` to build the registry, and if `capabilities.py` imported `wizard/__init__.py` at module level, Python would fail to load either file. The solution: import `wizard` **inside the view function**, not at module level. This defers the import until the view is called (during the wizard run), by which time both modules have finished loading.

**Step 3: Register**

In `_build_registry()`, add:

```python
def _build_registry() -> CapabilityRegistry:
    reg = CapabilityRegistry()
    reg.register(BACKENDS, view=_backends_view, config_view=_backends_config_view)
    reg.register(COST_REPORT, view=_cost_report_view)
    reg.register(MEMORY, view=_memory_view)
    reg.register(MY_FEATURE, view=_my_feature_view)  # ← ADD THIS
    return reg
```

**Step 4: Verify**

```bash
# Run the wizard
agent-notes install

# Your toggle should appear as a new step (step count increases automatically)
# Toggle state is returned in enabled_plugins dict in the orchestrator
```

---

### Recipe 2: Add a New Provider

**Goal:** Add a provider option `my-provider` that users can select (e.g., a new memory backend).

**Step 1: Define the Capability**

In `capabilities.py`:

```python
MY_PROVIDER = Capability(name="my-provider", kind=KIND_PROVIDER, default=False, order=0)
```

**Step 2: Implement the View**

```python
def _my_provider_view(step, total, version="") -> dict:
    """Ask user to select my-provider configuration."""
    from agent_notes.commands import wizard as _wiz
    
    # Your logic here. Example:
    option1 = _radio_select("Configure my-provider:", [("Option A", "a"), ("Option B", "b")], ...)
    config_value = {"choice": option1, "other_field": "value"}
    
    print(f"  {Color.GREEN}✓{Color.NC} My-provider configured")
    return config_value
```

**Step 3: Register**

```python
def _build_registry() -> CapabilityRegistry:
    reg = CapabilityRegistry()
    # ... existing registrations ...
    reg.register(MY_PROVIDER, view=_my_provider_view)
    return reg
```

**Step 4: Integrate in Orchestrator**

The orchestrator already has a step for provider collection:

```python
provider_selections = collect_provider_selections(
    step=7, total=TOTAL_STEPS, version=version
)
my_prov = provider_selections["my-provider"]  # ← Your provider's returned dict
```

---

### Recipe 3: Add a New Backend

**Goal:** Add a new backend option (e.g., a new AI CLI tool) to the backend selection step.

**Note:** The `backends` capability is special — it's a slot in the registry, but its actual options come from the CLI registry (`cli_registry.available()`), not hardcoded in code.

**To add a new CLI backend, see `docs/ADD_CLI.md`** (this adds it to the CLI registry, which the wizard's backend-selection view (`_select_cli`) queries automatically).

**If you need a custom backend capability** (e.g., a new multi-select feature besides CLIs):

```python
MY_BACKENDS = Capability(name="my-backends", kind=KIND_BACKEND, default=True, order=1)

def _my_backends_view(step, total, version="") -> set:
    """Let user select from my custom backends."""
    options = [("Backend A", "a"), ("Backend B", "b"), ("Backend C", "c")]
    selected = _checkbox_select("Select backends:", options, ...)
    return selected

def _my_backends_config_view(backends, step, total, version="") -> tuple:
    """Configure each selected backend."""
    # For each backend in 'backends', ask for per-role models/effort
    role_models: dict = {}
    role_efforts: dict = {}
    # ... populate ...
    return role_models, role_efforts

def _build_registry() -> CapabilityRegistry:
    reg = CapabilityRegistry()
    # ... existing ...
    reg.register(MY_BACKENDS, view=_my_backends_view, config_view=_my_backends_config_view)
    return reg
```

The step count and orchestration happen automatically — the orchestrator calls `collect_backend_selections()` and `collect_backend_config()`, which iterate over all registered backends.

---

## Section 5: Step Counting

The wizard's step count **derives automatically from the registry**. In `capabilities.py`:

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

**How it works:**
1. Start with 5 fixed steps (scope, mode, profile, skills, confirm).
2. Add 1 step if any `KIND_BACKEND` capability exists.
3. Add 1 step if any backend has a `config_view`.
4. Add 1 step per `KIND_PROVIDER` capability.
5. Add 1 step if any `KIND_TOGGLE` capability exists.

**When you add a capability:** Recompute `TOTAL_STEPS` by calling `_compute_total_steps()`. In `orchestrator.py`:

```python
TOTAL_STEPS = _compute_total_steps()
```

This is cached at module load time. When you add a new capability to the registry, `TOTAL_STEPS` updates automatically — no manual renumbering.

---

## Section 6: Byte-Identity Discipline

A new capability must not change the output of the install wizard when all capabilities use their defaults. This ensures that today's install produces the same `dist/` as yesterday's, byte-for-byte.

**Verification:**

```bash
# Baseline: commit your new capability, don't enable any non-default options during wizard
# Then run:
scripts/dev/verify_dist_equiv.sh <baseline-commit-hash>

# This compares your current dist/ against a clean rebuild from <baseline>.
# If they differ, your capability is breaking byte-identity.
```

**Common pitfalls:**
- New option's default is not honored during the view.
- Capability is always collected, even when it shouldn't be (e.g., a toggle always enabled).
- Step numbering changed, so display headers or state storage differ.

**To fix:** Check that your `Capability.default` matches the actual default behavior of your view. If a toggle defaults to `False`, the view should return `False` when the user doesn't explicitly enable it (including non-interactive runs).

---

## Checklist

- [ ] Created `Capability(name=..., kind=..., default=...)` in `capabilities.py`
- [ ] Implemented `view(step, total, version)` with the correct return type for the kind
- [ ] If `KIND_BACKEND`, implemented optional `config_view(selections, step, total, version) -> tuple`
- [ ] Used lazy import pattern to avoid circular imports (`from agent_notes.commands import wizard as _wiz` inside view function)
- [ ] Registered in `_build_registry()` via `reg.register(CAPABILITY, view=..., config_view=..., process=...)`
- [ ] Verified `TOTAL_STEPS = _compute_total_steps()` updates correctly (rerun wizard and check step count)
- [ ] Tested the new capability during `agent-notes install` (interactive or non-interactive)
- [ ] Ran `scripts/dev/verify_dist_equiv.sh <baseline-commit>` and confirmed byte-identity holds
- [ ] For toggles: enabled_plugins dict includes your capability in `orchestrator.py` `_execute_install()` call
- [ ] For providers: provider_selections dict includes your capability, accessible in orchestrator

---

## See Also

- `docs/ADD_CLI.md` — How to add a new AI CLI backend (feeds into `backends` capability slot)
- `docs/ADD_MODEL.md` — How to add a new AI model (affects model selection in backend config step)
- `docs/ARCHITECTURE.md` — 4-layer architecture, including the wizard as part of the commands layer
- `agent_notes/commands/wizard/capability_registry.py` — Registry implementation and `CapabilityBehaviour` dataclass
- `agent_notes/commands/wizard/capabilities.py` — Built-in capabilities (`BACKENDS`, `MEMORY`, `COST_REPORT`) and collectors
- `agent_notes/domain/capability.py` — `Capability` dataclass and kind constants
