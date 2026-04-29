"""Pure-unit tests for agent_notes.services.memory_backend (no I/O)."""
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
