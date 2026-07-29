"""Tests for agent-notes plugins list command."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

import agent_notes.commands.plugins as plugins_cmd
from agent_notes.domain.plugin import Plugin
from agent_notes.registries.plugin_registry import PluginRegistry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_plugin(name: str, description: str, default: bool) -> Plugin:
    return Plugin(
        name=name,
        description=description,
        default=default,
        path=Path("/fake") / name,
    )


def _make_registry(*plugins: Plugin) -> PluginRegistry:
    return PluginRegistry(list(plugins))


# ---------------------------------------------------------------------------
# plugins list
# ---------------------------------------------------------------------------

class TestPluginsList:
    def test_empty_registry_produces_no_output(self, capsys, monkeypatch):
        """When no plugins are registered, list_plugins prints nothing."""
        monkeypatch.setattr(plugins_cmd, "default_plugin_registry", lambda: _make_registry())
        monkeypatch.setattr(plugins_cmd, "config_path", lambda: Path("/nonexistent.yaml"))
        monkeypatch.setattr(plugins_cmd, "load_user_config", lambda p: {})

        plugins_cmd.list_plugins()

        out = capsys.readouterr().out
        assert out == ""

    def test_list_shows_plugin_name_and_description(self, capsys, monkeypatch):
        """list_plugins prints plugin name and description."""
        p = _make_plugin("cost-report", "Per-session token cost reporting", default=False)
        monkeypatch.setattr(plugins_cmd, "default_plugin_registry", lambda: _make_registry(p))
        monkeypatch.setattr(plugins_cmd, "config_path", lambda: Path("/nonexistent.yaml"))
        monkeypatch.setattr(plugins_cmd, "load_user_config", lambda path: {})

        plugins_cmd.list_plugins()

        out = capsys.readouterr().out
        assert "cost-report" in out
        assert "Per-session token cost reporting" in out

    def test_list_shows_default_status(self, capsys, monkeypatch):
        """list_plugins shows on/off status reflecting the plugin default."""
        p_on = _make_plugin("alpha", "Alpha plugin", default=True)
        p_off = _make_plugin("beta", "Beta plugin", default=False)
        monkeypatch.setattr(plugins_cmd, "default_plugin_registry",
                            lambda: _make_registry(p_on, p_off))
        monkeypatch.setattr(plugins_cmd, "config_path", lambda: Path("/nonexistent.yaml"))
        monkeypatch.setattr(plugins_cmd, "load_user_config", lambda path: {})

        plugins_cmd.list_plugins()

        out = capsys.readouterr().out
        lines = out.strip().splitlines()
        alpha_line = next(l for l in lines if "alpha" in l)
        beta_line = next(l for l in lines if "beta" in l)
        assert "on" in alpha_line
        assert "off" in beta_line

    def test_list_user_config_overrides_default(self, capsys, monkeypatch):
        """User config enabled_plugins overrides the plugin default."""
        p = _make_plugin("cost-report", "Cost reporting", default=False)
        monkeypatch.setattr(plugins_cmd, "default_plugin_registry", lambda: _make_registry(p))
        monkeypatch.setattr(plugins_cmd, "config_path", lambda: Path("/nonexistent.yaml"))
        # User has explicitly enabled cost-report
        monkeypatch.setattr(plugins_cmd, "load_user_config",
                            lambda path: {"enabled_plugins": {"cost-report": True}})

        plugins_cmd.list_plugins()

        out = capsys.readouterr().out
        assert "cost-report" in out
        assert "on" in out
