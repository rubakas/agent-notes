import pytest
from agent_notes.domain.capability import Capability, KIND_TOGGLE, KIND_PROVIDER
from agent_notes.commands.wizard.capability_registry import CapabilityRegistry


def _noop_row(ctx):
    return []


def test_register_get_and_by_kind():
    reg = CapabilityRegistry()
    cap = Capability(name="cost-report", kind=KIND_TOGGLE)
    reg.register(cap, row=_noop_row)
    assert reg.get("cost-report").row is _noop_row
    assert reg.get("cost-report").process is None
    assert reg.capability("cost-report") is cap
    assert reg.by_kind(KIND_TOGGLE) == [cap]
    assert reg.by_kind(KIND_PROVIDER) == []
    assert reg.names() == ["cost-report"]


def test_duplicate_registration_raises():
    reg = CapabilityRegistry()
    cap = Capability(name="a", kind=KIND_TOGGLE)
    reg.register(cap, row=_noop_row)
    with pytest.raises(ValueError):
        reg.register(cap, row=_noop_row)


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
    reg.register(second, row=_noop_row)
    reg.register(first, row=_noop_row)
    assert reg.by_kind(KIND_TOGGLE) == [first, second]


def test_by_kind_stable_for_equal_order():
    reg = CapabilityRegistry()
    a = Capability(name="a-cap", kind=KIND_TOGGLE, order=1)
    b = Capability(name="b-cap", kind=KIND_TOGGLE, order=1)
    reg.register(a, row=_noop_row)
    reg.register(b, row=_noop_row)
    assert reg.by_kind(KIND_TOGGLE) == [a, b]


def test_a_capability_without_a_review_row_is_rejected():
    reg = CapabilityRegistry()
    with pytest.raises(ValueError, match="no review row"):
        reg.register(Capability(name="x", kind=KIND_TOGGLE), row=None)
