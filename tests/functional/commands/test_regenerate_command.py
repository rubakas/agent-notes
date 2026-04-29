"""Functional tests for the regenerate command."""

import json
import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


# ── Helpers ────────────────────────────────────────────────────────────────────

def _write_minimal_state(sf: Path, cli: str = "claude") -> None:
    data = {
        "source_path": "/tmp/repo",
        "source_commit": "abc123",
        "global": {
            "installed_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-01T00:00:00Z",
            "mode": "copy",
            "clis": {cli: {"role_models": {}, "installed": {}}},
        },
        "local": {},
        "memory": {"backend": "local", "path": ""},
    }
    sf.parent.mkdir(parents=True, exist_ok=True)
    sf.write_text(json.dumps(data))


def _setup(tmp_path, monkeypatch, write_state: bool = True):
    xdg = tmp_path / "config"
    xdg.mkdir()
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
    sf = xdg / "agent-notes" / "state.json"
    if write_state:
        _write_minimal_state(sf)
    return sf


# ── Tests ──────────────────────────────────────────────────────────────────────

class TestRegenerateCallsRenderingPipeline:
    def test_regenerate_calls_rendering_pipeline(self, tmp_path, monkeypatch):
        _setup(tmp_path, monkeypatch)
        mock_generate = MagicMock(return_value=[])

        # generate_agent_files is imported from .build inside regenerate(), so patch at source
        with patch("agent_notes.commands.build.generate_agent_files", mock_generate), \
             patch("agent_notes.services.installer.install_component_for_backend"), \
             patch("agent_notes.install_state.build_install_state"), \
             patch("agent_notes.install_state.record_install_state"):
            from agent_notes.commands.regenerate import regenerate
            regenerate()

        mock_generate.assert_called_once()


class TestRegenerateAbortsWhenNoState:
    def test_regenerate_aborts_when_no_state(self, tmp_path, monkeypatch, capsys):
        _setup(tmp_path, monkeypatch, write_state=False)

        from agent_notes.commands.regenerate import regenerate
        with pytest.raises(SystemExit) as exc_info:
            regenerate()

        assert exc_info.value.code != 0
        out = capsys.readouterr().out
        assert "state" in out.lower() or "nothing" in out.lower()


class TestRegeneratePerCLIFilter:
    def test_regenerate_per_cli_filter_rejects_unknown_cli(self, tmp_path, monkeypatch, capsys):
        _setup(tmp_path, monkeypatch)

        with patch("agent_notes.commands.build.generate_agent_files", return_value=[]), \
             patch("agent_notes.services.installer.install_component_for_backend"):
            from agent_notes.commands.regenerate import regenerate
            with pytest.raises(SystemExit) as exc_info:
                regenerate(cli="unknown_cli_xyz")

        assert exc_info.value.code != 0
        out = capsys.readouterr().out
        assert "unknown_cli_xyz" in out or "cli" in out.lower()
