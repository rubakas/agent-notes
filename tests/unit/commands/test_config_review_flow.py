"""`agent-notes config` session (spec 005 FR-014, FR-016, FR-017, SC-005, SC-007)."""
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from agent_notes.commands import config_review
from agent_notes.commands.regenerate import regenerate as real_regenerate
from agent_notes.domain.state import BackendState, ScopeState, State
from agent_notes.services import state_store
from agent_notes.services.tui.keys import DOWN, ENTER, ESCAPE, RIGHT, TAB
from tests.unit.tui.fakes import tui_session


@pytest.fixture
def env(tmp_path, monkeypatch):
    """A saved state with one local install in tmp_path/project, and every
    write path replaced by a recorder."""
    project = tmp_path / "project"
    project.mkdir()
    state = State(local_installs={str(project.resolve()): ScopeState(clis={"claude": BackendState(
        role_models={"reasoner": "claude-opus-4-6", "worker": "claude-sonnet-5-5",
                     "scout": "claude-haiku-4-5"},
        role_efforts={"reasoner": "high", "worker": "medium"})})})
    monkeypatch.setattr(state_store, "load_state", lambda: state)
    mocks = {name: MagicMock() for name in ("record", "regenerate", "enable", "disable")}
    monkeypatch.setattr("agent_notes.services.state_store.record_install_state", mocks["record"])
    monkeypatch.setattr("agent_notes.commands.regenerate.regenerate", mocks["regenerate"])
    monkeypatch.setattr("agent_notes.commands.plugins.enable_plugin", mocks["enable"])
    monkeypatch.setattr("agent_notes.commands.plugins.disable_plugin", mocks["disable"])
    monkeypatch.setattr(config_review, "enabled_toggles", lambda *a: {"cost-report": False})
    monkeypatch.setattr("agent_notes.commands.wizard._detect_obsidian_vaults", lambda: [])
    mocks["project"], mocks["state"] = project, state
    return mocks


def _run(env, *keys, cwd=None, width=80):
    ui = tui_session(*keys, width=width)
    config_review.interactive_config(session_factory=lambda: ui, cwd=cwd or env["project"])
    return ui


def test_quitting_without_changes_writes_nothing(env):
    _run(env, "q")
    env["record"].assert_not_called()
    env["regenerate"].assert_not_called()


def test_three_edits_save_with_one_write_and_one_regenerate(env):
    # Models row is focused: u, then Memory → Obsidian, Cost report → on.
    ui = _run(env, "u", DOWN, RIGHT, DOWN, RIGHT, "s", ENTER)
    env["record"].assert_called_once()
    saved = env["record"].call_args.args[0]
    install = saved.local_installs[str(env["project"].resolve())]
    assert install.clis["claude"].role_models["reasoner"] == "claude-opus-5-5"
    assert saved.memory.backend == "obsidian"
    env["regenerate"].assert_called_once_with(scope="local", project_path=env["project"].resolve(),
                                              profile_label="")
    env["enable"].assert_called_once_with("cost-report")
    shown = "\n".join("\n".join(frame) for frame in ui.term.frames)
    assert "claude reasoner: claude-opus-4-6 → claude-opus-5-5" in shown
    assert "cost-report: off → on" in shown
    assert env["state"].memory.backend == "local"  # the loaded state itself is untouched


def test_quit_with_staged_edits_asks_and_escape_keeps_editing(env):
    ui = _run(env, "u", "q", ESCAPE, "q", ENTER)
    env["record"].assert_not_called()
    assert any("Discard 1 change?" in "\n".join(frame) for frame in ui.term.frames)


def test_tab_switches_installs_only_without_staged_edits(env, tmp_path):
    other = tmp_path / "other"
    other.mkdir()
    env["state"].local_installs[str(other.resolve())] = ScopeState(clis={"claude": BackendState()})
    # TAB to the other install and back, stage an edit, then TAB is refused.
    ui = _run(env, TAB, TAB, "u", TAB, "q", ENTER, width=300)  # wide: pytest tmp paths are long
    frames = ["\n".join(frame) for frame in ui.term.frames]
    assert "other" in frames[1].splitlines()[0]
    assert "other" not in frames[2].splitlines()[0]
    assert any("save or discard changes before switching" in frame for frame in frames)


def test_only_local_installs_elsewhere_ask_which_one(env, tmp_path):
    second = tmp_path / "second"
    second.mkdir()
    env["state"].local_installs[str(second.resolve())] = ScopeState(clis={"claude": BackendState()})
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    ui = _run(env, ENTER, "q", cwd=elsewhere)
    assert "Which install?" in "\n".join(ui.term.frames[0])


def test_a_failed_save_says_so_and_stays_open(env):
    env["regenerate"].side_effect = RuntimeError("boom")
    ui = _run(env, "u", "s", ENTER, "q", ENTER)
    assert any("Save failed: boom" in "\n".join(frame) for frame in ui.term.frames)


def test_saving_a_local_install_from_another_folder_places_files_in_that_project(
        env, tmp_path, monkeypatch):
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    monkeypatch.setattr("agent_notes.commands.regenerate.regenerate", real_regenerate)
    monkeypatch.setattr("agent_notes.commands.build.generate_agent_files", MagicMock(return_value=[]))
    monkeypatch.setattr("agent_notes.services.install_state_builder.build_install_state",
                        MagicMock(return_value=State()))
    placed_from = []
    monkeypatch.setattr("agent_notes.services.installer.install_component_for_backend",
                        lambda backend, component, scope, copy: placed_from.append(Path.cwd()))

    _run(env, "u", "s", ENTER, cwd=elsewhere)

    assert placed_from and set(placed_from) == {env["project"].resolve()}
    assert Path.cwd() == elsewhere.resolve()


def test_an_install_whose_folder_is_gone_is_not_saved(env, tmp_path):
    install = env["state"].local_installs.pop(str(env["project"].resolve()))
    env["state"].local_installs[str(tmp_path / "gone")] = install
    ui = _run(env, ENTER, "u", "s", "q", ENTER)   # ENTER picks the only (missing) install
    env["record"].assert_not_called()
    env["regenerate"].assert_not_called()
    assert any("this install's folder no longer exists" in "\n".join(frame)
               for frame in ui.term.frames)


def test_no_terminal_prints_the_settings_and_the_subcommands(env, capsys):
    config_review.interactive_config(session_factory=lambda: None, cwd=env["project"])
    out = capsys.readouterr().out
    assert "Current configuration:" in out   # `show` ran (its layout is Task 14's)
    assert "agent-notes config show | role-model" in out
    env["record"].assert_not_called()


def test_no_installs_exits_1(env, capsys):
    env["state"].local_installs.clear()
    with pytest.raises(SystemExit) as exit_info:
        config_review.interactive_config(session_factory=lambda: None, cwd=env["project"])
    assert exit_info.value.code == 1
    assert "No installation found — run agent-notes install" in capsys.readouterr().out
