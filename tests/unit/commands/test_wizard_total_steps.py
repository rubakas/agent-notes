from agent_notes.domain.capability import (
    Capability,
    KIND_BACKEND,
    KIND_PROVIDER,
    KIND_TOGGLE,
)
from agent_notes.commands.wizard.capability_registry import CapabilityRegistry
from agent_notes.commands.wizard.capabilities import _compute_total_steps


def test_default_registry_computes_to_nine():
    assert _compute_total_steps() == 9


def test_orchestrator_total_steps_is_the_computed_value():
    from agent_notes.commands.wizard import orchestrator as orch

    assert orch.TOTAL_STEPS == _compute_total_steps() == 9


def test_extra_provider_adds_a_step():
    reg = CapabilityRegistry()
    reg.register(
        Capability(name="backends", kind=KIND_BACKEND, default=True, order=0),
        view=lambda step, total, version: set(),
        config_view=lambda clis, step, total, version: ({}, {}),
    )
    reg.register(
        Capability(name="memory", kind=KIND_PROVIDER, default=True, order=0),
        view=lambda step, total, version: {},
    )
    reg.register(
        Capability(name="notes", kind=KIND_PROVIDER, default=True, order=1),
        view=lambda step, total, version: {},
    )
    reg.register(
        Capability(name="cost-report", kind=KIND_TOGGLE, default=False),
        view=lambda step, total, version: False,
    )
    # 5 fixed + 1 backend sel + 1 backend cfg + 2 providers + 1 toggle
    assert _compute_total_steps(reg) == 10


def test_backend_without_config_view_omits_the_config_step():
    reg = CapabilityRegistry()
    reg.register(
        Capability(name="backends", kind=KIND_BACKEND, default=True, order=0),
        view=lambda step, total, version: set(),
    )
    # 5 fixed + 1 backend sel (no config_view, no providers, no toggles)
    assert _compute_total_steps(reg) == 6
