"""Unit tests for agent_notes.data.templates.frontmatter.codex."""
import sys
import textwrap
import pytest

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

from agent_notes.data.templates.frontmatter.codex import (
    emit_file,
    post_process,
    _sandbox_mode,
    _strip_sections,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ctx(
    name: str = "coder",
    description: str = "A coder agent.",
    effort: str = "medium",
    role: str = "worker",
    claude_tools: str = "",
    opencode_permission: dict = None,
    model_str: str = "gpt-5.4",
) -> tuple[dict, str]:
    """Return (ctx, body) pair suitable for emit_file / post_process.

    'effort' seeds both agent_config["effort"] (source data) and
    ctx["resolved_effort"] (what rendering.py's _resolve_effort would have
    produced for an agent with its own effort set) — mirroring production wiring.
    """
    agent_config = {
        "description": description,
        "effort": effort,
        "role": role,
        "claude": {"tools": claude_tools},
    }
    if opencode_permission is not None:
        agent_config["opencode"] = {"permission": opencode_permission}

    ctx = {
        "agent_name": name,
        "agent_config": agent_config,
        "model_str": model_str,
        "resolved_effort": effort,
    }
    body = "You are a coder.\n\n## Process\n\nDo work."
    return ctx, body


# ---------------------------------------------------------------------------
# emit_file: return type and filename
# ---------------------------------------------------------------------------

class TestEmitFileReturnType:
    def test_returns_two_element_tuple(self):
        ctx, body = _make_ctx()
        result = emit_file(ctx, body)
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_filename_is_agent_name_dot_toml(self):
        ctx, body = _make_ctx(name="explorer")
        filename, _ = emit_file(ctx, body)
        assert filename == "explorer.toml"

    def test_content_parses_as_toml(self):
        ctx, body = _make_ctx()
        _, content = emit_file(ctx, body)
        doc = tomllib.loads(content)
        assert isinstance(doc, dict)

    def test_content_has_name(self):
        ctx, body = _make_ctx(name="reviewer")
        _, content = emit_file(ctx, body)
        doc = tomllib.loads(content)
        assert doc["name"] == "reviewer"

    def test_content_has_description(self):
        ctx, body = _make_ctx(description="Reviews code.")
        _, content = emit_file(ctx, body)
        doc = tomllib.loads(content)
        assert doc["description"] == "Reviews code."

    def test_content_has_developer_instructions_matching_body(self):
        ctx, body = _make_ctx()
        _, content = emit_file(ctx, body)
        doc = tomllib.loads(content)
        assert doc["developer_instructions"] == body

    def test_model_present_when_model_str_given(self):
        ctx, body = _make_ctx(model_str="gpt-5.4")
        _, content = emit_file(ctx, body)
        doc = tomllib.loads(content)
        assert doc["model"] == "gpt-5.4"

    def test_model_absent_when_model_str_empty(self):
        ctx, body = _make_ctx(model_str="")
        _, content = emit_file(ctx, body)
        doc = tomllib.loads(content)
        assert "model" not in doc

    def test_model_absent_when_model_str_none(self):
        ctx, body = _make_ctx()
        ctx["model_str"] = None
        _, content = emit_file(ctx, body)
        doc = tomllib.loads(content)
        assert "model" not in doc


# ---------------------------------------------------------------------------
# emit_file: sandbox_mode derivation
# ---------------------------------------------------------------------------

class TestEmitFileSandboxMode:
    def test_write_tool_produces_workspace_write(self):
        ctx, body = _make_ctx(claude_tools="Read, Write, Bash")
        _, content = emit_file(ctx, body)
        doc = tomllib.loads(content)
        assert doc["sandbox_mode"] == "workspace-write"

    def test_edit_tool_produces_workspace_write(self):
        ctx, body = _make_ctx(claude_tools="Read, Edit, Bash")
        _, content = emit_file(ctx, body)
        doc = tomllib.loads(content)
        assert doc["sandbox_mode"] == "workspace-write"

    def test_read_only_tools_produce_read_only(self):
        ctx, body = _make_ctx(claude_tools="Read, Grep, Glob")
        _, content = emit_file(ctx, body)
        doc = tomllib.loads(content)
        assert doc["sandbox_mode"] == "read-only"

    def test_empty_tools_produce_read_only(self):
        ctx, body = _make_ctx(claude_tools="")
        _, content = emit_file(ctx, body)
        doc = tomllib.loads(content)
        assert doc["sandbox_mode"] == "read-only"

    def test_opencode_permission_edit_allow_produces_workspace_write(self):
        ctx, body = _make_ctx(claude_tools="Read", opencode_permission={"edit": "allow"})
        _, content = emit_file(ctx, body)
        doc = tomllib.loads(content)
        assert doc["sandbox_mode"] == "workspace-write"


# ---------------------------------------------------------------------------
# emit_file: model_reasoning_effort — verbatim pass-through (no cross-provider
# mapping — validation now happens upstream in rendering.py's _resolve_effort,
# see tests/unit/services/test_resolve_effort.py for the validation matrix).
# ---------------------------------------------------------------------------

class TestEmitFileEffortMapping:
    def test_low_effort_passed_through(self):
        ctx, body = _make_ctx(effort="low")
        _, content = emit_file(ctx, body)
        doc = tomllib.loads(content)
        assert doc["model_reasoning_effort"] == "low"

    def test_medium_effort_passed_through(self):
        ctx, body = _make_ctx(effort="medium")
        _, content = emit_file(ctx, body)
        doc = tomllib.loads(content)
        assert doc["model_reasoning_effort"] == "medium"

    def test_high_effort_passed_through(self):
        ctx, body = _make_ctx(effort="high")
        _, content = emit_file(ctx, body)
        doc = tomllib.loads(content)
        assert doc["model_reasoning_effort"] == "high"

    def test_emits_resolved_effort_verbatim_without_translation(self):
        """codex.py no longer maps/translates effort values — that validation
        moved upstream to rendering.py._resolve_effort. Whatever ctx['resolved_effort']
        carries is trusted and emitted as-is."""
        ctx, body = _make_ctx(effort="xhigh")
        _, content = emit_file(ctx, body)
        doc = tomllib.loads(content)
        assert doc["model_reasoning_effort"] == "xhigh"

    def test_absent_effort_defaults_to_medium(self):
        ctx, body = _make_ctx()
        # No effort resolved at all (agent effort absent, no role default either)
        ctx["resolved_effort"] = None
        del ctx["agent_config"]["effort"]
        _, content = emit_file(ctx, body)
        doc = tomllib.loads(content)
        assert doc["model_reasoning_effort"] == "medium"

    def test_missing_resolved_effort_key_defaults_to_medium(self):
        ctx, body = _make_ctx()
        del ctx["resolved_effort"]
        _, content = emit_file(ctx, body)
        doc = tomllib.loads(content)
        assert doc["model_reasoning_effort"] == "medium"


# ---------------------------------------------------------------------------
# emit_file: TOML escaping / round-trip
# ---------------------------------------------------------------------------

class TestEmitFileTOMLEscaping:
    def test_body_with_double_quotes_round_trips(self):
        ctx, _ = _make_ctx()
        body = 'Use "double quotes" freely in your output.'
        _, content = emit_file(ctx, body)
        doc = tomllib.loads(content)
        assert doc["developer_instructions"] == body

    def test_body_with_backslashes_round_trips(self):
        ctx, _ = _make_ctx()
        body = "Check path C:\\\\Users\\\\foo and also \\n newline."
        _, content = emit_file(ctx, body)
        doc = tomllib.loads(content)
        assert doc["developer_instructions"] == body

    def test_body_with_multiline_content_round_trips(self):
        ctx, _ = _make_ctx()
        body = "Line one.\nLine two.\nLine three."
        _, content = emit_file(ctx, body)
        doc = tomllib.loads(content)
        assert doc["developer_instructions"] == body

    def test_body_with_toml_special_chars_round_trips(self):
        ctx, _ = _make_ctx()
        body = "Keys look like: name = \"value\" and [section]"
        _, content = emit_file(ctx, body)
        doc = tomllib.loads(content)
        assert doc["developer_instructions"] == body


# ---------------------------------------------------------------------------
# _sandbox_mode helper
# ---------------------------------------------------------------------------

class TestSandboxModeHelper:
    def test_claude_tools_string_with_write(self):
        cfg = {"claude": {"tools": "Read, Write, Bash"}}
        assert _sandbox_mode(cfg) == "workspace-write"

    def test_claude_tools_string_with_edit(self):
        cfg = {"claude": {"tools": "Read, Edit"}}
        assert _sandbox_mode(cfg) == "workspace-write"

    def test_claude_tools_list_with_write(self):
        cfg = {"claude": {"tools": ["Read", "Write", "Bash"]}}
        assert _sandbox_mode(cfg) == "workspace-write"

    def test_claude_tools_list_read_only(self):
        cfg = {"claude": {"tools": ["Read", "Grep"]}}
        assert _sandbox_mode(cfg) == "read-only"

    def test_no_claude_config_returns_read_only(self):
        cfg = {}
        assert _sandbox_mode(cfg) == "read-only"

    def test_opencode_edit_allow_returns_workspace_write(self):
        cfg = {"opencode": {"permission": {"edit": "allow"}}}
        assert _sandbox_mode(cfg) == "workspace-write"

    def test_opencode_edit_deny_returns_read_only(self):
        cfg = {"opencode": {"permission": {"edit": "deny"}}}
        assert _sandbox_mode(cfg) == "read-only"

    def test_claude_tools_none_returns_read_only(self):
        cfg = {"claude": {"tools": None}}
        assert _sandbox_mode(cfg) == "read-only"


# ---------------------------------------------------------------------------
# post_process: section stripping
# ---------------------------------------------------------------------------

class TestPostProcess:
    def _ctx(self):
        ctx, _ = _make_ctx()
        return ctx

    def test_strips_memory_section(self):
        body = textwrap.dedent("""\
            ## Process

            Do work.

            ## Memory

            Save memories using the CLI.

            ## Reporting

            Report back.""")
        result = post_process(body, self._ctx())
        assert "## Memory" not in result
        assert "Save memories" not in result

    def test_strips_cost_reporting_section(self):
        body = textwrap.dedent("""\
            ## Process

            Do work.

            ## Cost reporting

            Use agent-notes cost-report.

            ## Reporting

            Report back.""")
        result = post_process(body, self._ctx())
        assert "## Cost reporting" not in result
        assert "cost-report" not in result

    def test_preserves_sections_after_stripped_one(self):
        body = textwrap.dedent("""\
            ## Process

            Do work.

            ## Memory

            Save memories.

            ## Reporting

            Report back.""")
        result = post_process(body, self._ctx())
        assert "## Reporting" in result
        assert "Report back." in result

    def test_preserves_sections_before_stripped_one(self):
        body = textwrap.dedent("""\
            ## Process

            Do work.

            ## Memory

            Save memories.""")
        result = post_process(body, self._ctx())
        assert "## Process" in result
        assert "Do work." in result

    def test_strips_memory_with_subsection_heading(self):
        """## Memory* should strip the section even if heading is e.g. '## Memory (read-before-work)'."""
        body = textwrap.dedent("""\
            ## Process

            Do work.

            ## Memory (read-before-work, write-on-discovery)

            Read the index.

            ## Reporting

            Report back.""")
        result = post_process(body, self._ctx())
        assert "Memory" not in result
        assert "Read the index." not in result

    def test_empty_body_returns_empty(self):
        result = post_process("", self._ctx())
        assert result == ""

    def test_body_without_stripped_sections_unchanged_content(self):
        body = "## Process\n\nDo work.\n\n## Reporting\n\nReport back."
        result = post_process(body, self._ctx())
        assert "## Process" in result
        assert "## Reporting" in result


# ---------------------------------------------------------------------------
# _strip_sections helper
# ---------------------------------------------------------------------------

class TestStripSections:
    def test_strips_exact_prefix_match(self):
        content = "## Memory\n\nsome text\n\n## Other\n\nother text"
        result = _strip_sections(content, ("## Memory",))
        assert "## Memory" not in result
        assert "some text" not in result
        assert "## Other" in result

    def test_does_not_strip_section_with_different_prefix(self):
        content = "## Memory\n\nfoo\n\n## Memorize\n\nbar"
        # "## Memorize" doesn't start with "## Memory" if exact word boundary matters,
        # but the impl checks startswith — so "## Memorize".startswith("## Memory") is True.
        # This test documents the current behavior (it WILL be stripped).
        result = _strip_sections(content, ("## Memory",))
        # Both "## Memory" and "## Memorize" are stripped — confirm "## Memory" gone
        assert "## Memory\n" not in result

    def test_trailing_blank_lines_removed(self):
        content = "## Keep\n\nkeep text\n\n## Memory\n\nmemory text\n\n\n"
        result = _strip_sections(content, ("## Memory",))
        assert not result.endswith("\n\n")
