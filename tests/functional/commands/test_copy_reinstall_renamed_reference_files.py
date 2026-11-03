"""Copy-mode reinstall after a skill's reference files are renamed (spec 008 Req 5,
tasks T08).

Renamed files leave no stale copies because a copy-mode reinstall replaces the whole skill
directory (fs.handle_existing), not because of the spec 007a cleanup. The 007a cleanup
(install_cleanup.remove_stale) is what removes a skill that left dist/ altogether: the second
class covers that on its own."""
import shutil

import pytest

from tests.functional.commands.cleanup_world import World


@pytest.fixture
def world(tmp_path, monkeypatch):
    return World(tmp_path, monkeypatch)


def _plant_skill_v1(world) -> None:
    skill = world.dist / "skills" / "sample-skill"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("---\nname: sample-skill\ndescription: x\n---\n")
    (skill / "a.md").write_text("a v1")
    (skill / "b.md").write_text("b v1")


def _rewrite_skill_v2(world) -> None:
    skill = world.dist / "skills" / "sample-skill"
    (skill / "a.md").unlink()
    (skill / "b.md").unlink()
    (skill / "c.md").write_text("c v2")


class TestCopyModeReinstallReplacesTheSkillDirectorySoRenamedReferenceFilesLeaveNoStaleCopies:
    def test_the_skill_dirs_end_up_with_only_the_new_files_and_no_backup(self, world):
        world.use("main")
        _plant_skill_v1(world)
        world.wizard(copy=True, skills=["sample-skill"])
        claude_dir = world.home / ".claude" / "skills" / "sample-skill"
        mirror_dir = world.paths("main")["agents"] / "skills" / "sample-skill"
        assert (claude_dir / "a.md").exists() and (claude_dir / "b.md").exists()
        assert (mirror_dir / "a.md").exists() and (mirror_dir / "b.md").exists()

        _rewrite_skill_v2(world)
        world.wizard(copy=True, skills=["sample-skill"])

        for d in (claude_dir, mirror_dir):
            assert (d / "c.md").read_text() == "c v2"
            assert not (d / "a.md").exists()
            assert not (d / "b.md").exists()
            assert not any(".bak" in p.name for p in d.parent.rglob("*"))


class TestASkillRemovedFromDistIsCleanedUpByTheStaleCleanup:
    """Here nothing replaces the directory: the skill is simply not placed any more, so only
    install_cleanup.remove_stale can remove its old copies, and only while they are unedited."""

    def test_an_unedited_copy_is_removed_and_an_edited_one_is_kept(self, world):
        world.use("main")
        for name in ("kept-skill", "gone-skill", "edited-skill"):
            skill = world.dist / "skills" / name
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text(f"---\nname: {name}\ndescription: x\n---\n")
        world.wizard(copy=True)
        claude_skills = world.home / ".claude" / "skills"
        mirror = world.paths("main")["agents"] / "skills"
        (claude_skills / "edited-skill" / "SKILL.md").write_text("the user's own edit")

        for name in ("gone-skill", "edited-skill"):
            shutil.rmtree(world.dist / "skills" / name)
        world.wizard(copy=True)

        assert not (claude_skills / "gone-skill").exists()
        assert not (mirror / "gone-skill").exists()
        assert (claude_skills / "edited-skill" / "SKILL.md").read_text() == "the user's own edit"
        assert not (mirror / "edited-skill").exists()
        assert (claude_skills / "kept-skill" / "SKILL.md").is_file()
        assert not any(".bak" in p.name for p in claude_skills.rglob("*"))
