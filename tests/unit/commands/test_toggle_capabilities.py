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
