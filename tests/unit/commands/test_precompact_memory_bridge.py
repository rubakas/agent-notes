"""Unit tests for the PreCompact memory-bridge hook.

Tests the _precompact_memory_bridge handler (via hook(subaction)) and the
shared _load_memory_index renderer that both SessionStart and PreCompact use.
"""
import json
import sys
from io import StringIO
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from agent_notes.commands.hook import _load_memory_index, _precompact_memory_bridge, hook


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _capture_stdout(fn, *args, **kwargs):
    """Run fn(*args, **kwargs) and return whatever it printed to stdout."""
    buf = StringIO()
    with patch("sys.stdout", buf):
        fn(*args, **kwargs)
    return buf.getvalue()


# _load_memory_config is imported lazily inside _load_memory_index; patch it
# at the source module so the local import picks up the mock.
_MEMORY_CONFIG_PATH = "agent_notes.commands.memory._common._load_memory_config"


# ---------------------------------------------------------------------------
# _load_memory_index — shared renderer
# ---------------------------------------------------------------------------

class TestLoadMemoryIndex:
    def test_returns_content_for_obsidian_backend(self, tmp_path):
        index = tmp_path / "Index.md"
        index.write_text("# Memory\n- note A\n")

        with patch(_MEMORY_CONFIG_PATH, return_value=("obsidian", str(tmp_path))):
            result = _load_memory_index()

        assert result == "# Memory\n- note A\n"

    def test_returns_none_for_none_backend(self, tmp_path):
        with patch(_MEMORY_CONFIG_PATH, return_value=("none", str(tmp_path))):
            result = _load_memory_index()

        assert result is None

    def test_returns_none_when_backend_is_none(self, tmp_path):
        with patch(_MEMORY_CONFIG_PATH, return_value=(None, str(tmp_path))):
            result = _load_memory_index()

        assert result is None

    def test_returns_none_when_index_missing(self, tmp_path):
        with patch(_MEMORY_CONFIG_PATH, return_value=("obsidian", str(tmp_path))):
            result = _load_memory_index()

        assert result is None

    def test_returns_none_on_exception(self):
        with patch(_MEMORY_CONFIG_PATH, side_effect=Exception("unexpected")):
            result = _load_memory_index()

        assert result is None

    def test_local_backend_uses_index_md(self, tmp_path):
        (tmp_path / "Index.md").write_text("local index\n")

        with patch(_MEMORY_CONFIG_PATH, return_value=("local", str(tmp_path))):
            result = _load_memory_index()

        assert result == "local index\n"


# ---------------------------------------------------------------------------
# _precompact_memory_bridge — PreCompact hook output contract
# ---------------------------------------------------------------------------

class TestPrecompactMemoryBridge:
    def test_emits_json_with_additional_context(self, tmp_path):
        with patch("agent_notes.commands.hook._load_memory_index",
                   return_value="# Memory\n- note A\n"):
            output = _capture_stdout(_precompact_memory_bridge)

        data = json.loads(output.strip())
        assert "additionalContext" in data

    def test_additional_context_contains_memory_content(self):
        with patch("agent_notes.commands.hook._load_memory_index",
                   return_value="- memory line 1\n- memory line 2\n"):
            output = _capture_stdout(_precompact_memory_bridge)

        data = json.loads(output.strip())
        assert "- memory line 1" in data["additionalContext"]
        assert "- memory line 2" in data["additionalContext"]

    def test_additional_context_contains_header(self):
        with patch("agent_notes.commands.hook._load_memory_index",
                   return_value="content\n"):
            output = _capture_stdout(_precompact_memory_bridge)

        data = json.loads(output.strip())
        assert "agent-notes memory index" in data["additionalContext"]

    def test_empty_memory_emits_nothing(self):
        with patch("agent_notes.commands.hook._load_memory_index", return_value=None):
            output = _capture_stdout(_precompact_memory_bridge)

        assert output.strip() == ""

    def test_output_is_valid_json(self):
        with patch("agent_notes.commands.hook._load_memory_index",
                   return_value="some memory\n"):
            output = _capture_stdout(_precompact_memory_bridge)

        data = json.loads(output.strip())
        assert isinstance(data, dict)

    def test_output_has_only_additional_context_key(self):
        with patch("agent_notes.commands.hook._load_memory_index",
                   return_value="x\n"):
            output = _capture_stdout(_precompact_memory_bridge)

        data = json.loads(output.strip())
        assert set(data.keys()) == {"additionalContext"}

    def test_dispatched_via_hook_subaction(self):
        with patch("agent_notes.commands.hook._load_memory_index",
                   return_value="dispatched\n"):
            output = _capture_stdout(hook, "precompact-memory-bridge")

        data = json.loads(output.strip())
        assert "dispatched" in data["additionalContext"]


# ---------------------------------------------------------------------------
# Shared renderer: SessionStart and PreCompact use same code path
# ---------------------------------------------------------------------------

class TestSharedRendererCodePath:
    """Verify both hooks call _load_memory_index (the single renderer)."""

    def test_memory_bridge_uses_load_memory_index(self):
        calls = []

        def fake_load():
            calls.append(True)
            return "shared\n"

        with patch("agent_notes.commands.hook._load_memory_index", side_effect=fake_load):
            from agent_notes.commands.hook import _memory_bridge
            _capture_stdout(_memory_bridge)

        assert len(calls) == 1

    def test_precompact_memory_bridge_uses_load_memory_index(self):
        calls = []

        def fake_load():
            calls.append(True)
            return "shared\n"

        with patch("agent_notes.commands.hook._load_memory_index", side_effect=fake_load):
            _capture_stdout(_precompact_memory_bridge)

        assert len(calls) == 1
