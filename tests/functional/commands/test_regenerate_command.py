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
             patch("agent_notes.services.install_state_builder.build_install_state"), \
             patch("agent_notes.services.state_store.record_install_state"):
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


class TestRegeneratePreservesPins:
    """regenerate() rebuilds the state manifest via build_install_state and must
    carry BOTH role_models and role_efforts forward — dropping role_efforts
    silently reverted user effort selections on every regenerate/config change."""

    def _write_pinned_state(self, sf: Path) -> None:
        data = {
            "source_path": "/tmp/repo",
            "source_commit": "abc123",
            "global": {
                "installed_at": "2025-01-01T00:00:00Z",
                "updated_at": "2025-01-01T00:00:00Z",
                "mode": "symlink",
                "clis": {"claude": {
                    "role_models": {"worker": "claude-sonnet-4-6"},
                    "role_efforts": {"worker": "high"},
                    "installed": {},
                }},
            },
            "local": {},
            "memory": {"backend": "local", "path": ""},
        }
        sf.parent.mkdir(parents=True, exist_ok=True)
        sf.write_text(json.dumps(data))

    def test_regenerate_passes_role_models_and_efforts_to_state_builder(self, tmp_path, monkeypatch):
        xdg = tmp_path / "config"
        xdg.mkdir()
        monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
        self._write_pinned_state(xdg / "agent-notes" / "state.json")

        mock_builder = MagicMock(side_effect=Exception("stop before state write"))

        with patch("agent_notes.commands.build.generate_agent_files", return_value=[]), \
             patch("agent_notes.services.installer.install_component_for_backend"), \
             patch("agent_notes.services.install_state_builder.build_install_state", mock_builder):
            from agent_notes.commands.regenerate import regenerate
            regenerate()

        assert mock_builder.call_count == 1
        kwargs = mock_builder.call_args.kwargs
        assert kwargs["role_models"] == {"claude": {"worker": "claude-sonnet-4-6"}}
        assert kwargs["role_efforts"] == {"claude": {"worker": "high"}}
