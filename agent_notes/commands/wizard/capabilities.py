"""Registration of the built-in capabilities and their review rows."""
from __future__ import annotations

from functools import lru_cache

from ...domain.capability import Capability, KIND_TOGGLE, KIND_PROVIDER, KIND_BACKEND
from .capability_registry import CapabilityRegistry

COST_REPORT = Capability(name="cost-report", kind=KIND_TOGGLE, default=False)

# backend slot: always present (the CLI-selection step); options come from cli_registry.available(),
# default=True means "step always runs", not "pre-select every backend"
BACKENDS = Capability(name="backends", kind=KIND_BACKEND, default=True, order=0)

# provider slot: always present (floor = local); default=True means "required", not "pre-selected"
MEMORY = Capability(name="memory", kind=KIND_PROVIDER, default=True, order=0)


def _backends_rows(ctx) -> list:
    # lazy import: review imports this module for the registry
    from .review import backends_rows
    return backends_rows(ctx)


def _memory_rows(ctx) -> list:
    from .review import memory_row
    return [memory_row(ctx.ui, ctx.choices.memory)]


def _cost_report_rows(ctx) -> list:
    from .review import toggle_row
    return [toggle_row(ctx.ui, "cost-report", "Cost report", ctx.choices.plugins)]


def _build_registry() -> CapabilityRegistry:
    reg = CapabilityRegistry()
    reg.register(BACKENDS, row=_backends_rows)
    reg.register(COST_REPORT, row=_cost_report_rows)
    reg.register(MEMORY, row=_memory_rows)
    return reg


@lru_cache(maxsize=1)
def default_capability_registry() -> CapabilityRegistry:
    return _build_registry()
