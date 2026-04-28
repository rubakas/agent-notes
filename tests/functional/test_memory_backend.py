"""Tests for agent_notes.services.memory_backend."""
import re
import time
import pytest
from pathlib import Path

from agent_notes.services.memory_backend import (
    _slug,
    _now,
    _today,
    obsidian_write_note,
    obsidian_regenerate_index,
)


# ── _slug() ───────────────────────────────────────────────────────────────────

class TestSlug:
    def test_plain_title_lowercased_and_dashes(self):
        assert _slug("Hello World") == "hello-world"

    def test_plain_title_non_alphanum_replaced_with_dashes(self):
        assert _slug("My Title: Subtitle!") == "my-title-subtitle"

    def test_plain_title_trimmed_of_leading_trailing_dashes(self):
        result = _slug("  !! Leading and trailing !! ")
        assert not result.startswith("-")
        assert not result.endswith("-")

    def test_date_prefix_stripped_before_slugify(self):
        result = _slug("2026-04-28 my title")
        assert result == "my-title"

    def test_full_datetime_prefix_stripped_before_slugify(self):
        result = _slug("2026-04-28-14-35-22 my title")
        assert result == "my-title"

    def test_no_date_prefix_not_mangled(self):
        result = _slug("already clean title")
        assert result == "already-clean-title"

    def test_long_title_truncated_to_60_chars(self):
        long = "a" * 80
        result = _slug(long)
        assert len(result) <= 60

    def test_exactly_60_chars_not_truncated(self):
        sixty = "a" * 60
        result = _slug(sixty)
        assert len(result) == 60


# ── _now() and _today() ───────────────────────────────────────────────────────

class TestTimestampHelpers:
    def test_now_matches_datetime_format(self):
        result = _now()
        assert re.match(r"^\d{4}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2}$", result), (
            f"_now() returned {result!r}, expected YYYY-MM-DD-HH-MM-SS"
        )

    def test_now_has_no_T_separator(self):
        assert "T" not in _now()

    def test_today_matches_date_format(self):
        result = _today()
        assert re.match(r"^\d{4}-\d{2}-\d{2}$", result), (
            f"_today() returned {result!r}, expected YYYY-MM-DD"
        )

    def test_today_has_no_time_component(self):
        result = _today()
        # Must be exactly 10 chars: YYYY-MM-DD
        assert len(result) == 10


# ── obsidian_write_note() ─────────────────────────────────────────────────────

class TestObsidianWriteNote:
    def test_filename_uses_full_timestamp_format(self, tmp_path):
        path = obsidian_write_note(
            tmp_path, title="My Note", body="body text", note_type="pattern"
        )
        # Stem starts with YYYY-MM-DD-HH-MM-SS
        assert re.match(r"^\d{4}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2}-", path.name), (
            f"Filename {path.name!r} does not start with YYYY-MM-DD-HH-MM-SS-"
        )

    def test_filename_has_no_T_separator(self, tmp_path):
        path = obsidian_write_note(
            tmp_path, title="My Note", body="body text", note_type="pattern"
        )
        assert "T" not in path.name

    def test_pattern_note_saved_to_patterns_folder(self, tmp_path):
        path = obsidian_write_note(
            tmp_path, title="Test Pattern", body="body", note_type="pattern"
        )
        assert path.parent.name == "Patterns"

    def test_session_note_saved_to_sessions_folder(self, tmp_path):
        path = obsidian_write_note(
            tmp_path, title="Test Session", body="body", note_type="session"
        )
        assert path.parent.name == "Sessions"

    def test_decision_note_saved_to_decisions_folder(self, tmp_path):
        path = obsidian_write_note(
            tmp_path, title="Arch Decision", body="body", note_type="decision"
        )
        assert path.parent.name == "Decisions"

    def test_mistake_note_saved_to_mistakes_folder(self, tmp_path):
        path = obsidian_write_note(
            tmp_path, title="Oops", body="body", note_type="mistake"
        )
        assert path.parent.name == "Mistakes"

    def test_context_note_saved_to_context_folder(self, tmp_path):
        path = obsidian_write_note(
            tmp_path, title="Some Context", body="body", note_type="context"
        )
        assert path.parent.name == "Context"

    def test_frontmatter_contains_date_field(self, tmp_path):
        path = obsidian_write_note(
            tmp_path, title="Note", body="body", note_type="pattern"
        )
        content = path.read_text()
        assert "date:" in content

    def test_frontmatter_contains_type_field(self, tmp_path):
        path = obsidian_write_note(
            tmp_path, title="Note", body="body", note_type="pattern"
        )
        content = path.read_text()
        assert "type: pattern" in content

    def test_frontmatter_contains_agent_field_when_provided(self, tmp_path):
        path = obsidian_write_note(
            tmp_path, title="Note", body="body", note_type="pattern", agent="coder"
        )
        content = path.read_text()
        assert "agent: coder" in content

    def test_frontmatter_omits_agent_when_not_provided(self, tmp_path):
        path = obsidian_write_note(
            tmp_path, title="Note", body="body", note_type="pattern"
        )
        content = path.read_text()
        assert "agent:" not in content

    def test_file_contains_h1_title(self, tmp_path):
        path = obsidian_write_note(
            tmp_path, title="My Title", body="body text", note_type="pattern"
        )
        content = path.read_text()
        assert "# My Title" in content

    def test_file_contains_body_text(self, tmp_path):
        path = obsidian_write_note(
            tmp_path, title="Note", body="the body content", note_type="pattern"
        )
        content = path.read_text()
        assert "the body content" in content

    def test_frontmatter_delimited_by_triple_dashes(self, tmp_path):
        path = obsidian_write_note(
            tmp_path, title="Note", body="body", note_type="pattern"
        )
        content = path.read_text()
        assert content.startswith("---")
        # Second --- closes the frontmatter
        assert content.count("---") >= 2

    def test_two_rapid_notes_get_different_filenames(self, tmp_path):
        path1 = obsidian_write_note(
            tmp_path, title="Note One", body="body", note_type="pattern"
        )
        # Sleep 1 second so the second-resolution timestamp differs
        time.sleep(1)
        path2 = obsidian_write_note(
            tmp_path, title="Note Two", body="body", note_type="pattern"
        )
        assert path1 != path2


# ── obsidian_regenerate_index() ───────────────────────────────────────────────

class TestObsidianRegenerateIndex:
    def test_index_md_created_at_vault_root(self, tmp_path):
        obsidian_regenerate_index(tmp_path)
        assert (tmp_path / "Index.md").exists()

    def test_index_contains_wikilink_format(self, tmp_path):
        patterns = tmp_path / "Patterns"
        patterns.mkdir()
        note = patterns / "2026-04-28-10-00-00-test-pattern.md"
        note.write_text("---\ndate: 2026-04-28\ntype: pattern\n---\n\n# Test Pattern\n\nbody\n")

        obsidian_regenerate_index(tmp_path)

        index_content = (tmp_path / "Index.md").read_text()
        # Should contain [[stem]] wikilink
        assert "[[2026-04-28-10-00-00-test-pattern]]" in index_content

    def test_index_lists_notes_from_all_non_empty_categories(self, tmp_path):
        for cat, title in [("Patterns", "Pattern Note"), ("Sessions", "Session Note")]:
            folder = tmp_path / cat
            folder.mkdir(parents=True, exist_ok=True)
            note = folder / f"2026-04-28-10-00-00-{cat.lower()}.md"
            note.write_text(f"---\ndate: 2026-04-28\ntype: x\n---\n\n# {title}\n\nbody\n")

        obsidian_regenerate_index(tmp_path)

        index_content = (tmp_path / "Index.md").read_text()
        assert "Patterns" in index_content
        assert "Sessions" in index_content

    def test_index_skips_empty_categories(self, tmp_path):
        # Only create Patterns folder with a note; Sessions folder is absent
        patterns = tmp_path / "Patterns"
        patterns.mkdir()
        note = patterns / "2026-04-28-10-00-00-solo.md"
        note.write_text("---\ndate: 2026-04-28\ntype: pattern\n---\n\n# Solo\n\nbody\n")

        obsidian_regenerate_index(tmp_path)

        index_content = (tmp_path / "Index.md").read_text()
        # Sessions was never created so should not appear as a section
        assert "## Sessions" not in index_content

    def test_index_updated_after_write_note(self, tmp_path):
        obsidian_write_note(
            tmp_path, title="Index Test Note", body="body", note_type="pattern"
        )
        index_content = (tmp_path / "Index.md").read_text()
        # The slug of the title should appear in the index
        assert "index-test-note" in index_content
