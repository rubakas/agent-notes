"""Test config module."""
import pytest
from pathlib import Path
from unittest.mock import patch, mock_open
import sys
import io

import agent_notes.config as config


class TestFindRoot:
    """Test _find_root function."""
    
    def test_finds_pkg_dir_when_version_and_source_exist_in_package(self, tmp_path, monkeypatch):
        """Should find package directory when VERSION and source exist in the package."""
        # Setup mock package structure (pip install scenario)
        pkg_dir = tmp_path / "lib" / "agent_notes"
        pkg_dir.mkdir(parents=True)
        (pkg_dir / "VERSION").write_text("1.0.0")
        (pkg_dir / "source").mkdir()
        
        config_file = pkg_dir / "config.py"
        config_file.write_text("")
        
        with patch.object(config, '__file__', str(config_file)):
            root = config._find_root()
            assert root == pkg_dir
    def test_finds_dev_root_when_version_and_source_exist(self, tmp_path, monkeypatch):
        """Should find dev root when VERSION and source directories exist at repo root."""
        # Setup mock file structure (dev scenario)
        dev_root = tmp_path / "agent-notes"
        dev_root.mkdir()
        (dev_root / "VERSION").write_text("1.0.0")
        (dev_root / "source").mkdir()
        
        # Mock __file__ to point to our test structure
        config_file = dev_root / "lib" / "agent_notes" / "config.py"
        config_file.parent.mkdir(parents=True)
        config_file.write_text("")
        
        with patch.object(config, '__file__', str(config_file)):
            root = config._find_root()
            assert root == dev_root
    
    def test_uses_env_var_when_set(self, tmp_path, monkeypatch):
        """Should use AGENT_NOTES_DIR env var when set."""
        env_root = tmp_path / "env-root"
        env_root.mkdir()
        
        monkeypatch.setenv("AGENT_NOTES_DIR", str(env_root))
        
        # Create package structure that would normally be found
        pkg_dir = tmp_path / "lib" / "agent_notes"
        pkg_dir.mkdir(parents=True)
        
        config_file = pkg_dir / "config.py"
        config_file.write_text("")
        
        with patch.object(config, '__file__', str(config_file)):
            root = config._find_root()
            assert root == env_root
    
    def test_falls_back_to_pkg_dir_when_env_not_set(self, tmp_path, monkeypatch):
        """Should fall back to package directory when env var not set and files not found."""
        # Ensure env var is not set
        monkeypatch.delenv("AGENT_NOTES_DIR", raising=False)
        
        pkg_dir = tmp_path / "fallback" / "lib" / "agent_notes"
        config_file = pkg_dir / "config.py"
        config_file.parent.mkdir(parents=True)
        config_file.write_text("")
        
        with patch.object(config, '__file__', str(config_file)):
            root = config._find_root()
            assert root == pkg_dir


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
        
        # Mock ROOT and __file__ so both search locations point to tmp_path
        monkeypatch.setattr(config, 'ROOT', tmp_path)
        config_file = tmp_path / "lib" / "agent_notes" / "config.py"
        config_file.parent.mkdir(parents=True)
        
        with patch.object(config, '__file__', str(config_file)):
            skills = config.find_skill_dirs()
            skill_names = [s.name for s in skills]
            
            assert len(skills) == 2
            assert "skill-one" in skill_names
            assert "skill-two" in skill_names
            assert "not-a-skill" not in skill_names
    
    def test_returns_empty_when_no_skills(self, tmp_path, monkeypatch):
        """Should return empty list when no skill directories exist."""
        # Mock both ROOT and the computed repo_root to point to tmp_path
        monkeypatch.setattr(config, 'ROOT', tmp_path)
        
        # Also mock __file__ so repo_root computation points to tmp_path area
        config_file = tmp_path / "lib" / "agent_notes" / "config.py"
        config_file.parent.mkdir(parents=True)
        
        with patch.object(config, '__file__', str(config_file)):
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


class TestPathConstants:
    """Test that path constants are properly defined."""
    
    def test_source_paths_defined(self):
        """Source paths should be defined."""
        assert hasattr(config, 'SOURCE_DIR')
        assert hasattr(config, 'SOURCE_AGENTS_YAML')
        assert hasattr(config, 'SOURCE_AGENTS_DIR')
        assert hasattr(config, 'SOURCE_GLOBAL_MD')
        assert hasattr(config, 'SOURCE_GLOBAL_COPILOT_MD')
        assert hasattr(config, 'SOURCE_RULES_DIR')
    
    def test_dist_paths_defined(self):
        """Dist paths should be defined."""
        assert hasattr(config, 'DIST_DIR')
        assert hasattr(config, 'DIST_CLI_DIR')
        assert hasattr(config, 'DIST_CLAUDE_DIR')
        assert hasattr(config, 'DIST_OPENCODE_DIR')
        assert hasattr(config, 'DIST_GITHUB_DIR')
        assert hasattr(config, 'DIST_RULES_DIR')
        # DIST_SKILLS_DIR removed — skills live at repo root/skills/, not in dist
    
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