"""Tests for _agent_line_limit helper in validate command."""
from agent_notes.commands.validate import _agent_line_limit


class TestAgentLineLimit:
    def test_lead_gets_500(self):
        assert _agent_line_limit("lead") == 500

    def test_coder_gets_300(self):
        assert _agent_line_limit("coder") == 300

    def test_explorer_gets_300(self):
        assert _agent_line_limit("explorer") == 300
