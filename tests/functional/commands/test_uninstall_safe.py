"""Uninstall removes what is ours and nothing else, in both modes (spec 007 FR-A10, SC-003)."""
import os

import pytest

from agent_notes.commands.install import install, uninstall
from agent_notes.services.state_store import load_state
from tests.functional.commands.cleanup_world import World


@pytest.fixture
def world(tmp_path, monkeypatch):
    return World(tmp_path, monkeypatch)


def _user_files(claude, mirror=None):
    """A user agent, rule and skill (with a file next to its SKILL.md), and a foreign link."""
    for sub, name, text in (("agents", "mine.md", "# my agent"), ("rules", "mine.md", "# my rule")):
        (claude / sub).mkdir(parents=True, exist_ok=True)
        (claude / sub / name).write_text(text)
    (claude / "skills" / "mine").mkdir(parents=True, exist_ok=True)
    (claude / "skills" / "mine" / "SKILL.md").write_text("# my skill")
    (claude / "skills" / "foreign").symlink_to("/elsewhere/foreign")
    (claude / "commands").mkdir(exist_ok=True)
    (claude / "commands" / "foreign.md").symlink_to("/elsewhere/foreign.md")
    if mirror is not None:
        mirror.mkdir(parents=True, exist_ok=True)
        (mirror / "foreign").symlink_to("/elsewhere/foreign")
        (mirror / "my-own-skill").mkdir()
        (mirror / "my-own-skill" / "SKILL.md").write_text("# mine")


def _survivors(claude, mirror=None):
    assert (claude / "agents" / "mine.md").read_text() == "# my agent"
    assert (claude / "rules" / "mine.md").read_text() == "# my rule"
    assert (claude / "skills" / "mine" / "SKILL.md").read_text() == "# my skill"
    assert os.readlink(claude / "skills" / "foreign") == "/elsewhere/foreign"
    assert os.readlink(claude / "commands" / "foreign.md") == "/elsewhere/foreign.md"
    if mirror is not None:
        assert os.readlink(mirror / "foreign") == "/elsewhere/foreign"
        assert (mirror / "my-own-skill" / "SKILL.md").read_text() == "# mine"


def _ours_gone(claude):
    left = {p.name for sub in ("agents", "rules", "skills", "commands")
            for p in (claude / sub).glob("*") if (claude / sub).exists()}
    assert left <= {"mine.md", "mine", "foreign", "foreign.md"}, left
    assert not (claude / "CLAUDE.md").exists()


class TestSymlinkInstall:
    def test_global_keeps_user_files_and_foreign_links_including_agents_skills(self, world):
        world.use("main")
        world.wizard()
        claude, mirror = world.home / ".claude", world.paths("main")["agents"] / "skills"
        _user_files(claude, mirror)

        uninstall(global_=True)

        _survivors(claude, mirror)
        _ours_gone(claude)
        assert {p.name for p in mirror.iterdir()} == {"foreign", "my-own-skill"}

    def test_local_keeps_user_files_and_foreign_links(self, world):
        world.use("main")
        install(local=True)
        claude = world.project / ".claude"
        _user_files(claude)

        uninstall(local=True)

        _survivors(claude)
        _ours_gone(claude)


class TestCopyInstall:
    def test_local_keeps_user_files_and_a_file_edited_inside_a_copied_skill(self, world):
        world.use("main")
        install(local=True, copy=True)
        claude = world.project / ".claude"
        _user_files(claude)
        edited_skill = next(p for p in sorted((claude / "skills").iterdir())
                            if p.is_dir() and p.name != "mine" and len(list(p.rglob("*"))) > 1)
        extra = next(p for p in sorted(edited_skill.rglob("*")) if p.is_file() and p.name != "SKILL.md")
        extra.write_text("my edit")
        edited_agent = claude / "agents" / "coder.md"
        edited_agent.write_text("my edited agent")

        uninstall(local=True)

        _survivors(claude)
        assert extra.read_text() == "my edit"
        assert edited_agent.read_text() == "my edited agent"
        untouched = {p.name for p in (claude / "agents").iterdir()}
        assert untouched == {"mine.md", "coder.md"}

    def test_global_copy_keeps_the_agents_skills_user_entries(self, world):
        world.use("main")
        world.wizard(copy=True)
        claude, mirror = world.home / ".claude", world.paths("main")["agents"] / "skills"
        _user_files(claude, mirror)

        uninstall(global_=True)

        _survivors(claude, mirror)
        _ours_gone(claude)
        assert {p.name for p in mirror.iterdir()} == {"foreign", "my-own-skill"}


class TestAnotherInstallStillUsesTheMirror:
    def test_entries_it_records_stay(self, world):
        world.use("main")
        world.wizard()
        world.wizard(profile="work", folder_overrides={"claude": ".claude-work"},
                     global_home=str(world.home / ".claude-work"), skills=world.skills()[:2])
        mirror = world.paths("main")["agents"] / "skills"

        uninstall(global_=True)

        assert sorted(p.name for p in mirror.iterdir()) == world.skills()[:2]
        assert load_state().global_installs["work"]

    def test_the_whole_mirror_stays_if_the_other_install_predates_mirror_records(self, world):
        import json
        world.use("main")
        world.wizard()
        world.wizard(profile="work", folder_overrides={"claude": ".claude-work"},
                     global_home=str(world.home / ".claude-work"))
        state = json.loads(world.state_file.read_text())
        for bs in state["global_installs"]["work"]["clis"].values():
            bs["installed"].pop("skills_mirror", None)
        world.state_file.write_text(json.dumps(state))
        mirror = world.paths("main")["agents"] / "skills"
        before = sorted(p.name for p in mirror.iterdir())

        uninstall(global_=True)

        assert sorted(p.name for p in mirror.iterdir()) == before


class TestWithoutState:
    def test_our_links_are_still_cleaned_and_user_files_stay(self, world):
        world.use("main")
        world.wizard()
        claude, mirror = world.home / ".claude", world.paths("main")["agents"] / "skills"
        _user_files(claude, mirror)
        world.state_file.unlink()

        uninstall(global_=True)

        _survivors(claude, mirror)
        _ours_gone(claude)


class TestAnotherInstallStillUsesTheSessionHook:
    def test_uninstalling_one_global_install_keeps_the_hook_the_other_uses(self, world):
        world.use("main")
        world.wizard(clis=("claude", "codex"))
        world.wizard(clis=("claude", "codex"), profile="work", folder_overrides={"claude": ".claude-work"},
                     global_home=str(world.home / ".claude-work"))
        codex = world.home / ".codex"

        uninstall(global_=True)

        assert "agent-notes-context.md" in (codex / "hooks.json").read_text()
        assert (codex / "agent-notes-context.md").is_file()
        assert list((codex / "agents").glob("*.toml"))

    def test_the_last_install_takes_the_hook_and_the_emptied_home_with_it(self, world):
        world.use("main")
        world.wizard(clis=("claude", "codex"))

        uninstall(global_=True)

        assert not (world.home / ".codex").exists()


class TestUninstallSaysNothingAboutCliesItNeverInstalled:
    def test_no_hook_line_for_a_cli_that_is_not_in_the_manifest(self, world, capsys):
        world.use("main")
        world.wizard(clis=("claude",))
        capsys.readouterr()

        uninstall(global_=True)

        out = capsys.readouterr().out
        assert "Removing Claude Code SessionStart hook" in out
        assert "Codex" not in out
