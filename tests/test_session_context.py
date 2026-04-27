"""Tests for agent_notes/services/session_context.py."""
import pytest
from pathlib import Path

from agent_notes.services.session_context import render_context, write_context


VERSION = "1.2.0"
AGENTS = ["coder", "reviewer", "explorer"]


class TestRenderContext:
    """render_context() must produce a string with expected content."""

    def test_returns_a_string(self):
        result = render_context(AGENTS, VERSION)
        assert isinstance(result, str)

    def test_output_contains_version(self):
        result = render_context(AGENTS, VERSION)
        assert VERSION in result

    def test_output_contains_all_agent_names(self):
        result = render_context(AGENTS, VERSION)
        for agent in AGENTS:
            assert agent in result, f"Expected agent '{agent}' in rendered output"

    def test_agents_listed_in_sorted_order(self):
        unsorted = ["zebra-agent", "alpha-agent", "mango-agent"]
        result = render_context(unsorted, VERSION)
        # All names present
        for name in unsorted:
            assert name in result
        # alpha appears before mango, mango before zebra
        assert result.index("alpha-agent") < result.index("mango-agent")
        assert result.index("mango-agent") < result.index("zebra-agent")

    def test_empty_agent_list_does_not_raise(self):
        result = render_context([], VERSION)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_empty_agent_list_includes_fallback_text(self):
        """When no agents provided, output should mention where to find agents."""
        result = render_context([], VERSION)
        # Template uses a fallback message referencing ~/.claude/agents/
        assert "agents" in result.lower()

    def test_placeholder_tokens_are_replaced(self):
        """No raw template placeholders must remain in the output."""
        result = render_context(AGENTS, VERSION)
        assert "{{version}}" not in result
        assert "{{agents_list}}" not in result
        assert "{{installed_date}}" not in result

    def test_different_versions_render_correctly(self):
        v1 = render_context(AGENTS, "1.0.0")
        v2 = render_context(AGENTS, "2.5.3")
        assert "1.0.0" in v1
        assert "2.5.3" in v2


class TestWriteContext:
    """write_context() must create the file with expected content."""

    def test_creates_file_at_given_path(self, tmp_path):
        dest = tmp_path / "session-context.md"
        write_context(dest, AGENTS, VERSION)
        assert dest.exists()

    def test_created_file_is_not_empty(self, tmp_path):
        dest = tmp_path / "session-context.md"
        write_context(dest, AGENTS, VERSION)
        assert dest.stat().st_size > 0

    def test_file_content_matches_render_context(self, tmp_path):
        dest = tmp_path / "session-context.md"
        write_context(dest, AGENTS, VERSION)
        written = dest.read_text()
        rendered = render_context(AGENTS, VERSION)
        assert written == rendered

    def test_creates_parent_directories(self, tmp_path):
        dest = tmp_path / "nested" / "dir" / "session-context.md"
        write_context(dest, AGENTS, VERSION)
        assert dest.exists()

    def test_written_file_contains_version(self, tmp_path):
        dest = tmp_path / "session-context.md"
        write_context(dest, AGENTS, VERSION)
        assert VERSION in dest.read_text()

    def test_written_file_contains_agent_names(self, tmp_path):
        dest = tmp_path / "session-context.md"
        write_context(dest, AGENTS, VERSION)
        content = dest.read_text()
        for agent in AGENTS:
            assert agent in content

    def test_overwrites_existing_file(self, tmp_path):
        dest = tmp_path / "session-context.md"
        dest.write_text("old content")
        write_context(dest, AGENTS, VERSION)
        content = dest.read_text()
        assert "old content" not in content
        assert VERSION in content
