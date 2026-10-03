"""Reinstalling over our own files makes no backups, and the plan says so (spec 007 FR-A09)."""
import pytest

from agent_notes.commands.install import install
from agent_notes.services.install_ownership import replacing
from agent_notes.services.install_plan import plan_install, summarize_plan
from agent_notes.services.state_store import load_state
from tests.functional.commands.cleanup_world import World


@pytest.fixture
def world(tmp_path, monkeypatch):
    return World(tmp_path, monkeypatch)


def _baks(world):
    return [p for root in (world.home, world.project) for p in root.rglob("*.bak.*")]


def _agents(world):
    return sorted((world.project / ".claude" / "agents").glob("*.md"))


def _plan(world, copy):
    existing = load_state().local_installs[str(world.project)]
    with replacing(existing):
        return summarize_plan(plan_install(scope="local", copy_mode=copy))


class TestCopyOverCopy:
    def test_makes_no_backups_and_the_plan_counts_none(self, world):
        world.use("main")
        install(local=True, copy=True)

        assert _plan(world, copy=True).overwrites == []
        install(local=True, copy=True, assume_yes=True)

        assert _baks(world) == []

    def test_a_render_that_changed_since_is_replaced_without_a_backup(self, world):
        world.use("main")
        install(local=True, copy=True)
        (world.dist / "claude" / "agents" / "coder.md").write_text("a newer render")
        placed = world.project / ".claude" / "agents" / "coder.md"

        assert _plan(world, copy=True).overwrites == []
        from agent_notes.services.installer import install_all
        with replacing(load_state().local_installs[str(world.project)]):
            install_all("local", copy_mode=True)

        assert placed.read_text() == "a newer render"
        assert _baks(world) == []

    def test_a_copy_the_user_edited_is_the_only_one_backed_up(self, world):
        world.use("main")
        install(local=True, copy=True)
        edited = world.project / ".claude" / "agents" / "coder.md"
        edited.write_text("my edit")

        assert len(_plan(world, copy=True).overwrites) == 1
        install(local=True, copy=True, assume_yes=True)

        (backup,) = _baks(world)
        assert backup.name.startswith("coder.md.bak.") and backup.read_text() == "my edit"
        assert edited.read_text() != "my edit"


class TestFlippingTheMode:
    def test_copy_to_symlink_ends_with_links_and_state_says_symlink(self, world):
        world.use("main")
        install(local=True, copy=True)

        install(local=True, assume_yes=True)

        assert all(p.is_symlink() for p in _agents(world))
        assert all(p.is_symlink() for p in (world.project / ".claude" / "rules").glob("*.md"))
        assert all(p.is_symlink() for p in (world.project / ".claude" / "skills").iterdir())
        assert load_state().local_installs[str(world.project)].mode == "symlink"
        assert _baks(world) == []

    def test_symlink_to_copy_ends_with_files_and_state_says_copy(self, world):
        world.use("main")
        install(local=True)

        assert len(_plan(world, copy=True).to_install) > 0
        install(local=True, copy=True, assume_yes=True)

        assert _agents(world) and not any(p.is_symlink() for p in _agents(world))
        assert not any(p.is_symlink() for p in (world.project / ".claude" / "skills").iterdir())
        assert load_state().local_installs[str(world.project)].mode == "copy"
        assert _baks(world) == []

    def test_the_tree_matches_installing_in_that_mode_alone(self, world):
        world.use("flipped")
        install(local=True, copy=True)
        install(local=True, assume_yes=True)
        flipped = world.tree()
        world.use("alone")
        install(local=True)

        assert flipped == world.tree()


class TestAForeignLinkAtATarget:
    def test_ends_up_as_a_backup_the_user_can_restore(self, world):
        world.use("main")
        target = world.project / ".claude" / "agents"
        target.mkdir(parents=True)
        (target / "coder.md").symlink_to("/elsewhere/coder.md")

        install(local=True)

        (backup,) = [p for p in target.iterdir() if ".bak." in p.name]
        assert backup.is_symlink() and str(backup.readlink()) == "/elsewhere/coder.md"
        assert (target / "coder.md").is_symlink() and (target / "coder.md").exists()
