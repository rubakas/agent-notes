"""Tests for hook registration in agent_notes.services.installer."""
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from agent_notes.services.settings_writer import has_hook, install_hook
from agent_notes.constants import Hooks
from agent_notes.services.installer import _install_session_hook, _uninstall_session_hook


@pytest.fixture
def mock_backend(tmp_path):
    backend = MagicMock()
    backend.global_home = tmp_path
    backend.local_dir = str(tmp_path)
    backend.name = "claude"
    backend.layout = {
        "config": "CLAUDE.md",
        "agents": "agents",
        "rules": "rules",
        "skills": "skills",
        "commands": "commands",
    }
    return backend


@pytest.fixture(autouse=True)
def patch_deps(tmp_path):
    # _install_session_hook imports these locally inside its body, so we patch
    # at the source module level rather than the installer namespace.
    with patch("agent_notes.services.session_context.write_context"), \
         patch("agent_notes.registries.skill_registry.default_skill_registry") as mock_reg, \
         patch("agent_notes.services.state_store.load_state") as mock_state, \
         patch("agent_notes.config.get_version", return_value="0.0.0-test"), \
         patch("agent_notes.config.memory_dir_for_backend", return_value=None), \
         patch("agent_notes.services.installer.load_state") as mock_state2:
        mock_reg.return_value.all.return_value = []
        mock_state.return_value = None
        mock_state2.return_value = None
        yield


class TestInstallRegistersMemoryBridge:
    def test_obsidian_backend_registers_memory_bridge(self, mock_backend, tmp_path):
        settings_path = tmp_path / "settings.json"

        _install_session_hook(mock_backend, "global", memory_backend="obsidian")

        assert has_hook(settings_path, "SessionStart", Hooks.MEMORY_BRIDGE)

    def test_wiki_backend_registers_memory_bridge(self, mock_backend, tmp_path):
        settings_path = tmp_path / "settings.json"

        _install_session_hook(mock_backend, "global", memory_backend="wiki")

        assert has_hook(settings_path, "SessionStart", Hooks.MEMORY_BRIDGE)

    def test_local_backend_skips_memory_bridge(self, mock_backend, tmp_path):
        settings_path = tmp_path / "settings.json"

        _install_session_hook(mock_backend, "global", memory_backend="local")

        assert not has_hook(settings_path, "SessionStart", Hooks.MEMORY_BRIDGE)

    def test_none_backend_skips_memory_bridge(self, mock_backend, tmp_path):
        settings_path = tmp_path / "settings.json"

        _install_session_hook(mock_backend, "global", memory_backend="none")

        assert not has_hook(settings_path, "SessionStart", Hooks.MEMORY_BRIDGE)


class TestInstallRegistersCostReport:
    def test_always_registers_stop_hook(self, mock_backend, tmp_path):
        settings_path = tmp_path / "settings.json"

        _install_session_hook(mock_backend, "global", memory_backend="local")

        assert has_hook(settings_path, "Stop", Hooks.COST_REPORT)


class TestInstallCleansUpStaleHooks:
    def test_removes_stale_post_tool_use(self, mock_backend, tmp_path):
        settings_path = tmp_path / "settings.json"
        # Pre-seed a stale PostToolUse memory-bridge entry
        install_hook(settings_path, "PostToolUse", Hooks.MEMORY_BRIDGE)
        assert has_hook(settings_path, "PostToolUse", Hooks.MEMORY_BRIDGE)

        _install_session_hook(mock_backend, "global", memory_backend="obsidian")

        assert not has_hook(settings_path, "PostToolUse", Hooks.MEMORY_BRIDGE)

    def test_removes_memory_bridge_when_switching_to_local(self, mock_backend, tmp_path):
        settings_path = tmp_path / "settings.json"
        # Pre-seed a SessionStart memory-bridge (from a previous obsidian install)
        install_hook(settings_path, "SessionStart", Hooks.MEMORY_BRIDGE)
        assert has_hook(settings_path, "SessionStart", Hooks.MEMORY_BRIDGE)

        _install_session_hook(mock_backend, "global", memory_backend="local")

        assert not has_hook(settings_path, "SessionStart", Hooks.MEMORY_BRIDGE)


class TestUninstallRemovesAllHooks:
    def test_removes_memory_bridge(self, mock_backend, tmp_path):
        settings_path = tmp_path / "settings.json"
        _install_session_hook(mock_backend, "global", memory_backend="obsidian")
        assert has_hook(settings_path, "SessionStart", Hooks.MEMORY_BRIDGE)

        _uninstall_session_hook(mock_backend, "global")

        assert not has_hook(settings_path, "SessionStart", Hooks.MEMORY_BRIDGE)

    def test_removes_cost_report(self, mock_backend, tmp_path):
        settings_path = tmp_path / "settings.json"
        _install_session_hook(mock_backend, "global", memory_backend="local")
        assert has_hook(settings_path, "Stop", Hooks.COST_REPORT)

        _uninstall_session_hook(mock_backend, "global")

        assert not has_hook(settings_path, "Stop", Hooks.COST_REPORT)

    def test_removes_stale_post_tool_use_on_uninstall(self, mock_backend, tmp_path):
        settings_path = tmp_path / "settings.json"
        # Pre-seed a stale PostToolUse entry
        install_hook(settings_path, "PostToolUse", Hooks.MEMORY_BRIDGE)
        assert has_hook(settings_path, "PostToolUse", Hooks.MEMORY_BRIDGE)

        _uninstall_session_hook(mock_backend, "global")

        assert not has_hook(settings_path, "PostToolUse", Hooks.MEMORY_BRIDGE)
