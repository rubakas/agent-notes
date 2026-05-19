"""Tests for the memory migration framework."""
import pytest
from pathlib import Path

from agent_notes.services.migrations.base import Migration
from agent_notes.services.migrations.runner import get_pending_migrations, run_migration, run_all_pending
from agent_notes.services.migrations.v2_24_0_add_descriptions import AddDescriptionsMigration
from agent_notes.services.obsidian_backend import obsidian_init, obsidian_write_note


class TestMigrationRunner:
    def test_pending_when_none_completed(self, monkeypatch):
        """All migrations are pending when state has no completions."""
        from agent_notes.domain.state import State, MigrationState
        monkeypatch.setattr(
            "agent_notes.services.migrations.runner.load_state",
            lambda: State(memory_migrations=MigrationState(completed=[])),
        )
        pending = get_pending_migrations()
        assert len(pending) > 0

    def test_pending_after_completion(self, monkeypatch):
        """Completed migrations are filtered out."""
        from agent_notes.domain.state import State, MigrationState
        monkeypatch.setattr(
            "agent_notes.services.migrations.runner.load_state",
            lambda: State(memory_migrations=MigrationState(completed=["v2.24.0-add-descriptions"])),
        )
        pending = get_pending_migrations()
        assert all(m.name != "v2.24.0-add-descriptions" for m in pending)

    def test_run_migration_records_in_state(self, tmp_path, monkeypatch):
        """Running a migration appends its name to state."""
        from agent_notes.domain.state import State, MigrationState
        state = State(memory_migrations=MigrationState(completed=[]))
        saved_states = []
        monkeypatch.setattr("agent_notes.services.migrations.runner.load_state", lambda: state)
        monkeypatch.setattr("agent_notes.services.migrations.runner.save_state", lambda s: saved_states.append(s))
        obsidian_init(tmp_path)

        migration = AddDescriptionsMigration()
        run_migration(migration, tmp_path)
        assert saved_states
        assert "v2.24.0-add-descriptions" in saved_states[-1].memory_migrations.completed


class TestAddDescriptionsMigration:
    def test_injects_description_into_frontmatter(self, tmp_path):
        """Notes without description get one derived from body."""
        obsidian_init(tmp_path)
        path = obsidian_write_note(
            tmp_path, title="Test Note", body="This is the first line of content.",
            note_type="decision",
        )
        # Verify no description yet (since we didn't pass one)
        content = path.read_text()
        assert "description:" not in content

        migration = AddDescriptionsMigration()
        migration.run(tmp_path)

        content = path.read_text()
        assert "description:" in content
        assert "This is the first line of content." in content

    def test_skips_notes_with_existing_description(self, tmp_path):
        """Notes that already have description are not modified."""
        obsidian_init(tmp_path)
        path = obsidian_write_note(
            tmp_path, title="Test Note", body="body text",
            note_type="pattern", description="existing desc",
        )
        original = path.read_text()

        migration = AddDescriptionsMigration()
        summary = migration.run(tmp_path)

        assert path.read_text() == original
        assert "0 notes updated" in summary or "skipped" in summary

    def test_truncates_at_word_boundary(self):
        migration = AddDescriptionsMigration()
        long_line = "This is a very long description that goes well beyond one hundred characters and should be truncated at a word boundary not in the middle"
        result = migration._derive_description({}, f"# Title\n\n{long_line}")
        assert len(result) <= 100
        assert not result.endswith(" ")
        assert result == long_line[:100].rsplit(" ", 1)[0]

    def test_short_line_not_truncated(self):
        migration = AddDescriptionsMigration()
        result = migration._derive_description({}, "# Title\n\nShort line")
        assert result == "Short line"

    def test_migration_idempotent(self, tmp_path):
        """Running twice produces same result."""
        obsidian_init(tmp_path)
        obsidian_write_note(
            tmp_path, title="Note", body="First body line.",
            note_type="decision",
        )
        migration = AddDescriptionsMigration()
        migration.run(tmp_path)
        first_pass = list((tmp_path / "Decisions").glob("*.md"))
        first_contents = {p.name: p.read_text() for p in first_pass}

        migration.run(tmp_path)
        second_pass = list((tmp_path / "Decisions").glob("*.md"))
        second_contents = {p.name: p.read_text() for p in second_pass}

        assert first_contents == second_contents
