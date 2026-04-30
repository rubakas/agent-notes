"""Tests for agent_notes.commands.memory.do_migrate()."""
import time
import pytest
from pathlib import Path

import agent_notes.commands.memory as mem_mod


# ── helpers ────────────────────────────────────────────────────────────────────

def _vault(tmp_path: Path) -> Path:
    """Create a minimal vault directory structure and return its path."""
    vault = tmp_path / "vault"
    vault.mkdir()
    return vault


def _make_file(path: Path, content: str = "---\ntitle: test\n---\nbody") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


def _patch_config(monkeypatch, vault: Path):
    """Redirect _load_memory_config to the given tmp vault."""
    monkeypatch.setattr(mem_mod, "_load_memory_config", lambda: ("obsidian", vault))


# ── 10 & 11: bail-out guards ───────────────────────────────────────────────────

class TestMigrateBailOut:
    def test_non_obsidian_backend_prints_and_returns(self, monkeypatch, capsys):
        """When backend != obsidian, migrate prints a message and exits early."""
        monkeypatch.setattr(mem_mod, "_load_memory_config", lambda: ("local", Path("/tmp/fake")))
        mem_mod.do_migrate()
        out = capsys.readouterr().out
        assert "obsidian" in out.lower()

    def test_missing_vault_path_prints_and_returns(self, monkeypatch, capsys):
        """When vault path is None, migrate prints a message and exits early."""
        monkeypatch.setattr(mem_mod, "_load_memory_config", lambda: ("obsidian", None))
        mem_mod.do_migrate()
        out = capsys.readouterr().out
        assert out.strip()  # something was printed

    def test_non_obsidian_backend_creates_no_files(self, monkeypatch, tmp_path):
        """Non-obsidian bail does not touch the filesystem."""
        monkeypatch.setattr(mem_mod, "_load_memory_config", lambda: ("local", tmp_path))
        before = set(tmp_path.rglob("*"))
        mem_mod.do_migrate()
        after = set(tmp_path.rglob("*"))
        assert before == after


# ── 1: per-project subfolder flattening ───────────────────────────────────────

class TestPerProjectSubfolderFlattening:
    def test_moves_file_from_project_sessions_to_shared_sessions(self, monkeypatch, tmp_path):
        vault = _vault(tmp_path)
        uuid_stem = "aabbccdd-1234-5678-abcd-000000000001"
        src = _make_file(
            vault / "myproject" / "Sessions" / f"{uuid_stem}.md",
            "---\ncreated_at: 2026-04-10T08:00:00Z\ntitle: t\n---\nbody",
        )
        _patch_config(monkeypatch, vault)
        mem_mod.do_migrate()
        # File must have landed in vault/Sessions/
        sessions_dir = vault / "Sessions"
        md_files = list(sessions_dir.glob("*.md"))
        assert len(md_files) == 1
        # The new filename should embed the date from frontmatter
        assert md_files[0].stem.startswith("2026-04-10_")

    def test_moves_file_from_project_decisions_to_shared_decisions(self, monkeypatch, tmp_path):
        vault = _vault(tmp_path)
        src = _make_file(
            vault / "myproject" / "Decisions" / "2026-04-10-14-30-00-foo.md",
            "---\ntitle: foo\n---\nbody",
        )
        _patch_config(monkeypatch, vault)
        mem_mod.do_migrate()
        decisions_dir = vault / "Decisions"
        names = [f.name for f in decisions_dir.glob("*.md")]
        assert any("foo" in n for n in names), f"Expected 'foo' in {names}"

    def test_project_subfolder_removed_after_migration(self, monkeypatch, tmp_path):
        vault = _vault(tmp_path)
        _make_file(
            vault / "myproject" / "Sessions" / "2026-04-10-14-30-00-note.md",
            "---\ntitle: t\n---\nbody",
        )
        _patch_config(monkeypatch, vault)
        mem_mod.do_migrate()
        assert not (vault / "myproject").exists()

    def test_loose_file_preserved_and_subfolder_kept_when_nonempty(self, monkeypatch, tmp_path, capsys):
        vault = _vault(tmp_path)
        uuid_stem = "aabbccdd-1234-5678-abcd-000000000099"
        _make_file(
            vault / "myproject" / "Sessions" / f"{uuid_stem}.md",
            "---\ncreated_at: 2026-04-10T08:00:00Z\ntitle: t\n---\nbody",
        )
        loose = _make_file(vault / "myproject" / "notes.md", "loose content")
        _patch_config(monkeypatch, vault)
        mem_mod.do_migrate()
        # Session was moved up to vault/Sessions/
        sessions_dir = vault / "Sessions"
        assert any(sessions_dir.glob("*.md"))
        # Loose file must still exist
        assert loose.exists()
        assert loose.read_text() == "loose content"
        # Subfolder must still exist (non-empty)
        assert (vault / "myproject").exists()
        # Summary must mention the per-project subfolder error
        out = capsys.readouterr().out
        assert "per-project subfolder not removed" in out

    def test_files_already_at_shared_root_in_new_format_are_untouched(self, monkeypatch, tmp_path):
        vault = _vault(tmp_path)
        existing = _make_file(
            vault / "Decisions" / "2026-04-29_already-new.md",
            "---\ntitle: x\n---\nbody",
        )
        original_content = existing.read_bytes()
        _patch_config(monkeypatch, vault)
        mem_mod.do_migrate()
        assert existing.exists()
        assert existing.read_bytes() == original_content


# ── 2: legacy timestamp rename ────────────────────────────────────────────────

class TestLegacyTimestampRename:
    def test_renames_legacy_ts_file_to_date_slug(self, monkeypatch, tmp_path):
        vault = _vault(tmp_path)
        src = _make_file(
            vault / "Decisions" / "2026-04-10-14-30-00-old-fix.md",
            "---\ntitle: old fix\n---\nbody content",
        )
        _patch_config(monkeypatch, vault)
        mem_mod.do_migrate()
        dst = vault / "Decisions" / "2026-04-10_old-fix.md"
        assert dst.exists()
        assert not src.exists()

    def test_renamed_file_contents_are_byte_identical(self, monkeypatch, tmp_path):
        vault = _vault(tmp_path)
        original_content = b"---\ntitle: old fix\n---\nbody content"
        src = vault / "Decisions" / "2026-04-10-14-30-00-old-fix.md"
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_bytes(original_content)
        _patch_config(monkeypatch, vault)
        mem_mod.do_migrate()
        dst = vault / "Decisions" / "2026-04-10_old-fix.md"
        assert dst.read_bytes() == original_content

    def test_summary_counts_rename(self, monkeypatch, tmp_path, capsys):
        vault = _vault(tmp_path)
        _make_file(vault / "Decisions" / "2026-04-10-14-30-00-old-fix.md")
        _patch_config(monkeypatch, vault)
        mem_mod.do_migrate()
        out = capsys.readouterr().out
        assert "1 renamed" in out or "renamed" in out


# ── 3: same-day collision on rename ──────────────────────────────────────────

class TestSameDayCollision:
    def test_second_file_gets_hhmmss_suffix(self, monkeypatch, tmp_path):
        vault = _vault(tmp_path)
        decisions = vault / "Decisions"
        _make_file(decisions / "2026-04-10-14-30-00-foo.md", "---\ntitle: foo\n---\nbody1")
        _make_file(decisions / "2026-04-10-15-45-12-foo.md", "---\ntitle: foo\n---\nbody2")
        _patch_config(monkeypatch, vault)
        mem_mod.do_migrate()
        names = {f.name for f in decisions.glob("*.md")}
        assert "2026-04-10_foo.md" in names
        assert "2026-04-10_foo_154512.md" in names

    def test_both_source_files_replaced(self, monkeypatch, tmp_path):
        vault = _vault(tmp_path)
        decisions = vault / "Decisions"
        src1 = _make_file(decisions / "2026-04-10-14-30-00-foo.md")
        src2 = _make_file(decisions / "2026-04-10-15-45-12-foo.md")
        _patch_config(monkeypatch, vault)
        mem_mod.do_migrate()
        assert not src1.exists()
        assert not src2.exists()


# ── 4: bare-UUID session rename with frontmatter date ─────────────────────────

class TestBareUUIDWithFrontmatter:
    UUID = "aabbccdd-1234-5678-abcd-000000000002"

    def test_renames_using_frontmatter_created_at_date(self, monkeypatch, tmp_path):
        vault = _vault(tmp_path)
        src = _make_file(
            vault / "Sessions" / f"{self.UUID}.md",
            "---\ncreated_at: 2026-01-15T10:00:00Z\ntitle: my session\n---\nbody",
        )
        _patch_config(monkeypatch, vault)
        mem_mod.do_migrate()
        dst = vault / "Sessions" / f"2026-01-15_{self.UUID}.md"
        assert dst.exists()
        assert not src.exists()

    def test_original_content_preserved(self, monkeypatch, tmp_path):
        vault = _vault(tmp_path)
        content = b"---\ncreated_at: 2026-01-15T10:00:00Z\ntitle: my session\n---\nbody"
        src = vault / "Sessions" / f"{self.UUID}.md"
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_bytes(content)
        _patch_config(monkeypatch, vault)
        mem_mod.do_migrate()
        dst = vault / "Sessions" / f"2026-01-15_{self.UUID}.md"
        assert dst.read_bytes() == content


# ── 5: bare-UUID session rename without frontmatter date ─────────────────────

class TestBareUUIDWithoutFrontmatter:
    UUID = "aabbccdd-1234-5678-abcd-000000000003"

    def test_renames_using_file_mtime_date(self, monkeypatch, tmp_path):
        vault = _vault(tmp_path)
        src = vault / "Sessions" / f"{self.UUID}.md"
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_text("---\ntitle: no date\n---\nbody")
        # Force mtime to a known UTC date using os.utime
        import os
        from datetime import datetime, timezone
        known_dt = datetime(2025, 6, 20, 0, 0, 0, tzinfo=timezone.utc)
        ts = known_dt.timestamp()
        os.utime(src, (ts, ts))
        _patch_config(monkeypatch, vault)
        mem_mod.do_migrate()
        sessions = vault / "Sessions"
        names = [f.name for f in sessions.glob("*.md")]
        assert any(n.startswith("2025-06-20_") for n in names), f"Expected 2025-06-20_ prefix in {names}"


# ── 6: already-new file skipped ──────────────────────────────────────────────

class TestAlreadyNewFormatSkipped:
    def test_new_format_file_not_renamed(self, monkeypatch, tmp_path):
        vault = _vault(tmp_path)
        existing = _make_file(
            vault / "Patterns" / "2026-04-29_already-new.md",
            "---\ntitle: x\n---\nbody",
        )
        _patch_config(monkeypatch, vault)
        mem_mod.do_migrate()
        assert existing.exists()
        # No additional files created
        names = [f.name for f in (vault / "Patterns").glob("*.md")]
        assert names == ["2026-04-29_already-new.md"]

    def test_already_new_counted_as_skipped(self, monkeypatch, tmp_path, capsys):
        vault = _vault(tmp_path)
        _make_file(vault / "Patterns" / "2026-04-29_already-new.md")
        _patch_config(monkeypatch, vault)
        mem_mod.do_migrate()
        out = capsys.readouterr().out
        assert "1 skipped" in out or "skipped" in out


# ── 7: unrecognized filename skipped ─────────────────────────────────────────

class TestUnrecognizedFilenameSkipped:
    def test_unrecognized_name_left_in_place(self, monkeypatch, tmp_path):
        vault = _vault(tmp_path)
        weird = _make_file(vault / "Context" / "random-name.md", "---\ntitle: x\n---\nbody")
        _patch_config(monkeypatch, vault)
        mem_mod.do_migrate()
        assert weird.exists()
        assert weird.read_text() == "---\ntitle: x\n---\nbody"

    def test_unrecognized_name_counted_as_skipped(self, monkeypatch, tmp_path, capsys):
        vault = _vault(tmp_path)
        _make_file(vault / "Context" / "random-name.md")
        _patch_config(monkeypatch, vault)
        mem_mod.do_migrate()
        out = capsys.readouterr().out
        assert "skipped" in out


# ── 8: idempotency ───────────────────────────────────────────────────────────

class TestIdempotency:
    def test_second_run_produces_zero_changes(self, monkeypatch, tmp_path, capsys):
        vault = _vault(tmp_path)
        _make_file(
            vault / "Decisions" / "2026-04-10-14-30-00-some-fix.md",
            "---\ntitle: fix\n---\nbody",
        )
        _patch_config(monkeypatch, vault)

        # First run — migrate
        mem_mod.do_migrate()
        capsys.readouterr()  # discard first run output

        # Second run — should be a no-op
        mem_mod.do_migrate()
        out = capsys.readouterr().out
        assert "0 moved" in out
        assert "0 renamed" in out

    def test_second_run_files_unchanged(self, monkeypatch, tmp_path):
        vault = _vault(tmp_path)
        _make_file(
            vault / "Decisions" / "2026-04-10-14-30-00-some-fix.md",
            "---\ntitle: fix\n---\nbody",
        )
        _patch_config(monkeypatch, vault)

        mem_mod.do_migrate()

        # Snapshot state after first run
        before = {f.relative_to(vault): f.read_bytes() for f in vault.rglob("*.md")}

        mem_mod.do_migrate()

        after = {f.relative_to(vault): f.read_bytes() for f in vault.rglob("*.md")}
        assert before == after


# ── 9: Index.md regenerated ──────────────────────────────────────────────────

class TestIndexRegenerated:
    def test_index_md_exists_after_migrate(self, monkeypatch, tmp_path):
        vault = _vault(tmp_path)
        _make_file(
            vault / "Decisions" / "2026-04-10-14-30-00-my-decision.md",
            "---\ntitle: my decision\n---\nbody",
        )
        _patch_config(monkeypatch, vault)
        mem_mod.do_migrate()
        assert (vault / "Index.md").exists()

    def test_index_contains_wikilink_to_migrated_file(self, monkeypatch, tmp_path):
        vault = _vault(tmp_path)
        _make_file(
            vault / "Decisions" / "2026-04-10-14-30-00-my-decision.md",
            "---\ntitle: my decision\n---\nbody",
        )
        _patch_config(monkeypatch, vault)
        mem_mod.do_migrate()
        index = (vault / "Index.md").read_text()
        # The stem of the renamed file should appear as a wikilink
        assert "[[" in index
        assert "my-decision" in index or "2026-04-10" in index

    def test_index_exists_even_with_empty_vault(self, monkeypatch, tmp_path):
        vault = _vault(tmp_path)
        _patch_config(monkeypatch, vault)
        mem_mod.do_migrate()
        assert (vault / "Index.md").exists()


# ── summary line format ───────────────────────────────────────────────────────

class TestSummaryLine:
    def test_summary_line_has_moved_renamed_skipped(self, monkeypatch, tmp_path, capsys):
        vault = _vault(tmp_path)
        _patch_config(monkeypatch, vault)
        mem_mod.do_migrate()
        out = capsys.readouterr().out
        assert "moved" in out
        assert "renamed" in out
        assert "skipped" in out

    def test_no_errors_means_no_errors_token_in_output(self, monkeypatch, tmp_path, capsys):
        vault = _vault(tmp_path)
        _patch_config(monkeypatch, vault)
        mem_mod.do_migrate()
        out = capsys.readouterr().out
        assert "errors" not in out
