from agent_notes.domain.capability import Capability, KIND_PROVIDER
from agent_notes.commands.wizard.capability_registry import CapabilityRegistry
from agent_notes.commands.wizard.capabilities import (
    default_capability_registry,
    collect_provider_selections,
)


def test_memory_registered_as_provider():
    reg = default_capability_registry()
    assert [c.name for c in reg.by_kind(KIND_PROVIDER)] == ["memory"]


def test_collect_provider_selections_returns_named_dicts():
    reg = CapabilityRegistry()
    reg.register(
        Capability(name="memory", kind=KIND_PROVIDER, default=True, order=0),
        view=lambda step, total, version: {
            "backend": "local",
            "path": "",
            "strategy": "single-brain",
        },
    )
    result = collect_provider_selections(step=7, total=9, version="x", registry=reg)
    assert result == {
        "memory": {"backend": "local", "path": "", "strategy": "single-brain"}
    }


def test_collect_provider_selections_passes_step_args_to_view():
    seen = {}
    reg = CapabilityRegistry()

    def _view(step, total, version):
        seen.update(step=step, total=total, version=version)
        return {"backend": "local", "path": "", "strategy": "single-brain"}

    reg.register(
        Capability(name="memory", kind=KIND_PROVIDER, default=True, order=0),
        view=_view,
    )
    collect_provider_selections(step=7, total=9, version="2.34", registry=reg)
    assert seen == {"step": 7, "total": 9, "version": "2.34"}
