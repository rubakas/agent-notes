import pytest
from agent_notes.domain.capability import (
    Capability, KIND_BACKEND, KIND_PROVIDER, KIND_TOGGLE, KIND_CORE,
)


def test_each_kind_constructs():
    for kind in (KIND_BACKEND, KIND_PROVIDER, KIND_TOGGLE, KIND_CORE):
        assert Capability(name="x", kind=kind).kind == kind


def test_defaults():
    c = Capability(name="cost-report", kind=KIND_TOGGLE)
    assert c.default is False and c.order == 0


def test_unknown_kind_rejected():
    with pytest.raises(ValueError):
        Capability(name="x", kind="widget")
