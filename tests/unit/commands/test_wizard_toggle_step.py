"""Tests for wizard step 8 routing through the toggle capability runner
instead of the hardcoded _select_cost_report call."""
from agent_notes.commands.wizard import execute as execute_mod
import inspect


def test_execute_install_takes_enabled_plugins_not_cost_report_flag():
    sig = inspect.signature(execute_mod._execute_install)
    assert "enabled_plugins" in sig.parameters
    assert "cost_report_enabled" not in sig.parameters


def test_orchestrator_uses_toggle_runner(monkeypatch):
    # The orchestrator's step 8 must call collect_toggle_selections, not the
    # bespoke _select_cost_report directly.
    import agent_notes.commands.wizard.orchestrator as orch
    src = inspect.getsource(orch._interactive_install)
    assert "collect_toggle_selections" in src
    assert "_select_cost_report" not in src
