"""Tests for MemoryConfig schema changes: strategy field and none→local migration."""
import json
import pytest

from agent_notes.services.state_store import (
    _state_from_dict,
    _state_to_dict,
    save_state,
    load_state,
)
from agent_notes.domain.state import MemoryConfig, State


class TestMemoryConfigMigration:
    def test_legacy_none_backend_loads_as_local(self):
        """Legacy state JSON with backend='none' must be migrated to 'local' on load."""
        data = {
            "source_path": "",
            "source_commit": "",
            "global": None,
            "local": {},
            "memory": {"backend": "none", "path": ""},
        }
        restored = _state_from_dict(data)
        assert restored.memory.backend == "local"

    def test_fresh_memory_config_has_single_brain_strategy(self):
        """A freshly constructed MemoryConfig must default strategy to 'single-brain'."""
        config = MemoryConfig()
        assert config.strategy == "single-brain"

    def test_obsidian_per_project_strategy_roundtrips(self, monkeypatch, tmp_path):
        """An obsidian config with strategy='per-project' survives save→load intact."""
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
        state = State(
            source_path="",
            source_commit="",
            global_install=None,
            local_installs={},
            memory=MemoryConfig(backend="obsidian", path="/vault", strategy="per-project"),
        )
        save_state(state)
        loaded = load_state()
        assert loaded is not None
        assert loaded.memory.backend == "obsidian"
        assert loaded.memory.path == "/vault"
        assert loaded.memory.strategy == "per-project"
