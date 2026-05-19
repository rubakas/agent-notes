"""Tests that --description is threaded through do_add() to obsidian_write_note."""
import pytest
from pathlib import Path

from agent_notes.commands.memory.notes import do_add


class TestDoAddDescription:
    def test_description_written_to_frontmatter(self, tmp_path, monkeypatch):
        """--description flag value appears in note frontmatter."""
        monkeypatch.setattr(
            "agent_notes.commands.memory._common._load_memory_config",
            lambda: ("obsidian", tmp_path),
        )
        # Prevent index regeneration from failing on a bare tmp_path
        monkeypatch.setattr(
            "agent_notes.services.obsidian_backend.obsidian_regenerate_index",
            lambda vault: None,
        )

        do_add("My Title", "body text", note_type="context", description="test desc")

        written = list(tmp_path.rglob("*.md"))
        assert written, "Expected at least one .md file to be written"
        content = written[0].read_text()
        assert "description: test desc" in content

    def test_empty_description_does_not_error(self, tmp_path, monkeypatch):
        """Calling do_add without description (default '') succeeds."""
        monkeypatch.setattr(
            "agent_notes.commands.memory._common._load_memory_config",
            lambda: ("obsidian", tmp_path),
        )
        monkeypatch.setattr(
            "agent_notes.services.obsidian_backend.obsidian_regenerate_index",
            lambda vault: None,
        )

        do_add("Another Title", "body text", note_type="pattern")

        written = list(tmp_path.rglob("*.md"))
        assert written, "Expected at least one .md file to be written"
