from agent_notes.domain.capability import Capability, KIND_BACKEND
from agent_notes.commands.wizard.capability_registry import CapabilityRegistry
from agent_notes.commands.wizard.capabilities import (
    default_capability_registry,
    collect_backend_config,
)


def test_backend_capability_has_a_config_view():
    reg = default_capability_registry()
    assert reg.get("backends").config_view is not None


def test_collect_backend_config_merges_config_views():
    reg = CapabilityRegistry()
    reg.register(
        Capability(name="backends", kind=KIND_BACKEND, default=True, order=0),
        view=lambda step, total, version: {"claude"},
        config_view=lambda clis, step, total, version: (
            {"claude": {"reviewer": "m1"}},
            {"claude": {"reviewer": "high"}},
        ),
    )
    role_models, role_efforts = collect_backend_config(
        {"claude"}, step=2, total=9, version="x", registry=reg
    )
    assert role_models == {"claude": {"reviewer": "m1"}}
    assert role_efforts == {"claude": {"reviewer": "high"}}


def test_collect_backend_config_passes_clis_and_step_args():
    seen = {}
    reg = CapabilityRegistry()

    def _cfg(clis, step, total, version):
        seen.update(clis=clis, step=step, total=total, version=version)
        return {}, {}

    reg.register(
        Capability(name="backends", kind=KIND_BACKEND, default=True, order=0),
        view=lambda step, total, version: {"claude"},
        config_view=_cfg,
    )
    collect_backend_config({"claude", "codex"}, step=2, total=9, version="2.34", registry=reg)
    assert seen == {"clis": {"claude", "codex"}, "step": 2, "total": 9, "version": "2.34"}
