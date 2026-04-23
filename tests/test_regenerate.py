"""Test regenerate module."""
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
import tempfile
import yaml

import agent_notes.regenerate as regenerate_mod


class TestRegenerate:
    """Test regenerate command."""
    
    def test_regenerate_rebuilds_from_state(self, tmp_path, monkeypatch):
        """Should regenerate files from current state.json."""
        # Mock state_file 
        state_file_path = tmp_path / "state.json"
        monkeypatch.setattr("agent_notes.state.state_file", lambda: state_file_path)
        
        # Create mock state
        from agent_notes.state import State, ScopeState, BackendState
        state = State(
            global_install=ScopeState(
                mode="symlink",
                clis={
                    "claude": BackendState(
                        role_models={"worker": "claude-sonnet-4"},
                        installed={}
                    )
                }
            )
        )
        
        # Create the agents directory and file
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir(parents=True, exist_ok=True)
        agents_yaml_file = agents_dir / "agents.yaml"
        
        # Mock agents.yaml content
        agents_yaml_content = """
        agents:
          test-agent:
            role: worker
            description: Test agent
        """
        agents_yaml_file.write_text(agents_yaml_content)
        
        # Mock CLI registry
        mock_cli_registry = MagicMock()
        mock_backend = MagicMock()
        mock_backend.label = "Claude Code"
        mock_backend.supports.return_value = True
        mock_cli_registry.get.return_value = mock_backend
        
        # Mock generate_agent_files
        mock_generated_files = [Path("/dist/claude/agents/test-agent.md")]
        mock_generate = MagicMock(return_value=mock_generated_files)
        
        # Mock install_state functions
        mock_build_state = MagicMock()
        mock_build_state.global_install = state.global_install
        mock_record = MagicMock()
        
        with patch('agent_notes.state.load', return_value=state), \
             patch('agent_notes.config.DATA_DIR', tmp_path), \
             patch('agent_notes.cli_backend.load_registry', return_value=mock_cli_registry), \
             patch('agent_notes.build.generate_agent_files', mock_generate), \
             patch('agent_notes.install_state.build_install_state', return_value=mock_build_state), \
             patch('agent_notes.install_state.record_install_state', mock_record):
            
            regenerate_mod.regenerate()
            
            # Should call generate_agent_files with state
            mock_generate.assert_called_once()
            args, kwargs = mock_generate.call_args
            assert kwargs['state'] == state
            assert kwargs['scope'] == 'global'
            assert kwargs['project_path'] is None
            
            # Should update state
            mock_record.assert_called_once_with(state)
    
    def test_regenerate_single_cli(self, tmp_path, monkeypatch):
        """Should regenerate only specified CLI."""
        # Mock state_file
        state_file_path = tmp_path / "state.json"
        monkeypatch.setattr("agent_notes.state.state_file", lambda: state_file_path)
        
        # Create mock state with multiple CLIs
        from agent_notes.state import State, ScopeState, BackendState
        state = State(
            global_install=ScopeState(
                mode="symlink",
                clis={
                    "claude": BackendState(role_models={}, installed={}),
                    "opencode": BackendState(role_models={}, installed={})
                }
            )
        )
        
        # Create the agents directory and file
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir(parents=True, exist_ok=True)
        agents_yaml_file = agents_dir / "agents.yaml"
        
        # Mock agents.yaml content
        agents_yaml_content = """
        agents:
          test-agent:
            role: worker
        """
        agents_yaml_file.write_text(agents_yaml_content)
        
        # Mock registries
        mock_cli_registry = MagicMock()
        mock_backend = MagicMock()
        mock_backend.label = "Claude Code"
        mock_backend.supports.return_value = True
        mock_cli_registry.get.return_value = mock_backend
        
        mock_generate = MagicMock(return_value=[])
        
        with patch('agent_notes.state.load', return_value=state), \
             patch('agent_notes.config.DATA_DIR', tmp_path), \
             patch('agent_notes.cli_backend.load_registry', return_value=mock_cli_registry), \
             patch('agent_notes.build.generate_agent_files', mock_generate), \
             patch('agent_notes.install_state.build_install_state'), \
             patch('agent_notes.install_state.record_install_state'):
            
            regenerate_mod.regenerate(cli="claude")
            
            # Should only regenerate claude
            mock_cli_registry.get.assert_called_with("claude")
    
    def test_regenerate_errors_if_no_state(self, tmp_path, monkeypatch, capsys):
        """Should error if no state.json exists.""" 
        # Mock state_file
        state_file_path = tmp_path / "state.json"
        monkeypatch.setattr("agent_notes.state.state_file", lambda: state_file_path)
        
        with patch('agent_notes.state.load', return_value=None), \
             pytest.raises(SystemExit):
            
            regenerate_mod.regenerate()
        
        captured = capsys.readouterr()
        assert "No state.json found. Nothing to regenerate." in captured.out
    
    def test_regenerate_auto_detects_scope(self, tmp_path, monkeypatch):
        """Should auto-detect scope when not specified."""
        # Mock state_file
        state_file_path = tmp_path / "state.json"
        monkeypatch.setattr("agent_notes.state.state_file", lambda: state_file_path)
        
        # Create mock state with only global install
        from agent_notes.state import State, ScopeState, BackendState
        state = State(
            global_install=ScopeState(
                mode="symlink",
                clis={
                    "claude": BackendState(role_models={}, installed={})
                }
            )
        )
        
        # Create the agents directory and file
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir(parents=True, exist_ok=True)
        agents_yaml_file = agents_dir / "agents.yaml"
        agents_yaml_file.write_text("agents: {}")
        
        mock_cli_registry = MagicMock()
        mock_backend = MagicMock()
        mock_backend.label = "Claude Code"
        mock_backend.supports.return_value = True
        mock_cli_registry.get.return_value = mock_backend
        
        mock_generate = MagicMock(return_value=[])
        
        with patch('agent_notes.state.load', return_value=state), \
             patch('agent_notes.config.DATA_DIR', tmp_path), \
             patch('agent_notes.cli_backend.load_registry', return_value=mock_cli_registry), \
             patch('agent_notes.build.generate_agent_files', mock_generate), \
             patch('agent_notes.install_state.build_install_state'), \
             patch('agent_notes.install_state.record_install_state'):
            
            regenerate_mod.regenerate()  # no scope specified
            
            # Should detect global scope
            args, kwargs = mock_generate.call_args
            assert kwargs['scope'] == 'global'
    
    def test_regenerate_local_scope(self, tmp_path, monkeypatch):
        """Should regenerate local scope when --local flag used."""
        # Mock state_file
        state_file_path = tmp_path / "state.json"
        monkeypatch.setattr("agent_notes.state.state_file", lambda: state_file_path)
        
        # Create mock state with local install
        from agent_notes.state import State, ScopeState, BackendState
        project_path = Path.cwd()
        state = State(
            local_installs={
                str(project_path): ScopeState(
                    mode="symlink",
                    clis={
                        "claude": BackendState(role_models={}, installed={})
                    }
                )
            }
        )
        
        # Create the agents directory and file
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir(parents=True, exist_ok=True)
        agents_yaml_file = agents_dir / "agents.yaml"
        agents_yaml_file.write_text("agents: {}")
        
        mock_cli_registry = MagicMock()
        mock_backend = MagicMock()
        mock_backend.label = "Claude Code"
        mock_backend.supports.return_value = True
        mock_cli_registry.get.return_value = mock_backend
        
        mock_generate = MagicMock(return_value=[])
        
        with patch('agent_notes.state.load', return_value=state), \
             patch('agent_notes.config.DATA_DIR', tmp_path), \
             patch('agent_notes.cli_backend.load_registry', return_value=mock_cli_registry), \
             patch('agent_notes.build.generate_agent_files', mock_generate), \
             patch('agent_notes.install_state.build_install_state'), \
             patch('agent_notes.install_state.record_install_state'):
            
            regenerate_mod.regenerate(local=True)
            
            # Should use local scope
            args, kwargs = mock_generate.call_args
            assert kwargs['scope'] == 'local'
            assert kwargs['project_path'] == project_path