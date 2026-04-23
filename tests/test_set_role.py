"""Test set_role module."""
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import tempfile

import agent_notes.set_role as set_role_mod


class TestSetRole:
    """Test set_role command."""
    
    def test_set_role_updates_state_and_regenerates(self, tmp_path, monkeypatch):
        """Should update state.json and call regenerate."""
        # Mock state_file to use tmp path
        state_file_path = tmp_path / "state.json"
        monkeypatch.setattr("agent_notes.state.state_file", lambda: state_file_path)
        
        # Create mock state with a CLI and role
        from agent_notes.state import State, ScopeState, BackendState
        state = State(
            source_path="/test", 
            source_commit="abc123",
            global_install=ScopeState(
                installed_at="2026-04-22T13:05:00Z",
                updated_at="2026-04-22T13:05:00Z",
                mode="symlink",
                clis={
                    "claude": BackendState(
                        role_models={"worker": "claude-sonnet-4"},
                        installed={}
                    )
                }
            )
        )
        
        # Mock registries
        mock_role_registry = MagicMock()
        mock_role_registry.get.return_value = MagicMock(name="worker")
        
        mock_model_registry = MagicMock()
        mock_model = MagicMock()
        mock_model.aliases = {"anthropic": "claude-opus-4-7"}
        mock_model_registry.get.return_value = mock_model
        mock_model_registry.ids.return_value = ["claude-opus-4-7"]
        
        mock_cli_registry = MagicMock()
        mock_backend = MagicMock()
        mock_backend.label = "Claude Code"
        mock_backend.accepted_providers = ["anthropic"]
        mock_backend.first_alias_for.return_value = "claude-opus-4-7"
        mock_cli_registry.get.return_value = mock_backend
        
        # Mock regenerate
        mock_regenerate = MagicMock()
        
        with patch('agent_notes.state.load', return_value=state), \
             patch('agent_notes.role_registry.load_role_registry', return_value=mock_role_registry), \
             patch('agent_notes.model_registry.load_model_registry', return_value=mock_model_registry), \
             patch('agent_notes.cli_backend.load_registry', return_value=mock_cli_registry), \
             patch('agent_notes.install_state.record_install_state') as mock_record, \
             patch('agent_notes.regenerate.regenerate', mock_regenerate):
            
            set_role_mod.set_role("worker", "claude-opus-4-7", cli="claude", scope="global")
            
            # Should update state
            assert state.global_install.clis["claude"].role_models["worker"] == "claude-opus-4-7"
            mock_record.assert_called_once_with(state)
            
            # Should call regenerate
            mock_regenerate.assert_called_once_with(scope="global", cli="claude", project_path=None)
    
    def test_set_role_validates_role_name(self, tmp_path, monkeypatch, capsys):
        """Should error on unknown role name."""
        # Mock state_file
        state_file_path = tmp_path / "state.json"
        monkeypatch.setattr("agent_notes.state.state_file", lambda: state_file_path)
        
        # Create mock state
        from agent_notes.state import State, ScopeState
        state = State(global_install=ScopeState())
        
        # Mock role registry with KeyError
        mock_role_registry = MagicMock()
        mock_role_registry.get.side_effect = KeyError("unknown")
        mock_role_registry.names.return_value = ["worker", "orchestrator"]
        
        with patch('agent_notes.state.load', return_value=state), \
             patch('agent_notes.role_registry.load_role_registry', return_value=mock_role_registry), \
             pytest.raises(SystemExit):
            
            set_role_mod.set_role("unknown-role", "some-model")
        
        captured = capsys.readouterr()
        assert "Unknown role: unknown-role" in captured.out
        assert "Available roles: worker, orchestrator" in captured.out
    
    def test_set_role_validates_model_id(self, tmp_path, monkeypatch, capsys):
        """Should error on unknown model ID.""" 
        # Mock state_file
        state_file_path = tmp_path / "state.json"
        monkeypatch.setattr("agent_notes.state.state_file", lambda: state_file_path)
        
        # Create mock state
        from agent_notes.state import State, ScopeState
        state = State(global_install=ScopeState())
        
        # Mock registries
        mock_role_registry = MagicMock()
        mock_role_registry.get.return_value = MagicMock()
        
        mock_model_registry = MagicMock()
        mock_model_registry.get.side_effect = KeyError("unknown")
        mock_model_registry.ids.return_value = ["claude-opus-4-7", "claude-sonnet-4"]
        
        with patch('agent_notes.state.load', return_value=state), \
             patch('agent_notes.role_registry.load_role_registry', return_value=mock_role_registry), \
             patch('agent_notes.model_registry.load_model_registry', return_value=mock_model_registry), \
             pytest.raises(SystemExit):
            
            set_role_mod.set_role("worker", "unknown-model")
        
        captured = capsys.readouterr()
        assert "Unknown model: unknown-model" in captured.out
        assert "Available models: claude-opus-4-7, claude-sonnet-4" in captured.out
    
    def test_set_role_validates_compatibility(self, tmp_path, monkeypatch, capsys):
        """Should error if model not compatible with CLI."""
        # Mock state_file
        state_file_path = tmp_path / "state.json"
        monkeypatch.setattr("agent_notes.state.state_file", lambda: state_file_path)
        
        # Create mock state with CLI
        from agent_notes.state import State, ScopeState, BackendState
        state = State(
            global_install=ScopeState(
                clis={
                    "claude": BackendState(role_models={}, installed={})
                }
            )
        )
        
        # Mock registries
        mock_role_registry = MagicMock()
        mock_role_registry.get.return_value = MagicMock()
        
        mock_model_registry = MagicMock()
        mock_model = MagicMock()
        mock_model.aliases = {"openrouter": "some-model"}
        mock_model_registry.get.return_value = mock_model
        
        mock_cli_registry = MagicMock()
        mock_backend = MagicMock()
        mock_backend.label = "Claude Code"
        mock_backend.accepted_providers = ["anthropic"]
        mock_backend.first_alias_for.return_value = None  # Not compatible
        mock_cli_registry.get.return_value = mock_backend
        
        with patch('agent_notes.state.load', return_value=state), \
             patch('agent_notes.role_registry.load_role_registry', return_value=mock_role_registry), \
             patch('agent_notes.model_registry.load_model_registry', return_value=mock_model_registry), \
             patch('agent_notes.cli_backend.load_registry', return_value=mock_cli_registry), \
             pytest.raises(SystemExit):
            
            set_role_mod.set_role("worker", "incompatible-model", cli="claude")
        
        captured = capsys.readouterr()
        assert "Model incompatible-model is not compatible with Claude Code" in captured.out
        assert "Compatible providers: anthropic" in captured.out
        assert "Model providers: openrouter" in captured.out
    
    def test_set_role_auto_detects_single_cli(self, tmp_path, monkeypatch):
        """Should auto-detect CLI when only one CLI exists."""
        # Mock state_file
        state_file_path = tmp_path / "state.json"
        monkeypatch.setattr("agent_notes.state.state_file", lambda: state_file_path)
        
        # Create mock state with single CLI
        from agent_notes.state import State, ScopeState, BackendState
        state = State(
            global_install=ScopeState(
                clis={
                    "claude": BackendState(role_models={}, installed={})
                }
            )
        )
        
        # Mock registries (working case)
        mock_role_registry = MagicMock()
        mock_role_registry.get.return_value = MagicMock()
        
        mock_model_registry = MagicMock()
        mock_model = MagicMock()
        mock_model.aliases = {"anthropic": "claude-opus-4-7"}
        mock_model_registry.get.return_value = mock_model
        
        mock_cli_registry = MagicMock()
        mock_backend = MagicMock()
        mock_backend.label = "Claude Code"
        mock_backend.first_alias_for.return_value = "claude-opus-4-7"
        mock_cli_registry.get.return_value = mock_backend
        
        mock_regenerate = MagicMock()
        
        with patch('agent_notes.state.load', return_value=state), \
             patch('agent_notes.role_registry.load_role_registry', return_value=mock_role_registry), \
             patch('agent_notes.model_registry.load_model_registry', return_value=mock_model_registry), \
             patch('agent_notes.cli_backend.load_registry', return_value=mock_cli_registry), \
             patch('agent_notes.install_state.record_install_state'), \
             patch('agent_notes.regenerate.regenerate', mock_regenerate):
            
            # Should auto-detect claude CLI
            set_role_mod.set_role("worker", "claude-opus-4-7")  # no cli specified
            
            mock_regenerate.assert_called_once_with(scope="global", cli="claude", project_path=None)
    
    def test_set_role_requires_cli_when_multiple(self, tmp_path, monkeypatch, capsys):
        """Should error when multiple CLIs exist but none specified."""
        # Mock state_file
        state_file_path = tmp_path / "state.json"
        monkeypatch.setattr("agent_notes.state.state_file", lambda: state_file_path)
        
        # Create mock state with multiple CLIs
        from agent_notes.state import State, ScopeState, BackendState
        state = State(
            global_install=ScopeState(
                clis={
                    "claude": BackendState(role_models={}, installed={}),
                    "opencode": BackendState(role_models={}, installed={})
                }
            )
        )
        
        # Mock registries
        mock_role_registry = MagicMock()
        mock_role_registry.get.return_value = MagicMock()
        
        mock_model_registry = MagicMock()
        mock_model_registry.get.return_value = MagicMock()
        
        with patch('agent_notes.state.load', return_value=state), \
             patch('agent_notes.role_registry.load_role_registry', return_value=mock_role_registry), \
             patch('agent_notes.model_registry.load_model_registry', return_value=mock_model_registry), \
             pytest.raises(SystemExit):
            
            set_role_mod.set_role("worker", "some-model")  # no cli specified
        
        captured = capsys.readouterr()
        assert "Multiple CLIs found: claude, opencode" in captured.out
        assert "Specify --cli <name> or --cli all" in captured.out
    
    def test_set_role_cli_all_skips_incompatible(self, tmp_path, monkeypatch, capsys):
        """Should skip incompatible CLIs with --cli all and warn."""
        # Mock state_file
        state_file_path = tmp_path / "state.json"
        monkeypatch.setattr("agent_notes.state.state_file", lambda: state_file_path)
        
        # Create mock state with multiple CLIs
        from agent_notes.state import State, ScopeState, BackendState
        state = State(
            global_install=ScopeState(
                clis={
                    "claude": BackendState(role_models={}, installed={}),
                    "opencode": BackendState(role_models={}, installed={})
                }
            )
        )
        
        # Mock registries
        mock_role_registry = MagicMock()
        mock_role_registry.get.return_value = MagicMock()
        
        mock_model_registry = MagicMock()
        mock_model = MagicMock()
        mock_model.aliases = {"anthropic": "claude-opus-4-7"}
        mock_model_registry.get.return_value = mock_model
        
        mock_cli_registry = MagicMock()
        def get_backend(name):
            if name == "claude":
                backend = MagicMock()
                backend.label = "Claude Code"
                backend.first_alias_for.return_value = "claude-opus-4-7"  # Compatible
                return backend
            else:  # opencode
                backend = MagicMock()
                backend.label = "OpenCode"
                backend.first_alias_for.return_value = None  # Incompatible
                return backend
        
        mock_cli_registry.get.side_effect = get_backend
        mock_regenerate = MagicMock()
        
        with patch('agent_notes.state.load', return_value=state), \
             patch('agent_notes.role_registry.load_role_registry', return_value=mock_role_registry), \
             patch('agent_notes.model_registry.load_model_registry', return_value=mock_model_registry), \
             patch('agent_notes.cli_backend.load_registry', return_value=mock_cli_registry), \
             patch('agent_notes.install_state.record_install_state'), \
             patch('agent_notes.regenerate.regenerate', mock_regenerate):
            
            set_role_mod.set_role("worker", "claude-opus-4-7", cli="all")
            
        captured = capsys.readouterr()
        assert "Warning: Skipping OpenCode - model claude-opus-4-7 not compatible" in captured.out
        
        # Should only regenerate claude
        mock_regenerate.assert_called_once_with(scope="global", cli="claude", project_path=None)
    
    def test_set_role_auto_detects_scope(self, tmp_path, monkeypatch):
        """Should prefer global scope when available."""
        # Mock state_file
        state_file_path = tmp_path / "state.json"
        monkeypatch.setattr("agent_notes.state.state_file", lambda: state_file_path)
        
        # Create mock state with both global and local
        from agent_notes.state import State, ScopeState, BackendState
        state = State(
            global_install=ScopeState(
                clis={"claude": BackendState(role_models={}, installed={})}
            ),
            local_installs={
                "/some/path": ScopeState(
                    clis={"claude": BackendState(role_models={}, installed={})}
                )
            }
        )
        
        # Mock registries (working case)
        mock_role_registry = MagicMock()
        mock_role_registry.get.return_value = MagicMock()
        
        mock_model_registry = MagicMock()
        mock_model = MagicMock()
        mock_model.aliases = {"anthropic": "claude-opus-4-7"}
        mock_model_registry.get.return_value = mock_model
        
        mock_cli_registry = MagicMock()
        mock_backend = MagicMock()
        mock_backend.label = "Claude Code"
        mock_backend.first_alias_for.return_value = "claude-opus-4-7"
        mock_cli_registry.get.return_value = mock_backend
        
        mock_regenerate = MagicMock()
        
        with patch('agent_notes.state.load', return_value=state), \
             patch('agent_notes.role_registry.load_role_registry', return_value=mock_role_registry), \
             patch('agent_notes.model_registry.load_model_registry', return_value=mock_model_registry), \
             patch('agent_notes.cli_backend.load_registry', return_value=mock_cli_registry), \
             patch('agent_notes.install_state.record_install_state'), \
             patch('agent_notes.regenerate.regenerate', mock_regenerate):
            
            # Should auto-detect global scope
            set_role_mod.set_role("worker", "claude-opus-4-7")
            
            # Should update global state and regenerate with scope=global
            assert state.global_install.clis["claude"].role_models["worker"] == "claude-opus-4-7"
            mock_regenerate.assert_called_once_with(scope="global", cli="claude", project_path=None)
    
    def test_set_role_errors_if_no_install(self, tmp_path, monkeypatch, capsys):
        """Should error if no state.json exists."""
        # Mock state_file
        state_file_path = tmp_path / "state.json"
        monkeypatch.setattr("agent_notes.state.state_file", lambda: state_file_path)
        
        with patch('agent_notes.state.load', return_value=None), \
             pytest.raises(SystemExit):
            
            set_role_mod.set_role("worker", "some-model")
        
        captured = capsys.readouterr()
        assert "No installation found. Run `agent-notes install` first." in captured.out