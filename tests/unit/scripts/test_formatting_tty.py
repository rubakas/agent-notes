"""Tests for ANSI TTY auto-detect in _formatting.py."""
import pytest


class TestColorConstantsTTY:
    def test_constants_empty_when_not_tty(self, monkeypatch):
        import agent_notes.scripts._formatting as fmt
        monkeypatch.setattr(fmt, "_USE_COLOR", False)

        # Re-evaluate what the constants would be given _USE_COLOR=False.
        # Since constants are module-level, we test the gating logic by checking
        # that _USE_COLOR=False makes tier_color return "" and that the constants
        # themselves are empty strings when _USE_COLOR was False at import time.
        assert fmt.tier_color("claude-opus-4-7") == ""
        assert fmt.tier_color("claude-sonnet-4-6") == ""
        assert fmt.tier_color("claude-haiku-3-5") == ""

    def test_tier_color_returns_nonempty_when_tty(self, monkeypatch):
        import agent_notes.scripts._formatting as fmt
        monkeypatch.setattr(fmt, "_USE_COLOR", True)
        monkeypatch.setattr(fmt, "YELLOW", "\033[0;33m")
        monkeypatch.setattr(fmt, "CYAN", "\033[0;36m")
        monkeypatch.setattr(fmt, "DIM", "\033[2m")

        assert fmt.tier_color("claude-opus-4-7") != ""
        assert fmt.tier_color("claude-sonnet-4-6") != ""
        assert fmt.tier_color("claude-haiku-3-5") != ""

    def test_use_color_false_at_import_when_not_tty(self, monkeypatch):
        """Verify _USE_COLOR is driven by sys.stdout.isatty()."""
        import sys
        monkeypatch.setattr(sys.stdout, "isatty", lambda: False)

        # Force reimport to pick up the monkeypatched isatty
        import importlib
        import agent_notes.scripts._formatting as fmt
        importlib.reload(fmt)

        assert fmt._USE_COLOR is False
        assert fmt.BOLD == ""
        assert fmt.DIM == ""
        assert fmt.YELLOW == ""
        assert fmt.GREEN == ""
        assert fmt.CYAN == ""
        assert fmt.NC == ""

    def test_use_color_true_at_import_when_tty(self, monkeypatch):
        """Verify constants are non-empty when stdout is a TTY."""
        import sys
        monkeypatch.setattr(sys.stdout, "isatty", lambda: True)

        import importlib
        import agent_notes.scripts._formatting as fmt
        importlib.reload(fmt)

        assert fmt._USE_COLOR is True
        assert fmt.BOLD != ""
        assert fmt.YELLOW != ""
        assert fmt.NC != ""
