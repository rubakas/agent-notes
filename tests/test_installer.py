"""Tests for the installer module."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

import agent_notes.installer as installer
from agent_notes.cli_backend import CLIBackend, CLIRegistry


@pytest.fixture
def mock_claude_backend():
    """Mock Claude backend for testing."""
    return CLIBackend(
        name="claude",
        label="Claude Code",
        global_home=Path("~/.claude").expanduser(),
        local_dir=".claude",
        layout={
            "agents": "agents/",
            "skills": "skills/",
            "rules": "rules/",
            "config": "CLAUDE.md"
        },
        features={
            "agents": True,
            "skills": True,
            "rules": True,
            "config": True
        },
        global_template="global-claude.md",

    )


@pytest.fixture
def mock_opencode_backend():
    """Mock OpenCode backend for testing."""
    return CLIBackend(
        name="opencode",
        label="OpenCode",
        global_home=Path("~/.config/opencode").expanduser(),
        local_dir=".opencode",
        layout={
            "agents": "agents/",
            "skills": "skills/",
            "config": "AGENTS.md"
        },
        features={
            "agents": True,
            "skills": True,
            "rules": False,  # OpenCode doesn't support rules
            "config": True
        },
        global_template="global-opencode.md",

    )


@pytest.fixture
def mock_copilot_backend():
    """Mock Copilot backend for testing."""
    return CLIBackend(
        name="copilot",
        label="GitHub Copilot",
        global_home=Path("~/.github").expanduser(),
        local_dir=".github",
        layout={
            "config": "copilot-instructions.md"
        },
        features={
            "agents": False,  # Copilot doesn't support agents
            "skills": False,
            "rules": False,
            "config": True
        },
        global_template="global-copilot.md",

    )


class TestDistSourceFor:
    """Test dist_source_for function."""
    
    def test_agents_component(self, mock_claude_backend, tmp_path, monkeypatch):
        """Should return dist/claude/agents path when it exists."""
        dist_dir = tmp_path / "dist"
        claude_agents = dist_dir / "claude" / "agents"
        claude_agents.mkdir(parents=True)
        
        monkeypatch.setattr(installer, "DIST_DIR", dist_dir)
        
        result = installer.dist_source_for(mock_claude_backend, "agents")
        assert result == claude_agents
    
    def test_agents_component_missing(self, mock_claude_backend, tmp_path, monkeypatch):
        """Should return None when agents directory doesn't exist."""
        dist_dir = tmp_path / "dist"
        monkeypatch.setattr(installer, "DIST_DIR", dist_dir)
        
        result = installer.dist_source_for(mock_claude_backend, "agents")
        assert result is None
    
    def test_config_component(self, mock_claude_backend, tmp_path, monkeypatch):
        """Should return dist/claude directory for config component."""
        dist_dir = tmp_path / "dist"
        claude_dir = dist_dir / "claude"
        claude_dir.mkdir(parents=True)
        
        monkeypatch.setattr(installer, "DIST_DIR", dist_dir)
        
        result = installer.dist_source_for(mock_claude_backend, "config")
        assert result == claude_dir
    
    def test_skills_component(self, mock_claude_backend, tmp_path, monkeypatch):
        """Should return DIST_SKILLS_DIR for skills component."""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir(parents=True)
        
        monkeypatch.setattr(installer, "DIST_SKILLS_DIR", skills_dir)
        
        result = installer.dist_source_for(mock_claude_backend, "skills")
        assert result == skills_dir
    
    def test_rules_component(self, mock_claude_backend, tmp_path, monkeypatch):
        """Should return DIST_RULES_DIR for rules component."""
        rules_dir = tmp_path / "rules"
        rules_dir.mkdir(parents=True)
        
        monkeypatch.setattr(installer, "DIST_RULES_DIR", rules_dir)
        
        result = installer.dist_source_for(mock_claude_backend, "rules")
        assert result == rules_dir
    
    def test_commands_component(self, mock_claude_backend, tmp_path, monkeypatch):
        """Should return dist/claude/commands path when it exists."""
        dist_dir = tmp_path / "dist"
        claude_commands = dist_dir / "claude" / "commands"
        claude_commands.mkdir(parents=True)
        
        monkeypatch.setattr(installer, "DIST_DIR", dist_dir)
        
        result = installer.dist_source_for(mock_claude_backend, "commands")
        assert result == claude_commands
    
    def test_unknown_component(self, mock_claude_backend):
        """Should return None for unknown component."""
        result = installer.dist_source_for(mock_claude_backend, "unknown")
        assert result is None


class TestTargetDirFor:
    """Test target_dir_for function."""
    
    def test_global_agents(self, mock_claude_backend):
        """Should return ~/.claude/agents for global agents."""
        result = installer.target_dir_for(mock_claude_backend, "agents", "global")
        expected = mock_claude_backend.global_home / "agents"
        assert result == expected
    
    def test_local_agents(self, mock_claude_backend):
        """Should return .claude/agents for local agents."""
        result = installer.target_dir_for(mock_claude_backend, "agents", "local")
        expected = Path(".claude/agents")
        assert result == expected
    
    def test_global_config(self, mock_claude_backend):
        """Should return ~/.claude for global config."""
        result = installer.target_dir_for(mock_claude_backend, "config", "global")
        expected = mock_claude_backend.global_home
        assert result == expected
    
    def test_local_config(self, mock_claude_backend):
        """Should return .claude for local config."""
        result = installer.target_dir_for(mock_claude_backend, "config", "local")
        expected = Path(".claude")
        assert result == expected
    
    def test_unsupported_component(self, mock_opencode_backend):
        """Should return None for unsupported component."""
        result = installer.target_dir_for(mock_opencode_backend, "rules", "global")
        assert result is None
    
    def test_missing_layout(self, mock_copilot_backend):
        """Should return None when layout missing for component."""
        result = installer.target_dir_for(mock_copilot_backend, "agents", "global")
        assert result is None


class TestConfigFilenameFor:
    """Test config_filename_for function."""
    
    def test_claude_config(self, mock_claude_backend):
        """Should return CLAUDE.md for Claude backend."""
        result = installer.config_filename_for(mock_claude_backend)
        assert result == "CLAUDE.md"
    
    def test_opencode_config(self, mock_opencode_backend):
        """Should return AGENTS.md for OpenCode backend."""
        result = installer.config_filename_for(mock_opencode_backend)
        assert result == "AGENTS.md"
    
    def test_copilot_config(self, mock_copilot_backend):
        """Should return copilot-instructions.md for Copilot backend."""
        result = installer.config_filename_for(mock_copilot_backend)
        assert result == "copilot-instructions.md"


class TestInstallComponentForBackend:
    """Test install_component_for_backend function."""
    
    @patch('agent_notes.install.place_file')
    @patch('agent_notes.install.place_dir_contents')
    def test_install_agents(self, mock_place_dir, mock_place_file, mock_claude_backend, tmp_path, monkeypatch):
        """Should install agents using place_dir_contents."""
        # Setup source
        dist_dir = tmp_path / "dist"
        agents_src = dist_dir / "claude" / "agents"
        agents_src.mkdir(parents=True)
        (agents_src / "agent1.md").write_text("agent1")
        
        monkeypatch.setattr(installer, "DIST_DIR", dist_dir)
        
        installer.install_component_for_backend(mock_claude_backend, "agents", "global", False)
        
        expected_dst = mock_claude_backend.global_home / "agents"
        mock_place_dir.assert_called_once_with(agents_src, expected_dst, "*.md", False)
        mock_place_file.assert_not_called()
    
    @patch('agent_notes.install.place_file')
    @patch('agent_notes.install.place_dir_contents')
    def test_install_config(self, mock_place_dir, mock_place_file, mock_claude_backend, tmp_path, monkeypatch):
        """Should install config using place_file."""
        # Setup source
        dist_dir = tmp_path / "dist"
        claude_dir = dist_dir / "claude"
        claude_dir.mkdir(parents=True)
        config_file = claude_dir / "CLAUDE.md"
        config_file.write_text("config")
        
        monkeypatch.setattr(installer, "DIST_DIR", dist_dir)
        
        installer.install_component_for_backend(mock_claude_backend, "config", "global", False)
        
        expected_dst = mock_claude_backend.global_home / "CLAUDE.md"
        mock_place_file.assert_called_once_with(config_file, expected_dst, False)
        mock_place_dir.assert_not_called()
    
    @patch('agent_notes.install.place_file')
    def test_install_skills(self, mock_place_file, mock_claude_backend, tmp_path, monkeypatch):
        """Should install skills as directories."""
        # Setup source
        skills_dir = tmp_path / "skills"
        skill1_dir = skills_dir / "skill1"
        skill1_dir.mkdir(parents=True)
        (skill1_dir / "SKILL.md").write_text("skill1")
        
        monkeypatch.setattr(installer, "DIST_SKILLS_DIR", skills_dir)
        
        installer.install_component_for_backend(mock_claude_backend, "skills", "global", False)
        
        expected_dst = mock_claude_backend.global_home / "skills" / "skill1"
        mock_place_file.assert_called_once_with(skill1_dir, expected_dst, False)
    
    def test_no_op_when_unsupported(self, mock_opencode_backend):
        """Should be no-op when backend doesn't support component."""
        # This should not raise an error
        installer.install_component_for_backend(mock_opencode_backend, "rules", "global", False)
    
    def test_no_op_when_no_source(self, mock_claude_backend, tmp_path, monkeypatch):
        """Should be no-op when source doesn't exist."""
        dist_dir = tmp_path / "dist"  # Empty dist dir
        monkeypatch.setattr(installer, "DIST_DIR", dist_dir)
        
        # This should not raise an error
        installer.install_component_for_backend(mock_claude_backend, "agents", "global", False)


class TestUninstallComponentForBackend:
    """Test uninstall_component_for_backend function."""
    
    @patch('agent_notes.install.remove_symlink')
    def test_uninstall_config(self, mock_remove_symlink, mock_claude_backend):
        """Should remove config file."""
        installer.uninstall_component_for_backend(mock_claude_backend, "config", "global")
        
        expected_path = mock_claude_backend.global_home / "CLAUDE.md"
        mock_remove_symlink.assert_called_once_with(expected_path)
    
    @patch('agent_notes.install.remove_all_symlinks_in_dir')
    @patch('agent_notes.install.remove_dir_if_empty')
    def test_uninstall_agents(self, mock_remove_dir, mock_remove_symlinks, mock_claude_backend, tmp_path):
        """Should remove all symlinks and empty directory."""
        # Create a temporary target directory
        target_dir = tmp_path / "agents"
        target_dir.mkdir(exist_ok=True)
        
        with patch('agent_notes.installer.target_dir_for', return_value=target_dir):
            installer.uninstall_component_for_backend(mock_claude_backend, "agents", "global")
        
        mock_remove_symlinks.assert_called_once_with(target_dir)
        mock_remove_dir.assert_called_once_with(target_dir)
    
    def test_no_op_when_unsupported(self, mock_opencode_backend):
        """Should be no-op when backend doesn't support component."""
        # This should not raise an error
        installer.uninstall_component_for_backend(mock_opencode_backend, "rules", "global")


class TestInstallUninstallAll:
    """Test install_all and uninstall_all functions."""
    
    @patch('agent_notes.install.install_scripts_global')
    @patch('agent_notes.installer.install_component_for_backend')
    @patch('agent_notes.installer._install_universal_skills')
    def test_install_all_global(self, mock_universal, mock_component, mock_scripts, mock_claude_backend):
        """Should install scripts and all components for all backends."""
        registry = CLIRegistry([mock_claude_backend])
        
        installer.install_all("global", False, registry)
        
        mock_scripts.assert_called_once()
        mock_universal.assert_called_once_with(False, registry)
        # Should call install_component_for_backend for each component
        expected_calls = len(installer.COMPONENT_TYPES)
        assert mock_component.call_count == expected_calls
    
    @patch('agent_notes.install.install_scripts_global')
    @patch('agent_notes.installer.install_component_for_backend')
    @patch('agent_notes.installer._install_universal_skills')
    def test_install_all_local(self, mock_universal, mock_component, mock_scripts, mock_claude_backend):
        """Should not install scripts or universal skills for local scope."""
        registry = CLIRegistry([mock_claude_backend])
        
        installer.install_all("local", False, registry)
        
        mock_scripts.assert_not_called()
        mock_universal.assert_not_called()
        # Should still call install_component_for_backend for each component
        expected_calls = len(installer.COMPONENT_TYPES)
        assert mock_component.call_count == expected_calls
    
    @patch('agent_notes.install.uninstall_scripts_global')
    @patch('agent_notes.installer.uninstall_component_for_backend')
    @patch('agent_notes.installer._uninstall_universal_skills')
    def test_uninstall_all_global(self, mock_universal, mock_component, mock_scripts, mock_claude_backend):
        """Should uninstall scripts and all components for all backends."""
        registry = CLIRegistry([mock_claude_backend])
        
        installer.uninstall_all("global", registry)
        
        mock_scripts.assert_called_once()
        mock_universal.assert_called_once()
        # Should call uninstall_component_for_backend for each component
        expected_calls = len(installer.COMPONENT_TYPES)
        assert mock_component.call_count == expected_calls