"""Tests for the cost report wizard step (_select_cost_report)."""
import pytest
from unittest.mock import patch


def _noop(*a, **kw):
    pass


def _force_non_interactive(monkeypatch):
    monkeypatch.setattr("agent_notes.services.ui._can_interactive", lambda: False)
    monkeypatch.setattr("agent_notes.services.ui._clear_screen", _noop)
    monkeypatch.setattr("agent_notes.services.ui._render_step_header", _noop)


# ---------------------------------------------------------------------------
# _select_cost_report
# ---------------------------------------------------------------------------

class TestSelectCostReport:
    def test_default_no_returns_false(self, monkeypatch):
        """Non-interactive path with default selection returns False (disabled)."""
        _force_non_interactive(monkeypatch)

        def fake_fallback(title, options, default=0, **kw):
            # Simulate pressing Enter (default selected)
            return options[default][1]

        monkeypatch.setattr(
            "agent_notes.commands.wizard.cost_report._radio_select_fallback",
            fake_fallback,
        )

        from agent_notes.commands.wizard.cost_report import _select_cost_report
        result = _select_cost_report()
        assert result is False

    def test_selecting_yes_returns_true(self, monkeypatch):
        """Selecting 'yes' option returns True (enabled)."""
        _force_non_interactive(monkeypatch)

        def fake_fallback(title, options, default=0, **kw):
            # Select the "yes" option
            return "yes"

        monkeypatch.setattr(
            "agent_notes.commands.wizard.cost_report._radio_select_fallback",
            fake_fallback,
        )

        from agent_notes.commands.wizard.cost_report import _select_cost_report
        result = _select_cost_report()
        assert result is True

    def test_selecting_no_explicitly_returns_false(self, monkeypatch):
        """Explicitly selecting 'no' returns False."""
        _force_non_interactive(monkeypatch)

        def fake_fallback(title, options, default=0, **kw):
            return "no"

        monkeypatch.setattr(
            "agent_notes.commands.wizard.cost_report._radio_select_fallback",
            fake_fallback,
        )

        from agent_notes.commands.wizard.cost_report import _select_cost_report
        result = _select_cost_report()
        assert result is False

    def test_default_option_index_is_zero(self, monkeypatch):
        """The default option passed to the fallback is index 0 (No)."""
        _force_non_interactive(monkeypatch)
        captured = {}

        def fake_fallback(title, options, default=0, **kw):
            captured["default"] = default
            captured["options"] = options
            return options[default][1]

        monkeypatch.setattr(
            "agent_notes.commands.wizard.cost_report._radio_select_fallback",
            fake_fallback,
        )

        from agent_notes.commands.wizard.cost_report import _select_cost_report
        _select_cost_report()

        assert captured["default"] == 0
        assert captured["options"][0][1] == "no"

    def test_prints_disabled_confirmation(self, monkeypatch, capsys):
        """Selecting No prints a confirmation mentioning 'disabled'."""
        _force_non_interactive(monkeypatch)

        monkeypatch.setattr(
            "agent_notes.commands.wizard.cost_report._radio_select_fallback",
            lambda title, options, default=0, **kw: "no",
        )

        from agent_notes.commands.wizard.cost_report import _select_cost_report
        _select_cost_report()

        out = capsys.readouterr().out
        assert "disabled" in out.lower()

    def test_prints_enabled_confirmation(self, monkeypatch, capsys):
        """Selecting Yes prints a confirmation mentioning 'enabled'."""
        _force_non_interactive(monkeypatch)

        monkeypatch.setattr(
            "agent_notes.commands.wizard.cost_report._radio_select_fallback",
            lambda title, options, default=0, **kw: "yes",
        )

        from agent_notes.commands.wizard.cost_report import _select_cost_report
        _select_cost_report()

        out = capsys.readouterr().out
        assert "enabled" in out.lower()
