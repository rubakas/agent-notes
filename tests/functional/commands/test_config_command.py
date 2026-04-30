"""Functional tests for the `agent-notes config` command."""

import json
import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


# ── Fixtures ─────────────────────────────────────────────────────────────────

def _minimal_state_dict(role="orchestrator", model="claude-sonnet-4-6", cli="claude"):
    return {
        "source_path": "/tmp/test",
        "source_commit": "abc123",
        "global": {
            "installed_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-01T00:00:00Z",
            "mode": "symlink",
            "clis": {
                cli: {
                    "role_models": {role: model},
                    "installed": {},
                }
            },
        },
        "local": {},
        "memory": {"backend": "local", "path": ""},
    }


@pytest.fixture()
def state_file(tmp_path):
    """Write a minimal state.json into a temp dir and return the Path."""
    sf = tmp_path / "state.json"
    sf.write_text(json.dumps(_minimal_state_dict()))
    return sf


def _patch_state_file(state_file):
    """Return a context manager that redirects state_store to tmp state_file.

    state_store.state_file is a callable (not an attribute), so we patch it with
    a MagicMock whose return_value is the tmp path. load_state() and save_state()
    both call state_file() internally, so this correctly intercepts all I/O.
    """
    from agent_notes.services import state_store
    # state_file is a function — patch.object with return_value replaces it with a
    # MagicMock that returns state_file when called, which is the correct form.
    return patch.object(state_store, "state_file", return_value=state_file)


# ── Tests ────────────────────────────────────────────────────────────────────

def test_show_prints_current_state(capsys, state_file):
    from agent_notes.commands.config import show

    with _patch_state_file(state_file):
        show()

    out = capsys.readouterr().out
    assert "orchestrator" in out.lower() or "Orchestrator" in out
    assert "sonnet" in out.lower()


def test_role_model_scriptable_updates_state(state_file):
    from agent_notes.commands.config import role_model

    captured = {}

    def fake_apply(state, *args, **kwargs):
        captured["state"] = state

    with _patch_state_file(state_file), \
         patch("agent_notes.commands.config._apply_and_regenerate", side_effect=fake_apply):
        role_model("orchestrator", "claude-sonnet-4-6")

    assert "state" in captured
    cli_state = captured["state"].global_install.clis["claude"]
    assert cli_state.role_models["orchestrator"] == "claude-sonnet-4-6"


def test_role_model_updates_state_file(state_file):
    from agent_notes.commands.config import role_model

    with _patch_state_file(state_file):
        # Intercept apply to avoid full regenerate, but DO write state
        def _fake_apply(state, before):
            from agent_notes import install_state
            install_state.record_install_state(state)

        with patch("agent_notes.commands.config._apply_and_regenerate", side_effect=_fake_apply):
            role_model("orchestrator", "claude-sonnet-4-6")

    data = json.loads(state_file.read_text())
    assert data["global"]["clis"]["claude"]["role_models"]["orchestrator"] == "claude-sonnet-4-6"


def test_role_model_rejects_unknown_model(state_file):
    from agent_notes.commands.config import role_model

    with _patch_state_file(state_file), pytest.raises(SystemExit) as exc_info:
        role_model("orchestrator", "not-a-real-model-xyz")

    assert exc_info.value.code != 0


def test_role_model_rejects_unknown_role(state_file):
    from agent_notes.commands.config import role_model

    with _patch_state_file(state_file), pytest.raises(SystemExit) as exc_info:
        role_model("not-a-real-role", "claude-sonnet-4-6")

    assert exc_info.value.code != 0


def test_role_model_per_cli(tmp_path):
    """--cli claude only updates Claude, leaves OpenCode untouched."""
    sf = tmp_path / "state.json"
    data = _minimal_state_dict(role="orchestrator", model="claude-opus-4-7", cli="claude")
    # Add opencode CLI too
    data["global"]["clis"]["opencode"] = {
        "role_models": {"orchestrator": "claude-opus-4-7"},
        "installed": {},
    }
    sf.write_text(json.dumps(data))

    from agent_notes.commands.config import role_model
    from agent_notes.services import state_store

    with patch.object(state_store, "state_file", return_value=sf):
        def _fake_apply(state, before):
            from agent_notes import install_state
            install_state.record_install_state(state)

        with patch("agent_notes.commands.config._apply_and_regenerate", side_effect=_fake_apply):
            role_model("orchestrator", "claude-sonnet-4-6", cli_filter="claude")

    result = json.loads(sf.read_text())
    assert result["global"]["clis"]["claude"]["role_models"]["orchestrator"] == "claude-sonnet-4-6"
    assert result["global"]["clis"]["opencode"]["role_models"]["orchestrator"] == "claude-opus-4-7"


def test_apply_then_regenerate_called(state_file):
    """_apply_and_regenerate calls regenerate() when user confirms."""
    from agent_notes.commands.config import _apply_and_regenerate
    from agent_notes.services.state_store import load_state
    from agent_notes.services import ui as ui_mod

    with _patch_state_file(state_file):
        st = load_state()

    before = json.dumps({"dummy": "before"})
    st.memory.backend = "none"  # mutate so there IS a diff

    with _patch_state_file(state_file), \
         patch.object(ui_mod, "_safe_input", return_value="Y"), \
         patch("agent_notes.commands.regenerate.regenerate") as mock_regen, \
         patch("agent_notes.install_state.record_install_state"):
        _apply_and_regenerate(st, before)

    mock_regen.assert_called_once()


def test_apply_regenerate_skipped_on_no(state_file):
    """_apply_and_regenerate does NOT write or regenerate when user says n."""
    from agent_notes.commands.config import _apply_and_regenerate
    from agent_notes.services.state_store import load_state
    from agent_notes.services import ui as ui_mod

    with _patch_state_file(state_file):
        st = load_state()

    before = json.dumps({"dummy": "before"})

    with _patch_state_file(state_file), \
         patch.object(ui_mod, "_safe_input", return_value="n"), \
         patch("agent_notes.commands.regenerate.regenerate") as mock_regen, \
         patch("agent_notes.install_state.record_install_state") as mock_write:
        _apply_and_regenerate(st, before)

    mock_regen.assert_not_called()
    mock_write.assert_not_called()


def test_quit_does_nothing(state_file, capsys):
    """Wizard with q exits without modifying state."""
    from agent_notes.commands.config import interactive_config
    from agent_notes.services import ui as ui_mod

    original = state_file.read_text()

    with _patch_state_file(state_file), \
         patch.object(ui_mod, "_safe_input", return_value="q"):
        interactive_config()

    # State file unchanged
    assert state_file.read_text() == original
