"""The tail of an install reports a failure as an error with a recovery command, not a traceback,
and the recovery command it prints can be pasted into a shell."""
import shlex
import sys

import pytest

from agent_notes.cli import main
from agent_notes.commands._install_helpers import profile_label_problem, rerun_command
from agent_notes.commands.install import install
from tests.functional.commands.cleanup_world import World


@pytest.fixture
def world(tmp_path, monkeypatch):
    return World(tmp_path, monkeypatch)


class TestACleanupThatFailsIsReportedLikeAFailedStateWrite:
    @pytest.mark.parametrize("failing", ["prune_empty", "remove_dropped_hooks", "remove_stale"])
    def test_an_oserror_is_an_error_with_a_rerun_hint(self, world, monkeypatch, capsys, failing):
        world.use("main")
        install(local=True)
        capsys.readouterr()

        def broken(*args, **kwargs):
            raise OSError(13, "Permission denied", str(world.project / ".claude" / "skills"))

        monkeypatch.setattr(f"agent_notes.services.install_cleanup.{failing}", broken)

        with pytest.raises(SystemExit) as raised:
            install(local=True, assume_yes=True)

        err = capsys.readouterr().err
        assert raised.value.code == 1
        assert "could not remove the old install's files" in err
        assert "Permission denied" in err
        assert "agent-notes install --local --yes" in err
        assert "Traceback" not in err


class TestTheRerunCommandIsPasteable:
    def _parsed(self, monkeypatch, command):
        """What the real parser hands to install() for *command*, as a shell would split it."""
        seen = {}
        monkeypatch.setattr("agent_notes.commands.install.install", lambda **kwargs: seen.update(kwargs))
        monkeypatch.setattr(sys, "argv", shlex.split(command))
        main()
        return seen

    @pytest.mark.parametrize("profile, folder, home", [
        ("-x", "-d", "-h"),
        ("my work", "my dir/.claude", "~/my home"),
        ("a'b", "a'b", "~/a'b"),
        ("--yes", ".claude-work", "~/.claude-work"),
    ])
    def test_the_real_parser_reads_back_the_values_it_was_given(self, monkeypatch, profile, folder, home):
        command = rerun_command(local=True, profile_label=profile, folder=folder, global_home=home)

        seen = self._parsed(monkeypatch, command)

        assert (seen["profile_label"], seen["folder"], seen["global_home"]) == (profile, folder, home)
        assert seen["local"] and seen["assume_yes"]

    def test_plain_values_read_naturally(self):
        command = rerun_command(local=True, copy=True, profile_label="work", folder=".claude-work",
                                global_home="~/.claude-work")

        assert command == ("agent-notes install --local --copy --profile=work "
                           "--folder=.claude-work --global-home=~/.claude-work --yes")


class TestAProfileLabelIsAFolderNamePart:
    @pytest.mark.parametrize("label", ["../x", "a/b", "a\\b", "a\x00b", "a\x1bb", "a\nb", "a\x7fb"])
    def test_a_separator_or_control_character_is_refused(self, label):
        assert profile_label_problem(label)

    @pytest.mark.parametrize("label", ["", "work", "my work", "work-2", "wörk", "a.b"])
    def test_everything_else_is_allowed(self, label):
        assert profile_label_problem(label) == ""


class TestTheWizardChecksItsOverridesBeforePlacing:
    @pytest.mark.parametrize("kwargs, flag", [
        ({"folder_overrides": {"claude": "../x"}}, "folder"),
        ({"folder_overrides": {"claude": "/abs/elsewhere"}}, "folder"),
        ({"global_home": "$HOME"}, "home"),
        ({"global_home": "/"}, "home"),
        ({"global_home": "~/a\x1b[31mb"}, "home"),
    ])
    def test_an_unsafe_override_places_nothing_and_exits(self, world, capsys, kwargs, flag):
        world.use("main")
        kwargs = {k: (str(world.home) if v == "$HOME" else v) for k, v in kwargs.items()}
        before = world.tree()

        with pytest.raises(SystemExit) as raised:
            world.wizard(profile="work", scope="local", **kwargs)

        out = capsys.readouterr()
        assert raised.value.code == 2
        assert "\x1b" not in out.out + out.err
        assert world.tree() == before
        assert not world.state_file.exists()


class TestARefusalNamesTheInstallEscaped:
    def test_a_project_folder_with_an_escape_sequence_cannot_repaint_the_terminal(
            self, world, monkeypatch, capsys):
        world.use("main")
        evil = world.root / "main" / "pro\x1b[31mject"
        evil.mkdir()
        monkeypatch.chdir(evil)
        install(local=True)
        capsys.readouterr()

        with pytest.raises(SystemExit) as raised:
            install(local=True)

        out = capsys.readouterr().out
        assert raised.value.code == 2
        assert "Refusing to replace" in out and "\x1b" not in out
