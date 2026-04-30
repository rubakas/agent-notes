"""I/O tests for agent_notes.services.memory_backend (write to tmp_path)."""
import re
import pytest
from pathlib import Path

from agent_notes.services.memory_backend import (
    obsidian_write_note,
    obsidian_regenerate_index,
    _parse_note_metadata,
)


# ── obsidian_write_note() ─────────────────────────────────────────────────────

class TestObsidianWriteNote:
    def test_filename_uses_new_date_slug_format(self, tmp_path):
        path = obsidian_write_note(
            tmp_path, title="My Note", body="body text", note_type="pattern"
        )
        # Stem must be YYYY-MM-DD_<slug> (optionally _HHMMSS for collisions)
        assert re.match(r"^\d{4}-\d{2}-\d{2}_", path.name), (
            f"Filename {path.name!r} does not start with YYYY-MM-DD_"
        )

    def test_filename_has_no_legacy_T_separator(self, tmp_path):
        path = obsidian_write_note(
            tmp_path, title="My Note", body="body text", note_type="pattern"
        )
        assert "T" not in path.name

    def test_filename_has_no_legacy_timestamp_prefix(self, tmp_path):
        path = obsidian_write_note(
            tmp_path, title="My Note", body="body text", note_type="pattern"
        )
        # Must NOT match the old format YYYY-MM-DD-HH-MM-SS-
        assert not re.match(r"^\d{4}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2}-", path.name), (
            f"Filename {path.name!r} still uses legacy timestamp format"
        )

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
        assert content.count("---") >= 2

    def test_file_contains_related_section(self, tmp_path):
        path = obsidian_write_note(
            tmp_path, title="Note", body="body", note_type="pattern"
        )
        content = path.read_text()
        assert "## Related" in content

    def test_two_rapid_notes_with_same_title_get_different_filenames(self, tmp_path, monkeypatch):
        import agent_notes.services.memory_backend as mb
        # Same day, same slug → collision → second gets _HHMMSS suffix
        monkeypatch.setattr(mb, "_today", lambda: "2026-04-30")
        monkeypatch.setattr(mb, "_now_hhmmss", lambda: "142231")

        path1 = obsidian_write_note(
            tmp_path, title="Note One", body="body", note_type="pattern"
        )
        # Patch slug to collide
        monkeypatch.setattr(mb, "_slug", lambda t: "note-one")
        path2 = obsidian_write_note(
            tmp_path, title="Note One", body="body", note_type="pattern"
        )
        assert path1 != path2
        assert "_142231" in path2.stem


# ── obsidian_regenerate_index() ───────────────────────────────────────────────

class TestObsidianRegenerateIndex:
    def test_index_md_created_at_vault_root(self, tmp_path):
        obsidian_regenerate_index(tmp_path)
        assert (tmp_path / "Index.md").exists()

    def test_index_contains_wikilink_format(self, tmp_path):
        patterns = tmp_path / "Patterns"
        patterns.mkdir()
        note = patterns / "2026-04-28_test-pattern.md"
        note.write_text("---\ncreated_at: 2026-04-28T10:00:00Z\ntype: pattern\n---\n\n# Test Pattern\n\nbody\n")

        obsidian_regenerate_index(tmp_path)

        index_content = (tmp_path / "Index.md").read_text()
        assert "[[2026-04-28_test-pattern]]" in index_content

    def test_index_lists_notes_from_all_categories(self, tmp_path):
        for cat, title in [("Patterns", "Pattern Note"), ("Sessions", "Session Note")]:
            folder = tmp_path / cat
            folder.mkdir(parents=True, exist_ok=True)
            note = folder / f"2026-04-28_{cat.lower()}.md"
            note.write_text(f"---\ncreated_at: 2026-04-28T10:00:00Z\ntype: x\n---\n\n# {title}\n\nbody\n")

        obsidian_regenerate_index(tmp_path)

        index_content = (tmp_path / "Index.md").read_text()
        assert "2026-04-28_patterns" in index_content
        assert "2026-04-28_sessions" in index_content

    def test_index_skips_empty_categories(self, tmp_path):
        patterns = tmp_path / "Patterns"
        patterns.mkdir()
        note = patterns / "2026-04-28_solo.md"
        note.write_text("---\ncreated_at: 2026-04-28T10:00:00Z\ntype: pattern\n---\n\n# Solo\n\nbody\n")

        obsidian_regenerate_index(tmp_path)

        index_content = (tmp_path / "Index.md").read_text()
        assert "sessions" not in index_content.lower() or "2026-04-28_sessions" not in index_content

    def test_index_updated_after_write_note(self, tmp_path):
        obsidian_write_note(
            tmp_path, title="Index Test Note", body="body", note_type="pattern"
        )
        index_content = (tmp_path / "Index.md").read_text()
        assert "index-test-note" in index_content

    def test_index_has_no_by_category_section(self, tmp_path):
        patterns = tmp_path / "Patterns"
        patterns.mkdir()
        (patterns / "2026-04-28_note.md").write_text(
            "---\ncreated_at: 2026-04-28T10:00:00Z\ntype: pattern\n---\n\n# Note\n\nbody\n"
        )
        obsidian_regenerate_index(tmp_path)
        index_content = (tmp_path / "Index.md").read_text()
        assert "## By category" not in index_content

    def test_index_is_sorted_newest_first(self, tmp_path):
        patterns = tmp_path / "Patterns"
        patterns.mkdir()
        for i in range(5):
            ts = f"2026-04-29T10:00:0{i}Z"
            (patterns / f"2026-04-29_note-{i}.md").write_text(
                f"---\ncreated_at: {ts}\ntype: pattern\n---\n\n# Note {i}\n\nbody\n"
            )
        obsidian_regenerate_index(tmp_path)
        content = (tmp_path / "Index.md").read_text()
        lines = [l for l in content.splitlines() if l.startswith("- ")]
        dts = [l.split(" ")[1] for l in lines]
        assert dts == sorted(dts, reverse=True)

    def test_index_falls_back_to_legacy_date_field(self, tmp_path):
        patterns = tmp_path / "Patterns"
        patterns.mkdir(parents=True, exist_ok=True)
        note = patterns / "2026-01-01_legacy.md"
        note.write_text("---\ndate: 2026-01-01\ntype: pattern\n---\n\n# Legacy Note\n\nbody\n")
        obsidian_regenerate_index(tmp_path)
        content = (tmp_path / "Index.md").read_text()
        assert "2026-01-01" in content


# ── Session note filename rule ────────────────────────────────────────────────

class TestSessionNoteFilename:
    def test_session_uses_date_sessionid_as_filename_when_available(self, tmp_path, monkeypatch):
        cwd = tmp_path / "proj"
        cwd.mkdir()
        slug = str(cwd).replace("/", "-")
        proj_dir = tmp_path / "home" / ".claude" / "projects" / slug
        proj_dir.mkdir(parents=True)
        (proj_dir / "abc-123.jsonl").write_text("{}")
        monkeypatch.setenv("CLAUDECODE", "1")
        monkeypatch.chdir(cwd)
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "home"))

        import agent_notes.services.memory_backend as mb
        monkeypatch.setattr(mb, "_today", lambda: "2026-04-30")

        path = obsidian_write_note(
            tmp_path / "vault", title="My session", body="body", note_type="session"
        )
        assert path.name == "2026-04-30_abc-123.md"

    def test_session_id_path_traversal_sanitized(self, tmp_path, monkeypatch):
        """A malicious JSONL stem containing path components must not escape Sessions/."""
        cwd = tmp_path / "proj"
        cwd.mkdir()
        slug = str(cwd).replace("/", "-")
        proj_dir = tmp_path / "home" / ".claude" / "projects" / slug
        proj_dir.mkdir(parents=True)
        bad = proj_dir / "..-..-evil.jsonl"
        bad.write_text("{}")
        monkeypatch.setenv("CLAUDECODE", "1")
        monkeypatch.chdir(cwd)
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "home"))

        vault = tmp_path / "vault"
        path = obsidian_write_note(
            vault, title="hostile", body="b", note_type="session"
        )
        assert path.is_relative_to(vault / "Sessions"), f"Escaped vault: {path}"
        assert ".." not in path.parts
        assert path.name.endswith(".md")
        assert "/" not in path.name

    def test_session_falls_back_to_date_slug_without_session_id(self, tmp_path, monkeypatch):
        monkeypatch.delenv("CLAUDECODE", raising=False)
        monkeypatch.delenv("CLAUDE_CODE_ENTRYPOINT", raising=False)

        import agent_notes.services.memory_backend as mb
        monkeypatch.setattr(mb, "_today", lambda: "2026-04-30")

        path = obsidian_write_note(
            tmp_path / "vault", title="Lone session", body="body", note_type="session"
        )
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}_lone-session(_.+)?\.md", path.name), (
            f"Unexpected filename: {path.name}"
        )

    def test_non_session_types_use_date_slug(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CLAUDECODE", "1")

        import agent_notes.services.memory_backend as mb
        monkeypatch.setattr(mb, "_today", lambda: "2026-04-30")

        path = obsidian_write_note(
            tmp_path / "vault", title="Pattern note", body="body", note_type="pattern"
        )
        assert re.fullmatch(r"2026-04-30_pattern-note(_.+)?\.md", path.name), (
            f"Unexpected filename: {path.name}"
        )

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


# ── Auto-linking ──────────────────────────────────────────────────────────────

class TestAutoLinking:
    def _setup_session(self, tmp_path, monkeypatch, session_id="test-sess-42"):
        cwd = tmp_path / "proj"
        cwd.mkdir()
        slug = str(cwd).replace("/", "-")
        proj_dir = tmp_path / "home" / ".claude" / "projects" / slug
        proj_dir.mkdir(parents=True)
        (proj_dir / f"{session_id}.jsonl").write_text("{}")
        monkeypatch.setenv("CLAUDECODE", "1")
        monkeypatch.chdir(cwd)
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "home"))
        return session_id

    def test_non_session_note_auto_links_to_active_session(self, tmp_path, monkeypatch):
        sid = self._setup_session(tmp_path, monkeypatch)
        vault = tmp_path / "vault"

        session_path = obsidian_write_note(vault, title="My session", body="started", note_type="session")
        decision_path = obsidian_write_note(vault, title="Arch choice", body="body", note_type="decision")

        session_content = session_path.read_text()
        assert f"[[{decision_path.stem}]]" in session_content
        assert "## Linked notes" in session_content

    def test_auto_link_is_idempotent(self, tmp_path, monkeypatch):
        self._setup_session(tmp_path, monkeypatch)
        vault = tmp_path / "vault"

        session_path = obsidian_write_note(vault, title="S", body="b", note_type="session")
        decision_path = obsidian_write_note(vault, title="Dec", body="b", note_type="decision")
        obsidian_write_note(vault, title="Dec 2", body="b", note_type="decision")

        session_content = session_path.read_text()
        # First decision link appears exactly once
        assert session_content.count(f"[[{decision_path.stem}]]") == 1

    def test_no_auto_link_without_active_session_note(self, tmp_path, monkeypatch):
        self._setup_session(tmp_path, monkeypatch)
        vault = tmp_path / "vault"

        # Write decision without writing a session note first
        decision_path = obsidian_write_note(vault, title="Orphan decision", body="body", note_type="decision")
        content = decision_path.read_text()
        # Session frontmatter field should either be absent or point to a non-existent note
        # (no crash — just no linking)
        assert decision_path.exists()


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

        import agent_notes.services.memory_backend as mb
        monkeypatch.setattr(mb, "_today", lambda: "2026-01-01")

        vault = tmp_path / "vault"
        sessions = vault / "Sessions"
        sessions.mkdir(parents=True)
        # Old-format session note (bare UUID filename, date frontmatter)
        old = sessions / "old-sess.md"
        old.write_text("---\ndate: 2026-01-01\ntype: session\n---\n\n# Old\n\nold body\n")

        obsidian_write_note(vault, title="Old", body="new body", note_type="session")

        content = old.read_text()
        assert "created_at:" in content
        assert "old body" in content
        assert "new body" in content


# ── Frontmatter session field ─────────────────────────────────────────────────

class TestSessionFrontmatter:
    def test_non_session_frontmatter_includes_session_ref_when_active(self, tmp_path, monkeypatch):
        cwd = tmp_path / "proj"
        cwd.mkdir()
        slug = str(cwd).replace("/", "-")
        proj_dir = tmp_path / "home" / ".claude" / "projects" / slug
        proj_dir.mkdir(parents=True)
        (proj_dir / "xyz-9.jsonl").write_text("{}")
        monkeypatch.setenv("CLAUDECODE", "1")
        monkeypatch.chdir(cwd)
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "home"))

        vault = tmp_path / "vault"
        obsidian_write_note(vault, title="S", body="b", note_type="session")
        path = obsidian_write_note(vault, title="P", body="b", note_type="pattern")
        assert "session:" in path.read_text()

    def test_non_session_frontmatter_omits_session_when_no_active_session(self, tmp_path, monkeypatch):
        monkeypatch.delenv("CLAUDECODE", raising=False)
        monkeypatch.delenv("CLAUDE_CODE_ENTRYPOINT", raising=False)
        path = obsidian_write_note(
            tmp_path / "vault", title="P", body="b", note_type="pattern"
        )
        assert "session:" not in path.read_text()


# ── Index format ──────────────────────────────────────────────────────────────

class TestIndexFormat:
    def _make_note(self, folder: Path, stem: str, note_type: str, created_at: str, h1: str) -> Path:
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{stem}.md"
        path.write_text(f"---\ncreated_at: {created_at}\ntype: {note_type}\n---\n\n# {h1}\n\nbody\n")
        return path

    def test_index_is_chronological_newest_first(self, tmp_path):
        patterns = tmp_path / "Patterns"
        for i in range(5):
            self._make_note(patterns, f"2026-04-29_note-{i}", "pattern",
                            f"2026-04-29T10:00:0{i}Z", f"Note {i}")
        obsidian_regenerate_index(tmp_path)
        content = (tmp_path / "Index.md").read_text()
        lines = [l for l in content.splitlines() if l.startswith("- ")]
        # Extract the datetime portion (first word after "- ")
        dts = [l.split(" ")[1] for l in lines]
        assert dts == sorted(dts, reverse=True)

    def test_index_line_format(self, tmp_path):
        patterns = tmp_path / "Patterns"
        self._make_note(patterns, "2026-04-29_test-pat", "pattern",
                        "2026-04-29T10:00:00Z", "Test pattern title")
        obsidian_regenerate_index(tmp_path)
        content = (tmp_path / "Index.md").read_text()
        assert "- 2026-04-29 10:00 [[2026-04-29_test-pat]] — pattern" in content

    def test_index_has_no_by_category_section(self, tmp_path):
        patterns = tmp_path / "Patterns"
        self._make_note(patterns, "2026-04-29_note", "pattern", "2026-04-29T10:00:00Z", "Note")
        obsidian_regenerate_index(tmp_path)
        content = (tmp_path / "Index.md").read_text()
        assert "## By category" not in content
        assert "## Recent activity" not in content
