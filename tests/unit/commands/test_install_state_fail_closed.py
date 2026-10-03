"""An unreadable state.json fails closed (spec 007 FR-A01, FR-A02).

Absent state is a fresh machine; unreadable state is somebody's install we can no
longer see. Treating it as empty would overwrite or orphan every entry in it."""
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

import agent_notes.config as config
import agent_notes.commands.build as build_module
from agent_notes.cli import main
from agent_notes.commands.install import install
from agent_notes.services.state_store import StateUnreadable, load_state, state_file

VALID_ITEM = {"sha": "x", "target": "/t", "mode": "symlink"}

UNREADABLE = {
    "invalid-json": "{ not valid json {{",
    "empty-file": "",
    "not-an-object": "[]",
    "unknown-installed-item-key": json.dumps({
        "source_path": "",
        "source_commit": "",
        "global": {"clis": {"claude": {"installed": {"agents": {
            "lead.md": {**VALID_ITEM, "surprise": 1}}}}}},
        "local": {},
    }),
}


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """A tmp HOME, XDG and project dir, and an empty dist outside the package."""
    root = tmp_path / "claude-501"
    home, pkg, xdg, project = root / "home", root / "pkg", root / "xdg", root / "project"
    for d in (home, pkg, project):
        d.mkdir(parents=True)
    dist = pkg / "dist"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
    monkeypatch.setattr(config, "PKG_DIR", pkg)
    monkeypatch.setattr(config, "DIST_DIR", dist)
    monkeypatch.setattr(build_module, "DIST_DIR", dist)
    monkeypatch.setattr(config, "DIST_RULES_DIR", dist / "rules")
    monkeypatch.setattr(config, "DIST_SKILLS_DIR", dist / "skills")
    monkeypatch.setattr(config, "DIST_CLAUDE_DIR", dist / "claude")
    monkeypatch.setattr(config, "DIST_OPENCODE_DIR", dist / "opencode")
    monkeypatch.setattr(config, "DIST_GITHUB_DIR", dist / "copilot")
    monkeypatch.setattr(config, "AGENTS_HOME", root / "agents_home")
    monkeypatch.chdir(project)
    return state_file(), project, dist


def _write_state(path: Path, text: str) -> bytes:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path.read_bytes()


def _valid_state(scope: str = "global", **scope_extra) -> str:
    entry = {"installed_at": "2025-01-01T00:00:00Z", "updated_at": "2025-01-01T00:00:00Z",
             "mode": "symlink", "installed_version": "0.0.0-old",
             "clis": {"claude": {"role_models": {}, "installed": {}}}, **scope_extra}
    data = {"source_path": "/tmp/repo", "source_commit": "abc",
            "global": None, "local": {}, "memory": {"backend": "local", "path": ""}}
    if scope == "global":
        data["global"] = entry
    else:
        data["local"] = {scope: entry}
    return json.dumps(data)


def _run(monkeypatch, *argv) -> int:
    monkeypatch.setattr(sys, "argv", ["agent-notes", *argv])
    with pytest.raises(SystemExit) as raised:
        main()
    return raised.value.code


class TestLoadState:
    @pytest.mark.parametrize("content", UNREADABLE.values(), ids=UNREADABLE.keys())
    def test_an_unreadable_file_raises_with_its_path_and_cause(self, sandbox, content):
        path, _project, _dist = sandbox
        _write_state(path, content)

        with pytest.raises(StateUnreadable) as raised:
            load_state()

        assert raised.value.path == path
        assert raised.value.cause is not None
        assert str(path) in str(raised.value)

    def test_a_missing_file_is_still_a_fresh_machine(self, sandbox):
        path, _project, _dist = sandbox
        assert not path.exists()

        assert load_state() is None

    def test_a_directory_in_the_place_of_the_file_is_unreadable(self, sandbox):
        path, _project, _dist = sandbox
        path.mkdir(parents=True)

        with pytest.raises(StateUnreadable):
            load_state()


class TestCommandsRefuseUnreadableState:
    @pytest.mark.parametrize("content", UNREADABLE.values(), ids=UNREADABLE.keys())
    @pytest.mark.parametrize("argv", [
        ("install", "--local"),
        ("install", "--local", "--reconfigure"),
        ("uninstall",),
        ("uninstall", "--all-profiles"),
        ("regenerate",),
        ("doctor",),
        ("config", "show"),
    ], ids=lambda argv: " ".join(argv))
    def test_exit_2_names_the_file_and_leaves_it_untouched(
            self, sandbox, monkeypatch, capsys, argv, content):
        path, project, _dist = sandbox
        before = _write_state(path, content)

        code = _run(monkeypatch, *argv)

        err = capsys.readouterr().err
        assert code == 2
        assert f"Error: state file {path} is unreadable" in err
        assert "Fix it or move it aside, then rerun." in err
        assert path.read_bytes() == before
        assert not (project / ".claude").exists()

    def test_the_interactive_install_refuses_before_it_renders_or_installs(
            self, sandbox, monkeypatch, capsys):
        path, _project, _dist = sandbox
        before = _write_state(path, UNREADABLE["invalid-json"])
        reached = []
        import agent_notes.commands.wizard.orchestrator as orchestrator
        monkeypatch.setattr(orchestrator, "_render",
                            lambda *a, **k: reached.append("render"))
        monkeypatch.setattr(orchestrator, "_install",
                            lambda *a, **k: reached.append("install"))

        code = _run(monkeypatch, "install")

        assert code == 2
        assert reached == []
        assert str(path) in capsys.readouterr().err
        assert path.read_bytes() == before

    def test_the_review_screen_for_config_refuses_without_a_traceback(
            self, sandbox, monkeypatch, capsys):
        path, _project, _dist = sandbox
        _write_state(path, UNREADABLE["invalid-json"])

        code = _run(monkeypatch, "config")

        assert code == 2
        assert "Traceback" not in capsys.readouterr().err

    def test_the_build_command_does_not_report_it_as_a_build_failure(
            self, sandbox, monkeypatch, capsys):
        path, _project, _dist = sandbox
        _write_state(path, UNREADABLE["invalid-json"])

        code = _run(monkeypatch, "build")

        captured = capsys.readouterr()
        assert code == 2
        assert "Build failed" not in captured.out + captured.err
        assert str(path) in captured.err


class TestTerminalIsRestoredWhenTheStateIsUnreadable:
    def test_the_tui_session_leaves_cbreak_and_the_alternate_screen(self, tmp_path):
        from agent_notes.services.tui.session import TuiSession
        from agent_notes.services.tui.screen import Style
        events = []

        class Context:
            def __init__(self, name):
                self.name = name

            def __enter__(self):
                events.append(f"enter {self.name}")
                return self

            def __exit__(self, *exc):
                events.append(f"exit {self.name}")
                return False

        session = TuiSession(Context("keys"), Context("term"), Style(False))
        with pytest.raises(StateUnreadable):
            with session:
                raise StateUnreadable(tmp_path / "state.json", ValueError("boom"))

        assert events == ["enter keys", "enter term", "exit term", "exit keys"]


class TestInstallValidatesBeforeItChangesAnything:
    def test_reconfigure_with_a_bad_argument_leaves_state_byte_identical(
            self, sandbox, monkeypatch):
        path, _project, _dist = sandbox
        before = _write_state(path, _valid_state())

        monkeypatch.setattr(sys, "argv", ["agent-notes", "install", "--reconfigure", "--copy"])
        try:
            main()
        except SystemExit:
            pass

        assert path.read_bytes() == before

    def test_reconfigure_with_copy_but_not_local_is_an_error(
            self, sandbox, monkeypatch, capsys):
        _write_state(sandbox[0], _valid_state())

        code = _run(monkeypatch, "install", "--reconfigure", "--copy")

        assert code == 2
        assert "--copy is only valid with --local" in capsys.readouterr().out

    def test_the_validation_error_comes_before_the_state_read(self, sandbox, monkeypatch, capsys):
        path, _project, _dist = sandbox
        _write_state(path, UNREADABLE["invalid-json"])

        code = _run(monkeypatch, "install", "--copy")

        assert code == 2
        assert "--copy is only valid with --local" in capsys.readouterr().out

    def test_reconfigure_replaces_the_scope_entry_it_does_not_merge(self, sandbox):
        path, project, _dist = sandbox
        ghost = {"agents": {"ghost.md": VALID_ITEM}}
        _write_state(path, _valid_state(
            str(project), clis={"claude": {"role_models": {}, "installed": ghost}}))

        install(local=True, reconfigure=True)

        entry = load_state().local_installs[str(project)]
        assert entry.installed_version != "0.0.0-old"
        assert "ghost.md" not in entry.clis["claude"].installed.get("agents", {})
        assert entry.clis["claude"].installed.get("agents")

    def test_reconfigure_never_clears_state_up_front(self, sandbox):
        path, project, _dist = sandbox
        _write_state(path, _valid_state(str(project)))
        seen_during_build = []

        def spy(*args, **kwargs):
            seen_during_build.append(path.exists())

        with patch("agent_notes.commands.build.build", side_effect=spy):
            install(local=True, reconfigure=True)

        assert seen_during_build == [True]
