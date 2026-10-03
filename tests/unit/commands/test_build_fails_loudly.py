"""A build that cannot run raises, so no caller mistakes it for a success."""
import json
import sys
from unittest.mock import patch

import pytest

import agent_notes.config as config
from agent_notes.commands.build import build


def _missing_agents_config(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "AGENTS_YAML", tmp_path / "no-such-agents.yaml")


def test_build_raises_when_the_agents_config_is_missing(tmp_path, monkeypatch):
    _missing_agents_config(monkeypatch, tmp_path)

    with pytest.raises(FileNotFoundError, match="no-such-agents.yaml"):
        build()


def test_the_build_command_exits_non_zero_when_the_agents_config_is_missing(
        tmp_path, monkeypatch, capsys):
    _missing_agents_config(monkeypatch, tmp_path)
    monkeypatch.setattr(sys, "argv", ["agent-notes", "build"])

    from agent_notes.cli import main
    with pytest.raises(SystemExit) as exit_info:
        main()

    assert exit_info.value.code not in (0, None)
    assert "no-such-agents.yaml" in capsys.readouterr().out


def _existing_global_install(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    xdg = tmp_path / "config"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
    state = xdg / "agent-notes" / "state.json"
    state.parent.mkdir(parents=True)
    state.write_text(json.dumps({
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
    }))


def test_install_on_an_existing_install_fails_when_the_rebuild_fails(
        tmp_path, monkeypatch, capsys):
    _existing_global_install(tmp_path, monkeypatch)

    from agent_notes.commands.install import install
    with patch("agent_notes.commands.build.build", side_effect=FileNotFoundError("no agents")), \
         pytest.raises(SystemExit) as exit_info:
        install(assume_yes=True)

    assert exit_info.value.code not in (0, None)
    out = capsys.readouterr().out
    assert "no agents" in out


def test_a_fresh_install_exits_non_zero_when_the_build_fails(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))

    from agent_notes.commands.install import install
    with patch("agent_notes.commands.build.build", side_effect=FileNotFoundError("no agents")), \
         patch("agent_notes.services.installer.install_all") as install_all, \
         pytest.raises(SystemExit) as exit_info:
        install()

    assert exit_info.value.code not in (0, None)
    install_all.assert_not_called()
