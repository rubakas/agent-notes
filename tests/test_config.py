"""Test config module."""
import pytest
from pathlib import Path
from unittest.mock import patch, mock_open
import sys
import io

import agent_notes.config as config


class TestPathConstants:
    """Test that path constants are properly defined."""
    
    def test_pkg_paths_defined(self):
        """Package paths should be defined."""
        assert hasattr(config, 'PKG_DIR')
        assert hasattr(config, 'VERSION_FILE')
        assert hasattr(config, 'ROOT')  # alias for compatibility
        
    def test_data_paths_defined(self):
        """Data paths should be defined."""
        assert hasattr(config, 'DATA_DIR')
        assert hasattr(config, 'AGENTS_YAML')
        assert hasattr(config, 'AGENTS_DIR')
        assert hasattr(config, 'GLOBAL_MD')
        assert hasattr(config, 'GLOBAL_COPILOT_MD')
        assert hasattr(config, 'RULES_DIR')
        assert hasattr(config, 'SKILLS_DIR')
    
    def test_dist_paths_defined(self):
        """Dist paths should be defined."""
        assert hasattr(config, 'DIST_DIR')
        assert hasattr(config, 'DIST_CLAUDE_DIR')
        assert hasattr(config, 'DIST_OPENCODE_DIR')
        assert hasattr(config, 'DIST_GITHUB_DIR')
        assert hasattr(config, 'DIST_RULES_DIR')
        assert hasattr(config, 'DIST_SKILLS_DIR')
    
    def test_install_paths_defined(self):
        """Install target paths should be defined."""
        assert hasattr(config, 'CLAUDE_HOME')
        assert hasattr(config, 'OPENCODE_HOME')
        assert hasattr(config, 'GITHUB_HOME')
        assert hasattr(config, 'AGENTS_HOME')
    
    def test_memory_paths_defined(self):
        """Memory paths should be defined."""
        assert hasattr(config, 'MEMORY_DIR')
        assert hasattr(config, 'BACKUP_DIR')


class TestGetVersion:
    """Test get_version function."""
    
    def test_reads_version_from_file(self, tmp_path, monkeypatch):
        """Should read version from VERSION file."""
        version_file = tmp_path / "VERSION"
        version_file.write_text("2.1.3\n")
        
        monkeypatch.setattr(config, 'VERSION_FILE', version_file)
        
        assert config.get_version() == "2.1.3"
    
    def test_returns_unknown_when_file_not_found(self, tmp_path, monkeypatch):
        """Should return 'unknown' when VERSION file doesn't exist."""
        version_file = tmp_path / "nonexistent" / "VERSION"
        
        monkeypatch.setattr(config, 'VERSION_FILE', version_file)
        
        assert config.get_version() == "unknown"


class TestFindSkillDirs:
    """Test find_skill_dirs function."""
    
    def test_finds_directories_with_skill_md(self, tmp_path, monkeypatch):
        """Should find directories containing SKILL.md."""
        # Create test structure in skills/ subdirectory
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        
        skill1 = skills_dir / "skill-one"
        skill1.mkdir()
        (skill1 / "SKILL.md").write_text("skill content")
        
        skill2 = skills_dir / "skill-two"
        skill2.mkdir()
        (skill2 / "SKILL.md").write_text("skill content")
        
        # Directory without SKILL.md should be ignored
        not_skill = skills_dir / "not-a-skill"
        not_skill.mkdir()
        (not_skill / "other.md").write_text("not a skill")
        
        # File (not directory) should be ignored
        (skills_dir / "file.txt").write_text("just a file")
        
        # Mock SKILLS_DIR to point to our test skills directory
        monkeypatch.setattr(config, 'SKILLS_DIR', skills_dir)
        
        skills = config.find_skill_dirs()
        skill_names = [s.name for s in skills]
        
        assert len(skills) == 2
        assert "skill-one" in skill_names
        assert "skill-two" in skill_names
        assert "not-a-skill" not in skill_names
    
    def test_returns_empty_when_no_skills(self, tmp_path, monkeypatch):
        """Should return empty list when no skill directories exist."""
        # Mock SKILLS_DIR to point to nonexistent directory
        monkeypatch.setattr(config, 'SKILLS_DIR', tmp_path / "nonexistent")
        
        skills = config.find_skill_dirs()
        assert skills == []


class TestColorClass:
    """Test Color class."""
    
    def test_has_expected_color_constants(self):
        """Should have all expected color constants."""
        assert hasattr(config.Color, 'RED')
        assert hasattr(config.Color, 'GREEN')
        assert hasattr(config.Color, 'YELLOW')
        assert hasattr(config.Color, 'CYAN')
        assert hasattr(config.Color, 'DIM')
        assert hasattr(config.Color, 'NC')
        
        # Colors might be disabled in test environment, so just check they exist
        assert isinstance(config.Color.RED, str)
        assert isinstance(config.Color.NC, str)
    
    def test_disable_removes_colors(self):
        """Should remove color codes when disabled."""
        # Save original values
        original_red = config.Color.RED
        original_nc = config.Color.NC
        
        config.Color.disable()
        
        assert config.Color.RED == ""
        assert config.Color.NC == ""
        
        # Restore for other tests
        config.Color.RED = original_red
        config.Color.NC = original_nc


class TestOutputHelpers:
    """Test output helper functions."""
    
    def test_output_functions_dont_crash(self, capsys, disable_colors):
        """Output functions should not crash."""
        config.ok("test message")
        config.warn("test warning")
        config.fail("test failure")
        config.info("test info")
        config.issue("test issue")
        config.linked("test/path")
        config.removed("test/path")
        config.skipped("test/path")
        config.skipped("test/path", "custom reason")
        
        # Should have produced output
        captured = capsys.readouterr()
        assert "test message" in captured.out
        assert "test warning" in captured.out
        assert "test failure" in captured.out
    
    def test_error_exits_with_code_1(self, disable_colors):
        """Error function should exit with code 1."""
        with pytest.raises(SystemExit) as exc_info:
            config.error("test error")
        
        assert exc_info.value.code == 1


class TestColorDisabledForNonTTY:
    """Test color disabling for non-TTY output."""
    
    def test_colors_disabled_when_not_tty(self, monkeypatch):
        """Colors should be disabled when stdout is not a TTY."""
        # Mock stdout.isatty to return False
        mock_stdout = io.StringIO()
        mock_stdout.isatty = lambda: False
        
        with patch('sys.stdout', mock_stdout):
            # Reload the module to trigger the TTY check
            import importlib
            importlib.reload(config)
            
            # Colors should be empty strings
            assert config.Color.RED == ""
            assert config.Color.GREEN == ""