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
    def test_custom_path_includes_project_name(self, monkeypatch, tmp_path):
        monkeypatch.setattr(Path, "cwd", staticmethod(lambda: Path("/fake/my-project")))
        custom = tmp_path / "vault" / "notes"
        result = memory_dir_for_backend("obsidian", custom_path=str(custom))
        assert result == custom / "my-project"

    def test_custom_path_with_tilde_expanded_and_project_appended(self, monkeypatch):
        monkeypatch.setattr(Path, "cwd", staticmethod(lambda: Path("/work/test-proj")))
        result = memory_dir_for_backend("obsidian", custom_path="~/Documents/MyVault")
        assert "~" not in str(result)
        assert result == Path("~/Documents/MyVault").expanduser() / "test-proj"


class TestMemoryDirForBackendObsidianProjectScoped:
    """obsidian backend returns a per-project subfolder under the vault root."""

    def test_obsidian_returns_project_scoped_path(self, monkeypatch):
        monkeypatch.setattr(Path, "cwd", staticmethod(lambda: Path("/code/my-project")))
        result = memory_dir_for_backend("obsidian")
        expected = Path.home() / "Obsidian" / "agent-notes" / "notes" / "my-project"
        assert result == expected

    def test_obsidian_path_ends_with_project_name(self, monkeypatch):
        monkeypatch.setattr(Path, "cwd", staticmethod(lambda: Path("/repos/agent-notes")))
        result = memory_dir_for_backend("obsidian")
        assert result.name == "agent-notes"
        assert result.parent.name == "notes"

    def test_obsidian_custom_path_includes_project_subfolder(self, monkeypatch, tmp_path):
        monkeypatch.setattr(Path, "cwd", staticmethod(lambda: Path("/fake/my-project")))
        custom = tmp_path / "my" / "vault"
        result = memory_dir_for_backend("obsidian", custom_path=str(custom))
        assert result == custom / "my-project"

    def test_obsidian_default_is_deterministic(self, monkeypatch):
        monkeypatch.setattr(Path, "cwd", staticmethod(lambda: Path("/code/stable-project")))
        r1 = memory_dir_for_backend("obsidian")
        r2 = memory_dir_for_backend("obsidian")
        assert r1 == r2


class TestMemoryDirForBackendWiki:
    """wiki backend returns the knowledge root directly — not project-scoped."""

    def test_wiki_returns_knowledge_root_directly(self):
        result = memory_dir_for_backend("wiki")
        expected = Path.home() / "Obsidian" / "agent-notes" / "knowledge"
        assert result == expected

    def test_wiki_ignores_cwd(self, monkeypatch):
        monkeypatch.setattr(Path, "cwd", staticmethod(lambda: Path("/repos/agent-notes")))
        result = memory_dir_for_backend("wiki")
        assert result.name == "knowledge"

    def test_wiki_custom_path_used_directly(self, tmp_path):
        custom = tmp_path / "my" / "vault"
        result = memory_dir_for_backend("wiki", custom_path=str(custom))
        assert result == custom

    def test_wiki_custom_path_tilde_expanded(self):
        result = memory_dir_for_backend("wiki", custom_path="~/knowledge")
        assert "~" not in str(result)
        assert result == Path("~/knowledge").expanduser()

    def test_local_is_not_project_scoped(self, monkeypatch):
        monkeypatch.setattr(Path, "cwd", staticmethod(lambda: Path("/code/my-project")))
        result = memory_dir_for_backend("local")
        assert result == MEMORY_DIR
        assert result.name != "my-project"
