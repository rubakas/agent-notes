"""Tests for _apply_plugin_settings — plugin hook/allow-entry install and remove."""
import json
from pathlib import Path

import agent_notes.services.installer as installer
from agent_notes.domain.plugin import Plugin, PluginHook, PluginAllow
from agent_notes.registries.plugin_registry import PluginRegistry


class _Backend:
    """Minimal backend stub that supports stop_hook and allow_entries."""

    def supports(self, cap):
        return cap in {"stop_hook", "allow_entries"}


def _reg():
    """Registry with one disabled-by-default cost-report plugin."""
    return PluginRegistry([
        Plugin(
            name="cost-report",
            description="c",
            default=False,
            path=Path("."),
            hooks=(PluginHook(event="Stop", command="agent-notes cost-report", requires="stop_hook"),),
            allow=(PluginAllow(value="Bash(agent-notes cost-report)", requires="allow_entries"),),
        ),
    ])


# ---------------------------------------------------------------------------
# Hook schema helpers (match the shape install_hook writes)
# {"hooks": {"Stop": [{"matcher": "", "hooks": [{"type": "command", "command": "..."}]}]}}
# ---------------------------------------------------------------------------

def _stop_hook_commands(data: dict) -> list[str]:
    return [
        h.get("command", "")
        for entry in data.get("hooks", {}).get("Stop", [])
        for h in entry.get("hooks", [])
    ]


def _allow_entries(data: dict) -> list[str]:
    return data.get("permissions", {}).get("allow", [])


# ---------------------------------------------------------------------------
# _apply_plugin_settings tests
# ---------------------------------------------------------------------------

def test_enabled_plugin_installs_hook(tmp_path, monkeypatch):
    settings = tmp_path / "settings.json"
    settings.write_text("{}")
    monkeypatch.setattr(installer, "default_plugin_registry", _reg)

    installer._apply_plugin_settings(settings, _Backend(), {"enabled_plugins": {"cost-report": True}})

    data = json.loads(settings.read_text())
    assert "agent-notes cost-report" in _stop_hook_commands(data)


def test_enabled_plugin_installs_allow_entry(tmp_path, monkeypatch):
    settings = tmp_path / "settings.json"
    settings.write_text("{}")
    monkeypatch.setattr(installer, "default_plugin_registry", _reg)

    installer._apply_plugin_settings(settings, _Backend(), {"enabled_plugins": {"cost-report": True}})

    data = json.loads(settings.read_text())
    assert "Bash(agent-notes cost-report)" in _allow_entries(data)


def test_disabled_plugin_removes_hook(tmp_path, monkeypatch):
    settings = tmp_path / "settings.json"
    monkeypatch.setattr(installer, "default_plugin_registry", _reg)
    # Install first, then disable
    installer._apply_plugin_settings(settings, _Backend(), {"enabled_plugins": {"cost-report": True}})
    installer._apply_plugin_settings(settings, _Backend(), {"enabled_plugins": {"cost-report": False}})

    data = json.loads(settings.read_text())
    assert "agent-notes cost-report" not in _stop_hook_commands(data)


def test_disabled_plugin_removes_allow_entry(tmp_path, monkeypatch):
    settings = tmp_path / "settings.json"
    monkeypatch.setattr(installer, "default_plugin_registry", _reg)
    installer._apply_plugin_settings(settings, _Backend(), {"enabled_plugins": {"cost-report": True}})
    installer._apply_plugin_settings(settings, _Backend(), {"enabled_plugins": {"cost-report": False}})

    data = json.loads(settings.read_text())
    assert "Bash(agent-notes cost-report)" not in _allow_entries(data)


def test_unsupported_capability_skips_hook(tmp_path, monkeypatch):
    """A backend that does not support stop_hook must not install the hook."""

    class _NoStopBackend:
        def supports(self, cap):
            return cap == "allow_entries"  # stop_hook NOT supported

    settings = tmp_path / "settings.json"
    settings.write_text("{}")
    monkeypatch.setattr(installer, "default_plugin_registry", _reg)

    installer._apply_plugin_settings(settings, _NoStopBackend(), {"enabled_plugins": {"cost-report": True}})

    data = json.loads(settings.read_text())
    assert "agent-notes cost-report" not in _stop_hook_commands(data)


def test_no_double_install_with_empty_registry(tmp_path):
    """With no manifests, _apply_plugin_settings must not add any hooks.

    This guards against double-installing the hardcoded Stop hook that
    _install_session_hook writes independently.
    """
    from agent_notes.services.settings_writer import install_hook
    from agent_notes.constants import Hooks

    settings = tmp_path / "settings.json"
    settings.write_text("{}")
    # Mimic what _install_session_hook's hardcoded line does
    install_hook(settings, "Stop", Hooks.COST_REPORT)

    # Call with the REAL (empty) registry — must not add a second Stop hook
    installer._apply_plugin_settings(settings, _Backend(), {})

    data = json.loads(settings.read_text())
    count = sum(
        1
        for entry in data.get("hooks", {}).get("Stop", [])
        for h in entry.get("hooks", [])
        if h.get("command") == Hooks.COST_REPORT
    )
    assert count == 1, f"Stop hook installed {count} times (expected exactly 1)"
