"""Hermetic CLI smoke-tests for `agent-notes plugins` and related `config` surfaces.

Isolation strategy
------------------
Every test sets XDG_CONFIG_HOME to pytest's per-test `tmp_path`, so the real
user config at ~/.config/agent-notes/config.yaml is never read or written.

No `agent-notes build` or `agent-notes install` calls are made — these tests
cover CONFIG and CLI OUTPUT only.
"""

from __future__ import annotations

import os
import stat
import sys
import yaml
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _run(tmp_path: Path, *args: str):
    """Invoke the real agent-notes entry point via subprocess with XDG isolation.

    Returns a CompletedProcess with stdout and stderr as strings.
    """
    import subprocess

    env = {
        **os.environ,
        "XDG_CONFIG_HOME": str(tmp_path),
    }
    return subprocess.run(
        [sys.executable, "-m", "agent_notes", *args],
        env=env,
        capture_output=True,
        text=True,
    )


def _isolated_config_path(tmp_path: Path) -> Path:
    """Return the config.yaml path that the CLI will use under tmp_path."""
    return tmp_path / "agent-notes" / "config.yaml"


def _real_home_config() -> Path:
    """Return the real user config path (must not be touched by tests)."""
    return Path.home() / ".config" / "agent-notes" / "config.yaml"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestPluginsListEmptyConfig:
    """Case 1: `plugins list` on empty config shows cost-report as [off] with no annotation."""

    def test_cost_report_shown_as_off_when_no_config(self, tmp_path):
        result = _run(tmp_path, "plugins", "list")
        assert result.returncode == 0, f"stderr: {result.stderr}"
        out = result.stdout
        assert "cost-report" in out

    def test_status_is_off_when_no_config(self, tmp_path):
        result = _run(tmp_path, "plugins", "list")
        out = result.stdout
        # The line for cost-report must include [off]
        cost_report_line = next(
            (line for line in out.splitlines() if "cost-report" in line), None
        )
        assert cost_report_line is not None
        assert "[off]" in cost_report_line

    def test_no_default_annotation_when_state_matches_default(self, tmp_path):
        """When plugin is at its default state, no '(default:' annotation appears."""
        result = _run(tmp_path, "plugins", "list")
        out = result.stdout
        cost_report_line = next(
            (line for line in out.splitlines() if "cost-report" in line), ""
        )
        assert "(default:" not in cost_report_line


class TestPluginsInfoCostReport:
    """Case 2: `plugins info cost-report` shows key fields from the plugin manifest."""

    def test_info_shows_default_off(self, tmp_path):
        result = _run(tmp_path, "plugins", "info", "cost-report")
        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert "off" in result.stdout

    def test_info_shows_includes(self, tmp_path):
        result = _run(tmp_path, "plugins", "info", "cost-report")
        assert "cost_reporting" in result.stdout

    def test_info_shows_stop_hook(self, tmp_path):
        result = _run(tmp_path, "plugins", "info", "cost-report")
        assert "Stop" in result.stdout

    def test_info_shows_bash_allow_entry(self, tmp_path):
        result = _run(tmp_path, "plugins", "info", "cost-report")
        assert "Bash(agent-notes cost-report)" in result.stdout


class TestPluginsEnableCostReport:
    """Case 3: `plugins enable cost-report` writes enabled_plugins.cost-report = True."""

    def test_enable_writes_config_file(self, tmp_path):
        result = _run(tmp_path, "plugins", "enable", "cost-report")
        assert result.returncode == 0, f"stderr: {result.stderr}"
        cfg_path = _isolated_config_path(tmp_path)
        assert cfg_path.exists(), "Config file was not created by enable"

    def test_enable_sets_cost_report_true_in_config(self, tmp_path):
        _run(tmp_path, "plugins", "enable", "cost-report")
        cfg_path = _isolated_config_path(tmp_path)
        data = yaml.safe_load(cfg_path.read_text())
        assert data.get("enabled_plugins", {}).get("cost-report") is True

    def test_list_shows_on_after_enable(self, tmp_path):
        _run(tmp_path, "plugins", "enable", "cost-report")
        result = _run(tmp_path, "plugins", "list")
        cost_report_line = next(
            (line for line in result.stdout.splitlines() if "cost-report" in line), ""
        )
        assert "[on]" in cost_report_line

    def test_list_shows_default_annotation_after_enable(self, tmp_path):
        """Enabling flips away from default (off), so annotation '(default: off)' should appear."""
        _run(tmp_path, "plugins", "enable", "cost-report")
        result = _run(tmp_path, "plugins", "list")
        cost_report_line = next(
            (line for line in result.stdout.splitlines() if "cost-report" in line), ""
        )
        assert "(default:" in cost_report_line
        assert "off" in cost_report_line


class TestPluginsDisableCostReport:
    """Case 4: `plugins disable cost-report` writes enabled_plugins.cost-report = False."""

    def test_disable_writes_cost_report_false(self, tmp_path):
        # Enable first so there's something to disable
        _run(tmp_path, "plugins", "enable", "cost-report")
        result = _run(tmp_path, "plugins", "disable", "cost-report")
        assert result.returncode == 0, f"stderr: {result.stderr}"
        cfg_path = _isolated_config_path(tmp_path)
        data = yaml.safe_load(cfg_path.read_text())
        assert data.get("enabled_plugins", {}).get("cost-report") is False

    def test_list_shows_off_after_disable(self, tmp_path):
        _run(tmp_path, "plugins", "enable", "cost-report")
        _run(tmp_path, "plugins", "disable", "cost-report")
        result = _run(tmp_path, "plugins", "list")
        cost_report_line = next(
            (line for line in result.stdout.splitlines() if "cost-report" in line), ""
        )
        assert "[off]" in cost_report_line


class TestConfigSurfaceCoherence:
    """Case 5: `config cost-report on/off` and `plugins list` agree on the same key."""

    def test_config_cost_report_on_reflected_in_plugins_list(self, tmp_path):
        result = _run(tmp_path, "config", "cost-report", "on")
        assert result.returncode == 0, f"stderr: {result.stderr}"
        list_result = _run(tmp_path, "plugins", "list")
        cost_report_line = next(
            (line for line in list_result.stdout.splitlines() if "cost-report" in line), ""
        )
        assert "[on]" in cost_report_line

    def test_config_cost_report_off_reflected_in_plugins_list(self, tmp_path):
        # Turn on first, then off
        _run(tmp_path, "config", "cost-report", "on")
        result = _run(tmp_path, "config", "cost-report", "off")
        assert result.returncode == 0, f"stderr: {result.stderr}"
        list_result = _run(tmp_path, "plugins", "list")
        cost_report_line = next(
            (line for line in list_result.stdout.splitlines() if "cost-report" in line), ""
        )
        assert "[off]" in cost_report_line

    def test_config_and_plugins_write_same_yaml_key(self, tmp_path):
        """Both surfaces must write to enabled_plugins.cost-report in config.yaml."""
        _run(tmp_path, "config", "cost-report", "on")
        cfg_path = _isolated_config_path(tmp_path)
        data = yaml.safe_load(cfg_path.read_text())
        assert data.get("enabled_plugins", {}).get("cost-report") is True


class TestPluginsEnableUnknown:
    """Case 6: `plugins enable nonesuch` prints an 'Unknown plugin' error mentioning the name."""

    def test_unknown_plugin_exits_without_error_code(self, tmp_path):
        """The command should not crash — just print a friendly error."""
        result = _run(tmp_path, "plugins", "enable", "nonesuch")
        # The command prints a message and returns 0 (no sys.exit call in _set_enabled)
        # We test that it does not raise an unhandled exception (returncode != 1 from crash)
        assert result.returncode == 0

    def test_unknown_plugin_names_the_bad_plugin(self, tmp_path):
        result = _run(tmp_path, "plugins", "enable", "nonesuch")
        assert "nonesuch" in result.stdout

    def test_unknown_plugin_lists_known_plugins(self, tmp_path):
        result = _run(tmp_path, "plugins", "enable", "nonesuch")
        assert "cost-report" in result.stdout

    def test_unknown_plugin_message_indicates_unknown(self, tmp_path):
        result = _run(tmp_path, "plugins", "enable", "nonesuch")
        out_lower = result.stdout.lower()
        assert "unknown" in out_lower or "not found" in out_lower or "known" in out_lower

    def test_unknown_plugin_does_not_modify_config(self, tmp_path):
        """Attempting to enable a nonexistent plugin must not create/modify the config."""
        cfg_path = _isolated_config_path(tmp_path)
        existed_before = cfg_path.exists()
        content_before = cfg_path.read_text() if existed_before else None

        _run(tmp_path, "plugins", "enable", "nonesuch")

        if existed_before:
            assert cfg_path.read_text() == content_before
        else:
            assert not cfg_path.exists()


class TestPluginsHelp:
    """Case 7: `plugins --help` metavar shows the four subcommands."""

    def test_help_shows_subcommand_choices(self, tmp_path):
        result = _run(tmp_path, "plugins", "--help")
        # --help is non-zero only if the parser itself fails
        assert result.returncode == 0, f"stderr: {result.stderr}"
        out = result.stdout
        # Metavar is set to "{list,enable,disable,info}"
        assert "list" in out
        assert "enable" in out
        assert "disable" in out
        assert "info" in out

    def test_help_metavar_not_empty(self, tmp_path):
        result = _run(tmp_path, "plugins", "--help")
        out = result.stdout
        # The subaction positional must show the choices, not just a blank positional
        assert "{list,enable,disable,info}" in out


class TestHermeticityGuard:
    """Case 8: enabling a plugin in a tmp XDG dir must not touch the real user config."""

    def test_real_home_config_unchanged_after_enable(self, tmp_path):
        real = _real_home_config()

        # Snapshot before
        existed_before = real.exists()
        content_before = real.read_text() if existed_before else None
        mtime_before = real.stat().st_mtime if existed_before else None

        # Perform an enable in the isolated tmp dir
        _run(tmp_path, "plugins", "enable", "cost-report")

        # Verify the real file is unchanged
        if existed_before:
            assert real.exists(), "Real config was deleted — isolation failure"
            assert real.stat().st_mtime == mtime_before, (
                "Real config mtime changed — tmp XDG isolation leaked"
            )
            assert real.read_text() == content_before, (
                "Real config content changed — tmp XDG isolation leaked"
            )
        else:
            assert not real.exists(), (
                "Real config was created by test — tmp XDG isolation leaked"
            )

    def test_isolated_config_written_to_tmp_not_home(self, tmp_path):
        """Confirm writes land in tmp_path, not home."""
        _run(tmp_path, "plugins", "enable", "cost-report")

        isolated = _isolated_config_path(tmp_path)
        real = _real_home_config()

        assert isolated.exists(), "Isolated config should have been created"
        # The isolated path must be inside tmp_path, not under home
        assert str(isolated).startswith(str(tmp_path))
        assert str(isolated) != str(real)
