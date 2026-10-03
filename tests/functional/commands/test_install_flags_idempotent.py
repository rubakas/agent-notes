"""A flags reinstall changes nothing it need not (spec 007 review R2), and untrusted input is
validated or escaped before it is used or printed."""
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from agent_notes.cli import main
from agent_notes.commands.install import install
from agent_notes.services.install_plan import plan_install, summarize_plan
from agent_notes.services.install_ownership import replacing
from agent_notes.services.state_store import load_state
from tests.functional.commands.cleanup_world import World


@pytest.fixture
def world(tmp_path, monkeypatch):
    return World(tmp_path, monkeypatch)


def _files(world):
    """mtimes of everything placed, except the project AGENTS.md: codex and opencode both write it
    (last writer wins), so each install rewrites it twice with the same final content."""
    return {p: p.lstat().st_mtime_ns for p in sorted(world.project.rglob("*"))
            if (p.is_file() or p.is_symlink()) and p.name != "AGENTS.md"}


def _baks(world):
    return [p for p in world.project.rglob("*.bak.*")]


class TestAFlagsReinstallIsIdempotent:
    def test_copy_mode_rewrites_nothing_and_backs_up_nothing(self, world):
        world.use("main")
        install(local=True, copy=True)
        tree, mtimes = world.tree(), _files(world)

        install(local=True, copy=True, assume_yes=True)

        assert _baks(world) == []
        assert world.tree() == tree
        assert _files(world) == mtimes

    def test_symlink_mode_renders_the_same_dist_both_times(self, world):
        world.use("main")
        install(local=True)
        first_dist, tree = world.dist_files(), world.tree()

        install(local=True, assume_yes=True)

        assert world.dist_files() == first_dist
        assert world.tree() == tree

    def test_the_first_install_renders_the_text_a_reinstall_renders(self, world):
        world.use("main")
        install(local=True)
        first = (world.dist / "claude" / "agents" / "coder.md").read_text()
        assert "Memory is not configured" not in first

        install(local=True, assume_yes=True)

        assert (world.dist / "claude" / "agents" / "coder.md").read_text() == first

    def test_a_persisted_obsidian_memory_is_rendered_as_saved(self, world, tmp_path):
        import json
        world.use("main")
        install(local=True)
        state = json.loads(world.state_file.read_text())
        state["memory"] = {"backend": "obsidian", "path": str(tmp_path / "vault"), "strategy": "single-brain"}
        world.state_file.write_text(json.dumps(state))

        install(local=True, assume_yes=True)

        assert str(tmp_path / "vault") in (world.dist / "claude" / "agents" / "coder.md").read_text()


class TestThePlanCountsEachBackupOnce:
    def test_a_foreign_project_agents_md_shared_by_codex_and_opencode(self, world):
        world.use("main")
        (world.project / "AGENTS.md").write_text("my own project instructions")

        for copy in (False, True):
            plan = summarize_plan(plan_install(scope="local", copy_mode=copy))
            assert len([a for a in plan.overwrites if a.dst.name == "AGENTS.md"]) == 1, copy

    def test_the_plan_matches_the_backups_the_install_makes(self, world):
        world.use("main")
        (world.project / "AGENTS.md").write_text("my own project instructions")
        planned = len(summarize_plan(plan_install(scope="local", copy_mode=True)).overwrites)

        install(local=True, copy=True)

        backups = [p for p in world.project.iterdir() if ".bak." in p.name]
        assert planned == len(backups) == 1
        assert backups[0].read_text() == "my own project instructions"


class TestUntrustedPathsAreEscapedWhenPrinted:
    def test_the_confirm_summary_and_the_removed_line(self, world, monkeypatch, capsys):
        world.use("main")
        install(local=True)
        evil = world.project / ".claude" / "skills" / "retired\x1b[31mskill\nFAKE"
        evil.symlink_to(world.dist / "skills" / "retired-skill")
        monkeypatch.setattr("agent_notes.commands.install.has_terminal", lambda: True)
        monkeypatch.setattr("agent_notes.services.ui._safe_input", lambda prompt, default="": "y")
        capsys.readouterr()

        install(local=True)

        out = capsys.readouterr().out
        assert "\x1b[31mskill" not in out
        assert "retired\\x1b[31mskill\\nFAKE" in out
        assert out.count("retired\\x1b[31mskill\\nFAKE") >= 2   # summary and REMOVED line
        assert not evil.is_symlink()


class TestHomeAndFolderAreValidatedAtInput:
    @pytest.fixture
    def guarded(self, world):
        world.use("main")
        with patch("agent_notes.commands.build.build") as build:
            yield world, build

    def _run(self, monkeypatch, *argv):
        monkeypatch.setattr(sys, "argv", ["agent-notes", "install", *argv])
        with pytest.raises(SystemExit) as raised:
            main()
        return raised.value.code

    @pytest.mark.parametrize("value", ["/", "~", "~/..", "$PARENT"])
    def test_a_global_home_at_or_above_home_is_refused_before_anything_is_built(
            self, guarded, monkeypatch, capsys, value):
        world, build = guarded
        value = str(world.home.parent) if value == "$PARENT" else value

        code = self._run(monkeypatch, "--global-home", value)

        assert code == 2
        assert "--global-home" in capsys.readouterr().out
        build.assert_not_called()
        assert not world.state_file.exists()

    @pytest.mark.parametrize("value", ["/", "~", "."])
    def test_a_folder_that_is_a_root_home_or_the_project_itself_is_refused(
            self, guarded, monkeypatch, capsys, value):
        world, build = guarded

        code = self._run(monkeypatch, "--local", "--folder", value)

        assert code == 2
        assert "--folder" in capsys.readouterr().out
        build.assert_not_called()

    @pytest.mark.parametrize("label", ["../x", "a/b", "a\\b", "work\x1b[31m", "two\nlines"])
    def test_a_profile_label_that_is_not_a_folder_name_is_refused(
            self, guarded, monkeypatch, capsys, label):
        world, build = guarded

        code = self._run(monkeypatch, "--local", "--profile", label)

        out = capsys.readouterr().out
        assert code == 2
        assert "--profile" in out
        assert "\x1b" not in out
        build.assert_not_called()
        assert not world.state_file.exists()
        assert list(world.project.iterdir()) == []

    def test_a_profile_label_with_a_space_is_not_restricted(self, world, monkeypatch):
        world.use("main")
        monkeypatch.setattr(sys, "argv", ["agent-notes", "install", "--local", "--profile", "my work"])

        main()

        assert (world.project / ".claude-my work" / "agents").is_dir()

    @pytest.mark.parametrize("value", ["../x", "/abs/elsewhere", "a/../../x", "a\x1b[31mb", "~/.claude-w", "~nouser_zz"])
    def test_a_folder_the_plan_would_refuse_is_refused_up_front(
            self, guarded, monkeypatch, capsys, value):
        world, build = guarded

        code = self._run(monkeypatch, "--local", "--folder", value)

        out = capsys.readouterr().out
        assert code == 2
        assert "--folder" in out and "\x1b" not in out
        build.assert_not_called()
        assert not world.state_file.exists()
        assert list(world.project.iterdir()) == []

    def test_a_global_home_of_an_unknown_user_is_refused_not_a_traceback(self, guarded, monkeypatch, capsys):
        world, build = guarded

        code = self._run(monkeypatch, "--global-home=~nouser_zz/x")

        assert code == 2
        assert "--global-home" in capsys.readouterr().out
        build.assert_not_called()
        assert not world.state_file.exists()

    def test_a_global_home_with_a_control_character_is_refused(self, guarded, monkeypatch, capsys):
        world, build = guarded

        code = self._run(monkeypatch, "--global-home", "~/a\x1b[31mb")

        out = capsys.readouterr().out
        assert code == 2
        assert "--global-home" in out and "\x1b" not in out
        build.assert_not_called()

    def test_a_profile_style_home_and_folder_are_fine(self, world, monkeypatch):
        world.use("main")
        monkeypatch.setattr(sys, "argv", ["agent-notes", "install", "--local", "--profile", "work",
                                          "--folder", ".claude-work", "--global-home", "~/.claude-work"])

        main()

        assert (world.project / ".claude-work" / "agents").is_dir()
