"""Functional tests for the update command."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

import agent_notes.config as config


# ── Helpers ────────────────────────────────────────────────────────────────────

# build() is lazily imported inside update(), so patch at definition site.
_PATCH_BUILD = "agent_notes.commands.build.build"
# install() is lazily imported inside update(), so patch at definition site.
_PATCH_INSTALL = "agent_notes.commands.install.install"


def _write_minimal_state(sf: Path) -> None:
    data = {
        "source_path": "/tmp/repo",
        "source_commit": "abc123",
        "global": {
            "installed_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-01T00:00:00Z",
            "mode": "symlink",
            "clis": {"claude": {"role_models": {}, "installed": {}}},
        },
        "local": {},
        "memory": {"backend": "local", "path": ""},
    }
    sf.parent.mkdir(parents=True, exist_ok=True)
    sf.write_text(json.dumps(data))


def _setup(tmp_path, monkeypatch):
    """Redirect state.json and dist to tmp; write minimal state."""
    xdg = tmp_path / "config"
    xdg.mkdir()
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
    sf = xdg / "agent-notes" / "state.json"
    _write_minimal_state(sf)
    monkeypatch.setattr(config, "DIST_DIR", tmp_path / "dist")
    monkeypatch.setattr(config, "DIST_SKILLS_DIR", tmp_path / "dist" / "skills")
    monkeypatch.setattr(config, "DIST_RULES_DIR", tmp_path / "dist" / "rules")
    return sf


def _fake_diff(has_changes: bool = False):
    d = MagicMock()
    d.has_changes.return_value = has_changes
    return d


# ── Tests ──────────────────────────────────────────────────────────────────────

class TestUpdateCallsBuild:
    def test_update_calls_build(self, tmp_path, monkeypatch):
        _setup(tmp_path, monkeypatch)
        mock_build = MagicMock()
        fake_diff = _fake_diff(has_changes=False)

        with patch(_PATCH_BUILD, mock_build), \
             patch("agent_notes.services.diff.diff_states", return_value=fake_diff), \
             patch("agent_notes.services.diff.render_diff_report", return_value=""), \
             patch("agent_notes.services.diff.filter_diff", return_value=fake_diff), \
             patch("agent_notes.services.install_state_builder.git_head_short", return_value="abc"):
            from agent_notes.commands.update import update
            update(skip_pull=True)

        mock_build.assert_called_once()


class TestUpdateCallsInstallAfterBuild:
    def test_update_calls_install_after_build(self, tmp_path, monkeypatch):
        _setup(tmp_path, monkeypatch)
        fake_diff = _fake_diff(has_changes=True)
        mock_install = MagicMock()

        with patch(_PATCH_BUILD), \
             patch("agent_notes.services.diff.diff_states", return_value=fake_diff), \
             patch("agent_notes.services.diff.render_diff_report", return_value=""), \
             patch("agent_notes.services.diff.filter_diff", return_value=fake_diff), \
             patch("agent_notes.services.install_state_builder.git_head_short", return_value="abc"), \
             patch(_PATCH_INSTALL, mock_install), \
             patch("builtins.input", return_value="y"):
            from agent_notes.commands.update import update
            update(skip_pull=True)

        mock_install.assert_called_once()


class TestUpdateDryRun:
    def test_update_does_not_alter_state_when_dry_run(self, tmp_path, monkeypatch):
        sf = _setup(tmp_path, monkeypatch)
        original = sf.read_text()
        fake_diff = _fake_diff(has_changes=True)
        mock_install = MagicMock()

        with patch(_PATCH_BUILD), \
             patch("agent_notes.services.diff.diff_states", return_value=fake_diff), \
             patch("agent_notes.services.diff.render_diff_report", return_value=""), \
             patch("agent_notes.services.diff.filter_diff", return_value=fake_diff), \
             patch("agent_notes.services.install_state_builder.git_head_short", return_value="abc"), \
             patch(_PATCH_INSTALL, mock_install):
            from agent_notes.commands.update import update
            update(skip_pull=True, dry_run=True)

        mock_install.assert_not_called()
        assert sf.read_text() == original, "dry-run must not modify state.json"
