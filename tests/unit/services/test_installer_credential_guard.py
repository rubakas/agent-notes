"""Tests for credential guard hook registration in agent_notes.services.installer."""
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
    backend.label = "Claude Code"
    backend.layout = {
        "config": "CLAUDE.md",
        "agents": "agents",
        "rules": "rules",
        "skills": "skills",
        "commands": "commands",
        "settings": "settings.json",
    }
    backend.supports.side_effect = lambda f: f in ("stop_hook", "allow_entries", "session_hook")
    return backend


@pytest.fixture
def mock_backend_no_stop_hook(tmp_path):
    """Backend that does NOT support stop_hook (e.g. Codex)."""
    backend = MagicMock()
    backend.global_home = tmp_path
    backend.local_dir = str(tmp_path)
    backend.name = "codex"
    backend.label = "Codex"
    backend.layout = {
        "hooks": "hooks.json",
    }
    backend.supports.side_effect = lambda f: False
    return backend


@pytest.fixture(autouse=True)
def patch_deps(tmp_path):
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


class TestCredentialGuardInstall:
    def test_install_registers_pretooluse_hook(self, mock_backend, tmp_path):
        settings_path = tmp_path / "settings.json"

        _install_session_hook(mock_backend, "global", memory_backend="local")

        assert has_hook(settings_path, "PreToolUse", Hooks.GUARD_CREDENTIALS)

    def test_install_hook_has_read_bash_grep_matcher(self, mock_backend, tmp_path):
        settings_path = tmp_path / "settings.json"

        _install_session_hook(mock_backend, "global", memory_backend="local")

        data = json.loads(settings_path.read_text())
        pre_tool_hooks = data.get("hooks", {}).get("PreToolUse", [])
        guard_entries = [
            entry for entry in pre_tool_hooks
            if any(h.get("command") == Hooks.GUARD_CREDENTIALS for h in entry.get("hooks", []))
        ]
        assert guard_entries, "guard-credentials hook entry not found"
        assert guard_entries[0]["matcher"] == Hooks.GUARD_CREDENTIALS_MATCHER
        assert "Grep" in Hooks.GUARD_CREDENTIALS_MATCHER

    def test_install_is_idempotent(self, mock_backend, tmp_path):
        settings_path = tmp_path / "settings.json"

        _install_session_hook(mock_backend, "global", memory_backend="local")
        _install_session_hook(mock_backend, "global", memory_backend="local")

        data = json.loads(settings_path.read_text())
        pre_tool_hooks = data.get("hooks", {}).get("PreToolUse", [])
        guard_commands = [
            h.get("command")
            for entry in pre_tool_hooks
            for h in entry.get("hooks", [])
            if h.get("command") == Hooks.GUARD_CREDENTIALS
        ]
        assert len(guard_commands) == 1, "credential guard must not be duplicated"

    def test_install_does_not_register_on_codex_backend(self, mock_backend_no_stop_hook, tmp_path):
        settings_path = tmp_path / "hooks.json"

        _install_session_hook(mock_backend_no_stop_hook, "global", memory_backend="local")

        assert not has_hook(settings_path, "PreToolUse", Hooks.GUARD_CREDENTIALS)

    def test_install_does_not_clobber_user_keys(self, mock_backend, tmp_path):
        """Installing the credential guard must not remove unrelated settings."""
        settings_path = tmp_path / "settings.json"
        # Pre-seed an unrelated user setting
        settings_path.write_text(json.dumps({"theme": "dark", "fontSize": 14}) + "\n")

        _install_session_hook(mock_backend, "global", memory_backend="local")

        data = json.loads(settings_path.read_text())
        assert data.get("theme") == "dark"
        assert data.get("fontSize") == 14


class TestCredentialGuardUninstall:
    def test_uninstall_removes_pretooluse_hook(self, mock_backend, tmp_path):
        settings_path = tmp_path / "settings.json"
        _install_session_hook(mock_backend, "global", memory_backend="local")
        assert has_hook(settings_path, "PreToolUse", Hooks.GUARD_CREDENTIALS)

        _uninstall_session_hook(mock_backend, "global")

        assert not has_hook(settings_path, "PreToolUse", Hooks.GUARD_CREDENTIALS)

    def test_uninstall_does_not_remove_user_keys(self, mock_backend, tmp_path):
        settings_path = tmp_path / "settings.json"
        settings_path.write_text(json.dumps({"theme": "dark"}) + "\n")
        _install_session_hook(mock_backend, "global", memory_backend="local")

        _uninstall_session_hook(mock_backend, "global")

        data = json.loads(settings_path.read_text())
        assert data.get("theme") == "dark"

    def test_uninstall_no_op_when_not_installed(self, mock_backend, tmp_path):
        """Uninstalling when the hook was never installed must not raise."""
        settings_path = tmp_path / "settings.json"
        # No prior install
        _uninstall_session_hook(mock_backend, "global")
        # Should not raise, settings.json may or may not exist

    def test_uninstall_codex_no_op(self, mock_backend_no_stop_hook, tmp_path):
        """Uninstalling on a backend without stop_hook is a no-op."""
        _uninstall_session_hook(mock_backend_no_stop_hook, "global")
        # No exception expected
