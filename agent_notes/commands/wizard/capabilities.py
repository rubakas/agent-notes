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
    reg.register(BACKENDS, view=_backends_view)
    reg.register(COST_REPORT, view=_cost_report_view)
    reg.register(MEMORY, view=_memory_view)
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
