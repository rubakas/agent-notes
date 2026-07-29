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

    def test_list_annotates_when_effective_differs_from_default(self, capsys, monkeypatch):
        """When effective state differs from manifest default, annotation is shown."""
        p = _make_plugin("cost-report", "Cost reporting", default=False)
        monkeypatch.setattr(plugins_cmd, "default_plugin_registry", lambda: _make_registry(p))
        monkeypatch.setattr(plugins_cmd, "config_path", lambda: Path("/nonexistent.yaml"))
        # User enabled cost-report, which has default=False
        monkeypatch.setattr(plugins_cmd, "load_user_config",
                            lambda path: {"enabled_plugins": {"cost-report": True}})

        plugins_cmd.list_plugins()

        out = capsys.readouterr().out
        # Plugin is on but default is off → annotation expected
        assert "(default: off)" in out

    def test_list_no_annotation_when_effective_matches_default(self, capsys, monkeypatch):
        """When effective state matches manifest default, no annotation is shown."""
        p = _make_plugin("cost-report", "Cost reporting", default=False)
        monkeypatch.setattr(plugins_cmd, "default_plugin_registry", lambda: _make_registry(p))
        monkeypatch.setattr(plugins_cmd, "config_path", lambda: Path("/nonexistent.yaml"))
        # No user override — effective state equals default (off)
        monkeypatch.setattr(plugins_cmd, "load_user_config", lambda path: {})

        plugins_cmd.list_plugins()

        out = capsys.readouterr().out
        assert "(default:" not in out


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


# ---------------------------------------------------------------------------
# plugins --help metavar
# ---------------------------------------------------------------------------

class TestPluginsHelpMetavar:
    def test_plugins_help_has_no_blank_positional_entry(self, capsys):
        """agent-notes plugins --help must not show a blank positional-argument line."""
        import sys
        from agent_notes.cli import main

        with pytest.raises(SystemExit) as exc:
            sys.argv = ["agent-notes", "plugins", "--help"]
            main()

        assert exc.value.code == 0
        out = capsys.readouterr().out
        # The help output must not contain a blank "positional arguments:" label
        # which appears when metavar="" creates an empty heading line.
        lines = out.splitlines()
        positional_idx = next(
            (i for i, l in enumerate(lines) if "positional arguments" in l), None
        )
        assert positional_idx is not None, "Expected 'positional arguments' section"
        # The line immediately after "positional arguments:" must not be blank
        # (a blank line here is the symptom of metavar="")
        after_heading = lines[positional_idx + 1] if positional_idx + 1 < len(lines) else ""
        assert after_heading.strip() != "", (
            "Blank line after 'positional arguments:' — plugins subparser metavar is empty"
        )
