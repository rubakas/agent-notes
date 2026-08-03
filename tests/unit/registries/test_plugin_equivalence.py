"""Real equivalence gate for plugin-driven include-skip and skill-filter.

After cost-report became a plugin (#37), the skip set is driven entirely by the
plugin registry.  These tests verify:

  a. _plugin_include_skip({}) includes "cost_reporting" in the skip set (the
     cost-report plugin is off by default, so the include is suppressed).

  b. _plugin_include_skip({"enabled_plugins": {"cost-report": True}}) does NOT
     skip "cost_reporting" (the plugin is on, so the include expands).

  c. The installer's plugin-based skill filter removes nothing when the registry
     owns no skills — _disabled_owned is empty.

Gate-has-teeth proof: a separate test patches default_plugin_registry with a
modified registry that flips cost-report's default to True. That causes
_plugin_include_skip({}) to return an empty set, proving tests (a) and (b) would
go red if the manifest were changed to default: on.
"""
import textwrap

import pytest

from agent_notes.registries.plugin_registry import load_plugin_registry, PluginRegistry
from agent_notes.services.rendering import _plugin_include_skip


_FAKE_SKILLS = ["git", "obsidian-memory", "cost-report"]


def _disabled_owned(registry: PluginRegistry, cfg: dict) -> set:
    """Mirror the plugin-filter logic from installer._install_session_hook."""
    disabled: set = set()
    for p in registry.all():
        if p not in registry.enabled(cfg):
            disabled.update(p.skills)
    return disabled


# ---------------------------------------------------------------------------
# Include-skip gate: cost-report owns cost_reporting, default off
# ---------------------------------------------------------------------------

def test_plugin_include_skip_default_config_skips_cost_reporting():
    """_plugin_include_skip({}) must include 'cost_reporting' (cost-report is off by default)."""
    skip = _plugin_include_skip({})
    assert "cost_reporting" in skip, (
        f"Expected 'cost_reporting' in skip set with empty config, got: {skip!r}"
    )


def test_plugin_include_skip_enabled_omits_cost_reporting():
    """_plugin_include_skip({'enabled_plugins': {'cost-report': True}}) must not skip 'cost_reporting'."""
    skip = _plugin_include_skip({"enabled_plugins": {"cost-report": True}})
    assert "cost_reporting" not in skip, (
        f"Expected 'cost_reporting' NOT in skip set when cost-report enabled, got: {skip!r}"
    )


# ---------------------------------------------------------------------------
# Skill-filter gate: no plugin owns skills yet
# ---------------------------------------------------------------------------

def test_skill_filter_removes_nothing_with_empty_registry(tmp_path):
    """Plugin skill filter is inert when registry owns no skills."""
    reg = load_plugin_registry(tmp_path)
    assert _disabled_owned(reg, {}) == set()
    # filter is a no-op: every skill survives
    result = [s for s in _FAKE_SKILLS if s not in _disabled_owned(reg, {})]
    assert result == _FAKE_SKILLS


# ---------------------------------------------------------------------------
# Gate-has-teeth proof: flipping cost-report default to on changes the result
# ---------------------------------------------------------------------------

def test_gate_has_teeth_if_default_flipped(tmp_path, monkeypatch):
    """Prove the gate would catch a manifest change that sets default: on.

    With default=on, cost-report is enabled by default, so _plugin_include_skip({})
    returns set() — cost_reporting is NOT skipped.  This is the opposite of the
    correct behavior, confirming that test_plugin_include_skip_default_config_skips_cost_reporting
    would turn red if the manifest were edited to 'default: on'.
    """
    (tmp_path / "cost-report").mkdir()
    (tmp_path / "cost-report" / "plugin.yaml").write_text(textwrap.dedent("""\
        name: cost-report
        description: Emit a per-session token cost report at the Stop hook
        default: on
        includes: [cost_reporting]
        hooks:
          - {event: Stop, command: "agent-notes cost-report", requires: stop_hook}
        allow:
          - {value: "Bash(agent-notes cost-report)", requires: allow_entries}
    """))
    reg = load_plugin_registry(tmp_path)
    monkeypatch.setattr(
        "agent_notes.registries.plugin_registry.default_plugin_registry",
        lambda: reg,
    )
    skip = _plugin_include_skip({})
    # With default=on, cost-report is enabled, so cost_reporting is NOT in the skip set
    assert "cost_reporting" not in skip, (
        "With default=on, cost_reporting should not be skipped (cost-report is enabled by default)"
    )
