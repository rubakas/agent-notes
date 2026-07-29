"""Tests for agent-notes cost-report subcommand routing."""
import sys
import pytest
from unittest.mock import patch, MagicMock


class TestCostReportSubcommand:
    def test_cost_report_subcommand_routes_to_module(self, monkeypatch):
        """agent-notes cost-report dispatches to cost_report.main()."""
        called = []

        def fake_main(since=None, session_id=None):
            called.append({"since": since, "session_id": session_id})
            return 0

        import agent_notes.cli as cli_module

        monkeypatch.setattr(sys, "argv", ["agent-notes", "cost-report"])

        with patch("agent_notes.cost.cost_report.main", fake_main):
            with patch("sys.exit") as mock_exit:
                cli_module.main()
                mock_exit.assert_called_once_with(0)

    def test_cost_report_subcommand_passes_since_flag(self, monkeypatch):
        """--since flag is parsed and forwarded as a float to main."""
        received = {}

        def fake_main(since=None, session_id=None):
            received['since'] = since
            received['session_id'] = session_id
            return 0

        import agent_notes.cli as cli_module

        monkeypatch.setattr(sys, "argv", [
            "agent-notes", "cost-report", "--since", "2026-04-30T12:00:00Z"
        ])

        with patch("agent_notes.cost.cost_report.main", fake_main):
            with patch("sys.exit"):
                cli_module.main()

        from agent_notes.cost.cost_report import _parse_since
        expected = _parse_since("2026-04-30T12:00:00Z")
        assert received['since'] == expected

    def test_cost_report_subcommand_passes_session_flag(self, monkeypatch):
        """--session flag is forwarded as session_id kwarg to main."""
        received = {}

        def fake_main(since=None, session_id=None):
            received['since'] = since
            received['session_id'] = session_id
            return 0

        import agent_notes.cli as cli_module

        monkeypatch.setattr(sys, "argv", [
            "agent-notes", "cost-report", "--session", "abc123"
        ])

        with patch("agent_notes.cost.cost_report.main", fake_main):
            with patch("sys.exit"):
                cli_module.main()

        assert received['session_id'] == "abc123"
