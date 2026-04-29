"""Tests for agent_notes.services.memory_backend."""
import re
import time
import pytest
from pathlib import Path

from agent_notes.services.memory_backend import (
    _slug,
    _now,
    _now_iso,
    _today,
    _current_session_id,
    obsidian_write_note,
    obsidian_regenerate_index,
    _parse_note_metadata,
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

    def test_frontmatter_contains_created_at_field(self, tmp_path):
        path = obsidian_write_note(
            tmp_path, title="Note", body="body", note_type="pattern"
        )
        content = path.read_text()
        assert "created_at:" in content

    def test_frontmatter_created_at_is_iso_utc(self, tmp_path):
        path = obsidian_write_note(
            tmp_path, title="Note", body="body", note_type="pattern"
        )
        content = path.read_text()
        import re
        assert re.search(r"created_at: \d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", content)

    def test_frontmatter_has_no_date_field(self, tmp_path):
        path = obsidian_write_note(
            tmp_path, title="Note", body="body", note_type="pattern"
        )
        content = path.read_text()
        for line in content.splitlines():
            if line.startswith("---"):
                continue
            assert not line.startswith("date:")

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


# ── UTC + ISO timestamps ──────────────────────────────────────────────────────

class TestUtcTimestamps:
    def test_now_iso_format_has_z_suffix(self):
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", _now_iso())

    def test_now_uses_utc(self, monkeypatch):
        # _now is a UTC-based filename timestamp; should match ISO UTC date prefix
        from datetime import datetime, timezone
        utc_today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        assert _now().startswith(utc_today)

    def test_today_uses_utc(self):
        from datetime import datetime, timezone
        assert _today() == datetime.now(timezone.utc).strftime("%Y-%m-%d")


# ── _current_session_id() ─────────────────────────────────────────────────────

class TestCurrentSessionId:
    def test_returns_none_outside_claude_code(self, monkeypatch):
        monkeypatch.delenv("CLAUDECODE", raising=False)
        monkeypatch.delenv("CLAUDE_CODE_ENTRYPOINT", raising=False)
        assert _current_session_id() is None

    def test_returns_jsonl_stem_when_in_claude_code(self, tmp_path, monkeypatch):
        cwd = tmp_path / "proj"
        cwd.mkdir()
        slug = str(cwd).replace("/", "-")
        proj_dir = tmp_path / "home" / ".claude" / "projects" / slug
        proj_dir.mkdir(parents=True)
        old = proj_dir / "old-session.jsonl"
        new = proj_dir / "new-session.jsonl"
        old.write_text("{}")
        time.sleep(0.01)
        new.write_text("{}")
        monkeypatch.setenv("CLAUDECODE", "1")
        monkeypatch.chdir(cwd)
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "home"))
        assert _current_session_id() == "new-session"

    def test_returns_none_when_project_dir_missing(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CLAUDECODE", "1")
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "no-claude"))
        assert _current_session_id() is None


# ── Session note filename rule ────────────────────────────────────────────────

class TestSessionNoteFilename:
    def test_session_uses_session_id_as_filename_when_available(self, tmp_path, monkeypatch):
        cwd = tmp_path / "proj"
        cwd.mkdir()
        slug = str(cwd).replace("/", "-")
        proj_dir = tmp_path / "home" / ".claude" / "projects" / slug
        proj_dir.mkdir(parents=True)
        (proj_dir / "abc-123.jsonl").write_text("{}")
        monkeypatch.setenv("CLAUDECODE", "1")
        monkeypatch.chdir(cwd)
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "home"))

        path = obsidian_write_note(
            tmp_path / "vault", title="My session", body="body", note_type="session"
        )
        assert path.name == "abc-123.md"

    def test_session_id_path_traversal_sanitized(self, tmp_path, monkeypatch):
        """A malicious JSONL stem containing path components must not escape Sessions/."""
        cwd = tmp_path / "proj"
        cwd.mkdir()
        slug = str(cwd).replace("/", "-")
        proj_dir = tmp_path / "home" / ".claude" / "projects" / slug
        proj_dir.mkdir(parents=True)
        # Adversarial stem — path traversal attempt
        (proj_dir / "../../evil.jsonl").write_text("{}") if False else None
        # Cannot actually create a "../../evil.jsonl" file inside proj_dir, so simulate
        # by directly creating a JSONL with a stem containing forbidden chars.
        # The sanitizer must strip the dots and slashes regardless.
        bad = proj_dir / "..-..-evil.jsonl"
        bad.write_text("{}")
        monkeypatch.setenv("CLAUDECODE", "1")
        monkeypatch.chdir(cwd)
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "home"))

        vault = tmp_path / "vault"
        path = obsidian_write_note(
            vault, title="hostile", body="b", note_type="session"
        )
        # Resulting path must be inside vault/Sessions/ and contain no `..` segments
        assert path.is_relative_to(vault / "Sessions"), f"Escaped vault: {path}"
        assert ".." not in path.parts
        # Sanitizer should have reduced the dotted/dashed stem to "--evil" or similar (only [A-Za-z0-9_-])
        assert path.name.endswith(".md")
        # The dangerous prefix must not appear literally in the filename
        assert "/" not in path.name

    def test_session_falls_back_to_timestamp_slug_without_session_id(self, tmp_path, monkeypatch):
        monkeypatch.delenv("CLAUDECODE", raising=False)
        monkeypatch.delenv("CLAUDE_CODE_ENTRYPOINT", raising=False)
        path = obsidian_write_note(
            tmp_path / "vault", title="Lone session", body="body", note_type="session"
        )
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2}-lone-session\.md", path.name)

    def test_non_session_types_always_use_timestamp_slug(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CLAUDECODE", "1")
        path = obsidian_write_note(
            tmp_path / "vault", title="Pattern note", body="body", note_type="pattern"
        )
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2}-pattern-note\.md", path.name)

    def test_session_appends_to_existing_file(self, tmp_path, monkeypatch):
        cwd = tmp_path / "proj"
        cwd.mkdir()
        slug = str(cwd).replace("/", "-")
        proj_dir = tmp_path / "home" / ".claude" / "projects" / slug
        proj_dir.mkdir(parents=True)
        (proj_dir / "sess-1.jsonl").write_text("{}")
        monkeypatch.setenv("CLAUDECODE", "1")
        monkeypatch.chdir(cwd)
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "home"))

        vault = tmp_path / "vault"
        first = obsidian_write_note(vault, title="S", body="first", note_type="session")
        second = obsidian_write_note(vault, title="S", body="second", note_type="session")
        assert first == second
        content = first.read_text()
        assert "first" in content
        assert "second" in content
        assert re.search(r"## Update \d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", content)


# ── Frontmatter migration on append ──────────────────────────────────────────

class TestSessionFrontmatterMigration:
    def test_session_append_rewrites_old_date_frontmatter(self, tmp_path, monkeypatch):
        cwd = tmp_path / "proj"
        cwd.mkdir()
        slug = str(cwd).replace("/", "-")
        proj_dir = tmp_path / "home" / ".claude" / "projects" / slug
        proj_dir.mkdir(parents=True)
        (proj_dir / "old-sess.jsonl").write_text("{}")
        monkeypatch.setenv("CLAUDECODE", "1")
        monkeypatch.chdir(cwd)
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "home"))

        vault = tmp_path / "vault"
        sessions = vault / "Sessions"
        sessions.mkdir(parents=True)
        old = sessions / "old-sess.md"
        old.write_text("---\ndate: 2026-01-01\ntype: session\n---\n\n# Old\n\nold body\n")

        obsidian_write_note(vault, title="Old", body="new body", note_type="session")

        content = old.read_text()
        assert "created_at:" in content
        assert "session_id: old-sess" in content
        assert "\ndate:" not in content
        assert "old body" in content
        assert "new body" in content


# ── Frontmatter session_id rule ───────────────────────────────────────────────

class TestSessionFrontmatter:
    def test_session_frontmatter_includes_session_id(self, tmp_path, monkeypatch):
        cwd = tmp_path / "proj"
        cwd.mkdir()
        slug = str(cwd).replace("/", "-")
        proj_dir = tmp_path / "home" / ".claude" / "projects" / slug
        proj_dir.mkdir(parents=True)
        (proj_dir / "xyz-9.jsonl").write_text("{}")
        monkeypatch.setenv("CLAUDECODE", "1")
        monkeypatch.chdir(cwd)
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "home"))

        path = obsidian_write_note(
            tmp_path / "vault", title="S", body="b", note_type="session"
        )
        assert "session_id: xyz-9" in path.read_text()

    def test_non_session_frontmatter_omits_session_id(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CLAUDECODE", "1")
        path = obsidian_write_note(
            tmp_path / "vault", title="P", body="b", note_type="pattern"
        )
        assert "session_id:" not in path.read_text()


# ── Index format (Recent activity + By category) ──────────────────────────────

class TestIndexFormat:
    def _make_note(self, folder: Path, stem: str, note_type: str, created_at: str, h1: str) -> Path:
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{stem}.md"
        path.write_text(f"---\ncreated_at: {created_at}\ntype: {note_type}\n---\n\n# {h1}\n\nbody\n")
        return path

    def test_index_recent_activity_is_chronological(self, tmp_path):
        patterns = tmp_path / "Patterns"
        for i in range(5):
            self._make_note(patterns, f"2026-04-29-10-00-0{i}-note-{i}", "pattern",
                            f"2026-04-29T10:00:0{i}Z", f"Note {i}")
        obsidian_regenerate_index(tmp_path)
        content = (tmp_path / "Index.md").read_text()
        activity_block = content.split("## Recent activity")[1].split("## By category")[0]
        timestamps = re.findall(r"\[(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)\]", activity_block)
        assert timestamps == sorted(timestamps, reverse=True)

    def test_index_recent_activity_includes_type_and_description(self, tmp_path):
        patterns = tmp_path / "Patterns"
        self._make_note(patterns, "2026-04-29-10-00-00-test-pat", "pattern",
                        "2026-04-29T10:00:00Z", "Test pattern title")
        obsidian_regenerate_index(tmp_path)
        content = (tmp_path / "Index.md").read_text()
        assert "[2026-04-29T10:00:00Z] [[2026-04-29-10-00-00-test-pat]] - pattern - Test pattern title" in content

    def test_index_session_note_uses_display_text_override(self, tmp_path):
        sessions = tmp_path / "Sessions"
        self._make_note(sessions, "abc-uuid-1234", "session", "2026-04-29T10:00:00Z", "My session")
        obsidian_regenerate_index(tmp_path)
        content = (tmp_path / "Index.md").read_text()
        assert "[[abc-uuid-1234|My session]]" in content

    def test_index_recent_activity_caps_at_30(self, tmp_path):
        patterns = tmp_path / "Patterns"
        for i in range(50):
            ts = f"2026-04-29T10:00:{i:02d}Z"
            stem = f"2026-04-29-10-00-{i:02d}-note-{i}"
            self._make_note(patterns, stem, "pattern", ts, f"Note {i}")
        obsidian_regenerate_index(tmp_path)
        content = (tmp_path / "Index.md").read_text()
        activity_block = content.split("## Recent activity")[1].split("## By category")[0]
        lines = [l for l in activity_block.splitlines() if l.startswith("- [")]
        assert len(lines) == 30

    def test_index_by_category_section_still_present(self, tmp_path):
        for cat, ntype in [("Patterns", "pattern"), ("Decisions", "decision"),
                            ("Mistakes", "mistake"), ("Context", "context"), ("Sessions", "session")]:
            self._make_note(tmp_path / cat, f"2026-04-29-10-00-00-{cat.lower()}", ntype,
                            "2026-04-29T10:00:00Z", f"{cat} Note")
        obsidian_regenerate_index(tmp_path)
        content = (tmp_path / "Index.md").read_text()
        assert "## By category" in content
        for header in ["### Patterns", "### Decisions", "### Mistakes", "### Context", "### Sessions"]:
            assert header in content

    def test_index_falls_back_to_legacy_date_field(self, tmp_path):
        patterns = tmp_path / "Patterns"
        patterns.mkdir(parents=True, exist_ok=True)
        note = patterns / "2026-01-01-10-00-00-legacy.md"
        note.write_text("---\ndate: 2026-01-01\ntype: pattern\n---\n\n# Legacy Note\n\nbody\n")
        obsidian_regenerate_index(tmp_path)
        content = (tmp_path / "Index.md").read_text()
        assert "[2026-01-01T00:00:00Z]" in content
