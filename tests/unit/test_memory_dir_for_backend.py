"""Unit tests for agent_notes.config.memory_dir_for_backend."""
from pathlib import Path

import pytest

from agent_notes.config import memory_dir_for_backend, MEMORY_DIR


class TestMemoryDirForBackendNone:
    def test_none_backend_returns_none(self):
        assert memory_dir_for_backend("none") is None

    def test_none_backend_ignores_custom_path(self):
        assert memory_dir_for_backend("none", custom_path="/some/path") is None


class TestMemoryDirForBackendLocal:
    def test_local_returns_memory_dir_constant(self):
        result = memory_dir_for_backend("local")
        assert result == MEMORY_DIR

    def test_local_with_custom_path_uses_custom(self, tmp_path):
        custom = tmp_path / "custom-memory"
        result = memory_dir_for_backend("local", custom_path=str(custom))
        assert result == custom

    def test_local_custom_path_is_expanded(self):
        result = memory_dir_for_backend("local", custom_path="~/my-memory")
        assert "~" not in str(result)
        assert str(Path("~/my-memory").expanduser()) == str(result)


class TestMemoryDirForBackendObsidianCustomPath:
    def test_custom_path_returned_verbatim_expanded(self, tmp_path):
        custom = tmp_path / "vault" / "notes"
        result = memory_dir_for_backend("obsidian", custom_path=str(custom))
        assert result == custom

    def test_custom_path_with_tilde_expanded(self):
        result = memory_dir_for_backend("obsidian", custom_path="~/Documents/MyVault")
        assert "~" not in str(result)
        assert result == Path("~/Documents/MyVault").expanduser()


class TestMemoryDirForBackendObsidianPlainRoot:
    """obsidian backend returns the shared vault root — no per-project subfolder."""

    def test_obsidian_returns_plain_vault_root(self):
        result = memory_dir_for_backend("obsidian")
        expected = Path.home() / "Documents" / "Obsidian Vault" / "agent-notes"
        assert result == expected

    def test_obsidian_root_does_not_contain_project_subfolder(self):
        result = memory_dir_for_backend("obsidian")
        # Path must end exactly at agent-notes — no extra segment
        assert result.name == "agent-notes"
        assert result.parent.name == "Obsidian Vault"

    def test_obsidian_custom_path_returns_expanded_path(self, tmp_path):
        custom = tmp_path / "my" / "vault"
        result = memory_dir_for_backend("obsidian", custom_path=str(custom))
        assert result == custom

    def test_obsidian_default_is_deterministic(self):
        r1 = memory_dir_for_backend("obsidian")
        r2 = memory_dir_for_backend("obsidian")
        assert r1 == r2
