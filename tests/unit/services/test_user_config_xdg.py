"""Tests: config_path() honors $XDG_CONFIG_HOME, mirroring state_store.state_dir()."""
from __future__ import annotations

from pathlib import Path

import pytest


class TestConfigPathXdg:
    def test_xdg_config_home_set_uses_it(self, tmp_path, monkeypatch):
        """When XDG_CONFIG_HOME is set, config_path returns a path inside it."""
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        from agent_notes.services.user_config import config_path
        result = config_path()
        assert result == tmp_path / "agent-notes" / "config.yaml"

    def test_xdg_config_home_unset_uses_home_config(self, monkeypatch):
        """When XDG_CONFIG_HOME is not set, config_path falls back to ~/.config."""
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        from agent_notes.services.user_config import config_path
        result = config_path()
        assert result == Path.home() / ".config" / "agent-notes" / "config.yaml"

    def test_xdg_config_home_set_takes_priority_over_default(self, tmp_path, monkeypatch):
        """XDG_CONFIG_HOME overrides the ~/.config default regardless of home dir."""
        custom_dir = tmp_path / "xdg_custom"
        monkeypatch.setenv("XDG_CONFIG_HOME", str(custom_dir))
        from agent_notes.services.user_config import config_path
        result = config_path()
        assert str(result).startswith(str(custom_dir))
        assert result.name == "config.yaml"

    def test_legacy_path_honored_when_xdg_file_absent_and_legacy_exists(self, tmp_path, monkeypatch):
        """Legacy ~/.agent-notes.yaml is returned when it exists and XDG path does not."""
        # Point XDG to a dir where config.yaml won't exist
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        # Create a fake legacy file
        legacy = tmp_path / "legacy.yaml"
        legacy.write_text("key: val")
        # Patch Path.home() so legacy path is inside tmp_path
        import agent_notes.services.user_config as uc
        monkeypatch.setattr(uc.Path, "home", staticmethod(lambda: tmp_path))
        # XDG path is tmp_path/agent-notes/config.yaml — does not exist
        # legacy is tmp_path/.agent-notes.yaml — we need to create it at the legacy path
        legacy_path = tmp_path / ".agent-notes.yaml"
        legacy_path.write_text("key: val")

        result = uc.config_path()
        assert result == legacy_path

    def test_xdg_canonical_write_location_when_neither_exists(self, tmp_path, monkeypatch):
        """When neither XDG file nor legacy file exists, XDG path is returned as canonical."""
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        import agent_notes.services.user_config as uc
        monkeypatch.setattr(uc.Path, "home", staticmethod(lambda: tmp_path))

        result = uc.config_path()
        assert result == tmp_path / "agent-notes" / "config.yaml"
