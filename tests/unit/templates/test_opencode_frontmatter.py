"""Unit tests for agent_notes.data.templates.frontmatter.opencode — effort rendering."""
from agent_notes.data.templates.frontmatter.opencode import render


def _make_ctx(resolved_effort=None):
    agent_config = {
        "description": "A coder agent.",
        "mode": "subagent",
    }
    return {
        "agent_name": "coder",
        "agent_config": agent_config,
        "model_str": "moonshotai/kimi-k2",
        "resolved_effort": resolved_effort,
    }


class TestReasoningEffortLine:
    def test_reasoning_effort_emitted_when_resolved(self):
        ctx = _make_ctx(resolved_effort="medium")
        result = render(ctx)
        assert "reasoningEffort: medium" in result

    def test_no_reasoning_effort_line_when_none_resolved(self):
        ctx = _make_ctx(resolved_effort=None)
        result = render(ctx)
        assert "reasoningEffort:" not in result

    def test_no_reasoning_effort_line_when_key_absent(self):
        ctx = _make_ctx()
        del ctx["resolved_effort"]
        result = render(ctx)
        assert "reasoningEffort:" not in result
