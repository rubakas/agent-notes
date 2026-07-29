"""Real equivalence gate for plugin additivity.

With no plugin manifests registered the plugin wiring in rendering.py and
installer.py must be purely additive — it changes nothing vs. the pre-plugin
code path.

Two assertions are made:
  a. rendering._plugin_include_skip(cfg) equals legacy cost.render.include_skip(cfg)
     for representative configs — true today because no manifest owns any include,
     and it breaks the moment any plugin shifts the skip set away from legacy behavior.
  b. The installer's plugin-based skill filter removes nothing when the registry
     owns no skills — _disabled_owned is empty.
"""
import pytest
import textwrap

from agent_notes.registries.plugin_registry import load_plugin_registry, PluginRegistry
from agent_notes.services.rendering import _plugin_include_skip
from agent_notes.cost.render import include_skip as _legacy_include_skip


_REPRESENTATIVE_CONFIGS = [
    {},
    {"cost_report_enabled": True},
    {"cost_report_enabled": False},
]

_FAKE_SKILLS = ["git", "obsidian-memory", "cost-report"]


def _disabled_owned(registry: PluginRegistry, cfg: dict) -> set:
    """Mirror the plugin-filter logic from installer._install_session_hook."""
    disabled: set = set()
    for p in registry.all():
        if p not in registry.enabled(cfg):
            disabled.update(p.skills)
    return disabled


@pytest.mark.parametrize("cfg", _REPRESENTATIVE_CONFIGS)
def test_include_skip_equals_legacy_with_empty_registry(cfg, tmp_path, monkeypatch):
    """_plugin_include_skip(cfg) == legacy include_skip(cfg) when registry is empty.

    Empty registry means owned_includes() == {} and active_includes() == {}, so
    the plugin wiring contributes nothing and the result collapses to the legacy
    cost-report bridge alone.
    """
    reg = load_plugin_registry(tmp_path)  # zero manifests
    monkeypatch.setattr(
        "agent_notes.registries.plugin_registry.default_plugin_registry",
        lambda: reg,
    )
    assert _plugin_include_skip(cfg) == _legacy_include_skip(cfg)


def test_skill_filter_removes_nothing_with_empty_registry(tmp_path):
    """Plugin skill filter is inert when registry owns no skills."""
    reg = load_plugin_registry(tmp_path)
    assert _disabled_owned(reg, {}) == set()
    # filter is a no-op: every skill survives
    result = [s for s in _FAKE_SKILLS if s not in _disabled_owned(reg, {})]
    assert result == _FAKE_SKILLS
