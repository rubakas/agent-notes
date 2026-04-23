"""Test the new targeted doctor_checks functionality."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
import tempfile
import json

from agent_notes import doctor_checks
from agent_notes.cli_backend import CLIBackend, CLIRegistry
from agent_notes.state import State, ScopeState, BackendState, InstalledItem


@pytest.fixture
def mock_registry():
    """Create a mock CLI registry with test backends."""
    claude_backend = MagicMock(spec=CLIBackend)
    claude_backend.name = "claude"
    claude_backend.label = "Claude Code"
    claude_backend.supports.return_value = True
    claude_backend.global_home = Path("/tmp/test/.claude")
    claude_backend.local_dir = ".claude"
    claude_backend.layout = {
        "agents": "agents/",
        "skills": "skills/", 
        "config": "CLAUDE.md"
    }
    
    opencode_backend = MagicMock(spec=CLIBackend)
    opencode_backend.name = "opencode"
    opencode_backend.label = "OpenCode"
    opencode_backend.supports.return_value = True
    opencode_backend.global_home = Path("/tmp/test/.config/opencode")
    opencode_backend.local_dir = ".opencode"
    opencode_backend.layout = {
        "agents": "agents/",
        "skills": "skills/",
        "config": "AGENTS.md"
    }
    
    return CLIRegistry([claude_backend, opencode_backend])


@pytest.fixture
def mock_state():
    """Create a mock state with some installed items."""
    backend_state = BackendState()
    backend_state.agents = {
        "test-agent.md": InstalledItem(
            sha="abc123", 
            target="/tmp/test/.claude/agents/test-agent.md",
            mode="symlink"
        )
    }
    
    state = State()
    state.mode = "symlink"
    state.scope = "global"
    state.installed = {"claude": backend_state}
    return state


def test_expected_paths_for_install(mock_registry, tmp_path):
    """Test expected_paths_for_install returns correct paths."""
    # Create mock dist structure
    dist_dir = tmp_path / "dist"
    
    # Create claude agents
    claude_agents = dist_dir / "claude" / "agents"
    claude_agents.mkdir(parents=True)
    (claude_agents / "test-agent.md").write_text("test content")
    
    # Create claude config
    claude_dir = dist_dir / "claude"
    (claude_dir / "CLAUDE.md").write_text("claude config")
    
    # Mock installer functions
    with patch('agent_notes.doctor_checks.installer.dist_source_for') as mock_dist, \
         patch('agent_notes.doctor_checks.installer.target_dir_for') as mock_target, \
         patch('agent_notes.doctor_checks.installer.config_filename_for') as mock_config_name:
        
        def mock_dist_source(backend, component):
            if backend.name == "claude" and component == "agents":
                return claude_agents if claude_agents.exists() else None
            elif backend.name == "claude" and component == "config":
                return claude_dir if claude_dir.exists() else None
            return None
        
        def mock_target_dir(backend, component, scope):
            if backend.name == "claude":
                if component == "agents":
                    return Path("/tmp/test/.claude/agents")
                elif component == "config":
                    return Path("/tmp/test/.claude")
            return None
        
        def mock_config_filename(backend):
            if backend.name == "claude":
                return "CLAUDE.md"
            return None
        
        mock_dist.side_effect = mock_dist_source
        mock_target.side_effect = mock_target_dir
        mock_config_name.side_effect = mock_config_filename
        
        paths = doctor_checks.expected_paths_for_install(mock_registry, "global")
        
        # Should find the agent file and config file
        assert len(paths) >= 2
        
        # Find agent entry
        agent_paths = [p for p in paths if p[3] == "agents"]
        assert len(agent_paths) == 1
        assert agent_paths[0][0].name == "test-agent.md"
        assert str(agent_paths[0][1]) == "/tmp/test/.claude/agents/test-agent.md"
        
        # Find config entry  
        config_paths = [p for p in paths if p[3] == "config"]
        assert len(config_paths) == 1
        assert config_paths[0][0].name == "CLAUDE.md"
        assert str(config_paths[0][1]) == "/tmp/test/.claude/CLAUDE.md"


def test_check_missing_finds_missing_files(mock_registry, tmp_path):
    """Test check_missing identifies files that should be installed but aren't."""
    issues = []
    fix_actions = []
    
    # Mock expected_paths_for_install to return a missing file
    with patch('agent_notes.doctor_checks.expected_paths_for_install') as mock_expected:
        mock_expected.return_value = [
            (tmp_path / "src.md", Path("/nonexistent/target.md"), "claude", "agents")
        ]
        
        doctor_checks.check_missing("global", mock_registry, issues, fix_actions)
        
        assert len(issues) == 1
        assert issues[0].type == "missing"
        assert "/nonexistent/target.md" in issues[0].file
        assert len(fix_actions) == 1
        assert fix_actions[0].action == "INSTALL"


def test_check_stale_identifies_removed_backend(mock_registry):
    """Test check_stale identifies files from removed backends."""
    issues = []
    fix_actions = []

    # Create scope state with a backend that's no longer in registry
    backend_state = BackendState()
    backend_state.installed["agents"] = {
        "old-agent.md": InstalledItem(
            sha="abc123",
            target="/tmp/old-agent.md",
            mode="symlink"
        )
    }

    scope_state = ScopeState()
    scope_state.clis = {"removed_backend": backend_state}

    doctor_checks.check_stale("global", scope_state, mock_registry, issues, fix_actions)

    # Should identify that the entire backend is stale
    assert len(issues) == 1
    assert issues[0].type == "stale"
    assert "removed_backend" in issues[0].message
    assert len(fix_actions) == 1
    assert fix_actions[0].action == "DELETE"


def test_check_broken_finds_broken_symlinks(mock_registry):
    """Test check_broken identifies broken symlinks in expected paths."""
    issues = []
    fix_actions = []
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        
        # Create a broken symlink
        broken_link = tmp_path / "broken.md"
        broken_link.symlink_to("/nonexistent/target")
        
        # Mock expected_paths_for_install to return the broken symlink path
        with patch('agent_notes.doctor_checks.expected_paths_for_install') as mock_expected:
            mock_expected.return_value = [
                (tmp_path / "src.md", broken_link, "claude", "agents")
            ]
            
            doctor_checks.check_broken("global", mock_registry, issues, fix_actions, None)
            
            assert len(issues) == 1
            assert issues[0].type == "broken"
            assert str(broken_link) in issues[0].file
            assert len(fix_actions) == 1
            assert fix_actions[0].action == "RELINK"


def test_check_drift_only_works_in_copy_mode(mock_registry):
    """Test check_drift only reports issues when mode=copy."""
    issues = []
    fix_actions = []
    
    # Test with symlink mode - should not report drift
    scope_state = ScopeState()
    scope_state.mode = "symlink"
    
    doctor_checks.check_drift("global", mock_registry, issues, fix_actions, scope_state)
    assert len(issues) == 0
    
    # Test with copy mode - would report drift if files differed
    scope_state.mode = "copy"
    doctor_checks.check_drift("global", mock_registry, issues, fix_actions, scope_state)
    # Still 0 because we don't have any installed items in the mock state
    assert len(issues) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])