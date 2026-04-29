"""Functional tests for the info command."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


# ── Helpers ────────────────────────────────────────────────────────────────────

def _write_minimal_state(sf: Path) -> None:
    data = {
        "source_path": "/tmp/repo",
        "source_commit": "abc123",
        "global": {
            "installed_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-01T00:00:00Z",
            "mode": "symlink",
            "clis": {
                "claude": {
                    "role_models": {},
                    "installed": {"agents": ["lead.md", "coder.md"]},
                }
            },
        },
        "local": {},
        "memory": {"backend": "local", "path": ""},
    }
    sf.parent.mkdir(parents=True, exist_ok=True)
    sf.write_text(json.dumps(data))


def _setup_state(tmp_path, monkeypatch):
    xdg = tmp_path / "config"
    xdg.mkdir()
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
    sf = xdg / "agent-notes" / "state.json"
    _write_minimal_state(sf)
    return sf


# ── Tests ──────────────────────────────────────────────────────────────────────

class TestInfoPrintsStatusWhenStateExists:
    def test_info_prints_status_when_state_exists(self, tmp_path, monkeypatch, capsys):
        _setup_state(tmp_path, monkeypatch)

        fake_claude_home = tmp_path / "claude_home"
        (fake_claude_home / "agents").mkdir(parents=True)
        (fake_claude_home / "agents" / "lead.md").write_text("# lead")

        import agent_notes.config as config
        monkeypatch.setattr(config, "CLAUDE_HOME", fake_claude_home)

        from agent_notes.commands.info import show_info
        show_info()

        out = capsys.readouterr().out
        assert "agent-notes" in out
        assert "installed" in out.lower()


class TestInfoHandlesNoInstallGracefully:
    def test_info_handles_no_install_gracefully(self, tmp_path, monkeypatch, capsys):
        xdg = tmp_path / "config"
        xdg.mkdir()
        monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
        # No state.json written → load_current_state() returns None

        import agent_notes.config as config
        # Point CLAUDE_HOME to empty tmp dir so global_ok check is False
        empty_claude = tmp_path / "claude_home"
        empty_claude.mkdir()
        monkeypatch.setattr(config, "CLAUDE_HOME", empty_claude)

        from agent_notes.commands.info import show_info
        show_info()  # must not raise

        out = capsys.readouterr().out
        assert "agent-notes" in out
        # No state → "Last install:" section is absent; status shows "not installed"
        assert "not installed" in out.lower() or "Last install" not in out


class TestInfoIncludesComponentCounts:
    def test_info_includes_component_counts(self, tmp_path, monkeypatch, capsys):
        _setup_state(tmp_path, monkeypatch)

        import agent_notes.config as config
        monkeypatch.setattr(config, "CLAUDE_HOME", tmp_path / "no_claude")

        from agent_notes.commands.info import show_info
        show_info()

        out = capsys.readouterr().out
        # Output should contain "Skills:" and "Agents" count section
        assert "Skills" in out
        assert "Agents" in out or "Components" in out
