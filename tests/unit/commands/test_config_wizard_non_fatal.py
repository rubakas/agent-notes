"""The `config` wizard branches must never call sys.exit on user typos.

`role-model` / `role-effort` are scriptable and exit 1 on an unknown CLI or model
id. The wizard shares those helpers, but a mistyped answer there has to print a
message and drop back to the menu — exiting would kill the whole session.
"""

import json
import pytest
from unittest.mock import patch

from agent_notes.commands.config import _wizard_role_effort, _wizard_role_model


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


def _answers(*values):
    replies = list(values)
    return patch("agent_notes.services.ui._safe_input",
                 side_effect=lambda prompt, default="": replies.pop(0))


class TestUnknownCliStaysInteractive:
    def test_role_model_branch_returns_false(self, state, capsys):
        with _answers("nope"), \
             patch("agent_notes.commands.config._apply_and_regenerate") as apply_mock:
            result = _wizard_role_model(state, before="{}")

        assert result is False
        apply_mock.assert_not_called()
        out = capsys.readouterr().out
        assert "nope" in out and "No changes made." in out

    def test_role_effort_branch_returns_false(self, state, capsys):
        with _answers("nope"), \
             patch("agent_notes.commands.config._apply_and_regenerate") as apply_mock:
            result = _wizard_role_effort(state, before="{}")

        assert result is False
        apply_mock.assert_not_called()
        assert "No changes made." in capsys.readouterr().out


class TestUnknownModelStaysInteractive:
    def test_role_model_branch_returns_false(self, state, capsys):
        with _answers("both", "orchestrator", "no-such-model"), \
             patch("agent_notes.commands.config._apply_and_regenerate") as apply_mock:
            result = _wizard_role_model(state, before="{}")

        assert result is False
        apply_mock.assert_not_called()
        out = capsys.readouterr().out
        assert "Unknown model: no-such-model" in out
        assert "No changes made." in out


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
