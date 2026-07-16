"""Unit tests for agent_notes.data.templates.frontmatter.claude — model/effort rendering."""
from agent_notes.data.templates.frontmatter.claude import render


def _make_ctx(resolved_effort=None, color="green", model_str="claude-sonnet-5"):
    agent_config = {
        "description": "A coder agent.",
        "color": color,
    }
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
