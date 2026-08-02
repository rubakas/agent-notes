"""Registration of the built-in capabilities and the per-kind selection runners.

Phase 1 registers only the cost-report toggle. `collect_toggle_selections`
runs every registered toggle capability's view and returns {name: enabled}.
"""
from __future__ import annotations

from functools import lru_cache

from ...domain.capability import Capability, KIND_TOGGLE, KIND_PROVIDER, KIND_BACKEND
from .capability_registry import CapabilityRegistry
from .cost_report import _select_cost_report

COST_REPORT = Capability(name="cost-report", kind=KIND_TOGGLE, default=False)

# backend slot: always present (the CLI-selection step); options come from cli_registry.available(),
# default=True means "step always runs", not "pre-select every backend"
BACKENDS = Capability(name="backends", kind=KIND_BACKEND, default=True, order=0)

# provider slot: always present (floor = local); default=True means "required", not "pre-selected"
MEMORY = Capability(name="memory", kind=KIND_PROVIDER, default=True, order=0)


def _backends_view(step, total, version="") -> set:
    # lazy import: avoids a circular import between wizard.__init__ and capabilities
    from agent_notes.commands import wizard as _wiz

    return _wiz._select_cli(step=step, total=total, version=version)


def _backends_config_view(clis, step, total, version="") -> tuple:
    # lazy import: avoids a circular import between wizard.__init__ and capabilities
    from agent_notes.commands import wizard as _wiz

    return _wiz._select_models_per_role(clis, step=step, total=total, version=version)


def _cost_report_view(step, total, version) -> bool:
    return _select_cost_report(step=step, total=total, version=version)


def _memory_view(step, total, version="") -> dict:
    # lazy import: avoids a circular import between wizard.__init__ and capabilities
    from agent_notes.commands import wizard as _wiz

    backend, path, strategy = _wiz._select_memory(
        step=step, total=total, version=version
    )
    return {"backend": backend, "path": path, "strategy": strategy}


def _build_registry() -> CapabilityRegistry:
    reg = CapabilityRegistry()
    reg.register(BACKENDS, view=_backends_view, config_view=_backends_config_view)
    reg.register(COST_REPORT, view=_cost_report_view)
    reg.register(MEMORY, view=_memory_view)
    return reg


@lru_cache(maxsize=1)
def default_capability_registry() -> CapabilityRegistry:
    return _build_registry()


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


def collect_toggle_selections(step, total, version, registry=None) -> dict:
    """Run every registered toggle capability's view; return {name: enabled}."""
    reg = registry if registry is not None else default_capability_registry()
    result: dict = {}
    for cap in reg.by_kind(KIND_TOGGLE):
        result[cap.name] = reg.get(cap.name).view(step, total, version)
    return result


def collect_provider_selections(step, total, version, registry=None) -> dict:
    """Run every registered provider capability's view; return {name: selection}."""
    reg = registry if registry is not None else default_capability_registry()
    result: dict = {}
    for cap in reg.by_kind(KIND_PROVIDER):
        result[cap.name] = reg.get(cap.name).view(step, total, version)
    return result


def collect_backend_selections(step, total, version, registry=None) -> set:
    """Run every registered backend capability's view; return the union of selected names."""
    reg = registry if registry is not None else default_capability_registry()
    selected: set = set()
    for cap in reg.by_kind(KIND_BACKEND):
        selected |= reg.get(cap.name).view(step, total, version)
    return selected


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
