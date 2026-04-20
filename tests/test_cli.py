"""Test CLI module."""
import pytest
from unittest.mock import patch
import sys

import agent_notes.cli as cli


class TestArgumentParsing:
    """Test CLI argument parsing."""
    
    def test_version_flag(self, capsys, monkeypatch):
        """Should show version with --version flag."""
        test_args = ["agent-notes", "--version"]
        
        with patch.object(sys, 'argv', test_args):
            with patch('agent_notes.config.get_version', return_value="1.2.3"):
                cli.main()
        
        captured = capsys.readouterr()
        assert "agent-notes 1.2.3" in captured.out
    
    def test_version_short_flag(self, capsys, monkeypatch):
        """Should show version with -v flag."""
        test_args = ["agent-notes", "-v"]
        
        with patch.object(sys, 'argv', test_args):
            with patch('agent_notes.config.get_version', return_value="1.2.3"):
                cli.main()
        
        captured = capsys.readouterr()
        assert "agent-notes 1.2.3" in captured.out
    
    def test_help_when_no_command(self, capsys):
        """Should show help when no command provided."""
        test_args = ["agent-notes"]
        
        with patch.object(sys, 'argv', test_args):
            cli.main()
        
        captured = capsys.readouterr()
        assert "usage:" in captured.out
        assert "agent-notes" in captured.out
    
    def test_install_command_parsing(self):
        """Should parse install command correctly and call wizard."""
        test_args = ["agent-notes", "install"]
        
        with patch.object(sys, 'argv', test_args):
            with patch('agent_notes.wizard.interactive_install') as mock_wizard:
                cli.main()
                mock_wizard.assert_called_once()
    
    def test_install_with_flags_uses_old_install(self):
        """Should use old install function when flags are provided."""
        test_args = ["agent-notes", "install", "--local"]
        
        with patch.object(sys, 'argv', test_args):
            with patch('agent_notes.install.install') as mock_install:
                cli.main()
                mock_install.assert_called_once_with(local=True, copy=False)
    
    def test_install_with_local_flag(self):
        """Should parse install --local correctly."""
        test_args = ["agent-notes", "install", "--local"]
        
        with patch.object(sys, 'argv', test_args):
            with patch('agent_notes.install.install') as mock_install:
                cli.main()
                mock_install.assert_called_once_with(local=True, copy=False)
    
    def test_install_with_copy_flag(self):
        """Should parse install --local --copy correctly."""
        test_args = ["agent-notes", "install", "--local", "--copy"]
        
        with patch.object(sys, 'argv', test_args):
            with patch('agent_notes.install.install') as mock_install:
                cli.main()
                mock_install.assert_called_once_with(local=True, copy=True)
    
    def test_build_command_parsing(self):
        """Should parse build command correctly."""
        test_args = ["agent-notes", "build"]
        
        with patch.object(sys, 'argv', test_args):
            with patch('agent_notes.build.build') as mock_build:
                cli.main()
                mock_build.assert_called_once()
    
    def test_uninstall_command_parsing(self):
        """Should parse uninstall command correctly."""
        test_args = ["agent-notes", "uninstall"]
        
        with patch.object(sys, 'argv', test_args):
            with patch('agent_notes.install.uninstall') as mock_uninstall:
                cli.main()
                mock_uninstall.assert_called_once_with(local=False)
    
    def test_uninstall_with_local_flag(self):
        """Should parse uninstall --local correctly."""
        test_args = ["agent-notes", "uninstall", "--local"]
        
        with patch.object(sys, 'argv', test_args):
            with patch('agent_notes.install.uninstall') as mock_uninstall:
                cli.main()
                mock_uninstall.assert_called_once_with(local=True)
    
    def test_update_command_parsing(self):
        """Should parse update command correctly."""
        test_args = ["agent-notes", "update"]
        
        with patch.object(sys, 'argv', test_args):
            with patch('agent_notes.update.update') as mock_update:
                cli.main()
                mock_update.assert_called_once()
    
    def test_doctor_command_parsing(self):
        """Should parse doctor command correctly."""
        test_args = ["agent-notes", "doctor"]
        
        with patch.object(sys, 'argv', test_args):
            with patch('agent_notes.doctor.doctor') as mock_doctor:
                cli.main()
                mock_doctor.assert_called_once_with(local=False, fix=False)
    
    def test_doctor_with_flags(self):
        """Should parse doctor --local --fix correctly."""
        test_args = ["agent-notes", "doctor", "--local", "--fix"]
        
        with patch.object(sys, 'argv', test_args):
            with patch('agent_notes.doctor.doctor') as mock_doctor:
                cli.main()
                mock_doctor.assert_called_once_with(local=True, fix=True)
    
    def test_info_command_parsing(self):
        """Should parse info command correctly."""
        test_args = ["agent-notes", "info"]
        
        with patch.object(sys, 'argv', test_args):
            with patch('agent_notes.install.show_info') as mock_show_info:
                cli.main()
                mock_show_info.assert_called_once()
    
    def test_list_command_parsing(self):
        """Should parse list command correctly."""
        test_args = ["agent-notes", "list"]
        
        with patch.object(sys, 'argv', test_args):
            with patch('agent_notes.list.list_components') as mock_list:
                cli.main()
                mock_list.assert_called_once_with("all")
    
    def test_list_with_filter(self):
        """Should parse list with filter correctly."""
        test_args = ["agent-notes", "list", "agents"]
        
        with patch.object(sys, 'argv', test_args):
            with patch('agent_notes.list.list_components') as mock_list:
                cli.main()
                mock_list.assert_called_once_with("agents")
    
    def test_validate_command_parsing(self):
        """Should parse validate command correctly."""
        test_args = ["agent-notes", "validate"]
        
        with patch.object(sys, 'argv', test_args):
            with patch('agent_notes.validate.validate') as mock_validate:
                cli.main()
                mock_validate.assert_called_once()
    
    def test_memory_command_parsing(self):
        """Should parse memory command correctly."""
        test_args = ["agent-notes", "memory"]
        
        with patch.object(sys, 'argv', test_args):
            with patch('agent_notes.memory.memory') as mock_memory:
                cli.main()
                mock_memory.assert_called_once_with("list", None)
    
    def test_memory_with_action(self):
        """Should parse memory with action correctly."""
        test_args = ["agent-notes", "memory", "size"]
        
        with patch.object(sys, 'argv', test_args):
            with patch('agent_notes.memory.memory') as mock_memory:
                cli.main()
                mock_memory.assert_called_once_with("size", None)
    
    def test_memory_with_action_and_name(self):
        """Should parse memory with action and name correctly."""
        test_args = ["agent-notes", "memory", "show", "coder"]
        
        with patch.object(sys, 'argv', test_args):
            with patch('agent_notes.memory.memory') as mock_memory:
                cli.main()
                mock_memory.assert_called_once_with("show", "coder")


class TestCommandRouting:
    """Test that commands are routed to correct modules."""
    
    def test_imports_happen_on_demand(self):
        """Should import modules only when needed."""
        # This test ensures lazy loading of modules
        test_args = ["agent-notes", "build"]
        
        with patch.object(sys, 'argv', test_args):
            with patch('agent_notes.build.build') as mock_build:
                cli.main()
                mock_build.assert_called_once()
    
    def test_all_commands_have_handlers(self):
        """Should have handlers for all defined commands."""
        # Test that each subcommand is properly handled
        commands = [
            ("build", "agent_notes.build.build"),
            ("uninstall", "agent_notes.install.uninstall"),
            ("update", "agent_notes.update.update"),
            ("doctor", "agent_notes.doctor.doctor"),
            ("info", "agent_notes.install.show_info"),
            ("list", "agent_notes.list.list_components"),
            ("validate", "agent_notes.validate.validate"),
            ("memory", "agent_notes.memory.memory")
        ]
        
        for command, handler_path in commands:
            test_args = ["agent-notes", command]
            
            with patch.object(sys, 'argv', test_args):
                with patch(handler_path) as mock_handler:
                    cli.main()
                    mock_handler.assert_called_once()
        
        # Test install separately since it now routes to wizard
        test_args = ["agent-notes", "install"]
        with patch.object(sys, 'argv', test_args):
            with patch('agent_notes.wizard.interactive_install') as mock_wizard:
                cli.main()
                mock_wizard.assert_called_once()


class TestListFilterChoices:
    """Test list command filter choices validation."""
    
    def test_accepts_valid_filters(self):
        """Should accept all valid filter choices."""
        valid_filters = ["agents", "skills", "rules", "all"]
        
        for filter_choice in valid_filters:
            test_args = ["agent-notes", "list", filter_choice]
            
            with patch.object(sys, 'argv', test_args):
                with patch('agent_notes.list.list_components') as mock_list:
                    cli.main()
                    mock_list.assert_called_once_with(filter_choice)


class TestMemoryActionChoices:
    """Test memory command action choices validation."""
    
    def test_accepts_valid_actions(self):
        """Should accept all valid memory actions."""
        valid_actions = ["list", "size", "show", "reset", "export", "import"]
        
        for action in valid_actions:
            test_args = ["agent-notes", "memory", action]
            
            with patch.object(sys, 'argv', test_args):
                with patch('agent_notes.memory.memory') as mock_memory:
                    cli.main()
                    mock_memory.assert_called_once_with(action, None)


class TestHelpText:
    """Test help text generation."""
    
    def test_main_help(self, capsys):
        """Should show main help text."""
        test_args = ["agent-notes", "--help"]
        
        with patch.object(sys, 'argv', test_args):
            with pytest.raises(SystemExit):
                cli.main()
        
        captured = capsys.readouterr()
        assert "AI agent configuration manager" in captured.out
        assert "install" in captured.out
        assert "build" in captured.out
        assert "uninstall" in captured.out
    
    def test_install_help(self, capsys):
        """Should show install command help."""
        test_args = ["agent-notes", "install", "--help"]
        
        with patch.object(sys, 'argv', test_args):
            with pytest.raises(SystemExit):
                cli.main()
        
        captured = capsys.readouterr()
        assert "--local" in captured.out
        assert "--copy" in captured.out
        assert "Install to current project" in captured.out
    
    def test_doctor_help(self, capsys):
        """Should show doctor command help."""
        test_args = ["agent-notes", "doctor", "--help"]
        
        with patch.object(sys, 'argv', test_args):
            with pytest.raises(SystemExit):
                cli.main()
        
        captured = capsys.readouterr()
        assert "--local" in captured.out
        assert "--fix" in captured.out
        assert "Check local installation" in captured.out
        assert "Fix found issues" in captured.out
    
    def test_memory_help(self, capsys):
        """Should show memory command help."""
        test_args = ["agent-notes", "memory", "--help"]
        
        with patch.object(sys, 'argv', test_args):
            with pytest.raises(SystemExit):
                cli.main()
        
        captured = capsys.readouterr()
        assert "list,size,show,reset,export,import" in captured.out
        assert "Agent name (for show/reset)" in captured.out


class TestProgramName:
    """Test program name configuration."""
    
    def test_program_name_set(self, capsys):
        """Should have correct program name in help."""
        test_args = ["agent-notes", "--help"]
        
        with patch.object(sys, 'argv', test_args):
            with pytest.raises(SystemExit):
                cli.main()
        
        captured = capsys.readouterr()
        assert "agent-notes" in captured.out


class TestMainFunctionEntry:
    """Test main function as entry point."""
    
    def test_main_function_exists(self):
        """Should have main function for entry point."""
        assert hasattr(cli, 'main')
        assert callable(cli.main)