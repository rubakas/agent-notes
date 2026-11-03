"""Tests for the agent line-limit helpers in validate command."""
from agent_notes.commands.validate import AGENT_TRIM_LINES, _agent_line_limit, _agent_trim_lines


class TestAgentLineLimit:
    def test_lead_gets_500(self):
        assert _agent_line_limit("lead") == 500

    def test_coder_gets_300(self):
        assert _agent_line_limit("coder") == 300

    def test_explorer_gets_300(self):
        assert _agent_line_limit("explorer") == 300


class TestAgentTrimLines:
    def test_lead_is_not_warned_below_its_own_ceiling(self):
        assert _agent_trim_lines("lead") == _agent_line_limit("lead")

    def test_other_agents_keep_the_trim_threshold(self):
        assert _agent_trim_lines("coder") == AGENT_TRIM_LINES
        assert _agent_trim_lines("explorer") == AGENT_TRIM_LINES
