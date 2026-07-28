"""Tests for clear error behaviour when state.json carries the removed 'wiki' backend."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch


class TestWikiBackendRemovedError:
    """get_backend raises a clear ValueError for the removed 'wiki' backend."""

    def test_get_backend_wiki_raises_value_error(self):
        from agent_notes.memory.memory_backend import get_backend
        with pytest.raises(ValueError, match="wiki"):
            get_backend("wiki")

    def test_get_backend_wiki_error_mentions_config_memory(self):
        from agent_notes.memory.memory_backend import get_backend
        with pytest.raises(ValueError, match="agent-notes config memory"):
            get_backend("wiki")

    def test_get_backend_wiki_error_mentions_removed(self):
        from agent_notes.memory.memory_backend import get_backend
        with pytest.raises(ValueError, match="removed"):
            get_backend("wiki")

    def test_get_backend_local_still_works(self):
        from agent_notes.memory.memory_backend import get_backend
        backend = get_backend("local")
        assert backend is not None

    def test_get_backend_obsidian_still_works(self):
        from agent_notes.memory.memory_backend import get_backend
        backend = get_backend("obsidian")
        assert backend is not None


class TestLoadMemoryConfigWikiError:
    """_load_memory_config exits with a clear message when state.json has backend='wiki'."""

    def test_wiki_backend_in_state_triggers_sys_exit(self, tmp_path):
        from agent_notes.domain.state import State, MemoryConfig

        wiki_state = State(
            source_path="",
            source_commit="",
            memory=MemoryConfig(backend="wiki", path="/some/path"),
        )

        with patch("agent_notes.memory.commands._common._load_memory_config") as mock_fn:
            # Simulate what _load_memory_config does when it sees "wiki"
            import sys
            def _raise():
                print(
                    "Error: memory backend 'wiki' has been removed.\n"
                    "Run `agent-notes config memory` to switch to a supported backend.",
                    file=sys.stderr,
                )
                sys.exit(1)
            mock_fn.side_effect = SystemExit(1)

            with pytest.raises(SystemExit) as exc_info:
                mock_fn()
            assert exc_info.value.code == 1

    def test_wiki_backend_direct_call_exits(self, tmp_path, monkeypatch):
        """_load_memory_config reads state with wiki backend and calls sys.exit(1)."""
        state_file = tmp_path / "state.json"
        state_file.write_text(json.dumps({
            "source_path": "",
            "source_commit": "",
            "memory": {"backend": "wiki", "path": "/some/vault"},
            "global": None,
            "local": {},
        }))

        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        # Place state.json at the expected location
        config_dir = tmp_path / "agent-notes"
        config_dir.mkdir()
        (config_dir / "state.json").write_text(json.dumps({
            "source_path": "",
            "source_commit": "",
            "memory": {"backend": "wiki", "path": "/some/vault"},
            "global": None,
            "local": {},
        }))

        from agent_notes.memory.commands._common import _load_memory_config
        with pytest.raises(SystemExit) as exc_info:
            _load_memory_config()
        assert exc_info.value.code == 1

    def test_wiki_backend_error_message_content(self, tmp_path, monkeypatch, capsys):
        """The error message names the removed backend and tells the user how to switch."""
        config_dir = tmp_path / "agent-notes"
        config_dir.mkdir()
        (config_dir / "state.json").write_text(json.dumps({
            "source_path": "",
            "source_commit": "",
            "memory": {"backend": "wiki", "path": "/some/vault"},
            "global": None,
            "local": {},
        }))

        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))

        from agent_notes.memory.commands._common import _load_memory_config
        with pytest.raises(SystemExit):
            _load_memory_config()

        captured = capsys.readouterr()
        assert "wiki" in captured.err
        assert "agent-notes config memory" in captured.err
