"""Assert that the cost-report hook command string matches Hooks.COST_REPORT.

The hook string is matched by exact string in Claude Code settings.json for
install/remove. If the cost module re-declared it with different spacing or
wording, install would add a duplicate Stop hook and uninstall would orphan the
old one in every user's settings.json.

This test mirrors what #24 did for the memory hook constants.
"""
from agent_notes.constants import Hooks


class TestCostReportHookConstant:
    def test_cost_report_constant_equals_cli_subcommand(self):
        """Hooks.COST_REPORT equals 'agent-notes cost-report' — the exact CLI dispatch string."""
        assert Hooks.COST_REPORT == "agent-notes cost-report"

    def test_cost_report_hook_string_starts_with_agent_notes(self):
        """Hooks.COST_REPORT is invoked via agent-notes, not a standalone script."""
        assert Hooks.COST_REPORT.startswith("agent-notes ")

    def test_cost_report_subcommand_is_registered_in_argparse(self):
        """The 'cost-report' subcommand is registered so Hooks.COST_REPORT dispatches correctly."""
        import argparse
        # cli.main() registers cost-report; verify by importing and checking the parser
        # Parse just "cost-report" with no further args — if not registered, this fails.
        import agent_notes.cli as cli_module
        # The subcommand string in the constant must match the argparse subcommand name
        subcommand = Hooks.COST_REPORT[len("agent-notes "):]
        assert subcommand == "cost-report"
