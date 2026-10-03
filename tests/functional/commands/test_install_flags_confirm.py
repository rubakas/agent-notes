"""Installing over an existing install asks first (spec 007 FR-A11).

`install --local/--copy/--profile/...` on an existing install always replaces and cleans: it
shows what it will place and remove, asks, and without a terminal refuses unless --yes."""
import sys
from unittest.mock import patch

import pytest

from agent_notes.cli import main
from agent_notes.commands.install import install
from tests.functional.commands.cleanup_world import World


@pytest.fixture
def world(tmp_path, monkeypatch):
    return World(tmp_path, monkeypatch)


@pytest.fixture
def existing(world):
    """A local install, and one stale link of ours that the new install would not place."""
    world.use("main")
    install(local=True)
    stale = world.project / ".claude" / "skills" / "retired-skill"
    stale.symlink_to(world.dist / "skills" / "retired-skill")
    return world, stale


def _terminal(monkeypatch, answer=None, *, present=True):
    monkeypatch.setattr("agent_notes.commands.install.has_terminal", lambda: present)
    asked = []

    def answer_with(prompt, default=""):
        asked.append(prompt)
        return answer if answer is not None else default

    monkeypatch.setattr("agent_notes.services.ui._safe_input", answer_with)
    return asked


def _run(monkeypatch, *argv) -> int:
    monkeypatch.setattr(sys, "argv", ["agent-notes", "install", *argv])
    try:
        main()
    except SystemExit as exit_:
        return exit_.code
    return 0


def _unchanged(world, run):
    tree, state = world.tree(), world.state_file.read_bytes()
    code = run()
    assert world.tree() == tree
    assert world.state_file.read_bytes() == state
    return code


class TestThePrompt:
    def test_yes_replaces_and_cleans(self, existing, monkeypatch):
        world, stale = existing
        asked = _terminal(monkeypatch, "y")

        assert _run(monkeypatch, "--local") == 0

        assert asked == ["Replace this install? [y/N]: "]
        assert not stale.is_symlink()

    def test_no_changes_nothing_at_all(self, existing, monkeypatch, capsys):
        world, stale = existing
        _terminal(monkeypatch, "n")

        code = _unchanged(world, lambda: _run(monkeypatch, "--local"))

        assert code == 0
        assert stale.is_symlink()
        assert "Nothing was changed." in capsys.readouterr().out

    def test_an_empty_answer_is_no(self, existing, monkeypatch):
        world, stale = existing
        _terminal(monkeypatch, "")

        _unchanged(world, lambda: _run(monkeypatch, "--local"))

        assert stale.is_symlink()

    def test_the_summary_names_the_install_and_what_changes(self, existing, monkeypatch, capsys):
        world, stale = existing
        _terminal(monkeypatch, "n")

        _run(monkeypatch, "--local")

        out = capsys.readouterr().out
        assert f"Replacing the local install at {world.project}" in out
        assert "files will be placed." in out
        assert "1 stale files will be removed." in out
        assert str(stale) in out

    def test_nothing_stale_says_so(self, world, monkeypatch, capsys):
        world.use("main")
        install(local=True)
        _terminal(monkeypatch, "n")
        capsys.readouterr()

        _run(monkeypatch, "--local")

        assert "Nothing stale to remove." in capsys.readouterr().out

    def test_at_most_ten_stale_items_are_listed(self, existing, monkeypatch, capsys):
        world, _stale = existing
        for i in range(11):
            (world.project / ".claude" / "skills" / f"retired-{i:02}").symlink_to(
                world.dist / "skills" / f"retired-{i:02}")
        _terminal(monkeypatch, "n")

        _run(monkeypatch, "--local")

        out = capsys.readouterr().out
        assert "12 stale files will be removed." in out
        assert out.count("/.claude/skills/retired") == 10
        assert "... 2 more" in out

    def test_the_prompt_names_a_profile_install(self, world, monkeypatch, capsys):
        world.use("main")
        install(local=True, profile_label="work")
        _terminal(monkeypatch, "n")
        capsys.readouterr()

        _run(monkeypatch, "--local", "--profile", "work")

        assert f"Replacing the local install at {world.project} (profile work)" in capsys.readouterr().out


class TestWithoutATerminal:
    def test_refuses_with_a_hint_and_changes_nothing(self, existing, monkeypatch, capsys):
        world, stale = existing
        asked = _terminal(monkeypatch, present=False)

        code = _unchanged(world, lambda: _run(monkeypatch, "--local"))

        assert code == 2
        assert asked == []
        assert (f"Refusing to replace local install at {world.project} without a terminal; "
                "rerun with --yes.") in capsys.readouterr().out
        assert stale.is_symlink()

    def test_yes_replaces_without_asking(self, existing, monkeypatch):
        world, stale = existing
        asked = _terminal(monkeypatch, present=False)

        assert _run(monkeypatch, "--local", "--yes") == 0

        assert asked == []
        assert not stale.is_symlink()

    def test_a_first_install_needs_neither_a_terminal_nor_yes(self, world, monkeypatch):
        world.use("main")
        asked = _terminal(monkeypatch, present=False)

        assert _run(monkeypatch, "--local") == 0

        assert asked == []
        assert (world.project / ".claude" / "agents").is_dir()

    def test_a_different_profile_is_a_first_install_too(self, world, monkeypatch):
        world.use("main")
        install(local=True)
        _terminal(monkeypatch, present=False)

        assert _run(monkeypatch, "--local", "--profile", "work") == 0

    def test_yes_on_a_terminal_skips_the_prompt(self, existing, monkeypatch):
        world, stale = existing
        asked = _terminal(monkeypatch, "n")

        assert _run(monkeypatch, "--local", "--yes") == 0

        assert asked == []
        assert not stale.is_symlink()


class TestReconfigureIsAnAlias:
    def test_it_prompts_exactly_like_the_plain_flags_path(self, existing, monkeypatch):
        world, stale = existing
        asked = _terminal(monkeypatch, "y")

        assert _run(monkeypatch, "--local", "--reconfigure") == 0

        assert asked == ["Replace this install? [y/N]: "]
        assert not stale.is_symlink()

    def test_it_refuses_without_a_terminal_and_yes(self, existing, monkeypatch):
        world, stale = existing
        _terminal(monkeypatch, present=False)

        assert _unchanged(world, lambda: _run(monkeypatch, "--local", "--reconfigure")) == 2

    def test_with_copy_it_is_a_confirmed_reinstall_not_a_new_wizard(self, existing, monkeypatch):
        world, stale = existing
        _terminal(monkeypatch, present=False)

        with patch("agent_notes.commands.wizard.interactive_install") as wizard:
            assert _run(monkeypatch, "--local", "--copy", "--reconfigure", "--yes") == 0

        wizard.assert_not_called()
        assert not (world.project / ".claude" / "agents" / "lead.md").is_symlink()


class TestBareInstallWithoutATerminal:
    @pytest.fixture
    def stubs(self, monkeypatch):
        import agent_notes.commands.wizard.orchestrator as orchestrator
        calls = []
        monkeypatch.setattr(orchestrator, "_render", lambda *a, **k: calls.append("render"))
        monkeypatch.setattr(orchestrator, "_install", lambda *a, **k: calls.append("install"))
        return calls

    def _global_install_exists(self, world):
        world.use("main")
        world.state_file.parent.mkdir(parents=True)
        world.state_file.write_text(
            '{"source_path": "", "source_commit": "", "global": {"mode": "symlink", '
            '"clis": {"claude": {"installed": {}}}}, "local": {}, "memory": {"backend": "local"}}')

    def test_refuses_on_an_existing_install(self, world, stubs, monkeypatch, capsys):
        self._global_install_exists(world)

        code = _unchanged(world, lambda: _run(monkeypatch))

        assert code == 2
        assert stubs == []
        assert ("Refusing to replace global install without a terminal; rerun with --yes."
                in capsys.readouterr().out)

    def test_yes_installs_the_recommended_setup(self, world, stubs, monkeypatch):
        self._global_install_exists(world)

        assert _run(monkeypatch, "--yes") == 0

        assert stubs == ["render", "install"]

    def test_a_first_install_needs_no_yes(self, world, stubs, monkeypatch):
        world.use("main")

        assert _run(monkeypatch) == 0

        assert stubs == ["render", "install"]

    def test_on_a_terminal_yes_changes_nothing(self, world, monkeypatch):
        """The review screen keeps its own confirm: --yes only matters without a terminal."""
        import agent_notes.commands.wizard.orchestrator as orchestrator
        self._global_install_exists(world)
        seen = {}
        monkeypatch.setattr(orchestrator, "_review", lambda *a, **k: seen.setdefault("review", True) and False)
        from tests.unit.tui.fakes import tui_session

        orchestrator.interactive_install(session_factory=lambda: tui_session(), assume_yes=True)

        assert seen == {"review": True}
