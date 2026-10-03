"""build removes what the source no longer has, so it is no longer installed (spec 007 FR-A12)."""
import pytest

import agent_notes.config as config
from agent_notes.commands.build import build
from agent_notes.commands.install import install
from tests.functional.commands.cleanup_world import World


@pytest.fixture
def world(tmp_path, monkeypatch):
    return World(tmp_path, monkeypatch)


def _plant(world):
    """Files an earlier build rendered from sources that have since been removed."""
    stale = {
        world.dist / "rules" / "removed-rule.md": "x",
        world.dist / "claude" / "agents" / "removed-agent.md": "x",
        world.dist / "codex" / "agents" / "removed-agent.toml": "x",
        world.dist / "opencode" / "agents" / "removed-agent.md": "x",
    }
    for path, text in stale.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    return list(stale)


class TestBuildPrunes:
    def test_a_rule_or_agent_removed_from_the_source_is_gone_from_dist(self, world):
        stale = _plant(world)

        build()

        assert [p for p in stale if p.exists()] == []

    def test_what_the_source_still_has_is_rendered_again(self, world):
        _plant(world)

        build()

        assert (world.dist / "claude" / "agents" / "coder.md").is_file()
        assert list((world.dist / "rules").glob("*.md"))
        assert list((world.dist / "codex" / "agents").glob("*.toml"))

    def test_a_removed_source_rule_leaves_dist_when_the_source_dir_loses_it(self, world, tmp_path, monkeypatch):
        rules = tmp_path / "source-rules"
        rules.mkdir()
        (rules / "keep.md").write_text("keep")
        (rules / "drop.md").write_text("drop")
        monkeypatch.setattr(config, "RULES_DIR", rules)
        build()
        assert (world.dist / "rules" / "drop.md").exists()

        (rules / "drop.md").unlink()
        build()

        assert sorted(p.name for p in (world.dist / "rules").iterdir()) == ["keep.md"]

    def test_the_other_dist_content_is_untouched(self, world):
        _plant(world)
        marker = world.dist / "claude" / "commands"
        before = sorted(p.name for p in marker.iterdir())

        build()

        assert sorted(p.name for p in marker.iterdir()) == before
        assert (world.dist / "claude" / "CLAUDE.md").is_file()


class TestAndSoItIsNoLongerInstalled:
    def test_a_reinstall_places_neither_the_removed_rule_nor_the_removed_agent(self, world):
        world.use("main")
        _plant(world)

        install(local=True)

        claude = world.project / ".claude"
        assert not (claude / "rules" / "removed-rule.md").exists()
        assert not (claude / "agents" / "removed-agent.md").exists()
        assert (claude / "agents" / "coder.md").is_symlink()


class TestAFailedRenderLeavesDistIntact:
    def test_generate_agent_files_raising_changes_nothing(self, world):
        stale = _plant(world)
        before = world.dist_files()

        from unittest.mock import patch
        with patch("agent_notes.commands.build.generate_agent_files", side_effect=RuntimeError("no model")):
            with pytest.raises(RuntimeError, match="no model"):
                build()

        assert world.dist_files() == before
        assert all(p.exists() for p in stale)

    def test_copy_global_files_raising_changes_nothing_either(self, world):
        stale = _plant(world)
        before = world.dist_files()

        from unittest.mock import patch
        with patch("agent_notes.commands.build.copy_global_files", side_effect=RuntimeError("no rules")):
            with pytest.raises(RuntimeError):
                build()

        assert all(p.exists() for p in stale)
