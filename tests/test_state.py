"""Test state module v2."""

import pytest
import json
import os
from pathlib import Path
from datetime import datetime
from unittest.mock import patch

from agent_notes.state import (
    state_dir, state_file, load, save, clear, sha256_of, now_iso,
    State, ScopeState, BackendState, InstalledItem,
    get_scope, set_scope, remove_scope
)


class TestStatePaths:
    """Test state path functions."""
    
    def test_state_dir_with_xdg_config_home(self, monkeypatch, tmp_path):
        """Test state_dir() honors $XDG_CONFIG_HOME."""
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        
        expected = tmp_path / "agent-notes"
        assert state_dir() == expected
    
    def test_state_dir_without_xdg_config_home(self, monkeypatch):
        """Test state_dir() falls back to ~/.config/agent-notes when env var unset."""
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        
        expected = Path.home() / ".config" / "agent-notes"
        assert state_dir() == expected
    
    def test_state_file(self, monkeypatch, tmp_path):
        """Test state_file() returns correct path."""
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        
        expected = tmp_path / "agent-notes" / "state.json"
        assert state_file() == expected


class TestLoadSave:
    """Test load/save functionality."""
    
    def test_load_nonexistent_file(self, monkeypatch, tmp_path):
        """Test load() returns None when file does not exist."""
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        
        result = load()
        assert result is None
    
    def test_save_creates_directory(self, monkeypatch, tmp_path):
        """Test save() creates parent directory."""
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        
        state = State()
        save(state)
        
        # Directory should be created
        assert (tmp_path / "agent-notes").exists()
        assert (tmp_path / "agent-notes" / "state.json").exists()
    
    def test_save_writes_valid_json(self, monkeypatch, tmp_path):
        """Test save() writes a valid JSON file."""
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        
        state = State()
        save(state)
        
        file_path = tmp_path / "agent-notes" / "state.json"
        data = json.loads(file_path.read_text())
        

        assert "source_path" in data
        assert "source_commit" in data
        assert data["global"] is None  # No global install
        assert data["local"] == {}     # No local installs
    
    def test_round_trip_basic_state(self, monkeypatch, tmp_path):
        """Test save then load returns equivalent State."""
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        
        original = State(
            source_commit="abc123",
            source_path="/path/to/repo"
        )
        
        save(original)
        loaded = load()
        
        assert loaded is not None

        assert loaded.source_commit == original.source_commit
        assert loaded.source_commit == original.source_commit
        assert loaded.source_path == original.source_path
        assert loaded.global_install is None
        assert loaded.local_installs == {}
    
    def test_round_trip_with_global_install(self, monkeypatch, tmp_path):
        """Test a State with global install round-trips correctly."""
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        
        # Create state with global install
        installed_item = InstalledItem(
            sha="abc123def456",
            target="/home/user/.claude/agents/lead.md",
            mode="symlink"
        )
        
        backend_state = BackendState(
            role_models={"orchestrator": "claude-opus-4-7", "worker": "claude-sonnet-4"},
            installed={"agents": {"lead.md": installed_item}}
        )
        
        global_install = ScopeState(
            installed_at="2026-04-22T13:05:00Z",
            updated_at="2026-04-22T13:05:00Z",
            mode="symlink",
            clis={"claude": backend_state}
        )
        
        original = State(
            
            global_install=global_install
        )
        
        save(original)
        loaded = load()
        
        assert loaded is not None
        assert loaded.global_install is not None
        assert "claude" in loaded.global_install.clis
        assert "lead.md" in loaded.global_install.clis["claude"].installed["agents"]
        
        loaded_item = loaded.global_install.clis["claude"].installed["agents"]["lead.md"]
        assert loaded_item.sha == "abc123def456"
        assert loaded_item.target == "/home/user/.claude/agents/lead.md"
        assert loaded_item.mode == "symlink"
        
        # Check role_models
        assert loaded.global_install.clis["claude"].role_models["orchestrator"] == "claude-opus-4-7"
        assert loaded.global_install.clis["claude"].role_models["worker"] == "claude-sonnet-4"
    
    def test_round_trip_with_local_installs(self, monkeypatch, tmp_path):
        """Test a State with local installs round-trips correctly."""
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        
        # Create state with local install
        installed_item = InstalledItem(
            sha="def456abc123",
            target="/project/.claude/agents/coder.md",
            mode="copy"
        )
        
        backend_state = BackendState(
            role_models={"worker": "claude-sonnet-4"},
            installed={"agents": {"coder.md": installed_item}}
        )
        
        local_install = ScopeState(
            installed_at="2026-04-22T14:00:00Z",
            updated_at="2026-04-22T14:00:00Z",
            mode="copy",
            clis={"claude": backend_state}
        )
        
        original = State(
            
            local_installs={"/path/to/project": local_install}
        )
        
        save(original)
        loaded = load()
        
        assert loaded is not None
        assert "/path/to/project" in loaded.local_installs
        local = loaded.local_installs["/path/to/project"]
        assert local.mode == "copy"
        assert "claude" in local.clis
        assert "coder.md" in local.clis["claude"].installed["agents"]
        
        loaded_item = local.clis["claude"].installed["agents"]["coder.md"]
        assert loaded_item.sha == "def456abc123"
        assert loaded_item.mode == "copy"
    
    def test_save_updates_timestamps(self, monkeypatch, tmp_path):
        """Test save() updates updated_at on all scopes."""
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        
        global_install = ScopeState(
            installed_at="2026-04-22T13:05:00Z",
            updated_at="2026-04-22T13:05:00Z",
            mode="symlink"
        )
        
        local_install = ScopeState(
            installed_at="2026-04-22T14:00:00Z",
            updated_at="2026-04-22T14:00:00Z",
            mode="copy"
        )
        
        state = State(
            
            global_install=global_install,
            local_installs={"/project": local_install}
        )
        
        # Mock time to get consistent result
        with patch('agent_notes.services.state_store.now_iso', return_value="2026-04-22T15:00:00Z"):
            save(state)
        
        # Both scopes should have updated timestamps
        assert state.global_install.updated_at == "2026-04-22T15:00:00Z"
        assert state.local_installs["/project"].updated_at == "2026-04-22T15:00:00Z"
    
    def test_save_is_atomic(self, monkeypatch, tmp_path):
        """Test save is atomic — no .tmp file remains after save()."""
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        
        state = State()
        save(state)
        
        # No .tmp files should remain
        state_dir_path = tmp_path / "agent-notes"
        tmp_files = list(state_dir_path.glob("*.tmp"))
        assert len(tmp_files) == 0
    

class TestClear:
    """Test clear functionality."""
    
    def test_clear_removes_file(self, monkeypatch, tmp_path):
        """Test clear() removes the file."""
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        
        # Create a state file
        state = State()
        save(state)
        
        file_path = tmp_path / "agent-notes" / "state.json"
        assert file_path.exists()
        
        # Clear it
        clear()
        assert not file_path.exists()
    
    def test_clear_no_error_when_absent(self, monkeypatch, tmp_path):
        """Test clear() is a no-op when file doesn't exist."""
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        
        # Should not raise an error
        clear()


class TestScopeHelpers:
    """Test scope helper functions."""
    
    def test_get_scope_global(self):
        """Test get_scope for global scope."""
        global_install = ScopeState(mode="symlink")
        state = State(global_install=global_install)
        
        result = get_scope(state, "global")
        assert result is global_install
    
    def test_get_scope_local(self):
        """Test get_scope for local scope."""
        local_install = ScopeState(mode="copy")
        state = State(local_installs={"/project": local_install})
        
        result = get_scope(state, "local", Path("/project"))
        assert result is local_install
    
    def test_get_scope_local_missing_path(self):
        """Test get_scope raises error for local without path."""
        state = State()
        
        with pytest.raises(ValueError, match="project_path required"):
            get_scope(state, "local")
    
    def test_get_scope_nonexistent(self):
        """Test get_scope returns None for nonexistent scope."""
        state = State()
        
        result = get_scope(state, "global")
        assert result is None
        
        result = get_scope(state, "local", Path("/nonexistent"))
        assert result is None
    
    def test_set_scope_global(self):
        """Test set_scope for global scope."""
        state = State()
        scope_state = ScopeState(mode="symlink")
        
        set_scope(state, "global", scope_state)
        assert state.global_install is scope_state
    
    def test_set_scope_local(self):
        """Test set_scope for local scope."""
        state = State()
        scope_state = ScopeState(mode="copy")
        project_path = Path("/project")
        
        set_scope(state, "local", scope_state, project_path)
        assert str(project_path.resolve()) in state.local_installs
        assert state.local_installs[str(project_path.resolve())] is scope_state
    
    def test_remove_scope_global(self):
        """Test remove_scope for global scope."""
        global_install = ScopeState(mode="symlink")
        state = State(global_install=global_install)
        
        remove_scope(state, "global")
        assert state.global_install is None
    
    def test_remove_scope_local(self):
        """Test remove_scope for local scope."""
        local_install = ScopeState(mode="copy")
        project_path = Path("/project")
        state = State(local_installs={str(project_path.resolve()): local_install})
        
        remove_scope(state, "local", project_path)
        assert str(project_path.resolve()) not in state.local_installs


class TestUtilities:
    """Test utility functions."""
    
    def test_sha256_of_stable(self, tmp_path):
        """Test sha256_of() returns stable digest for same content."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello, world!")
        
        hash1 = sha256_of(test_file)
        hash2 = sha256_of(test_file)
        
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 hex digest length
        assert isinstance(hash1, str)
    
    def test_sha256_of_different_content(self, tmp_path):
        """Test sha256_of() returns different hashes for different content."""
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        
        file1.write_text("Content 1")
        file2.write_text("Content 2")
        
        hash1 = sha256_of(file1)
        hash2 = sha256_of(file2)
        
        assert hash1 != hash2
    
    def test_now_iso_format(self):
        """Test now_iso() returns correct format."""
        timestamp = now_iso()
        
        # Should end with Z
        assert timestamp.endswith("Z")
        
        # Should be parseable as ISO format
        # Remove Z and parse
        dt_str = timestamp[:-1] + "+00:00"
        parsed = datetime.fromisoformat(dt_str)
        assert parsed is not None
        
        # Should be recent (within last minute)
        import datetime as dt_module
        now = datetime.now(dt_module.timezone.utc)
        assert abs((now - parsed).total_seconds()) < 60


class TestComplexScenarios:
    """Test complex state scenarios."""
    
    def test_empty_state_round_trip(self, monkeypatch, tmp_path):
        """Test empty state saves and loads correctly."""
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        
        state = State()
        save(state)
        loaded = load()
        
        assert loaded is not None

        assert loaded.global_install is None
        assert loaded.local_installs == {}
    
    def test_multiple_local_installs(self, monkeypatch, tmp_path):
        """Test state with multiple local installs."""
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        
        # Create multiple local installs
        local1 = ScopeState(mode="symlink")
        local2 = ScopeState(mode="copy")
        
        state = State(
            
            local_installs={
                "/project1": local1,
                "/project2": local2
            }
        )
        
        save(state)
        loaded = load()
        
        assert loaded is not None
        assert len(loaded.local_installs) == 2
        assert "/project1" in loaded.local_installs
        assert "/project2" in loaded.local_installs
        assert loaded.local_installs["/project1"].mode == "symlink"
        assert loaded.local_installs["/project2"].mode == "copy"
    
    def test_global_and_local_together(self, monkeypatch, tmp_path):
        """Test state with both global and local installs."""
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        
        global_install = ScopeState(mode="symlink")
        local_install = ScopeState(mode="copy")
        
        state = State(
            
            global_install=global_install,
            local_installs={"/project": local_install}
        )
        
        save(state)
        loaded = load()
        
        assert loaded is not None
        assert loaded.global_install is not None
        assert loaded.global_install.mode == "symlink"
        assert len(loaded.local_installs) == 1
        assert loaded.local_installs["/project"].mode == "copy"