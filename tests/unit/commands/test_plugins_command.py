"""Tests for agent-notes plugins list/enable/disable/info commands."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
import yaml

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


def _two_plugin_registry() -> PluginRegistry:
    return _make_registry(
        _make_plugin("cost-report", "cost", default=False),
        _make_plugin("memory", "mem", default=True),
    )


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


# ---------------------------------------------------------------------------
# plugins enable
# ---------------------------------------------------------------------------

class TestPluginsEnable:
    def test_enable_writes_true_to_config(self, tmp_path, monkeypatch):
        """enable_plugin writes enabled_plugins.<name> = True to the config file."""
        cfg = tmp_path / "config.yaml"
        monkeypatch.setattr(plugins_cmd, "default_plugin_registry", _two_plugin_registry)
        monkeypatch.setattr(plugins_cmd, "config_path", lambda: cfg)

        plugins_cmd.enable_plugin("cost-report")

        data = yaml.safe_load(cfg.read_text())
        assert data["enabled_plugins"]["cost-report"] is True

    def test_enable_unknown_plugin_prints_error_and_writes_nothing(self, tmp_path, monkeypatch, capsys):
        """enable_plugin on an unknown name prints the name and does not write config."""
        cfg = tmp_path / "config.yaml"
        monkeypatch.setattr(plugins_cmd, "default_plugin_registry", _two_plugin_registry)
        monkeypatch.setattr(plugins_cmd, "config_path", lambda: cfg)

        plugins_cmd.enable_plugin("nope")

        out = capsys.readouterr().out
        assert "nope" in out
        assert not cfg.exists()

    def test_enable_unknown_plugin_names_known_plugins(self, tmp_path, monkeypatch, capsys):
        """Error message for unknown plugin lists the known plugin names."""
        cfg = tmp_path / "config.yaml"
        monkeypatch.setattr(plugins_cmd, "default_plugin_registry", _two_plugin_registry)
        monkeypatch.setattr(plugins_cmd, "config_path", lambda: cfg)

        plugins_cmd.enable_plugin("nope")

        out = capsys.readouterr().out
        assert "cost-report" in out
        assert "memory" in out


# ---------------------------------------------------------------------------
# plugins disable
# ---------------------------------------------------------------------------

class TestPluginsDisable:
    def test_disable_writes_false_to_config(self, tmp_path, monkeypatch):
        """disable_plugin writes enabled_plugins.<name> = False to the config file."""
        cfg = tmp_path / "config.yaml"
        monkeypatch.setattr(plugins_cmd, "default_plugin_registry", _two_plugin_registry)
        monkeypatch.setattr(plugins_cmd, "config_path", lambda: cfg)

        plugins_cmd.disable_plugin("memory")

        data = yaml.safe_load(cfg.read_text())
        assert data["enabled_plugins"]["memory"] is False

    def test_disable_unknown_plugin_prints_error_and_writes_nothing(self, tmp_path, monkeypatch, capsys):
        """disable_plugin on an unknown name prints the name and does not write config."""
        cfg = tmp_path / "config.yaml"
        monkeypatch.setattr(plugins_cmd, "default_plugin_registry", _two_plugin_registry)
        monkeypatch.setattr(plugins_cmd, "config_path", lambda: cfg)

        plugins_cmd.disable_plugin("nope")

        out = capsys.readouterr().out
        assert "nope" in out
        assert not cfg.exists()


# ---------------------------------------------------------------------------
# plugins info
# ---------------------------------------------------------------------------

class TestPluginsInfo:
    def test_info_unknown_plugin_prints_error(self, monkeypatch, capsys):
        """info_plugin on an unknown name prints the name."""
        monkeypatch.setattr(plugins_cmd, "default_plugin_registry", _two_plugin_registry)

        plugins_cmd.info_plugin("unknown-plugin")

        out = capsys.readouterr().out
        assert "unknown-plugin" in out

    def test_info_known_plugin_prints_name_and_description(self, monkeypatch, capsys):
        """info_plugin prints the plugin name, description, and default."""
        monkeypatch.setattr(plugins_cmd, "default_plugin_registry", _two_plugin_registry)

        plugins_cmd.info_plugin("cost-report")

        out = capsys.readouterr().out
        assert "cost-report" in out
        assert "cost" in out
        assert "off" in out  # default is False

    def test_info_shows_default_on_for_default_enabled_plugin(self, monkeypatch, capsys):
        """info_plugin shows 'on' for a plugin whose default is True."""
        monkeypatch.setattr(plugins_cmd, "default_plugin_registry", _two_plugin_registry)

        plugins_cmd.info_plugin("memory")

        out = capsys.readouterr().out
        assert "on" in out
