"""set_role writes the pin, then hands the re-render to regenerate."""
import json
from unittest.mock import patch

from agent_notes.commands.set_role import set_role
from agent_notes.services.state_store import load_state


def _write_state(xdg_config):
    state = xdg_config / "agent-notes" / "state.json"
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


def test_set_role_records_the_pin_and_calls_regenerate(tmp_path, monkeypatch):
    xdg = tmp_path / "config"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
    _write_state(xdg)

    with patch("agent_notes.commands.regenerate.regenerate") as regenerate:
        set_role("worker", "claude-haiku-4-5", cli="claude", scope="global")

    regenerate.assert_called_once_with(scope="global", cli="claude", project_path=None)
    assert load_state().global_install.clis["claude"].role_models == {"worker": "claude-haiku-4-5"}
