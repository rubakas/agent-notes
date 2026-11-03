"""Unit tests for agent_notes.data.templates.frontmatter.claude — model/effort rendering."""
import yaml

from agent_notes.data.templates.frontmatter.claude import render


def _make_ctx(resolved_effort=None, color="green", model_str="claude-sonnet-5",
              description="A coder agent.", claude=None):
    agent_config = {
        "description": description,
        "color": color,
    }
    if claude is not None:
        agent_config["claude"] = claude
    return {
        "agent_name": "coder",
        "agent_config": agent_config,
        "model_str": model_str,
        "resolved_effort": resolved_effort,
    }


class TestModelLine:
    def test_model_str_rendered_verbatim(self):
        """The resolved model string (exact version pin) must appear untouched —
        the template must never normalize or shorten it."""
        result = render(_make_ctx(model_str="claude-sonnet-4-6"))
        assert "model: claude-sonnet-4-6" in result

    def test_pinned_model_and_effort_render_together(self):
        result = render(_make_ctx(model_str="claude-opus-4-8", resolved_effort="xhigh"))
        assert "model: claude-opus-4-8" in result
        assert "effort: xhigh" in result


class TestEffortLine:
    def test_effort_line_emitted_when_resolved(self):
        ctx = _make_ctx(resolved_effort="high")
        result = render(ctx)
        assert "effort: high" in result

    def test_no_effort_line_when_none_resolved(self):
        ctx = _make_ctx(resolved_effort=None)
        result = render(ctx)
        assert "effort:" not in result

    def test_no_effort_line_when_key_absent(self):
        ctx = _make_ctx()
        del ctx["resolved_effort"]
        result = render(ctx)
        assert "effort:" not in result


def _frontmatter(text):
    return yaml.safe_load(text.split("---")[1])


class TestDescriptionQuoting:
    def test_colon_and_quotes_round_trip(self):
        description = 'Reviews code: says "stop" when a path like C:\\tmp breaks. Triggers: review.'
        result = render(_make_ctx(description=description))
        assert _frontmatter(result)["description"] == description

    def test_description_is_double_quoted(self):
        result = render(_make_ctx(description="Plain text."))
        assert 'description: "Plain text."' in result

    def test_field_order_unchanged(self):
        result = render(_make_ctx(resolved_effort="high", claude={"tools": "Read", "memory": "user"}))
        keys = [line.split(":")[0] for line in result.splitlines()[1:-1]]
        assert keys == ["name", "description", "model", "tools", "memory", "color", "effort"]


class TestClaudeFlags:
    def test_omit_claude_md_emitted_when_set(self):
        result = render(_make_ctx(claude={"omitClaudeMd": True}))
        assert "omitClaudeMd: true" in result
        assert _frontmatter(result)["omitClaudeMd"] is True

    def test_omit_claude_md_absent_when_not_set(self):
        assert "omitClaudeMd" not in render(_make_ctx())
        assert "omitClaudeMd" not in render(_make_ctx(claude={"memory": "user"}))

    def test_background_emitted_when_set(self):
        result = render(_make_ctx(claude={"background": True}))
        assert _frontmatter(result)["background"] is True

    def test_background_absent_when_not_set(self):
        assert "background" not in render(_make_ctx())
