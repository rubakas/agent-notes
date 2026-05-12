"""Tests for agent_notes.services.memory_router dispatch functions."""
import pytest
from pathlib import Path
from unittest.mock import patch, call


# ── Import sanity ──────────────────────────────────────────────────────────────

class TestImports:
    def test_memory_init_importable(self):
        from agent_notes.services.memory_router import memory_init
        assert callable(memory_init)

    def test_memory_regenerate_index_importable(self):
        from agent_notes.services.memory_router import memory_regenerate_index
        assert callable(memory_regenerate_index)


# ── memory_init ───────────────────────────────────────────────────────────────

class TestMemoryInit:
    def test_wiki_backend_calls_wiki_init(self, tmp_path):
        from agent_notes.services.memory_router import memory_init
        with patch("agent_notes.services.wiki_backend.wiki_init") as mock_fn:
            memory_init("wiki", tmp_path)
        mock_fn.assert_called_once_with(tmp_path)

    def test_obsidian_backend_calls_obsidian_init(self, tmp_path):
        from agent_notes.services.memory_router import memory_init
        with patch("agent_notes.services.obsidian_backend.obsidian_init") as mock_fn:
            memory_init("obsidian", tmp_path)
        mock_fn.assert_called_once_with(tmp_path)

    def test_local_backend_calls_local_init(self, tmp_path):
        from agent_notes.services.memory_router import memory_init
        with patch("agent_notes.services.local_backend.local_init") as mock_fn:
            memory_init("local", tmp_path)
        mock_fn.assert_called_once_with(tmp_path)

    def test_none_backend_raises(self, tmp_path):
        from agent_notes.services.memory_router import memory_init
        with pytest.raises(ValueError, match="Unknown memory backend"):
            memory_init("none", tmp_path)

    def test_unknown_backend_raises(self, tmp_path):
        from agent_notes.services.memory_router import memory_init
        with pytest.raises(ValueError, match="Unknown memory backend"):
            memory_init("unknown_backend_xyz", tmp_path)

    def test_none_backend_raises_valueerror(self, tmp_path):
        from agent_notes.services.memory_router import memory_init
        with pytest.raises(ValueError):
            memory_init("none", tmp_path)

    def test_totally_unknown_backend_raises_valueerror(self, tmp_path):
        from agent_notes.services.memory_router import memory_init
        with pytest.raises(ValueError):
            memory_init("totally_unknown", tmp_path)


# ── memory_regenerate_index ───────────────────────────────────────────────────

class TestMemoryRegenerateIndex:
    def test_wiki_backend_calls_wiki_regenerate_index(self, tmp_path):
        from agent_notes.services.memory_router import memory_regenerate_index
        with patch("agent_notes.services.wiki_backend.wiki_regenerate_index") as mock_fn:
            memory_regenerate_index("wiki", tmp_path)
        mock_fn.assert_called_once_with(tmp_path)

    def test_obsidian_backend_calls_obsidian_regenerate_index(self, tmp_path):
        from agent_notes.services.memory_router import memory_regenerate_index
        with patch("agent_notes.services.obsidian_backend.obsidian_regenerate_index") as mock_fn:
            memory_regenerate_index("obsidian", tmp_path)
        mock_fn.assert_called_once_with(tmp_path)

    def test_local_backend_calls_local_regenerate_index(self, tmp_path):
        from agent_notes.services.memory_router import memory_regenerate_index
        with patch("agent_notes.services.local_backend.local_regenerate_index") as mock_fn:
            memory_regenerate_index("local", tmp_path)
        mock_fn.assert_called_once_with(tmp_path)

    def test_none_backend_raises(self, tmp_path):
        from agent_notes.services.memory_router import memory_regenerate_index
        with pytest.raises(ValueError, match="Unknown memory backend"):
            memory_regenerate_index("none", tmp_path)

    def test_unknown_backend_raises(self, tmp_path):
        from agent_notes.services.memory_router import memory_regenerate_index
        with pytest.raises(ValueError, match="Unknown memory backend"):
            memory_regenerate_index("unknown_backend_xyz", tmp_path)

    def test_none_backend_raises_valueerror(self, tmp_path):
        from agent_notes.services.memory_router import memory_regenerate_index
        with pytest.raises(ValueError):
            memory_regenerate_index("none", tmp_path)

    def test_totally_unknown_backend_raises_valueerror(self, tmp_path):
        from agent_notes.services.memory_router import memory_regenerate_index
        with pytest.raises(ValueError):
            memory_regenerate_index("totally_unknown", tmp_path)
