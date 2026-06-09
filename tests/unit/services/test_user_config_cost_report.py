"""Tests for cost_report_enabled preference: user_config I/O, expand_includes skip,
cost_report.main() disabled guard, and cost_report_toggle command."""
import sys
import pytest
from pathlib import Path
from unittest.mock import patch


# ---------------------------------------------------------------------------
# save_user_config / load_user_config round-trip
# ---------------------------------------------------------------------------

class TestSaveLoadUserConfig:
    def test_round_trip_cost_report_enabled_true(self, tmp_path):
        """save then load preserves cost_report_enabled=True."""
        from agent_notes.services.user_config import save_user_config, load_user_config

        cfg_file = tmp_path / "config.yaml"
        save_user_config({"cost_report_enabled": True}, path=cfg_file)
        result = load_user_config(path=cfg_file)
        assert result["cost_report_enabled"] is True

    def test_round_trip_cost_report_enabled_false(self, tmp_path):
        """save then load preserves cost_report_enabled=False."""
        from agent_notes.services.user_config import save_user_config, load_user_config

        cfg_file = tmp_path / "config.yaml"
        save_user_config({"cost_report_enabled": False}, path=cfg_file)
        result = load_user_config(path=cfg_file)
        assert result["cost_report_enabled"] is False

    def test_round_trip_preserves_other_keys(self, tmp_path):
        """save/load does not lose unrelated keys alongside cost_report_enabled."""
        from agent_notes.services.user_config import save_user_config, load_user_config

        cfg_file = tmp_path / "config.yaml"
        data = {"cost_report_enabled": False, "agent_roles": {"explorer": "haiku"}}
        save_user_config(data, path=cfg_file)
        result = load_user_config(path=cfg_file)
        assert result["cost_report_enabled"] is False
        assert result["agent_roles"]["explorer"] == "haiku"

    def test_save_creates_parent_dirs(self, tmp_path):
        """save_user_config creates intermediate directories if they don't exist."""
        from agent_notes.services.user_config import save_user_config, load_user_config

        nested = tmp_path / "a" / "b" / "config.yaml"
        save_user_config({"cost_report_enabled": True}, path=nested)
        assert nested.exists()
        result = load_user_config(path=nested)
        assert result["cost_report_enabled"] is True

    def test_config_path_not_touched(self, tmp_path, monkeypatch):
        """Passing an explicit path never writes to config_path() (the real user home)."""
        import agent_notes.services.user_config as uc_mod

        real_config_path_calls = []
        original = uc_mod.config_path

        def spy_config_path():
            real_config_path_calls.append(True)
            return original()

        monkeypatch.setattr(uc_mod, "config_path", spy_config_path)

        cfg_file = tmp_path / "config.yaml"
        uc_mod.save_user_config({"cost_report_enabled": False}, path=cfg_file)
        uc_mod.load_user_config(path=cfg_file)

        assert real_config_path_calls == [], "config_path() was called despite explicit path arg"


# ---------------------------------------------------------------------------
# Default absence == disabled
# ---------------------------------------------------------------------------

class TestDefaultCostReportEnabled:
    def test_missing_file_returns_empty_dict(self, tmp_path):
        """load_user_config returns {} when the file does not exist."""
        from agent_notes.services.user_config import load_user_config

        missing = tmp_path / "no_such_config.yaml"
        result = load_user_config(path=missing)
        assert result == {}

    def test_absent_key_defaults_to_disabled(self, tmp_path):
        """When cost_report_enabled is absent, .get(..., False) returns False (feature disabled)."""
        from agent_notes.services.user_config import load_user_config

        missing = tmp_path / "no_such_config.yaml"
        cfg = load_user_config(path=missing)
        assert cfg.get("cost_report_enabled", False) is False

    def test_empty_yaml_file_defaults_to_disabled(self, tmp_path):
        """An empty YAML file produces {} and therefore cost_report_enabled defaults False."""
        from agent_notes.services.user_config import load_user_config

        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text("")
        cfg = load_user_config(path=cfg_file)
        assert cfg.get("cost_report_enabled", False) is False


# ---------------------------------------------------------------------------
# expand_includes with skip={'cost_reporting'}
# ---------------------------------------------------------------------------

class TestExpandIncludesSkip:
    def _make_shared(self, tmp_path):
        shared = tmp_path / "shared"
        shared.mkdir()
        (shared / "cost_reporting.md").write_text("## Cost Reporting\n\nRun cost-report.\n")
        (shared / "other.md").write_text("## Other Section\n\nOther content.\n")
        return shared

    def test_skipped_include_produces_empty_string(self, tmp_path):
        """With skip={'cost_reporting'}, the cost_reporting include line is removed."""
        from agent_notes.services.rendering import expand_includes

        shared = self._make_shared(tmp_path)
        text = "Before\n<!-- include: cost_reporting -->\nAfter"
        result = expand_includes(text, shared, skip={"cost_reporting"})
        assert "## Cost Reporting" not in result
        assert "Run cost-report." not in result

    def test_skipped_include_leaves_surrounding_text(self, tmp_path):
        """Lines around a skipped include are preserved."""
        from agent_notes.services.rendering import expand_includes

        shared = self._make_shared(tmp_path)
        text = "Before\n<!-- include: cost_reporting -->\nAfter"
        result = expand_includes(text, shared, skip={"cost_reporting"})
        assert "Before" in result
        assert "After" in result

    def test_non_skipped_include_still_expands(self, tmp_path):
        """Includes NOT in skip set are expanded as normal."""
        from agent_notes.services.rendering import expand_includes

        shared = self._make_shared(tmp_path)
        text = "<!-- include: other -->"
        result = expand_includes(text, shared, skip={"cost_reporting"})
        assert "## Other Section" in result
        assert "Other content." in result

    def test_both_includes_mixed(self, tmp_path):
        """skip removes cost_reporting but expands other in the same document."""
        from agent_notes.services.rendering import expand_includes

        shared = self._make_shared(tmp_path)
        text = "<!-- include: cost_reporting -->\n<!-- include: other -->"
        result = expand_includes(text, shared, skip={"cost_reporting"})
        assert "## Cost Reporting" not in result
        assert "## Other Section" in result

    def test_skip_none_default_expands_everything(self, tmp_path):
        """Default skip=None expands all includes including cost_reporting."""
        from agent_notes.services.rendering import expand_includes

        shared = self._make_shared(tmp_path)
        text = "<!-- include: cost_reporting -->"
        result = expand_includes(text, shared)
        assert "## Cost Reporting" in result

    def test_skip_empty_set_expands_everything(self, tmp_path):
        """Explicit empty set skip=set() also expands all includes."""
        from agent_notes.services.rendering import expand_includes

        shared = self._make_shared(tmp_path)
        text = "<!-- include: cost_reporting -->"
        result = expand_includes(text, shared, skip=set())
        assert "## Cost Reporting" in result


# ---------------------------------------------------------------------------
# cost_report.main() disabled guard
# ---------------------------------------------------------------------------

class TestCostReportMainDisabledGuard:
    """load_user_config is imported inside main() via a local 'from' import,
    so the correct patch target is the source module:
    agent_notes.services.user_config.load_user_config.
    """

    def test_returns_zero_when_disabled(self, monkeypatch, capsys):
        """main() returns 0 and does not raise when cost_report_enabled is False."""
        monkeypatch.setattr(sys, "argv", ["x"])
        with patch(
            "agent_notes.services.user_config.load_user_config",
            return_value={"cost_report_enabled": False},
        ):
            from agent_notes.scripts import cost_report
            result = cost_report.main()
        assert result == 0

    def test_prints_disabled_message(self, monkeypatch, capsys):
        """main() prints a message mentioning the feature is disabled."""
        monkeypatch.setattr(sys, "argv", ["x"])
        with patch(
            "agent_notes.services.user_config.load_user_config",
            return_value={"cost_report_enabled": False},
        ):
            from agent_notes.scripts import cost_report
            cost_report.main()

        out = capsys.readouterr().out
        assert "disabled" in out.lower()

    def test_disabled_message_suggests_re_enable(self, monkeypatch, capsys):
        """Disabled message hints at how to re-enable cost reporting."""
        monkeypatch.setattr(sys, "argv", ["x"])
        with patch(
            "agent_notes.services.user_config.load_user_config",
            return_value={"cost_report_enabled": False},
        ):
            from agent_notes.scripts import cost_report
            cost_report.main()

        out = capsys.readouterr().out
        # Should mention enabling or the config subcommand in some form
        assert "on" in out or "enable" in out.lower() or "cost-report" in out

    def test_enabled_config_does_not_early_return_on_disabled_guard(self, monkeypatch):
        """main() does NOT short-circuit when cost_report_enabled is True."""
        monkeypatch.setattr(sys, "argv", ["x"])
        # We expect it to proceed past the guard and eventually call backend logic.
        # Intercept at _by_recency to avoid touching real filesystem/DB.
        with patch(
            "agent_notes.services.user_config.load_user_config",
            return_value={"cost_report_enabled": True},
        ), patch(
            "agent_notes.scripts.cost_report._by_recency",
            return_value=0,
        ) as mock_backend:
            from agent_notes.scripts import cost_report
            # Patch env so we fall through to _by_recency branch
            with patch.dict("os.environ", {}, clear=False):
                import os
                os.environ.pop("CLAUDECODE", None)
                os.environ.pop("CLAUDE_CODE_ENTRYPOINT", None)
                os.environ.pop("OPENCODE", None)
                os.environ.pop("OPENCODE_SESSION_ID", None)
                cost_report.main()

        mock_backend.assert_called_once()


# ---------------------------------------------------------------------------
# cost_report_toggle
# ---------------------------------------------------------------------------

class TestCostReportToggle:
    def test_toggle_off_saves_false(self, tmp_path, monkeypatch):
        """cost_report_toggle('off') persists cost_report_enabled=False."""
        import agent_notes.services.user_config as uc_mod
        import agent_notes.commands.config as cfg_mod

        cfg_file = tmp_path / "config.yaml"
        monkeypatch.setattr(uc_mod, "config_path", lambda: cfg_file)

        cfg_mod.cost_report_toggle("off")

        result = uc_mod.load_user_config(path=cfg_file)
        assert result["cost_report_enabled"] is False

    def test_toggle_on_saves_true(self, tmp_path, monkeypatch):
        """cost_report_toggle('on') persists cost_report_enabled=True."""
        import agent_notes.services.user_config as uc_mod
        import agent_notes.commands.config as cfg_mod

        cfg_file = tmp_path / "config.yaml"
        monkeypatch.setattr(uc_mod, "config_path", lambda: cfg_file)

        cfg_mod.cost_report_toggle("on")

        result = uc_mod.load_user_config(path=cfg_file)
        assert result["cost_report_enabled"] is True

    def test_toggle_off_then_on_round_trip(self, tmp_path, monkeypatch):
        """Toggling off then on leaves cost_report_enabled=True."""
        import agent_notes.services.user_config as uc_mod
        import agent_notes.commands.config as cfg_mod

        cfg_file = tmp_path / "config.yaml"
        monkeypatch.setattr(uc_mod, "config_path", lambda: cfg_file)

        cfg_mod.cost_report_toggle("off")
        cfg_mod.cost_report_toggle("on")

        result = uc_mod.load_user_config(path=cfg_file)
        assert result["cost_report_enabled"] is True

    def test_toggle_on_prints_enabled(self, tmp_path, monkeypatch, capsys):
        """cost_report_toggle('on') prints a message indicating it's enabled."""
        import agent_notes.services.user_config as uc_mod
        import agent_notes.commands.config as cfg_mod

        cfg_file = tmp_path / "config.yaml"
        monkeypatch.setattr(uc_mod, "config_path", lambda: cfg_file)

        cfg_mod.cost_report_toggle("on")
        out = capsys.readouterr().out
        assert "enabled" in out.lower()

    def test_toggle_off_prints_disabled(self, tmp_path, monkeypatch, capsys):
        """cost_report_toggle('off') prints a message indicating it's disabled."""
        import agent_notes.services.user_config as uc_mod
        import agent_notes.commands.config as cfg_mod

        cfg_file = tmp_path / "config.yaml"
        monkeypatch.setattr(uc_mod, "config_path", lambda: cfg_file)

        cfg_mod.cost_report_toggle("off")
        out = capsys.readouterr().out
        assert "disabled" in out.lower()

    def test_toggle_preserves_existing_keys(self, tmp_path, monkeypatch):
        """cost_report_toggle does not erase pre-existing user config keys."""
        import agent_notes.services.user_config as uc_mod
        import agent_notes.commands.config as cfg_mod

        cfg_file = tmp_path / "config.yaml"
        uc_mod.save_user_config({"agent_roles": {"coder": "sonnet"}}, path=cfg_file)
        monkeypatch.setattr(uc_mod, "config_path", lambda: cfg_file)

        cfg_mod.cost_report_toggle("off")

        result = uc_mod.load_user_config(path=cfg_file)
        assert result.get("agent_roles", {}).get("coder") == "sonnet"
        assert result["cost_report_enabled"] is False
