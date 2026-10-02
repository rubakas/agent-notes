"""The `config` wizard branches must never call sys.exit on user typos.

`role-model` / `role-effort` are scriptable and exit 1 on an unknown CLI or model
id. The wizard shares those helpers, but a mistyped answer there has to print a
message and drop back to the menu — exiting would kill the whole session.
"""

import json
import pytest
from unittest.mock import patch


def _state_dict(clis=("claude", "opencode")):
    return {
        "source_path": "/tmp/test",
        "source_commit": "abc123",
        "global": {
            "installed_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-01T00:00:00Z",
            "mode": "symlink",
            "clis": {
                name: {
                    "role_models": {"orchestrator": "claude-sonnet-4-6"},
                    "role_efforts": {"orchestrator": "high"},
                    "installed": {},
                }
                for name in clis
            },
        },
        "local": {},
        "memory": {"backend": "local", "path": ""},
    }


@pytest.fixture()
def state(tmp_path):
    sf = tmp_path / "state.json"
    sf.write_text(json.dumps(_state_dict()))
    from agent_notes.services import state_store
    with patch.object(state_store, "state_file", return_value=sf):
        yield state_store.load_state()


class TestScriptablePathsStayFatal:
    def test_role_model_still_exits_on_unknown_cli(self, state):
        from agent_notes.commands.config import role_model

        with patch("agent_notes.commands.config._load_state", return_value=state), \
             patch("agent_notes.commands.config._apply_and_regenerate"), \
             pytest.raises(SystemExit) as exc:
            role_model("orchestrator", "claude-sonnet-4-6", cli_filter="nope")

        assert exc.value.code == 1

    def test_role_model_still_exits_on_unknown_model(self, state):
        from agent_notes.commands.config import role_model

        with patch("agent_notes.commands.config._load_state", return_value=state), \
             patch("agent_notes.commands.config._apply_and_regenerate"), \
             pytest.raises(SystemExit) as exc:
            role_model("orchestrator", "no-such-model", cli_filter="claude")

        assert exc.value.code == 1
