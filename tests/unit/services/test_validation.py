"""Tests for agent_notes.services.validation."""
import pytest
from pathlib import Path

from agent_notes.services.validation import (
    has_field,
    get_field,
    line_count,
    has_frontmatter,
    check_unclosed_code_blocks,
)


# ---------------------------------------------------------------------------
# TestHasField
# ---------------------------------------------------------------------------

class TestHasField:
    def test_returns_true_when_field_present(self, tmp_path):
        f = tmp_path / "note.md"
        f.write_text("---\ntitle: My Note\n---\n\nBody text.\n")
        assert has_field(f, "title") is True

    def test_returns_false_when_field_absent(self, tmp_path):
        f = tmp_path / "note.md"
        f.write_text("---\nauthor: Alice\n---\n\nBody.\n")
        assert has_field(f, "title") is False

    def test_returns_false_for_nonexistent_file(self, tmp_path):
        missing = tmp_path / "ghost.md"
        assert has_field(missing, "title") is False

    def test_returns_true_for_field_in_body_not_frontmatter(self, tmp_path):
        """has_field is a simple substring check — matches anywhere in file."""
        f = tmp_path / "note.md"
        f.write_text("No frontmatter here.\ntitle: in body\n")
        assert has_field(f, "title") is True

    def test_returns_false_for_empty_file(self, tmp_path):
        f = tmp_path / "empty.md"
        f.write_text("")
        assert has_field(f, "title") is False

    def test_handles_multiple_fields(self, tmp_path):
        f = tmp_path / "note.md"
        f.write_text("---\nname: Test\ntype: concepts\nagent: coder\n---\n")
        assert has_field(f, "name") is True
        assert has_field(f, "type") is True
        assert has_field(f, "agent") is True


# ---------------------------------------------------------------------------
# TestGetField
# ---------------------------------------------------------------------------

class TestGetField:
    def test_returns_value_for_existing_field(self, tmp_path):
        f = tmp_path / "note.md"
        f.write_text("---\ntype: concepts\n---\n")
        assert get_field(f, "type") == "concepts"

    def test_returns_none_when_field_missing(self, tmp_path):
        f = tmp_path / "note.md"
        f.write_text("---\ntype: concepts\n---\n")
        assert get_field(f, "agent") is None

    def test_returns_none_for_nonexistent_file(self, tmp_path):
        missing = tmp_path / "ghost.md"
        assert get_field(missing, "type") is None

    def test_strips_quotes_from_value(self, tmp_path):
        f = tmp_path / "note.md"
        f.write_text('---\nconfidence: "high"\n---\n')
        assert get_field(f, "confidence") == "high"

    def test_strips_single_quotes_from_value(self, tmp_path):
        f = tmp_path / "note.md"
        f.write_text("---\nstatus: 'draft'\n---\n")
        assert get_field(f, "status") == "draft"

    def test_returns_value_with_spaces(self, tmp_path):
        f = tmp_path / "note.md"
        f.write_text("---\ntitle: Hello World\n---\n")
        assert get_field(f, "title") == "Hello World"

    def test_returns_none_for_empty_file(self, tmp_path):
        f = tmp_path / "empty.md"
        f.write_text("")
        assert get_field(f, "title") is None

    def test_stops_at_closing_frontmatter_delimiter(self, tmp_path):
        """Field appearing after closing --- is NOT read as frontmatter field."""
        f = tmp_path / "note.md"
        f.write_text("---\ntype: concepts\n---\n\ntype: in-body\n")
        # The first occurrence inside frontmatter should be returned
        assert get_field(f, "type") == "concepts"

    def test_handles_value_with_colon(self, tmp_path):
        f = tmp_path / "note.md"
        f.write_text("---\nurl: https://example.com/path\n---\n")
        result = get_field(f, "url")
        assert result is not None
        assert "example.com" in result

    def test_returns_none_when_no_frontmatter(self, tmp_path):
        f = tmp_path / "note.md"
        f.write_text("# Just a heading\n\nNo frontmatter here.\n")
        assert get_field(f, "type") is None


# ---------------------------------------------------------------------------
# TestLineCount
# ---------------------------------------------------------------------------

class TestLineCount:
    def test_returns_correct_count_for_simple_file(self, tmp_path):
        f = tmp_path / "file.md"
        f.write_text("line one\nline two\nline three\n")
        # split('\n') on "line one\nline two\nline three\n" gives 4 elements
        assert line_count(f) == 4

    def test_returns_zero_for_nonexistent_file(self, tmp_path):
        missing = tmp_path / "ghost.md"
        assert line_count(missing) == 0

    def test_returns_one_for_single_line_no_newline(self, tmp_path):
        f = tmp_path / "single.md"
        f.write_text("only one line")
        assert line_count(f) == 1

    def test_returns_one_for_empty_file(self, tmp_path):
        f = tmp_path / "empty.md"
        f.write_text("")
        # "".split('\n') == [''] — one element
        assert line_count(f) == 1

    def test_counts_increase_with_more_lines(self, tmp_path):
        f = tmp_path / "many.md"
        content = "\n".join(f"line {i}" for i in range(10))
        f.write_text(content)
        assert line_count(f) >= 10


# ---------------------------------------------------------------------------
# TestHasFrontmatter
# ---------------------------------------------------------------------------

class TestHasFrontmatter:
    def test_returns_true_for_file_starting_with_triple_dashes(self, tmp_path):
        f = tmp_path / "note.md"
        f.write_text("---\ntype: concepts\n---\n\nBody.\n")
        assert has_frontmatter(f) is True

    def test_returns_false_for_file_without_frontmatter(self, tmp_path):
        f = tmp_path / "note.md"
        f.write_text("# Heading\n\nJust content.\n")
        assert has_frontmatter(f) is False

    def test_returns_false_for_empty_file(self, tmp_path):
        f = tmp_path / "empty.md"
        f.write_text("")
        assert has_frontmatter(f) is False

    def test_returns_false_for_nonexistent_file(self, tmp_path):
        missing = tmp_path / "ghost.md"
        assert has_frontmatter(missing) is False

    def test_returns_false_when_dashes_not_at_start(self, tmp_path):
        f = tmp_path / "note.md"
        f.write_text("\n---\ntype: concepts\n---\n")
        assert has_frontmatter(f) is False

    def test_returns_true_for_minimal_frontmatter(self, tmp_path):
        f = tmp_path / "note.md"
        f.write_text("---\n---\n")
        assert has_frontmatter(f) is True


# ---------------------------------------------------------------------------
# TestCheckUnclosedCodeBlocks
# ---------------------------------------------------------------------------

class TestCheckUnclosedCodeBlocks:
    def test_returns_true_for_file_with_no_code_blocks(self, tmp_path):
        f = tmp_path / "note.md"
        f.write_text("Just plain text, no code blocks.\n")
        assert check_unclosed_code_blocks(f) is True

    def test_returns_true_for_properly_closed_block(self, tmp_path):
        f = tmp_path / "note.md"
        f.write_text("Some text.\n```python\nprint('hello')\n```\nMore text.\n")
        assert check_unclosed_code_blocks(f) is True

    def test_returns_false_for_unclosed_code_block(self, tmp_path):
        f = tmp_path / "note.md"
        f.write_text("Some text.\n```python\nprint('hello')\nno closing fence\n")
        assert check_unclosed_code_blocks(f) is False

    def test_returns_true_for_multiple_closed_blocks(self, tmp_path):
        f = tmp_path / "note.md"
        f.write_text("```python\ncode\n```\n\n```bash\necho hi\n```\n")
        assert check_unclosed_code_blocks(f) is True

    def test_returns_false_for_odd_number_of_fences(self, tmp_path):
        f = tmp_path / "note.md"
        f.write_text("```python\ncode\n```\n\n```bash\nno close\n")
        assert check_unclosed_code_blocks(f) is False

    def test_returns_true_for_nonexistent_file(self, tmp_path):
        """Missing file is treated as 'no blocks to worry about'."""
        missing = tmp_path / "ghost.md"
        assert check_unclosed_code_blocks(missing) is True

    def test_returns_true_for_empty_file(self, tmp_path):
        f = tmp_path / "empty.md"
        f.write_text("")
        assert check_unclosed_code_blocks(f) is True
