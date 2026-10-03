"""`doctor --fix` deletes only what is ours and inside the install's roots (spec 007 review R1: H1, M5)
and repairs through regenerate, never through a fresh install."""
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import agent_notes.config as config
from agent_notes.domain.diagnostics import FixAction, Issue
from agent_notes.services.diagnostics._fix import do_fix
from agent_notes.services.install_ownership import tree_sha


@pytest.fixture
def env(tmp_path, monkeypatch):
    home = tmp_path / "home"
    pkg = tmp_path / "pkg"
    dist = pkg / "dist"
    (dist / "claude" / "agents").mkdir(parents=True)
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    monkeypatch.setattr(config, "PKG_DIR", pkg)
    monkeypatch.setattr(config, "DIST_DIR", dist)
    monkeypatch.chdir(home)
    return home, dist, tmp_path / "xdg" / "agent-notes" / "state.json"


def _state(path: Path, clis: dict, scope="global") -> None:
    entry = {"installed_at": "2025-01-01T00:00:00Z", "updated_at": "2025-01-01T00:00:00Z",
             "mode": "symlink", "installed_version": "1.0.0", "clis": clis}
    data = {"source_path": "", "source_commit": "", "global": entry if scope == "global" else None,
            "local": {} if scope == "global" else scope, "memory": {"backend": "local", "path": ""}}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))


def _item(target, sha="x", mode="symlink"):
    return {"sha": sha, "target": str(target), "mode": mode}


def _fix(*paths, details="stale"):
    actions = [FixAction("DELETE", str(p), details) for p in paths]
    issues = [Issue("stale", str(p), details) for p in paths]
    with patch("builtins.input", return_value="y"):
        do_fix(issues, actions)


class TestOnlyWhatIsOursAndInsideTheRootsIsDeleted:
    def test_a_manifest_item_of_an_unregistered_cli_pointing_at_a_users_directory_survives(self, env):
        home, _dist, state = env
        project = home / "Documents" / "proj"
        project.mkdir(parents=True)
        (project / "main.py").write_text("print(1)")
        _state(state, {"ghost": {"installed": {"agents": {"proj": _item(project, tree_sha(project), "copy")}}}})

        _fix(project)

        assert (project / "main.py").read_text() == "print(1)"

    def test_a_user_edited_copy_flagged_stale_survives(self, env):
        home, _dist, state = env
        agent = home / ".claude" / "agents" / "a.md"
        agent.parent.mkdir(parents=True)
        agent.write_text("rendered")
        recorded = tree_sha(agent)
        agent.write_text("rendered, then edited by me")
        _state(state, {"claude": {"installed": {"agents": {"a.md": _item(agent, recorded, "copy")}}}})

        _fix(agent)

        assert agent.read_text() == "rendered, then edited by me"

    def test_an_unedited_recorded_copy_inside_its_install_is_deleted(self, env):
        home, _dist, state = env
        agent = home / ".claude" / "agents" / "a.md"
        agent.parent.mkdir(parents=True)
        agent.write_text("rendered")
        _state(state, {"claude": {"installed": {"agents": {"a.md": _item(agent, tree_sha(agent), "copy")}}}})

        _fix(agent)

        assert not agent.exists()

    def test_a_recorded_path_the_user_replaced_with_their_own_link_survives(self, env):
        home, _dist, state = env
        agent = home / ".claude" / "agents" / "a.md"
        agent.parent.mkdir(parents=True)
        agent.symlink_to("/elsewhere/a.md")
        _state(state, {"claude": {"installed": {"agents": {"a.md": _item(agent)}}}})

        _fix(agent)

        assert agent.is_symlink()

    def test_our_dangling_link_in_an_install_dir_is_deleted(self, env):
        home, dist, state = env
        link = home / ".claude" / "agents" / "gone.md"
        link.parent.mkdir(parents=True)
        link.symlink_to(dist / "claude" / "agents" / "gone.md")
        _state(state, {"claude": {"installed": {}}})

        _fix(link)

        assert not link.is_symlink()

    def test_our_link_outside_any_install_dir_survives(self, env):
        home, dist, state = env
        link = home / "Documents" / "x.md"
        link.parent.mkdir()
        link.symlink_to(dist / "claude" / "agents" / "x.md")
        _state(state, {"claude": {"installed": {}}})

        _fix(link)

        assert link.is_symlink()

    def test_a_link_into_a_users_agent_notes_checkout_survives(self, env, tmp_path):
        home, _dist, state = env
        link = home / ".claude" / "agents" / "x.md"
        link.parent.mkdir(parents=True)
        link.symlink_to(tmp_path / "work" / "agent_notes" / "dist" / "x.md")
        _state(state, {"claude": {"installed": {"agents": {"x.md": _item(link)}}}})

        _fix(link)

        assert link.is_symlink()

    def test_a_home_override_of_home_itself_makes_the_whole_install_untrusted(self, env):
        home, dist, state = env
        victim = home / "Documents" / "x.md"
        victim.parent.mkdir()
        victim.symlink_to(dist / "claude" / "agents" / "x.md")
        _state(state, {"claude": {"global_home_override": "~",
                                  "installed": {"agents": {"x.md": _item(victim)}}}})

        _fix(victim)

        assert victim.is_symlink()

    def test_a_manifest_path_through_a_symlinked_parent_survives(self, env, tmp_path):
        home, dist, state = env
        outside = tmp_path / "outside"
        outside.mkdir()
        victim = outside / "a.md"
        victim.symlink_to(dist / "claude" / "agents" / "a.md")
        agents = home / ".claude" / "agents"
        agents.mkdir(parents=True)
        (agents / "sub").symlink_to(outside)
        _state(state, {"claude": {"installed": {"agents": {"a.md": _item(agents / "sub" / "a.md")}}}})

        _fix(agents / "sub" / "a.md")

        assert victim.is_symlink()


class TestRelinkKeepsEveryBackup:
    def test_an_existing_bak_is_not_overwritten(self, env, tmp_path):
        home, dist, state = env
        source = dist / "claude" / "agents" / "a.md"
        source.write_text("rendered")
        target = home / ".claude" / "agents" / "a.md"
        target.parent.mkdir(parents=True)
        target.write_text("user version")
        (target.parent / "a.md.bak").write_text("older backup")
        _state(state, {"claude": {"installed": {}}})
        action = FixAction("RELINK", str(target), f"symlink to {source}")

        with patch("builtins.input", return_value="y"):
            do_fix([Issue("broken", str(target), "x")], [action])

        assert target.is_symlink()
        assert (target.parent / "a.md.bak").read_text() == "older backup"
        backups = [p for p in target.parent.iterdir() if ".bak." in p.name]
        assert [p.read_text() for p in backups] == ["user version"]


class TestRepairingGoesThroughRegenerate:
    def _diagnose(self, scope, answer=None):
        """*answer* is what the user types at "Proceed? [y/N]" (the real do_fix runs); without
        it do_fix is stubbed to succeed."""
        from agent_notes.commands import doctor as doctor_module

        def stale(scope_, issues, fix_actions, profile_label=""):
            issues.append(Issue("version_drift", "state.json", "old"))
            fix_actions.append(FixAction("_TRIGGER_INSTALL", "state.json", "reinstall to update"))

        noop = lambda *a, **k: None
        with patch.object(doctor_module, "check_stale_files", stale), \
             patch.object(doctor_module, "check_broken_symlinks", noop), \
             patch.object(doctor_module, "check_shadowed_files", noop), \
             patch.object(doctor_module, "check_missing_files", noop), \
             patch.object(doctor_module, "check_content_drift", noop), \
             patch.object(doctor_module, "check_build_freshness", noop), \
             patch.object(doctor_module, "check_version_drift", noop), \
             patch.object(doctor_module, "_check_session_hook", noop), \
             patch.object(doctor_module, "check_skill_frontmatter", noop), \
             patch.object(doctor_module, "_check_role_models", noop), \
             patch.object(doctor_module, "_check_wip_components", noop), \
             patch.object(doctor_module, "print_summary"), \
             patch.object(doctor_module, "do_fix", **({} if answer else {"return_value": True})) as fix, \
             patch("builtins.input", return_value=answer), \
             patch("agent_notes.commands.install.install") as install, \
             patch("agent_notes.commands.regenerate.regenerate") as regenerate:
            if answer:
                fix.side_effect = do_fix
            doctor_module.diagnose(scope, fix=True)
        return install, regenerate

    def test_a_global_install_is_regenerated_not_reinstalled(self, env):
        _home, _dist, state = env
        _state(state, {"claude": {"installed": {}}})

        install, regenerate = self._diagnose("global")

        install.assert_not_called()
        regenerate.assert_called_once_with(scope="global", profile_label="")

    def test_declining_the_prompt_regenerates_nothing(self, env):
        _home, _dist, state = env
        _state(state, {"claude": {"installed": {}}})

        install, regenerate = self._diagnose("global", answer="n")

        install.assert_not_called()
        regenerate.assert_not_called()

    def test_accepting_the_prompt_regenerates(self, env):
        _home, _dist, state = env
        _state(state, {"claude": {"installed": {}}})

        _install, regenerate = self._diagnose("global", answer="y")

        regenerate.assert_called_once_with(scope="global", profile_label="")

    def test_a_local_project_regenerates_each_of_its_profiles(self, env, tmp_path):
        home, _dist, state = env
        project = home.resolve()
        entry = {"installed_at": "", "updated_at": "", "mode": "symlink", "installed_version": "1.0.0",
                 "clis": {"claude": {"installed": {}}}}
        _state(state, {}, scope={str(project): entry, f"{project}#work": {**entry, "profile_label": "work"}})

        install, regenerate = self._diagnose("local")

        install.assert_not_called()
        labels = sorted(call.kwargs["profile_label"] for call in regenerate.call_args_list)
        assert labels == ["", "work"]
        assert all(call.kwargs["scope"] == "local" for call in regenerate.call_args_list)

    def test_no_install_means_a_hint_and_no_install(self, env, capsys):
        install, regenerate = self._diagnose("global")

        install.assert_not_called()
        regenerate.assert_not_called()
        assert "agent-notes install" in capsys.readouterr().out


class TestPathsInTheOutputAreEscaped:
    def test_an_escape_sequence_in_a_flagged_path_cannot_repaint_the_terminal(self, env, capsys):
        home, _dist, state = env
        evil = home / "a\x1b[2Jb"
        _state(state, {"claude": {"installed": {}}})

        with patch("builtins.input", return_value="n"):
            do_fix([Issue("stale", str(evil), "x")], [FixAction("DELETE", str(evil), "stale")])
        out = capsys.readouterr().out

        assert "UNSAFE DELETE BLOCKED" in out
        assert "a\x1b[2Jb" not in out
        assert "a\\x1b[2Jb" in out

    def test_the_same_goes_for_the_listing_of_a_fix_that_is_applied(self, env, capsys):
        home, _dist, state = env
        evil = home / ".claude" / "agents" / "a\x1b[2Jb.md"
        _state(state, {"claude": {"installed": {}}})

        with patch("builtins.input", return_value="n"):
            do_fix([Issue("missing", str(evil), "x")], [FixAction("INSTALL", str(evil), "missing")])
        out = capsys.readouterr().out

        assert "INSTALL" in out
        assert "a\x1b[2Jb" not in out


class TestPathsAreEscapedWhenTheFixIsApplied:
    ESC = "a\x1b[2Jb"

    def _apply(self, issue_kind, action, capsys):
        with patch("builtins.input", return_value="y"):
            do_fix([Issue(issue_kind, action.file, "x")], [action])
        out = capsys.readouterr().out
        assert self.ESC not in out
        return out

    def test_a_safe_delete_names_the_path_escaped_in_the_listing_and_when_done(self, env, capsys):
        home, dist, state = env
        agents = home / ".claude" / "agents"
        agents.mkdir(parents=True)
        link = agents / f"{self.ESC}.md"
        link.symlink_to(dist / "claude" / "agents" / "x.md")
        _state(state, {"claude": {"installed": {}}})

        out = self._apply("stale", FixAction("DELETE", str(link), "stale"), capsys)

        assert not link.is_symlink()
        assert "DELETE" in out and "DELETED" in out
        assert out.count("a\\x1b[2Jb") >= 2

    def test_a_relink_names_the_path_escaped_in_the_listing_and_when_done(self, env, capsys):
        home, dist, state = env
        source = dist / "claude" / "agents" / "x.md"
        source.write_text("rendered")
        target = home / ".claude" / "agents" / f"{self.ESC}.md"
        _state(state, {"claude": {"installed": {}}})

        out = self._apply("broken", FixAction("RELINK", str(target), f"symlink to {source}"), capsys)

        assert target.is_symlink()
        assert "RELINKED" in out and out.count("a\\x1b[2Jb") >= 2

    def test_a_failed_relink_names_the_missing_source_escaped(self, env, capsys):
        home, dist, state = env
        source = dist / "claude" / "agents" / f"{self.ESC}.md"
        target = home / ".claude" / "agents" / "x.md"
        _state(state, {"claude": {"installed": {}}})

        out = self._apply("broken", FixAction("RELINK", str(target), f"symlink to {source}"), capsys)

        assert "FAILED" in out and "a\\x1b[2Jb" in out

    def test_a_blocked_symlink_names_its_foreign_target_escaped(self, env, capsys):
        home, _dist, state = env
        link = home / "mine.md"
        link.symlink_to(f"/elsewhere/{self.ESC}.md")
        _state(state, {"claude": {"installed": {}}})

        out = self._apply("stale", FixAction("DELETE", str(link), "stale"), capsys)

        assert "Symlink target" in out and "a\\x1b[2Jb" in out
        assert link.is_symlink()

    def test_a_delete_that_turned_unsafe_while_the_prompt_was_open_is_skipped_by_escaped_name(self, env, capsys):
        home, dist, state = env
        agents = home / ".claude" / "agents"
        agents.mkdir(parents=True)
        link = agents / f"{self.ESC}.md"
        link.symlink_to(dist / "claude" / "agents" / "x.md")
        _state(state, {"claude": {"installed": {}}})

        def swapped_while_asking(_prompt):
            link.unlink()
            link.symlink_to("/elsewhere/theirs.md")
            return "y"

        with patch("builtins.input", swapped_while_asking):
            do_fix([Issue("stale", str(link), "x")], [FixAction("DELETE", str(link), "stale")])
        out = capsys.readouterr().out

        assert "SKIPPED" in out and "a\\x1b[2Jb" in out and self.ESC not in out
        assert link.is_symlink()
