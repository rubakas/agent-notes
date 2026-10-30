"""Claude Code's synced-skills mirror and trash must never be touched, renamed or
backed up by install, reinstall, uninstall or doctor --fix, and a shipped skill must
never claim either name (spec 008 Req 5, SC-006/SC-007)."""
import hashlib
from pathlib import Path

import pytest

from agent_notes.commands.build import copy_skills
from agent_notes.commands.doctor import diagnose
from agent_notes.commands.install import install, uninstall
from tests.functional.commands.cleanup_world import World


@pytest.fixture
def world(tmp_path, monkeypatch):
    return World(tmp_path, monkeypatch)


def _tree(root: Path) -> dict:
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file()}


def _plant(claude_skills: Path) -> tuple[dict, dict]:
    synced = claude_skills / "synced" / "some-skill"
    trash = claude_skills / ".trash" / "old-skill"
    synced.mkdir(parents=True)
    trash.mkdir(parents=True)
    (synced / "SKILL.md").write_text("# synced from claude.ai")
    (trash / "file.txt").write_text("leftover")
    return _tree(claude_skills / "synced"), _tree(claude_skills / ".trash")


def _assert_untouched(claude_skills: Path, before: tuple[dict, dict]) -> None:
    assert _tree(claude_skills / "synced") == before[0]
    assert _tree(claude_skills / ".trash") == before[1]
    assert not any(".bak" in p.name for p in claude_skills.rglob("*"))


class TestSymlinkMode:
    def test_untouched_through_install_reinstall_doctor_fix_and_uninstall(self, world, monkeypatch):
        world.use("main")
        world.wizard()
        claude_skills = world.home / ".claude" / "skills"
        before = _plant(claude_skills)

        world.wizard()  # reinstall
        _assert_untouched(claude_skills, before)

        monkeypatch.setattr("builtins.input", lambda *_: "y")
        diagnose("global", fix=True)
        _assert_untouched(claude_skills, before)

        uninstall(global_=True)
        _assert_untouched(claude_skills, before)


class TestCopyMode:
    def test_untouched_through_install_reinstall_doctor_fix_and_uninstall(self, world, monkeypatch):
        world.use("main")
        world.wizard(copy=True)
        claude_skills = world.home / ".claude" / "skills"
        before = _plant(claude_skills)

        world.wizard(copy=True)  # reinstall
        _assert_untouched(claude_skills, before)

        monkeypatch.setattr("builtins.input", lambda *_: "y")
        diagnose("global", fix=True)
        _assert_untouched(claude_skills, before)

        uninstall(global_=True)
        _assert_untouched(claude_skills, before)


class TestASourceSkillNamedSyncedIsRefused:
    def test_copy_skills_refuses_before_touching_dist(self, tmp_path, monkeypatch):
        import agent_notes.config as config
        bad_source = tmp_path / "bad-skills"
        (bad_source / "synced").mkdir(parents=True)
        (bad_source / "synced" / "SKILL.md").write_text("# fake")
        monkeypatch.setattr(config, "SKILLS_DIR", bad_source)

        with pytest.raises(ValueError, match="synced"):
            copy_skills()

    def test_install_refuses_and_leaves_the_real_synced_tree_untouched(self, world, monkeypatch):
        import agent_notes.config as config
        world.use("main")
        world.wizard()
        claude_skills = world.home / ".claude" / "skills"
        before = _plant(claude_skills)

        bad_source = world.root / "bad-skills"
        (bad_source / "synced").mkdir(parents=True)
        (bad_source / "synced" / "SKILL.md").write_text("# fake")
        monkeypatch.setattr(config, "SKILLS_DIR", bad_source)

        with pytest.raises(SystemExit) as raised:
            install(assume_yes=True)

        assert raised.value.code != 0
        _assert_untouched(claude_skills, before)


class TestTheReservedNameMatchIsCaseInsensitive:
    """~/.claude/skills/Synced is the same folder as .../synced on a case-insensitive filesystem."""

    def test_copy_skills_refuses_a_differently_cased_synced(self, tmp_path, monkeypatch):
        import agent_notes.config as config
        bad_source = tmp_path / "bad-skills"
        (bad_source / "Synced").mkdir(parents=True)
        (bad_source / "Synced" / "SKILL.md").write_text("# fake")
        monkeypatch.setattr(config, "SKILLS_DIR", bad_source)

        with pytest.raises(ValueError, match="Synced"):
            copy_skills()

    def test_install_refuses_and_leaves_the_real_synced_tree_untouched(self, world, monkeypatch):
        import agent_notes.config as config
        world.use("main")
        world.wizard()
        claude_skills = world.home / ".claude" / "skills"
        before = _plant(claude_skills)

        bad_source = world.root / "bad-skills"
        (bad_source / "Synced").mkdir(parents=True)
        (bad_source / "Synced" / "SKILL.md").write_text("# fake")
        monkeypatch.setattr(config, "SKILLS_DIR", bad_source)

        with pytest.raises(SystemExit) as raised:
            install(assume_yes=True)

        assert raised.value.code != 0
        _assert_untouched(claude_skills, before)


class TestReservedNamesAreSkippedAtThePointOfUse:
    """Even if a reserved name reaches dist/ some other way, nothing places or reports it."""

    @pytest.fixture
    def dist_skills(self, tmp_path, monkeypatch):
        import agent_notes.config as config
        dist_skills = tmp_path / "dist" / "skills"
        for name in ("Synced", ".trash", "good"):
            (dist_skills / name).mkdir(parents=True)
            (dist_skills / name / "SKILL.md").write_text("# x")
        monkeypatch.setattr(config, "DIST_SKILLS_DIR", dist_skills)
        monkeypatch.setattr(config, "AGENTS_HOME", tmp_path / "agents_home")
        return dist_skills

    def test_universal_mirror_does_not_place_them(self, dist_skills, tmp_path, monkeypatch):
        from agent_notes.services import install_executor
        placed = []
        monkeypatch.setattr(install_executor, "place_file",
                            lambda src, dst, copy_mode: placed.append(dst.name))

        install_executor._install_universal_skills(False, None)

        assert placed == ["good"]

    def test_doctor_does_not_report_them_as_missing(self, dist_skills, tmp_path, monkeypatch):
        from agent_notes.registries.cli_registry import load_registry
        from agent_notes.services.diagnostics._checks import expected_paths_for_install
        monkeypatch.setenv("HOME", str(tmp_path / "home"))

        skills = {(dst.parent.name, dst.name)
                  for _src, dst, _backend, component in expected_paths_for_install(load_registry(), "global")
                  if component == "skills"}

        assert skills
        assert {name for _parent, name in skills} == {"good"}
