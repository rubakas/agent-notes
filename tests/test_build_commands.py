"""Tests for copy_commands() in agent_notes/commands/build.py."""
import pytest
from pathlib import Path

import agent_notes.config as config
from agent_notes.commands.build import copy_commands


class TestCopyCommands:
    """copy_commands() copies .md files from data/commands/ to dist/claude/commands/."""

    def _setup_source(self, tmp_path, filenames):
        """Create a fake data/commands/ dir with the given filenames."""
        src = tmp_path / "data" / "commands"
        src.mkdir(parents=True)
        for name in filenames:
            (src / name).write_text(f"# {name}\nCommand content.")
        return src

    def test_returns_list_of_paths(self, tmp_path, monkeypatch):
        """copy_commands() must return a list of Path objects."""
        src = self._setup_source(tmp_path, ["plan.md"])
        dist = tmp_path / "dist"

        monkeypatch.setattr(config, "DATA_DIR", tmp_path / "data")
        monkeypatch.setattr(config, "DIST_DIR", dist)

        result = copy_commands()

        assert isinstance(result, list)
        assert all(isinstance(p, Path) for p in result)

    def test_copies_files_to_dist_claude_commands(self, tmp_path, monkeypatch):
        """Files must land in dist/claude/commands/."""
        src = self._setup_source(tmp_path, ["plan.md", "review.md"])
        dist = tmp_path / "dist"

        monkeypatch.setattr(config, "DATA_DIR", tmp_path / "data")
        monkeypatch.setattr(config, "DIST_DIR", dist)

        copy_commands()

        assert (dist / "claude" / "commands" / "plan.md").exists()
        assert (dist / "claude" / "commands" / "review.md").exists()

    def test_all_four_expected_files_present_with_real_data(self, tmp_path, monkeypatch):
        """The real data/commands/ must produce plan, review, debug, brainstorm."""
        dist = tmp_path / "dist"
        # Use real DATA_DIR (do not patch it) but redirect DIST_DIR to tmp
        monkeypatch.setattr(config, "DIST_DIR", dist)

        result = copy_commands()

        dest = dist / "claude" / "commands"
        for filename in ("plan.md", "review.md", "debug.md", "brainstorm.md"):
            assert (dest / filename).exists(), (
                f"Expected {filename} in dist/claude/commands/"
            )

    def test_result_paths_match_created_files(self, tmp_path, monkeypatch):
        """Returned paths must point to the created destination files."""
        src = self._setup_source(tmp_path, ["plan.md", "debug.md"])
        dist = tmp_path / "dist"

        monkeypatch.setattr(config, "DATA_DIR", tmp_path / "data")
        monkeypatch.setattr(config, "DIST_DIR", dist)

        result = copy_commands()

        for path in result:
            assert path.exists(), f"Returned path does not exist: {path}"

    def test_copied_file_content_matches_source(self, tmp_path, monkeypatch):
        """Content of copied files must equal the source content."""
        src = self._setup_source(tmp_path, ["plan.md"])
        dist = tmp_path / "dist"

        monkeypatch.setattr(config, "DATA_DIR", tmp_path / "data")
        monkeypatch.setattr(config, "DIST_DIR", dist)

        copy_commands()

        source_content = (src / "plan.md").read_text()
        dest_content = (dist / "claude" / "commands" / "plan.md").read_text()
        assert dest_content == source_content

    def test_returns_empty_list_when_source_dir_missing(self, tmp_path, monkeypatch):
        """If data/commands/ does not exist, return [] without raising."""
        monkeypatch.setattr(config, "DATA_DIR", tmp_path / "nonexistent")
        monkeypatch.setattr(config, "DIST_DIR", tmp_path / "dist")

        result = copy_commands()

        assert result == []

    def test_non_md_files_are_not_copied(self, tmp_path, monkeypatch):
        """Only .md files should be copied; other file types are ignored."""
        src = tmp_path / "data" / "commands"
        src.mkdir(parents=True)
        (src / "plan.md").write_text("plan")
        (src / "README.txt").write_text("readme")
        (src / "helper.py").write_text("# python")

        dist = tmp_path / "dist"
        monkeypatch.setattr(config, "DATA_DIR", tmp_path / "data")
        monkeypatch.setattr(config, "DIST_DIR", dist)

        result = copy_commands()

        dest = dist / "claude" / "commands"
        assert len(result) == 1
        assert (dest / "plan.md").exists()
        assert not (dest / "README.txt").exists()
        assert not (dest / "helper.py").exists()
