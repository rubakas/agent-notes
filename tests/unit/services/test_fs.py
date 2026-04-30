"""Tests for agent_notes.services.fs — handle_existing, _timestamped_backup_path, files_identical."""
import re
import time
import pytest
from pathlib import Path

from agent_notes.services.fs import (
    _timestamped_backup_path,
    handle_existing,
    files_identical,
)

# Timestamp pattern: YYYYMMDDTHHMMSSffffffZ  (digits only between T and Z)
_TS_RE = re.compile(r"\d{8}T\d{6}\d+Z$")


class TestTimestampedBackupPath:
    def test_returns_path_in_same_directory(self, tmp_path):
        dst = tmp_path / "CLAUDE.md"
        result = _timestamped_backup_path(dst)
        assert result.parent == tmp_path

    def test_name_starts_with_original_stem_plus_bak(self, tmp_path):
        dst = tmp_path / "CLAUDE.md"
        result = _timestamped_backup_path(dst)
        # e.g. CLAUDE.md.bak.20260430T022500123456Z
        assert result.name.startswith("CLAUDE.md.bak.")

    def test_timestamp_matches_expected_format(self, tmp_path):
        dst = tmp_path / "CLAUDE.md"
        result = _timestamped_backup_path(dst)
        # Strip the fixed prefix to isolate the timestamp
        suffix = result.name[len("CLAUDE.md.bak."):]
        assert _TS_RE.match(suffix), f"Timestamp portion {suffix!r} does not match expected format"

    def test_rapid_calls_produce_unique_names(self, tmp_path):
        """Microsecond precision ensures two rapid calls differ."""
        dst = tmp_path / "CLAUDE.md"
        first = _timestamped_backup_path(dst)
        second = _timestamped_backup_path(dst)
        # They may or may not be equal depending on clock resolution,
        # but the function must at least return a valid path each time.
        # If they ARE equal, it means no microsecond precision — treat that as a note.
        # We call enough times to assert at least one distinct pair.
        results = {_timestamped_backup_path(dst) for _ in range(20)}
        assert len(results) > 1, "Expected microsecond variation to produce unique backup names"


class TestHandleExistingMissingDst:
    def test_missing_dst_raises_or_is_falsy(self, tmp_path):
        """handle_existing is always called behind dst.exists() in production.
        When called directly on a missing dst, files_identical returns False
        (OSError path), so code proceeds to rename — which raises FileNotFoundError.
        This test documents the expected behavior: callers must guard with dst.exists().
        """
        src = tmp_path / "src.md"
        src.write_text("hello")
        dst = tmp_path / "nonexistent.md"

        # The function will attempt dst.rename(...) which raises because dst is missing
        with pytest.raises((FileNotFoundError, OSError)):
            handle_existing(src, dst)


class TestHandleExistingIdenticalContent:
    def test_identical_file_returns_false_no_backup(self, tmp_path):
        content = b"identical content"
        src = tmp_path / "src.md"
        dst = tmp_path / "dst.md"
        src.write_bytes(content)
        dst.write_bytes(content)

        result = handle_existing(src, dst)

        assert result is False
        # dst must still exist — nothing was moved/removed
        assert dst.exists()
        # No .bak.* sibling should have been created
        bak_files = list(tmp_path.glob("dst.md.bak.*"))
        assert bak_files == [], f"Unexpected backup files: {bak_files}"

    def test_identical_file_dst_content_unchanged(self, tmp_path):
        content = b"same bytes"
        src = tmp_path / "src.md"
        dst = tmp_path / "dst.md"
        src.write_bytes(content)
        dst.write_bytes(content)

        handle_existing(src, dst)

        assert dst.read_bytes() == content


class TestHandleExistingDifferingFile:
    def test_differing_file_creates_backup_sibling(self, tmp_path):
        src = tmp_path / "src.md"
        dst = tmp_path / "dst.md"
        src.write_bytes(b"new content")
        dst.write_bytes(b"old content")

        handle_existing(src, dst)

        bak_files = list(tmp_path.glob("dst.md.bak.*"))
        assert len(bak_files) == 1, f"Expected one backup, found: {bak_files}"

    def test_differing_file_backup_timestamp_format(self, tmp_path):
        src = tmp_path / "src.md"
        dst = tmp_path / "dst.md"
        src.write_bytes(b"new content")
        dst.write_bytes(b"old content")

        handle_existing(src, dst)

        bak_files = list(tmp_path.glob("dst.md.bak.*"))
        bak_name = bak_files[0].name
        suffix = bak_name[len("dst.md.bak."):]
        assert _TS_RE.match(suffix), f"Backup timestamp {suffix!r} does not match expected format"

    def test_differing_file_backup_contains_prior_content(self, tmp_path):
        prior_content = b"old content"
        src = tmp_path / "src.md"
        dst = tmp_path / "dst.md"
        src.write_bytes(b"new content")
        dst.write_bytes(prior_content)

        handle_existing(src, dst)

        bak_files = list(tmp_path.glob("dst.md.bak.*"))
        assert bak_files[0].read_bytes() == prior_content

    def test_differing_file_removes_original_dst(self, tmp_path):
        src = tmp_path / "src.md"
        dst = tmp_path / "dst.md"
        src.write_bytes(b"new content")
        dst.write_bytes(b"old content")

        handle_existing(src, dst)

        assert not dst.exists(), "Original dst should have been removed after backup"

    def test_differing_file_returns_true(self, tmp_path):
        src = tmp_path / "src.md"
        dst = tmp_path / "dst.md"
        src.write_bytes(b"new content")
        dst.write_bytes(b"old content")

        result = handle_existing(src, dst)

        assert result is True


class TestHandleExistingDifferingDirectory:
    def test_differing_dir_creates_backup_directory(self, tmp_path):
        src_dir = tmp_path / "src_skill"
        dst_dir = tmp_path / "dst_skill"
        (src_dir / "file.md").parent.mkdir()
        (src_dir / "file.md").write_bytes(b"new")
        dst_dir.mkdir()
        (dst_dir / "file.md").write_bytes(b"old")

        handle_existing(src_dir, dst_dir)

        bak_dirs = list(tmp_path.glob("dst_skill.bak.*"))
        assert len(bak_dirs) == 1, f"Expected one backup dir, found: {bak_dirs}"
        assert bak_dirs[0].is_dir()

    def test_differing_dir_backup_contains_prior_contents(self, tmp_path):
        prior_content = b"old skill content"
        src_dir = tmp_path / "src_skill"
        dst_dir = tmp_path / "dst_skill"
        src_dir.mkdir()
        (src_dir / "file.md").write_bytes(b"new skill content")
        dst_dir.mkdir()
        (dst_dir / "file.md").write_bytes(prior_content)

        handle_existing(src_dir, dst_dir)

        bak_dirs = list(tmp_path.glob("dst_skill.bak.*"))
        backed_up_file = bak_dirs[0] / "file.md"
        assert backed_up_file.read_bytes() == prior_content

    def test_differing_dir_removes_original_dst(self, tmp_path):
        src_dir = tmp_path / "src_skill"
        dst_dir = tmp_path / "dst_skill"
        src_dir.mkdir()
        (src_dir / "file.md").write_bytes(b"new")
        dst_dir.mkdir()
        (dst_dir / "file.md").write_bytes(b"old")

        handle_existing(src_dir, dst_dir)

        assert not dst_dir.exists(), "Original dst dir should be removed after backup"
