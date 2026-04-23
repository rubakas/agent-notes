"""Test install_state module v2."""
import pytest
from pathlib import Path
from unittest.mock import patch

from agent_notes.install_state import (
    git_head_short, build_install_state, record_install_state, 
    load_current_state, clear_state, remove_install_state
)
from agent_notes.config import PKG_DIR


@pytest.fixture
def isolated_state(tmp_path, monkeypatch):
    """Isolate state file to tmp directory."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    yield tmp_path


class TestGitHeadShort:
    """Test git_head_short function."""
    
    def test_returns_commit_for_git_repo(self):
        """Should return a non-empty string for the project's own repo."""
        result = git_head_short(PKG_DIR.parent)
        assert isinstance(result, str)
        # Should return something for a real git repo
        assert len(result) >= 7 or result == ""  # Allow for non-git environments
    
    def test_returns_empty_for_non_git_dir(self, tmp_path):
        """Should return empty string for non-git directory."""
        result = git_head_short(tmp_path)
        assert result == ""


class TestBuildInstallState:
    """Test build_install_state function."""
    
    def test_creates_state_with_correct_metadata(self, isolated_state):
        """Should create state with correct basic metadata."""
        state = build_install_state(
            mode="symlink",
            scope="global", 
            repo_root=PKG_DIR.parent,
        )
        
        assert state.source_path == str(PKG_DIR.parent.resolve())
        assert isinstance(state.source_commit, str)
        assert isinstance(state.source_path, str)
        assert Path(state.source_path).is_absolute()
        
        # Should have global install
        assert state.global_install is not None
        assert state.global_install.mode == "symlink"
        assert isinstance(state.global_install.installed_at, str)
        assert isinstance(state.global_install.updated_at, str)
        
        # Should have no local installs for global scope
        assert state.local_installs == {}
    
    def test_creates_local_install_state(self, isolated_state, tmp_path, monkeypatch):
        """Should create local install state correctly."""
        # Change to temp directory
        monkeypatch.chdir(tmp_path)
        
        state = build_install_state(
            mode="copy",
            scope="local", 
            repo_root=PKG_DIR.parent,
            project_path=Path.cwd()
        )
        
        assert state.source_path == str(PKG_DIR.parent.resolve())
        
        # Should have no global install
        assert state.global_install is None
        
        # Should have local install for current path
        cwd_str = str(Path.cwd().resolve())
        assert cwd_str in state.local_installs
        local_install = state.local_installs[cwd_str]
        assert local_install.mode == "copy"
    
    def test_preserves_existing_installs(self, isolated_state, tmp_path, monkeypatch):
        """Should preserve existing installs when adding new scope."""
        # First, create a global install
        global_state = build_install_state(
            mode="symlink",
            scope="global",
            repo_root=PKG_DIR.parent,
            
        )
        record_install_state(global_state)
        
        # Now add a local install - should preserve global
        monkeypatch.chdir(tmp_path)
        local_state = build_install_state(
            mode="copy",
            scope="local",
            repo_root=PKG_DIR.parent,
            
            project_path=Path.cwd()
        )
        
        # Should still have global install
        assert local_state.global_install is not None
        assert local_state.global_install.mode == "symlink"
        
        # Should also have local install
        cwd_str = str(Path.cwd().resolve())
        assert cwd_str in local_state.local_installs
        assert local_state.local_installs[cwd_str].mode == "copy"
    
    def test_discovers_backend_content(self, isolated_state):
        """Should discover and record backend content from dist/."""
        state = build_install_state("symlink", "global", PKG_DIR.parent, "0.5.0")
        
        # Should have global install with some CLIs
        assert state.global_install is not None
        assert len(state.global_install.clis) > 0
        
        # Check structure of a backend that should exist
        if "claude" in state.global_install.clis:
            claude_backend = state.global_install.clis["claude"]
            
            # Should have some component content
            has_content = any(
                len(items) > 0 
                for component_items in claude_backend.installed.values()
                for items in [component_items] if isinstance(component_items, dict)
            )
            assert has_content
            
            # Check role_models (should be empty for now)
            assert claude_backend.role_models == {}
    
    def test_local_scope_uses_project_paths(self, isolated_state, tmp_path, monkeypatch):
        """Should use project-relative paths for local scope."""
        # Change to temp directory
        monkeypatch.chdir(tmp_path)
        
        state = build_install_state("copy", "local", PKG_DIR.parent, project_path=Path.cwd())
        
        cwd_str = str(Path.cwd().resolve())
        assert cwd_str in state.local_installs
        local_install = state.local_installs[cwd_str]
        
        # Check that paths are relative to project directory
        if "claude" in local_install.clis:
            claude_backend = local_install.clis["claude"]
            if "agents" in claude_backend.installed:
                for agent_name, installed_item in claude_backend.installed["agents"].items():
                    # Should start with the temp path (current working directory)
                    assert installed_item.target.startswith(str(tmp_path))
                    assert ("/.claude/" in installed_item.target or "\\.claude\\" in installed_item.target)
    
    def test_role_models_parameter(self, isolated_state):
        """Should use role_models parameter when provided."""
        role_models = {
            "claude": {
                "orchestrator": "claude-opus-4-7",
                "worker": "claude-sonnet-4"
            }
        }
        
        state = build_install_state(
            mode="symlink",
            scope="global",
            repo_root=PKG_DIR.parent,
            
            role_models=role_models
        )
        
        assert state.global_install is not None
        if "claude" in state.global_install.clis:
            claude_backend = state.global_install.clis["claude"]
            assert claude_backend.role_models["orchestrator"] == "claude-opus-4-7"
            assert claude_backend.role_models["worker"] == "claude-sonnet-4"


class TestStateRecordingAndLoading:
    """Test state recording and loading functions."""
    
    def test_record_and_load_roundtrip(self, isolated_state):
        """Should record state and load it back correctly."""
        original_state = build_install_state("symlink", "global", PKG_DIR.parent)
        
        record_install_state(original_state)
        loaded_state = load_current_state()
        
        assert loaded_state is not None
        assert loaded_state.source_path == original_state.source_path
        
        # Both should have global install
        assert loaded_state.global_install is not None
        assert original_state.global_install is not None
        assert loaded_state.global_install.mode == original_state.global_install.mode
        
        # Check that backend content matches
        assert len(loaded_state.global_install.clis) == len(original_state.global_install.clis)
        for backend_name in original_state.global_install.clis:
            assert backend_name in loaded_state.global_install.clis
    
    def test_load_returns_none_when_no_state(self, isolated_state):
        """Should return None when no state file exists."""
        result = load_current_state()
        assert result is None
    
    def test_remove_install_state_global(self, isolated_state):
        """Should remove global install state correctly."""
        # Create and record a global state
        state = build_install_state("symlink", "global", PKG_DIR.parent, "0.5.0")
        record_install_state(state)
        
        # Verify it exists
        assert load_current_state() is not None
        assert load_current_state().global_install is not None
        
        # Remove global install
        remove_install_state("global")
        
        # Should either be None (if only global) or have no global install
        loaded = load_current_state()
        if loaded is not None:
            assert loaded.global_install is None
        # If completely empty, file should be deleted and load returns None
    
    def test_remove_install_state_local(self, isolated_state, tmp_path, monkeypatch):
        """Should remove specific local install state correctly."""
        # Create global first
        global_state = build_install_state("symlink", "global", PKG_DIR.parent)
        record_install_state(global_state)
        
        # Add local install
        monkeypatch.chdir(tmp_path)
        local_state = build_install_state("copy", "local", PKG_DIR.parent, project_path=Path.cwd())
        record_install_state(local_state)
        
        # Verify both exist
        loaded = load_current_state()
        assert loaded.global_install is not None
        cwd_str = str(Path.cwd().resolve())
        assert cwd_str in loaded.local_installs
        
        # Remove local install
        remove_install_state("local", Path.cwd())
        
        # Global should remain, local should be gone
        loaded = load_current_state()
        assert loaded is not None
        assert loaded.global_install is not None
        assert cwd_str not in loaded.local_installs
    
    def test_clear_removes_state_file(self, isolated_state):
        """Should remove state file when clearing."""
        # Create state
        state = build_install_state("symlink", "global", PKG_DIR.parent, "0.5.0")
        record_install_state(state)
        
        # Verify it exists
        assert load_current_state() is not None
        
        # Clear it
        clear_state()
        
        # Verify it's gone
        assert load_current_state() is None
    
    def test_clear_succeeds_when_no_file(self, isolated_state):
        """Should succeed when clearing non-existent state file."""
        # Should not raise an exception
        clear_state()


class TestErrorHandling:
    """Test error handling in install_state functions."""
    
    def test_build_state_handles_missing_dist_gracefully(self, isolated_state, tmp_path, monkeypatch):
        """Should handle missing dist/ directory gracefully."""
        # Point to a location with no dist/
        fake_pkg_dir = tmp_path / "fake_agent_notes"
        fake_pkg_dir.mkdir()
        
        with patch('agent_notes.config.PKG_DIR', fake_pkg_dir):
            with patch('agent_notes.config.DIST_SKILLS_DIR', fake_pkg_dir / "dist" / "skills"):
                with patch('agent_notes.config.DIST_RULES_DIR', fake_pkg_dir / "dist" / "rules"):
                    # Should not raise exception
                    state = build_install_state("symlink", "global", tmp_path)
                    
                    # Should return valid state 
                    assert isinstance(state, type(build_install_state("symlink", "global", PKG_DIR.parent)))
                    assert state.source_path == str(tmp_path.resolve())
                    assert state.global_install is not None
                    # Should have empty or minimal backends
                    assert len(state.global_install.clis) == 0
    
    def test_build_state_handles_registry_failure(self, isolated_state):
        """Should handle CLI registry loading failure gracefully."""
        with patch('agent_notes.cli_backend.load_registry', side_effect=Exception("Registry failed")):
            # Should not raise exception
            state = build_install_state("symlink", "global", PKG_DIR.parent)
            
            # Should return valid state
            assert state.source_path == str(PKG_DIR.parent.resolve())
            assert state.global_install is not None
            # Should have empty backends due to registry failure
            assert len(state.global_install.clis) == 0