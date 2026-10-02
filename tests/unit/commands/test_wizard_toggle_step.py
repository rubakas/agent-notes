"""Tests for wizard step 8 routing through the toggle capability runner
instead of a hardcoded cost-report step."""
from agent_notes.commands.wizard import execute as execute_mod
import inspect


def test_execute_install_takes_enabled_plugins_not_cost_report_flag():
    sig = inspect.signature(execute_mod._execute_install)
    assert "enabled_plugins" in sig.parameters
    assert "cost_report_enabled" not in sig.parameters
