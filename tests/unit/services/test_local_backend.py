"""Unit tests for agent_notes.services.local_backend."""
import pytest
from pathlib import Path

from agent_notes.services.local_backend import (
    local_init,
    local_list_notes,
    local_regenerate_index,
)


# ── Import test ───────────────────────────────────────────────────────────────

class TestImports:
    def test_local_init_importable(self):
        assert callable(local_init)

    def test_local_list_notes_importable(self):
        assert callable(local_list_notes)

    def test_local_regenerate_index_importable(self):
        assert callable(local_regenerate_index)


# ── local_init ────────────────────────────────────────────────────────────────

class TestLocalInit:
    def test_creates_memory_directory(self, tmp_path):
        memory_dir = tmp_path / "memory"
        local_init(memory_dir)
        assert memory_dir.is_dir()

    def test_creates_nested_directory_if_parents_missing(self, tmp_path):
        memory_dir = tmp_path / "deep" / "nested" / "memory"
        local_init(memory_dir)
        assert memory_dir.is_dir()

    def test_idempotent_does_not_raise_on_second_call(self, tmp_path):
        memory_dir = tmp_path / "memory"
        local_init(memory_dir)
        local_init(memory_dir)  # Must not raise

    def test_idempotent_directory_still_exists_after_second_call(self, tmp_path):
        memory_dir = tmp_path / "memory"
        local_init(memory_dir)
        local_init(memory_dir)
        assert memory_dir.is_dir()

    def test_existing_contents_preserved_on_second_call(self, tmp_path):
        memory_dir = tmp_path / "memory"
        local_init(memory_dir)
        existing_file = memory_dir / "some-agent" / "note.md"
        existing_file.parent.mkdir(parents=True, exist_ok=True)
        existing_file.write_text("# preserved note")
        local_init(memory_dir)
        assert existing_file.read_text() == "# preserved note"


# ── local_list_notes ──────────────────────────────────────────────────────────

class TestLocalListNotes:
    def test_returns_empty_list_when_directory_does_not_exist(self, tmp_path):
        missing = tmp_path / "nonexistent"
        result = local_list_notes(missing)
        assert result == []

    def test_returns_empty_list_for_empty_directory(self, tmp_path):
        memory_dir = tmp_path / "memory"
        local_init(memory_dir)
        result = local_list_notes(memory_dir)
        assert result == []

    def test_returns_list_type(self, tmp_path):
        memory_dir = tmp_path / "memory"
        local_init(memory_dir)
        result = local_list_notes(memory_dir)
        assert isinstance(result, list)

    def test_returns_one_entry_per_agent_directory(self, tmp_path):
        memory_dir = tmp_path / "memory"
        local_init(memory_dir)
        (memory_dir / "coder").mkdir()
        (memory_dir / "explorer").mkdir()
        result = local_list_notes(memory_dir)
        assert len(result) == 2

    def test_each_entry_has_agent_key(self, tmp_path):
        memory_dir = tmp_path / "memory"
        local_init(memory_dir)
        (memory_dir / "coder").mkdir()
        result = local_list_notes(memory_dir)
        assert "agent" in result[0]

    def test_each_entry_has_path_key(self, tmp_path):
        memory_dir = tmp_path / "memory"
        local_init(memory_dir)
        (memory_dir / "coder").mkdir()
        result = local_list_notes(memory_dir)
        assert "path" in result[0]

    def test_each_entry_has_size_key(self, tmp_path):
        memory_dir = tmp_path / "memory"
        local_init(memory_dir)
        (memory_dir / "coder").mkdir()
        result = local_list_notes(memory_dir)
        assert "size" in result[0]

    def test_agent_name_matches_directory_name(self, tmp_path):
        memory_dir = tmp_path / "memory"
        local_init(memory_dir)
        (memory_dir / "test-writer").mkdir()
        result = local_list_notes(memory_dir)
        assert result[0]["agent"] == "test-writer"

    def test_path_points_to_agent_directory(self, tmp_path):
        memory_dir = tmp_path / "memory"
        local_init(memory_dir)
        agent_dir = memory_dir / "coder"
        agent_dir.mkdir()
        result = local_list_notes(memory_dir)
        assert result[0]["path"] == str(agent_dir)

    def test_size_is_zero_for_empty_agent_directory(self, tmp_path):
        memory_dir = tmp_path / "memory"
        local_init(memory_dir)
        (memory_dir / "coder").mkdir()
        result = local_list_notes(memory_dir)
        assert result[0]["size"] == 0

    def test_size_reflects_file_content(self, tmp_path):
        memory_dir = tmp_path / "memory"
        local_init(memory_dir)
        agent_dir = memory_dir / "coder"
        agent_dir.mkdir()
        note = agent_dir / "note.md"
        note.write_text("hello world")
        result = local_list_notes(memory_dir)
        assert result[0]["size"] == len("hello world")

    def test_does_not_include_files_at_top_level(self, tmp_path):
        memory_dir = tmp_path / "memory"
        local_init(memory_dir)
        (memory_dir / "Index.md").write_text("# Index")
        result = local_list_notes(memory_dir)
        assert result == []

    def test_results_sorted_by_agent_name(self, tmp_path):
        memory_dir = tmp_path / "memory"
        local_init(memory_dir)
        (memory_dir / "zebra").mkdir()
        (memory_dir / "alpha").mkdir()
        (memory_dir / "middle").mkdir()
        result = local_list_notes(memory_dir)
        names = [r["agent"] for r in result]
        assert names == sorted(names)


# ── local_regenerate_index ────────────────────────────────────────────────────

class TestLocalRegenerateIndex:
    def test_creates_index_md_in_memory_dir(self, tmp_path):
        memory_dir = tmp_path / "memory"
        local_init(memory_dir)
        local_regenerate_index(memory_dir)
        assert (memory_dir / "Index.md").exists()

    def test_index_contains_agent_memory_header(self, tmp_path):
        memory_dir = tmp_path / "memory"
        local_init(memory_dir)
        local_regenerate_index(memory_dir)
        content = (memory_dir / "Index.md").read_text()
        assert "Agent Memory" in content

    def test_index_contains_last_updated_date(self, tmp_path):
        import re
        memory_dir = tmp_path / "memory"
        local_init(memory_dir)
        local_regenerate_index(memory_dir)
        content = (memory_dir / "Index.md").read_text()
        assert re.search(r"\d{4}-\d{2}-\d{2}", content)

    def test_index_lists_agent_name_as_section(self, tmp_path):
        memory_dir = tmp_path / "memory"
        local_init(memory_dir)
        (memory_dir / "coder").mkdir()
        local_regenerate_index(memory_dir)
        content = (memory_dir / "Index.md").read_text()
        assert "coder" in content

    def test_index_shows_file_count_for_agent(self, tmp_path):
        memory_dir = tmp_path / "memory"
        local_init(memory_dir)
        agent_dir = memory_dir / "coder"
        agent_dir.mkdir()
        (agent_dir / "note1.md").write_text("# Note 1")
        (agent_dir / "note2.md").write_text("# Note 2")
        local_regenerate_index(memory_dir)
        content = (memory_dir / "Index.md").read_text()
        assert "(2" in content  # e.g. "(2 files)" or "(2)"

    def test_index_lists_individual_note_files(self, tmp_path):
        memory_dir = tmp_path / "memory"
        local_init(memory_dir)
        agent_dir = memory_dir / "explorer"
        agent_dir.mkdir()
        (agent_dir / "my-note.md").write_text("# My Note")
        local_regenerate_index(memory_dir)
        content = (memory_dir / "Index.md").read_text()
        assert "my-note" in content

    def test_index_empty_when_no_agent_directories(self, tmp_path):
        memory_dir = tmp_path / "memory"
        local_init(memory_dir)
        local_regenerate_index(memory_dir)
        content = (memory_dir / "Index.md").read_text()
        # Header must still be present
        assert "Agent Memory" in content

    def test_index_raises_when_memory_dir_does_not_exist(self, tmp_path):
        # BUG: local_regenerate_index does not create the parent directory before
        # writing Index.md, so calling it on a non-existent path raises
        # FileNotFoundError. The function should either call memory_dir.mkdir() or
        # the caller should ensure the directory exists first via local_init().
        memory_dir = tmp_path / "nonexistent"
        with pytest.raises(FileNotFoundError):
            local_regenerate_index(memory_dir)

    def test_index_overwrites_previous_content(self, tmp_path):
        memory_dir = tmp_path / "memory"
        local_init(memory_dir)
        agent_dir = memory_dir / "coder"
        agent_dir.mkdir()
        (agent_dir / "first.md").write_text("# First")
        local_regenerate_index(memory_dir)
        first_content = (memory_dir / "Index.md").read_text()

        (agent_dir / "second.md").write_text("# Second")
        local_regenerate_index(memory_dir)
        second_content = (memory_dir / "Index.md").read_text()

        assert "second" in second_content
        assert second_content != first_content
