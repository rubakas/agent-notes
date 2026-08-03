from agent_notes.domain.capability import Capability, KIND_BACKEND
from agent_notes.commands.wizard.capability_registry import CapabilityRegistry
from agent_notes.commands.wizard.capabilities import (
    default_capability_registry,
    collect_backend_selections,
)


def test_backends_registered_as_backend_kind():
    reg = default_capability_registry()
    assert [c.name for c in reg.by_kind(KIND_BACKEND)] == ["backends"]


def test_collect_backend_selections_returns_union_of_views():
    reg = CapabilityRegistry()
    reg.register(
        Capability(name="backends", kind=KIND_BACKEND, default=True, order=0),
        view=lambda step, total, version: {"claude", "codex"},
    )
    result = collect_backend_selections(step=1, total=9, version="x", registry=reg)
    assert result == {"claude", "codex"}


def test_collect_backend_selections_passes_step_args_to_view():
    seen = {}
    reg = CapabilityRegistry()

    def _view(step, total, version):
        seen.update(step=step, total=total, version=version)
        return {"claude"}

    reg.register(
        Capability(name="backends", kind=KIND_BACKEND, default=True, order=0),
        view=_view,
    )
    collect_backend_selections(step=1, total=9, version="2.34", registry=reg)
    assert seen == {"step": 1, "total": 9, "version": "2.34"}


def test_collect_backend_selections_importable_at_orchestrator_module_scope():
    from agent_notes.commands.wizard import orchestrator as orch

    assert hasattr(orch, "collect_backend_selections")
    assert orch.TOTAL_STEPS == 9
