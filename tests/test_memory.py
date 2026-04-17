"""Test memory module."""
import pytest
from pathlib import Path
from unittest.mock import patch
import shutil

import agent_notes.memory as memory


class TestDoList:
    """Test do_list function."""
    
    def test_lists_agent_memories(self, mock_paths, tmp_path, capsys):
        """Should list agent memories with sizes."""
        memory_dir = mock_paths['memory']
        
        # Create agent memory directories
        agent1_dir = memory_dir / "agent1"
        agent1_dir.mkdir()
        (agent1_dir / "memory.txt").write_text("agent1 memory content")
        
        agent2_dir = memory_dir / "agent2"
        agent2_dir.mkdir()
        (agent2_dir / "memory.txt").write_text("agent2 memory content with more data")
        
        memory.do_list()
        
        captured = capsys.readouterr()
        assert "Agent memories" in captured.out
        assert "agent1" in captured.out
        assert "agent2" in captured.out
        assert "AGENT" in captured.out
        assert "SIZE" in captured.out
    
    def test_handles_empty_memory_dir(self, mock_paths, capsys):
        """Should handle empty memory directory."""
        memory.do_list()
        
        captured = capsys.readouterr()
        assert "No agent memories found" in captured.out
    
    def test_handles_nonexistent_memory_dir(self, tmp_path, monkeypatch, capsys):
        """Should handle non-existent memory directory."""
        nonexistent = tmp_path / "nonexistent"
        monkeypatch.setattr(memory, 'MEMORY_DIR', nonexistent)
        
        memory.do_list()
        
        captured = capsys.readouterr()
        assert "No agent memories found" in captured.out


class TestDoSize:
    """Test do_size function."""
    
    def test_shows_total_memory_usage(self, mock_paths, capsys):
        """Should show total memory usage."""
        memory_dir = mock_paths['memory']
        
        # Create some memory files
        agent_dir = memory_dir / "test-agent"
        agent_dir.mkdir()
        (agent_dir / "file1.txt").write_text("content1")
        (agent_dir / "file2.txt").write_text("content2")
        
        memory.do_size()
        
        captured = capsys.readouterr()
        assert "Total memory usage" in captured.out
        # Should show some size (exact value depends on filesystem)
    
    def test_handles_nonexistent_memory_dir(self, tmp_path, monkeypatch, capsys):
        """Should handle non-existent memory directory."""
        nonexistent = tmp_path / "nonexistent"
        monkeypatch.setattr(memory, 'MEMORY_DIR', nonexistent)
        
        memory.do_size()
        
        captured = capsys.readouterr()
        assert "No agent memories found" in captured.out


class TestDoShow:
    """Test do_show function."""
    
    def test_shows_agent_memory_contents(self, mock_paths, capsys):
        """Should show memory contents for specific agent."""
        memory_dir = mock_paths['memory']
        
        # Create agent memory
        agent_dir = memory_dir / "test-agent"
        agent_dir.mkdir()
        (agent_dir / "conversation1.txt").write_text("First conversation")
        (agent_dir / "conversation2.txt").write_text("Second conversation")
        
        memory.do_show("test-agent")
        
        captured = capsys.readouterr()
        assert "Memory for agent 'test-agent'" in captured.out
        assert "conversation1.txt" in captured.out
        assert "conversation2.txt" in captured.out
        assert "First conversation" in captured.out
        assert "Second conversation" in captured.out
    
    def test_handles_missing_agent(self, mock_paths, capsys):
        """Should handle missing agent memory."""
        with pytest.raises(SystemExit) as exc_info:
            memory.do_show("nonexistent-agent")
        
        assert exc_info.value.code == 1
        
        captured = capsys.readouterr()
        assert "No memory found for agent 'nonexistent-agent'" in captured.out
    
    def test_shows_available_agents_on_error(self, mock_paths, capsys):
        """Should show available agents when agent not found."""
        memory_dir = mock_paths['memory']
        
        # Create some agents
        (memory_dir / "agent1").mkdir()
        (memory_dir / "agent2").mkdir()
        
        with pytest.raises(SystemExit):
            memory.do_show("nonexistent")
        
        captured = capsys.readouterr()
        assert "Available: agent1 agent2" in captured.out
    
    def test_handles_binary_files(self, mock_paths, capsys):
        """Should handle binary files gracefully."""
        memory_dir = mock_paths['memory']
        
        agent_dir = memory_dir / "test-agent"
        agent_dir.mkdir()
        
        # Create binary file
        (agent_dir / "binary.dat").write_bytes(b'\x00\x01\x02\x03')
        
        memory.do_show("test-agent")
        
        captured = capsys.readouterr()
        assert "binary.dat" in captured.out
        assert "(binary file or read error)" in captured.out


class TestDoReset:
    """Test do_reset function."""
    
    def test_resets_specific_agent_with_confirmation(self, mock_paths, capsys):
        """Should reset specific agent memory with user confirmation."""
        memory_dir = mock_paths['memory']
        
        # Create agent memory
        agent_dir = memory_dir / "test-agent"
        agent_dir.mkdir()
        (agent_dir / "memory.txt").write_text("agent memory")
        
        with patch('builtins.input', return_value='y'):
            memory.do_reset("test-agent")
        
        assert not agent_dir.exists()
        
        captured = capsys.readouterr()
        assert "This will delete all memory for agent 'test-agent'" in captured.out
        assert "Memory for 'test-agent' cleared" in captured.out
    
    def test_cancels_reset_on_no(self, mock_paths, capsys):
        """Should cancel reset when user says no."""
        memory_dir = mock_paths['memory']
        
        # Create agent memory
        agent_dir = memory_dir / "test-agent"
        agent_dir.mkdir()
        (agent_dir / "memory.txt").write_text("agent memory")
        
        with patch('builtins.input', return_value='n'):
            memory.do_reset("test-agent")
        
        assert agent_dir.exists()
        
        captured = capsys.readouterr()
        assert "Cancelled" in captured.out
    
    def test_resets_all_agents_with_confirmation(self, mock_paths, capsys):
        """Should reset all agent memories with strong confirmation."""
        memory_dir = mock_paths['memory']
        
        # Create multiple agent memories
        agent1_dir = memory_dir / "agent1"
        agent1_dir.mkdir()
        (agent1_dir / "memory.txt").write_text("agent1 memory")
        
        agent2_dir = memory_dir / "agent2"
        agent2_dir.mkdir()
        (agent2_dir / "memory.txt").write_text("agent2 memory")
        
        with patch('builtins.input', return_value='yes'):
            memory.do_reset()
        
        assert not agent1_dir.exists()
        assert not agent2_dir.exists()
        
        captured = capsys.readouterr()
        assert "This will delete ALL agent memories" in captured.out
        assert "Type 'yes' to confirm" in captured.out
        assert "All agent memories cleared" in captured.out
    
    def test_cancels_reset_all_on_wrong_confirmation(self, mock_paths, capsys):
        """Should cancel reset all when user doesn't type 'yes' exactly."""
        memory_dir = mock_paths['memory']
        
        # Create agent memory
        agent_dir = memory_dir / "agent1"
        agent_dir.mkdir()
        
        with patch('builtins.input', return_value='y'):  # Not 'yes'
            memory.do_reset()
        
        assert agent_dir.exists()
        
        captured = capsys.readouterr()
        assert "Cancelled" in captured.out
    
    def test_handles_missing_agent_for_reset(self, mock_paths, capsys):
        """Should handle missing agent gracefully."""
        with pytest.raises(SystemExit) as exc_info:
            memory.do_reset("nonexistent")
        
        assert exc_info.value.code == 1
        
        captured = capsys.readouterr()
        assert "No memory found for agent 'nonexistent'" in captured.out
    
    def test_handles_empty_memory_dir_for_reset_all(self, mock_paths, capsys):
        """Should handle empty memory directory for reset all."""
        memory.do_reset()
        
        captured = capsys.readouterr()
        assert "No agent memories to clear" in captured.out


class TestDoExport:
    """Test do_export function."""
    
    def test_exports_memories_to_backup(self, mock_paths, capsys):
        """Should export all memories to backup directory."""
        memory_dir = mock_paths['memory']
        backup_dir = mock_paths['backup']
        
        # Create agent memories
        agent1_dir = memory_dir / "agent1"
        agent1_dir.mkdir()
        (agent1_dir / "memory.txt").write_text("agent1 memory")
        
        agent2_dir = memory_dir / "agent2"
        agent2_dir.mkdir()
        (agent2_dir / "memory.txt").write_text("agent2 memory")
        
        # Create a file (not directory) too
        (memory_dir / "global.txt").write_text("global memory")
        
        memory.do_export()
        
        # Check backup was created
        assert (backup_dir / "agent1" / "memory.txt").exists()
        assert (backup_dir / "agent2" / "memory.txt").exists()
        assert (backup_dir / "global.txt").exists()
        
        assert (backup_dir / "agent1" / "memory.txt").read_text() == "agent1 memory"
        
        captured = capsys.readouterr()
        assert "Exported to" in captured.out
        assert "agent1" in captured.out
        assert "agent2" in captured.out
        assert "global.txt" in captured.out
        assert "memory-backup/ is in .gitignore" in captured.out
    
    def test_overwrites_existing_backup(self, mock_paths):
        """Should overwrite existing backup."""
        memory_dir = mock_paths['memory']
        backup_dir = mock_paths['backup']
        
        # Create existing backup
        old_backup = backup_dir / "agent1"
        old_backup.mkdir()
        (old_backup / "old.txt").write_text("old backup")
        
        # Create new memory
        agent_dir = memory_dir / "agent1"
        agent_dir.mkdir()
        (agent_dir / "new.txt").write_text("new memory")
        
        memory.do_export()
        
        # Old backup should be replaced
        assert not (backup_dir / "agent1" / "old.txt").exists()
        assert (backup_dir / "agent1" / "new.txt").exists()
    
    def test_handles_no_memories_to_export(self, mock_paths, capsys):
        """Should handle case with no memories to export."""
        memory.do_export()
        
        captured = capsys.readouterr()
        assert "No agent memories to export" in captured.out


class TestDoImport:
    """Test do_import function."""
    
    def test_imports_from_backup(self, mock_paths, capsys):
        """Should import memories from backup directory."""
        memory_dir = mock_paths['memory']
        backup_dir = mock_paths['backup']
        
        # Create backup
        agent1_backup = backup_dir / "agent1"
        agent1_backup.mkdir()
        (agent1_backup / "memory.txt").write_text("backed up memory")
        
        agent2_backup = backup_dir / "agent2"
        agent2_backup.mkdir()
        (agent2_backup / "memory.txt").write_text("another backup")
        
        # Create file backup too
        (backup_dir / "global.txt").write_text("global backup")
        
        memory.do_import()
        
        # Check memories were restored
        assert (memory_dir / "agent1" / "memory.txt").exists()
        assert (memory_dir / "agent2" / "memory.txt").exists()
        assert (memory_dir / "global.txt").exists()
        
        assert (memory_dir / "agent1" / "memory.txt").read_text() == "backed up memory"
        
        captured = capsys.readouterr()
        assert "Imported from" in captured.out
        assert "Restored agents:" in captured.out
        assert "agent1" in captured.out
        assert "agent2" in captured.out
    
    def test_overwrites_existing_memories(self, mock_paths):
        """Should overwrite existing memories."""
        memory_dir = mock_paths['memory']
        backup_dir = mock_paths['backup']
        
        # Create existing memory
        existing_agent = memory_dir / "agent1"
        existing_agent.mkdir()
        (existing_agent / "old.txt").write_text("old memory")
        
        # Create backup with different content
        backup_agent = backup_dir / "agent1"
        backup_agent.mkdir()
        (backup_agent / "new.txt").write_text("backup memory")
        
        memory.do_import()
        
        # Old memory should be replaced
        assert not (memory_dir / "agent1" / "old.txt").exists()
        assert (memory_dir / "agent1" / "new.txt").exists()
    
    def test_handles_no_backup(self, tmp_path, monkeypatch, capsys):
        """Should handle missing backup directory."""
        nonexistent_backup = tmp_path / "nonexistent"
        monkeypatch.setattr(memory, 'BACKUP_DIR', nonexistent_backup)
        
        with pytest.raises(SystemExit) as exc_info:
            memory.do_import()
        
        assert exc_info.value.code == 1
        
        captured = capsys.readouterr()
        assert "No backup found" in captured.out


class TestUtilityFunctions:
    """Test utility functions."""
    
    def test_get_directory_size(self, tmp_path):
        """Should calculate directory size correctly."""
        test_dir = tmp_path / "test"
        test_dir.mkdir()
        
        (test_dir / "file1.txt").write_text("content1")  # 8 bytes
        (test_dir / "file2.txt").write_text("content2")  # 8 bytes
        
        subdir = test_dir / "subdir"
        subdir.mkdir()
        (subdir / "file3.txt").write_text("content3")   # 8 bytes
        
        size = memory.get_directory_size(test_dir)
        assert size >= 24  # At least 24 bytes of content
    
    def test_get_directory_size_handles_permission_error(self, tmp_path, monkeypatch):
        """Should handle permission errors gracefully."""
        test_dir = tmp_path / "test"
        test_dir.mkdir()
        
        # Mock rglob to raise PermissionError
        def mock_rglob(*args):
            raise PermissionError("Permission denied")
        
        monkeypatch.setattr(Path, 'rglob', mock_rglob)
        
        size = memory.get_directory_size(test_dir)
        assert size == 0
    
    def test_format_size(self):
        """Should format sizes in human-readable format."""
        assert memory.format_size(0) == "0B"
        assert memory.format_size(512) == "512B"
        assert memory.format_size(1024) == "1.0K"
        assert memory.format_size(1024 * 1024) == "1.0M"
        assert memory.format_size(1024 * 1024 * 1024) == "1.0G"
        assert memory.format_size(1024 * 1024 * 1024 * 1024) == "1.0T"
    
    def test_format_size_with_decimals(self):
        """Should format sizes with proper decimals."""
        assert memory.format_size(1536) == "1.5K"  # 1.5 KB
        assert memory.format_size(2560) == "2.5K"  # 2.5 KB


class TestMemoryFunction:
    """Test main memory function."""
    
    def test_routes_to_list_by_default(self, mock_paths):
        """Should route to list function by default."""
        with patch('agent_notes.memory.do_list') as mock_list:
            memory.memory()
            mock_list.assert_called_once()
    
    def test_routes_to_list_explicitly(self, mock_paths):
        """Should route to list function explicitly."""
        with patch('agent_notes.memory.do_list') as mock_list:
            memory.memory("list")
            mock_list.assert_called_once()
    
    def test_routes_to_size(self, mock_paths):
        """Should route to size function."""
        with patch('agent_notes.memory.do_size') as mock_size:
            memory.memory("size")
            mock_size.assert_called_once()
    
    def test_routes_to_show_with_name(self, mock_paths):
        """Should route to show function with agent name."""
        with patch('agent_notes.memory.do_show') as mock_show:
            memory.memory("show", "test-agent")
            mock_show.assert_called_once_with("test-agent")
    
    def test_show_requires_name(self, mock_paths, capsys):
        """Should require name for show command."""
        with pytest.raises(SystemExit) as exc_info:
            memory.memory("show")
        
        assert exc_info.value.code == 1
        
        captured = capsys.readouterr()
        assert "show requires an agent name" in captured.out
    
    def test_routes_to_reset(self, mock_paths):
        """Should route to reset function."""
        with patch('agent_notes.memory.do_reset') as mock_reset:
            memory.memory("reset")
            mock_reset.assert_called_once_with(None)
    
    def test_routes_to_reset_with_name(self, mock_paths):
        """Should route to reset function with agent name."""
        with patch('agent_notes.memory.do_reset') as mock_reset:
            memory.memory("reset", "test-agent")
            mock_reset.assert_called_once_with("test-agent")
    
    def test_routes_to_export(self, mock_paths):
        """Should route to export function."""
        with patch('agent_notes.memory.do_export') as mock_export:
            memory.memory("export")
            mock_export.assert_called_once()
    
    def test_routes_to_import(self, mock_paths):
        """Should route to import function."""
        with patch('agent_notes.memory.do_import') as mock_import:
            memory.memory("import")
            mock_import.assert_called_once()
    
    def test_handles_unknown_command(self, mock_paths, capsys):
        """Should handle unknown command gracefully."""
        with pytest.raises(SystemExit) as exc_info:
            memory.memory("unknown")
        
        assert exc_info.value.code == 1
        
        captured = capsys.readouterr()
        assert "Unknown command: unknown" in captured.out


class TestShowHelp:
    """Test show_help function."""
    
    def test_shows_help_text(self, capsys):
        """Should show comprehensive help text."""
        memory.show_help()
        
        captured = capsys.readouterr()
        assert "Usage: agent-notes memory" in captured.out
        assert "Manage agent memory stored in ~/.claude/agent-memory/" in captured.out
        assert "Commands:" in captured.out
        assert "list" in captured.out
        assert "size" in captured.out
        assert "show <name>" in captured.out
        assert "reset" in captured.out
        assert "export" in captured.out
        assert "import" in captured.out
        assert "Examples:" in captured.out