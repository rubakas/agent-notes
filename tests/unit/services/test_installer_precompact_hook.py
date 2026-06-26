"""Tests for PreCompact memory-bridge hook registration in the installer."""
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
    }
    backend.supports.side_effect = lambda f: f in ("stop_hook", "allow_entries")
    return backend


@pytest.fixture
def mock_backend_no_stop_hook(tmp_path):
    """Backend without stop_hook support (e.g., Codex)."""
    backend = MagicMock()
    backend.global_home = tmp_path
    backend.local_dir = str(tmp_path)
    backend.name = "codex"
    backend.label = "Codex"
    backend.layout = {
        "config": "AGENTS.md",
        "agents": "agents",
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


class TestPrecompactHookInstall:
    def test_obsidian_backend_registers_precompact_hook(self, mock_backend, tmp_path):
        settings_path = tmp_path / "settings.json"

        _install_session_hook(mock_backend, "global", memory_backend="obsidian")

        assert has_hook(settings_path, "PreCompact", Hooks.PRECOMPACT_MEMORY_BRIDGE)

    def test_wiki_backend_registers_precompact_hook(self, mock_backend, tmp_path):
        settings_path = tmp_path / "settings.json"

        _install_session_hook(mock_backend, "global", memory_backend="wiki")

        assert has_hook(settings_path, "PreCompact", Hooks.PRECOMPACT_MEMORY_BRIDGE)

    def test_local_backend_skips_precompact_hook(self, mock_backend, tmp_path):
        settings_path = tmp_path / "settings.json"

        _install_session_hook(mock_backend, "global", memory_backend="local")

        assert not has_hook(settings_path, "PreCompact", Hooks.PRECOMPACT_MEMORY_BRIDGE)

    def test_none_backend_skips_precompact_hook(self, mock_backend, tmp_path):
        settings_path = tmp_path / "settings.json"

        _install_session_hook(mock_backend, "global", memory_backend="none")

        assert not has_hook(settings_path, "PreCompact", Hooks.PRECOMPACT_MEMORY_BRIDGE)

    def test_non_capable_backend_skips_precompact_hook(self, mock_backend_no_stop_hook, tmp_path):
        settings_path = tmp_path / "settings.json"

        _install_session_hook(mock_backend_no_stop_hook, "global", memory_backend="obsidian")

        assert not has_hook(settings_path, "PreCompact", Hooks.PRECOMPACT_MEMORY_BRIDGE)

    def test_install_is_idempotent(self, mock_backend, tmp_path):
        settings_path = tmp_path / "settings.json"

        _install_session_hook(mock_backend, "global", memory_backend="obsidian")
        _install_session_hook(mock_backend, "global", memory_backend="obsidian")

        data = json.loads(settings_path.read_text())
        entries = data.get("hooks", {}).get("PreCompact", [])
        matching = [
            h
            for entry in entries
            for h in entry.get("hooks", [])
            if h.get("command") == Hooks.PRECOMPACT_MEMORY_BRIDGE
        ]
        assert len(matching) == 1, "PreCompact hook should be registered exactly once"


class TestPrecompactHookUninstall:
    def test_uninstall_removes_precompact_hook(self, mock_backend, tmp_path):
        settings_path = tmp_path / "settings.json"
        _install_session_hook(mock_backend, "global", memory_backend="obsidian")
        assert has_hook(settings_path, "PreCompact", Hooks.PRECOMPACT_MEMORY_BRIDGE)

        _uninstall_session_hook(mock_backend, "global")

        assert not has_hook(settings_path, "PreCompact", Hooks.PRECOMPACT_MEMORY_BRIDGE)

    def test_uninstall_preserves_user_keys(self, mock_backend, tmp_path):
        settings_path = tmp_path / "settings.json"
        # Pre-seed settings with a user-defined key
        settings_path.write_text(json.dumps({"model": "claude-opus-4-7"}) + "\n")

        _install_session_hook(mock_backend, "global", memory_backend="obsidian")
        _uninstall_session_hook(mock_backend, "global")

        data = json.loads(settings_path.read_text())
        assert data.get("model") == "claude-opus-4-7"

    def test_uninstall_is_noop_when_not_installed(self, mock_backend, tmp_path):
        settings_path = tmp_path / "settings.json"
        # No prior install — should not raise
        _uninstall_session_hook(mock_backend, "global")

        assert not settings_path.exists() or not has_hook(
            settings_path, "PreCompact", Hooks.PRECOMPACT_MEMORY_BRIDGE
        )


class TestPrecompactHookSwitchBackend:
    def test_switching_to_local_removes_precompact_hook(self, mock_backend, tmp_path):
        settings_path = tmp_path / "settings.json"
        # First install with obsidian
        _install_session_hook(mock_backend, "global", memory_backend="obsidian")
        assert has_hook(settings_path, "PreCompact", Hooks.PRECOMPACT_MEMORY_BRIDGE)

        # Re-install with local backend — should remove the precompact hook
        _install_session_hook(mock_backend, "global", memory_backend="local")

        assert not has_hook(settings_path, "PreCompact", Hooks.PRECOMPACT_MEMORY_BRIDGE)
