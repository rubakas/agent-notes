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
