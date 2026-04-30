"""Tests for agent-notes cost-report subcommand routing."""
import sys
import pytest
from unittest.mock import patch, MagicMock


class TestCostReportSubcommand:
    def test_cost_report_subcommand_routes_to_module(self, monkeypatch):
        """agent-notes cost-report dispatches to cost_report.main()."""
        called_with_argv = []

        def fake_main():
            called_with_argv.extend(sys.argv[:])
            return 0

        import agent_notes.cli as cli_module

        monkeypatch.setattr(sys, "argv", ["agent-notes", "cost-report"])

        with patch("agent_notes.scripts.cost_report.main", fake_main):
            with patch("sys.exit") as mock_exit:
                cli_module.main()
                mock_exit.assert_called_once_with(0)

    def test_cost_report_subcommand_passes_since_flag(self, monkeypatch):
        """--since flag is forwarded to cost_report.main via sys.argv."""
        received_argv = []

        def fake_main():
            received_argv.extend(sys.argv[:])
            return 0

        import agent_notes.cli as cli_module

        monkeypatch.setattr(sys, "argv", [
            "agent-notes", "cost-report", "--since", "2026-04-30T12:00:00Z"
        ])

        with patch("agent_notes.scripts.cost_report.main", fake_main):
            with patch("sys.exit"):
                cli_module.main()

        assert "--since" in received_argv
        assert "2026-04-30T12:00:00Z" in received_argv

    def test_cost_report_subcommand_passes_session_flag(self, monkeypatch):
        """--session flag is forwarded to cost_report.main via sys.argv."""
        received_argv = []

        def fake_main():
            received_argv.extend(sys.argv[:])
            return 0

        import agent_notes.cli as cli_module

        monkeypatch.setattr(sys, "argv", [
            "agent-notes", "cost-report", "--session", "abc123"
        ])

        with patch("agent_notes.scripts.cost_report.main", fake_main):
            with patch("sys.exit"):
                cli_module.main()

        assert "--session" in received_argv
        assert "abc123" in received_argv
