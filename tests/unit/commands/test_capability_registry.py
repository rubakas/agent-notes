import pytest
from agent_notes.domain.capability import Capability, KIND_TOGGLE, KIND_PROVIDER
from agent_notes.commands.wizard.capability_registry import CapabilityRegistry


def _noop_view(step, total, version):
    return None


def test_register_get_and_by_kind():
    reg = CapabilityRegistry()
    cap = Capability(name="cost-report", kind=KIND_TOGGLE)
    reg.register(cap, view=_noop_view)
    assert reg.get("cost-report").view is _noop_view
    assert reg.get("cost-report").process is None
    assert reg.capability("cost-report") is cap
    assert reg.by_kind(KIND_TOGGLE) == [cap]
    assert reg.by_kind(KIND_PROVIDER) == []
    assert reg.names() == ["cost-report"]


def test_duplicate_registration_raises():
    reg = CapabilityRegistry()
    cap = Capability(name="a", kind=KIND_TOGGLE)
    reg.register(cap, view=_noop_view)
    with pytest.raises(ValueError):
        reg.register(cap, view=_noop_view)


def test_unknown_get_raises():
    reg = CapabilityRegistry()
    with pytest.raises(ValueError):
        reg.get("nope")
    with pytest.raises(ValueError):
        reg.capability("nope")


def test_by_kind_sorted_by_order():
    reg = CapabilityRegistry()
    second = Capability(name="second", kind=KIND_TOGGLE, order=2)
    first = Capability(name="first", kind=KIND_TOGGLE, order=1)
    reg.register(second, view=_noop_view)
    reg.register(first, view=_noop_view)
    assert reg.by_kind(KIND_TOGGLE) == [first, second]


def test_by_kind_stable_for_equal_order():
    reg = CapabilityRegistry()
    a = Capability(name="a-cap", kind=KIND_TOGGLE, order=1)
    b = Capability(name="b-cap", kind=KIND_TOGGLE, order=1)
    reg.register(a, view=_noop_view)
    reg.register(b, view=_noop_view)
    assert reg.by_kind(KIND_TOGGLE) == [a, b]
