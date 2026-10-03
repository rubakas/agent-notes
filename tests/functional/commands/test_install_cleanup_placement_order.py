"""A reinstall replaces the old install: place, then remove what is stale, then write
state (spec 007 FR-A07, FR-A08, SC-001, SC-003, SC-005).

The oracle: installing A and then B in one HOME leaves the tree that installing B alone
leaves in another."""
import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from agent_notes.commands.install import install
from agent_notes.services.state_store import load_state
from tests.functional.commands.cleanup_world import World, dangling


@pytest.fixture
def world(tmp_path, monkeypatch):
    return World(tmp_path, monkeypatch)


def _a_then_b_equals_b_alone(world, install_a, install_b):
    world.use("a_then_b")
    install_a()
    install_b()
    reinstalled = world.tree()
    world.use("b_alone")
    install_b()
    assert reinstalled == world.tree()


class TestSkillSubset:
    def test_a_subset_leaves_the_tree_of_installing_the_subset_alone(self, world):
        subset = world.skills()[:2]
        assert len(world.skills()) > 2

        _a_then_b_equals_b_alone(world,
                                 lambda: world.wizard(),
                                 lambda: world.wizard(skills=subset))

        world.use("a_then_b")
        assert sorted(p.name for p in (world.home / ".claude" / "skills").iterdir()) == subset
        assert sorted(p.name for p in (world.paths("a_then_b")["agents"] / "skills").iterdir()) == subset

    def test_the_manifest_afterwards_is_the_manifest_of_the_subset_alone(self, world):
        subset = world.skills()[:2]
        manifests = {}
        for name, first in (("a_then_b", True), ("b_alone", False)):
            world.use(name)
            if first:
                world.wizard()
            world.wizard(skills=subset)
            installed = load_state().global_install.clis["claude"].installed
            manifests[name] = {c: sorted(items) for c, items in installed.items()}

        assert manifests["a_then_b"] == manifests["b_alone"]

    def test_the_flags_path_repairs_a_removed_link_to_the_same_tree(self, world):
        world.use("local")
        install(local=True)
        before = world.tree()
        (world.project / ".claude" / "skills" / world.skills()[0]).unlink()

        install(local=True, assume_yes=True)

        assert world.tree() == before


class TestUserFilesSurvive:
    def test_a_user_skill_a_foreign_link_and_an_edit_are_left_alone(self, world):
        world.use("main")
        world.wizard()
        claude_skills = world.home / ".claude" / "skills"
        mirror = world.paths("main")["agents"] / "skills"
        (claude_skills / "mine").mkdir()
        (claude_skills / "mine" / "SKILL.md").write_text("# mine")
        (claude_skills / "foreign").symlink_to("/elsewhere/foreign")
        (mirror / "foreign").symlink_to("/elsewhere/foreign")
        (claude_skills.parent / "agents" / "custom.md").write_text("# my agent")
        (claude_skills.parent / "rules" / "custom.md").write_text("# my rule")

        world.wizard(skills=world.skills()[:1])

        assert (claude_skills / "mine" / "SKILL.md").read_text() == "# mine"
        assert os.readlink(claude_skills / "foreign") == "/elsewhere/foreign"
        assert os.readlink(mirror / "foreign") == "/elsewhere/foreign"
        assert (claude_skills.parent / "agents" / "custom.md").read_text() == "# my agent"
        assert (claude_skills.parent / "rules" / "custom.md").read_text() == "# my rule"


class TestAnIncompleteManifest:
    def test_a_manifest_shrunk_to_agents_only_still_gets_its_stale_skills_cleaned(self, world):
        """The owner's state.json: the claude manifest lists agents and nothing else."""
        subset = world.skills()[:2]
        world.use("shrunk")
        world.wizard()
        state = json.loads(world.state_file.read_text())
        claude = state["global"]["clis"]["claude"]
        claude["installed"] = {"agents": claude["installed"]["agents"]}
        world.state_file.write_text(json.dumps(state))

        world.wizard(skills=subset)
        shrunk = world.tree()
        world.use("alone")
        world.wizard(skills=subset)

        assert shrunk == world.tree()


class TestDroppingACli:
    def _codex(self, world) -> Path:
        return world.home / ".codex"

    def test_its_agents_config_context_and_hook_are_removed(self, world):
        world.use("main")
        world.wizard(clis=("claude", "codex"))
        codex = self._codex(world)
        assert list((codex / "agents").glob("*.toml"))
        assert (codex / "AGENTS.md").is_symlink()
        assert (codex / "agent-notes-context.md").is_file()
        assert "agent-notes-context.md" in (codex / "hooks.json").read_text()

        world.wizard(clis=("claude",))

        assert not (codex / "agents").exists()
        assert not (codex / "AGENTS.md").exists() and not (codex / "AGENTS.md").is_symlink()
        assert not (codex / "agent-notes-context.md").exists()
        hooks = codex / "hooks.json"
        assert not hooks.exists() or "agent-notes-context.md" not in hooks.read_text()
        assert "codex" not in load_state().global_install.clis

    def test_the_tree_matches_installing_claude_alone_exactly(self, world):
        world.use("a_then_b")
        world.wizard(clis=("claude", "codex"))
        world.wizard(clis=("claude",))
        reinstalled = world.tree()
        world.use("b_alone")
        world.wizard(clis=("claude",))

        assert reinstalled == world.tree()
        assert not (world.paths("a_then_b")["home"] / ".codex").exists()

    def test_a_hooks_file_with_a_hook_of_the_users_keeps_the_file_and_the_home(self, world):
        import json
        world.use("main")
        world.wizard(clis=("claude", "codex"))
        hooks = world.home / ".codex" / "hooks.json"
        data = json.loads(hooks.read_text())
        data["hooks"]["Stop"] = [{"hooks": [{"type": "command", "command": "my-own-hook"}]}]
        hooks.write_text(json.dumps(data))

        world.wizard(clis=("claude",))

        assert "my-own-hook" in hooks.read_text()
        assert "agent-notes-context.md" not in hooks.read_text()

    def test_a_hooks_file_that_does_not_parse_is_left_alone(self, world):
        world.use("main")
        world.wizard(clis=("claude", "codex"))
        hooks = world.home / ".codex" / "hooks.json"
        hooks.write_text("{ not json")

        world.wizard(clis=("claude",))

        assert hooks.read_text() == "{ not json"

    def test_another_global_install_that_still_lists_codex_keeps_all_of_it(self, world):
        world.use("main")
        world.wizard(clis=("claude", "codex"))
        world.wizard(clis=("claude", "codex"), profile="work",
                     folder_overrides={"claude": ".claude-work"},
                     global_home=str(world.home / ".claude-work"))
        codex = self._codex(world)
        before = sorted(p.name for p in (codex / "agents").glob("*.toml"))
        assert before

        world.wizard(clis=("claude",))

        assert sorted(p.name for p in (codex / "agents").glob("*.toml")) == before
        assert (codex / "AGENTS.md").is_symlink()
        assert (codex / "agent-notes-context.md").is_file()
        assert "agent-notes-context.md" in (codex / "hooks.json").read_text()


class TestSharedMirror:
    def test_entries_another_global_install_lists_stay_in_agents_skills(self, world):
        world.use("main")
        world.wizard()
        world.wizard(profile="work", folder_overrides={"claude": ".claude-work"},
                     global_home=str(world.home / ".claude-work"))
        mirror = world.paths("main")["agents"] / "skills"
        everything = sorted(p.name for p in mirror.iterdir())

        world.wizard(skills=world.skills()[:2])

        assert sorted(p.name for p in mirror.iterdir()) == everything
        assert len(list((world.home / ".claude" / "skills").iterdir())) == 2

    def test_an_install_that_predates_mirror_records_claims_the_whole_mirror(self, world):
        world.use("main")
        world.wizard()
        world.wizard(profile="work", folder_overrides={"claude": ".claude-work"},
                     global_home=str(world.home / ".claude-work"), skills=world.skills()[:1])
        state = json.loads(world.state_file.read_text())
        for bs in state["global_installs"]["work"]["clis"].values():
            bs["installed"].pop("skills_mirror", None)
        world.state_file.write_text(json.dumps(state))
        mirror = world.paths("main")["agents"] / "skills"
        everything = sorted(p.name for p in mirror.iterdir())

        world.wizard(skills=world.skills()[:2])

        assert sorted(p.name for p in mirror.iterdir()) == everything


class TestPlaceThenCleanThenState:
    def _fail_on_call(self, monkeypatch, n):
        import agent_notes.commands.wizard.execute as execute
        import agent_notes.services.fs as fs
        real = fs.place_file
        calls = []

        def flaky(*args, **kwargs):
            calls.append(args)
            if len(calls) == n:
                raise OSError("disk full")
            return real(*args, **kwargs)

        monkeypatch.setattr(fs, "place_file", flaky)
        monkeypatch.setattr(execute, "place_file", flaky)

    def test_a_failure_while_placing_runs_no_cleanup_and_leaves_state_alone(self, world, monkeypatch):
        world.use("main")
        world.wizard()
        before_tree, before_state = world.tree(), world.state_file.read_bytes()
        self._fail_on_call(monkeypatch, 4)

        with pytest.raises(SystemExit) as raised:
            world.wizard(skills=world.skills()[:2])
        assert raised.value.code == 1

        stale = world.skills()[2:]
        assert all((world.home / ".claude" / "skills" / s).exists() for s in stale)
        assert dangling(world.home) == []
        assert world.state_file.read_bytes() == before_state
        assert world.tree() == before_tree

    def test_rerunning_with_the_same_choices_converges(self, world, monkeypatch):
        subset = world.skills()[:2]
        world.use("flaky")
        world.wizard()
        with monkeypatch.context() as m:
            self._fail_on_call(m, 4)
            with pytest.raises(SystemExit):
                world.wizard(skills=subset)

        world.wizard(skills=subset)
        converged = world.tree()
        world.use("alone")
        world.wizard(skills=subset)

        assert converged == world.tree()

    def test_a_failed_state_write_exits_non_zero_with_the_recovery_command(
            self, world, monkeypatch, capsys):
        world.use("main")
        world.wizard()
        before = world.state_file.read_bytes()

        def refuse(state):
            raise OSError("read-only file system")

        monkeypatch.setattr("agent_notes.services.state_store.record_install_state", refuse)
        with pytest.raises(SystemExit) as raised:
            world.wizard(skills=world.skills()[:2])

        err = capsys.readouterr().err
        assert raised.value.code == 1
        assert "state.json could not be written (read-only file system)" in err
        assert ("Fix the cause, then rerun agent-notes install and pick the same choices.\n"
                "To install the recommended setup on the same target instead: agent-notes install --yes") in err
        assert world.state_file.read_bytes() == before

    def test_a_failed_local_copy_profile_wizard_install_names_that_target_not_the_global_one(
            self, world, monkeypatch, capsys):
        """`agent-notes install --yes` without a terminal would replace the GLOBAL default."""
        world.use("main")
        monkeypatch.setattr("agent_notes.services.state_store.record_install_state",
                            lambda state: (_ for _ in ()).throw(OSError("read-only file system")))

        with pytest.raises(SystemExit):
            world.wizard(scope="local", copy=True, profile="work",
                         folder_overrides={"claude": ".claude-work"}, global_home="~/.claude-work")

        err = capsys.readouterr().err
        assert ("Fix the cause, then rerun agent-notes install and pick the same choices.\n"
                "To install the recommended setup on the same target instead: "
                "agent-notes install --local --copy --profile=work --yes") in err
        assert "agent-notes install --yes\n" not in err

    def test_a_custom_folder_and_home_stay_in_the_flags_form(self, world, monkeypatch, capsys):
        world.use("main")
        monkeypatch.setattr("agent_notes.services.state_store.record_install_state",
                            lambda state: (_ for _ in ()).throw(OSError("read-only file system")))

        with pytest.raises(SystemExit):
            world.wizard(profile="work", folder_overrides={"claude": ".claude-custom"},
                         global_home="~/custom-home")

        assert ("agent-notes install --profile=work --folder=.claude-custom --global-home=~/custom-home --yes"
                in capsys.readouterr().err)

    def test_the_flags_path_fails_the_same_way(self, world, monkeypatch, capsys):
        world.use("main")
        monkeypatch.setattr("agent_notes.services.state_store.record_install_state",
                            lambda state: (_ for _ in ()).throw(OSError("read-only file system")))

        with pytest.raises(SystemExit) as raised:
            install(local=True, profile_label="")

        assert raised.value.code == 1
        assert ("Fix the cause, then rerun to converge: agent-notes install --local --yes"
                in capsys.readouterr().err)

    def test_stale_links_are_removed_only_after_the_new_ones_are_placed(self, world, monkeypatch):
        world.use("main")
        world.wizard()
        order = []
        import agent_notes.services.install_cleanup as cleanup
        import agent_notes.services.state_store as store
        real_remove, real_record = cleanup.remove_stale, store.record_install_state

        def remove(stale, **kwargs):
            order.append(("remove", sorted(p.name for p in (world.home / ".claude" / "skills").iterdir())))
            return real_remove(stale, **kwargs)

        def record(state):
            order.append(("record", None))
            return real_record(state)

        monkeypatch.setattr(cleanup, "remove_stale", remove)
        monkeypatch.setattr(store, "record_install_state", record)
        subset = world.skills()[:2]

        world.wizard(skills=subset)

        assert [kind for kind, _ in order] == ["remove", "record"]
        # at removal time everything was still there: the new links were placed, the stale not yet gone
        assert order[0][1] == world.skills()


class TestAFailedHookIsAnError:
    def test_the_install_exits_non_zero_with_the_recovery_command(self, world, monkeypatch, capsys):
        world.use("main")

        def boom(*args, **kwargs):
            raise RuntimeError("settings.json is not writable")

        monkeypatch.setattr("agent_notes.services.installer._install_session_hook", boom)
        with pytest.raises(SystemExit) as raised:
            world.wizard()

        err = capsys.readouterr().err
        assert raised.value.code == 1
        assert "session hook could not be installed (settings.json is not writable)" in err
        assert ("Fix the cause, then rerun agent-notes install and pick the same choices.\n"
                "To install the recommended setup on the same target instead: agent-notes install --yes") in err
        assert not world.state_file.exists()

    def test_the_flags_path_has_the_same_handler_with_its_exact_flags(self, world, monkeypatch, capsys):
        world.use("main")

        def boom(*args, **kwargs):
            raise RuntimeError("settings.json is not writable")

        monkeypatch.setattr("agent_notes.services.installer._install_session_hook", boom)
        with pytest.raises(SystemExit) as raised:
            install(local=True, copy=True, profile_label="work")

        err = capsys.readouterr().err
        assert raised.value.code == 1
        assert "session hook could not be installed (settings.json is not writable)" in err
        assert ("Fix the cause, then rerun to converge: "
                "agent-notes install --local --copy --profile=work --yes") in err
        assert "Traceback" not in err
        assert not world.state_file.exists()


class TestAPlacementFailureIsAnErrorNotATraceback:
    @pytest.fixture(autouse=True)
    def not_root(self):
        if os.geteuid() == 0:
            pytest.skip("chmod does not stop root")

    def _lock(self, directory):
        directory.chmod(0o555)

    def _unlock(self, directory):
        directory.chmod(0o755)

    def test_the_flags_path_names_the_path_and_changes_nothing(self, world, capsys):
        world.use("main")
        install(local=True)
        stale = world.project / ".claude" / "skills" / "retired-skill"
        stale.symlink_to(world.dist / "skills" / "retired-skill")
        tree, state = world.tree(), world.state_file.read_bytes()
        agents = world.project / ".claude" / "agents"
        self._lock(agents)
        try:
            with pytest.raises(SystemExit) as raised:
                install(local=True, assume_yes=True)
        finally:
            self._unlock(agents)

        err = capsys.readouterr().err
        assert raised.value.code == 1
        assert f"Error: could not place {agents}/" in err and "Permission denied" in err
        assert "Fix the cause, then rerun to converge: agent-notes install --local --yes" in err
        assert "Traceback" not in err
        assert stale.is_symlink()
        assert world.tree() == tree
        assert world.state_file.read_bytes() == state

    def test_the_wizard_path_does_the_same(self, world, capsys):
        world.use("main")
        world.wizard()
        stale = world.home / ".claude" / "skills" / "retired-skill"
        stale.symlink_to(world.dist / "skills" / "retired-skill")
        tree, state = world.tree(), world.state_file.read_bytes()
        agents = world.home / ".claude" / "agents"
        self._lock(agents)
        try:
            with pytest.raises(SystemExit) as raised:
                world.wizard()
        finally:
            self._unlock(agents)

        err = capsys.readouterr().err
        assert raised.value.code == 1
        assert f"Error: could not place {agents}/" in err and "Permission denied" in err
        assert ("Fix the cause, then rerun agent-notes install and pick the same choices.\n"
                "To install the recommended setup on the same target instead: agent-notes install --yes") in err
        assert stale.is_symlink()
        assert world.tree() == tree
        assert world.state_file.read_bytes() == state


class TestAnEmptyMirrorIsAnAnswerNotASilence:
    def test_a_global_install_records_the_mirror_key_even_with_no_skills(self, world):
        world.use("main")

        world.wizard(skills=[])

        installed = load_state().global_install.clis["claude"].installed
        assert installed["skills_mirror"] == {}

    def test_a_zero_skill_install_does_not_freeze_the_mirror_for_the_others(self, world):
        world.use("main")
        world.wizard()
        world.wizard(profile="work", folder_overrides={"claude": ".claude-work"},
                     global_home=str(world.home / ".claude-work"), skills=[])
        mirror = world.paths("main")["agents"] / "skills"

        world.wizard(skills=world.skills()[:2])

        assert sorted(p.name for p in mirror.iterdir()) == world.skills()[:2]
