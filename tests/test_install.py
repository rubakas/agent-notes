"""Test install module."""
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import shutil

import agent_notes.install as install
import agent_notes.config as config


class TestPlaceFile:
    """Test place_file function."""
    
    def test_creates_symlink_by_default(self, tmp_path):
        """Should create symlink by default."""
        src = tmp_path / "source.txt"
        src.write_text("source content")
        
        dst = tmp_path / "dest" / "target.txt"
        
        install.place_file(src, dst)
        
        assert dst.exists()
        assert dst.is_symlink()
        assert dst.readlink() == src
        assert dst.read_text() == "source content"
    
    def test_copies_in_copy_mode(self, tmp_path):
        """Should copy file when copy_mode=True."""
        src = tmp_path / "source.txt"
        src.write_text("source content")
        
        dst = tmp_path / "dest" / "target.txt"
        
        install.place_file(src, dst, copy_mode=True)
        
        assert dst.exists()
        assert not dst.is_symlink()
        assert dst.read_text() == "source content"
    
    def test_copies_directory_in_copy_mode(self, tmp_path):
        """Should copy directory recursively in copy mode."""
        src = tmp_path / "source_dir"
        src.mkdir()
        (src / "file1.txt").write_text("content1")
        (src / "subdir").mkdir()
        (src / "subdir" / "file2.txt").write_text("content2")
        
        dst = tmp_path / "dest_dir"
        
        install.place_file(src, dst, copy_mode=True)
        
        assert dst.exists()
        assert dst.is_dir()
        assert not dst.is_symlink()
        assert (dst / "file1.txt").read_text() == "content1"
        assert (dst / "subdir" / "file2.txt").read_text() == "content2"
    
    def test_replaces_existing_symlink(self, tmp_path):
        """Should replace existing symlink."""
        old_src = tmp_path / "old_source.txt"
        old_src.write_text("old content")
        
        src = tmp_path / "new_source.txt"
        src.write_text("new content")
        
        dst = tmp_path / "target.txt"
        dst.symlink_to(old_src)
        
        install.place_file(src, dst)
        
        assert dst.is_symlink()
        assert dst.readlink() == src
        assert dst.read_text() == "new content"
    
    def test_skips_existing_non_symlink(self, tmp_path, capsys):
        """Should skip existing non-symlink files."""
        src = tmp_path / "source.txt"
        src.write_text("source content")
        
        dst = tmp_path / "existing.txt"
        dst.write_text("existing content")
        
        install.place_file(src, dst)
        
        # File should remain unchanged
        assert dst.read_text() == "existing content"
        assert not dst.is_symlink()
        
        # Should print skip message
        captured = capsys.readouterr()
        assert "SKIP" in captured.out
        assert "not a symlink" in captured.out
    
    def test_replaces_existing_symlink_in_copy_mode(self, tmp_path):
        """Should replace existing symlink with copy in copy mode."""
        old_src = tmp_path / "old_source.txt"
        old_src.write_text("old content")
        
        src = tmp_path / "new_source.txt"
        src.write_text("new content")
        
        dst = tmp_path / "target.txt"
        dst.symlink_to(old_src)
        
        install.place_file(src, dst, copy_mode=True)
        
        assert dst.exists()
        assert not dst.is_symlink()
        assert dst.read_text() == "new content"


class TestPlaceDirContents:
    """Test place_dir_contents function."""
    
    def test_places_matching_files(self, tmp_path):
        """Should place all files matching pattern."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "file1.md").write_text("content1")
        (src_dir / "file2.md").write_text("content2")
        (src_dir / "file3.txt").write_text("content3")  # Should be ignored
        
        dst_dir = tmp_path / "dst"
        
        install.place_dir_contents(src_dir, dst_dir, "*.md")
        
        assert (dst_dir / "file1.md").exists()
        assert (dst_dir / "file2.md").exists()
        assert not (dst_dir / "file3.txt").exists()
        
        assert (dst_dir / "file1.md").is_symlink()
        assert (dst_dir / "file2.md").is_symlink()


class TestSkillInstallation:
    """Test skill installation functions."""
    
    def test_install_skills_global(self, mock_paths, tmp_path, monkeypatch):
        """Should install skills globally."""
        # Setup skills
        skill1 = tmp_path / "skill-one"
        skill1.mkdir()
        (skill1 / "SKILL.md").write_text("skill content")
        
        skill2 = tmp_path / "skill-two" 
        skill2.mkdir()
        (skill2 / "SKILL.md").write_text("skill content")
        
        with patch('agent_notes.install.find_skill_dirs', return_value=[skill1, skill2]):
            install.install_skills_global()
        
        # Check symlinks were created
        claude_skills = mock_paths['claude'] / "skills"
        opencode_skills = mock_paths['opencode'] / "skills"
        agents_skills = mock_paths['agents'] / "skills"
        
        assert (claude_skills / "skill-one").is_symlink()
        assert (claude_skills / "skill-two").is_symlink()
        assert (opencode_skills / "skill-one").is_symlink()
        assert (opencode_skills / "skill-two").is_symlink()
        assert (agents_skills / "skill-one").is_symlink()
        assert (agents_skills / "skill-two").is_symlink()
    
    def test_install_skills_local(self, tmp_path, monkeypatch):
        """Should install skills locally."""
        # Setup skills
        skill1 = tmp_path / "skill-one"
        skill1.mkdir()
        (skill1 / "SKILL.md").write_text("skill content")
        
        # Change to temp directory
        original_cwd = Path.cwd()
        monkeypatch.chdir(tmp_path)
        
        try:
            with patch('agent_notes.install.find_skill_dirs', return_value=[skill1]):
                install.install_skills_local()
            
            # Check local symlinks were created
            assert (tmp_path / ".claude" / "skills" / "skill-one").is_symlink()
            assert (tmp_path / ".opencode" / "skills" / "skill-one").is_symlink()
        finally:
            monkeypatch.chdir(original_cwd)


class TestAgentInstallation:
    """Test agent installation functions."""
    
    def test_install_agents_global(self, mock_paths, tmp_path, monkeypatch):
        """Should install agents globally."""
        # Setup agent files
        claude_agents_dir = tmp_path / "dist" / "cli" / "claude" / "agents"
        claude_agents_dir.mkdir(parents=True)
        (claude_agents_dir / "agent1.md").write_text("claude agent1")
        (claude_agents_dir / "agent2.md").write_text("claude agent2")
        
        opencode_agents_dir = tmp_path / "dist" / "cli" / "opencode" / "agents"
        opencode_agents_dir.mkdir(parents=True)
        (opencode_agents_dir / "agent1.md").write_text("opencode agent1")
        (opencode_agents_dir / "agent2.md").write_text("opencode agent2")
        
        monkeypatch.setattr(install, 'DIST_CLAUDE_DIR', tmp_path / "dist" / "cli" / "claude")
        monkeypatch.setattr(install, 'DIST_OPENCODE_DIR', tmp_path / "dist" / "cli" / "opencode")
        
        install.install_agents_global()
        
        # Check symlinks were created
        claude_home = mock_paths['claude']
        opencode_home = mock_paths['opencode']
        
        assert (claude_home / "agents" / "agent1.md").is_symlink()
        assert (claude_home / "agents" / "agent2.md").is_symlink()
        assert (opencode_home / "agents" / "agent1.md").is_symlink()
        assert (opencode_home / "agents" / "agent2.md").is_symlink()
    
    def test_install_agents_local(self, tmp_path, monkeypatch):
        """Should install agents locally."""
        # Setup agent files
        claude_agents_dir = tmp_path / "dist" / "cli" / "claude" / "agents"
        claude_agents_dir.mkdir(parents=True)
        (claude_agents_dir / "agent1.md").write_text("claude agent1")
        
        opencode_agents_dir = tmp_path / "dist" / "cli" / "opencode" / "agents"
        opencode_agents_dir.mkdir(parents=True)
        (opencode_agents_dir / "agent1.md").write_text("opencode agent1")
        
        monkeypatch.setattr(install, 'DIST_CLAUDE_DIR', tmp_path / "dist" / "cli" / "claude")
        monkeypatch.setattr(install, 'DIST_OPENCODE_DIR', tmp_path / "dist" / "cli" / "opencode")
        
        # Change to temp directory
        original_cwd = Path.cwd()
        monkeypatch.chdir(tmp_path)
        
        try:
            install.install_agents_local()
            
            # Check local symlinks were created
            assert (tmp_path / ".claude" / "agents" / "agent1.md").is_symlink()
            assert (tmp_path / ".opencode" / "agents" / "agent1.md").is_symlink()
        finally:
            monkeypatch.chdir(original_cwd)


class TestRulesInstallation:
    """Test rules and global config installation."""
    
    def test_install_rules_global(self, mock_paths, tmp_path, monkeypatch):
        """Should install global config and rules."""
        # Setup files
        dist_claude_dir = tmp_path / "dist" / "cli" / "claude"
        dist_claude_dir.mkdir(parents=True)
        (dist_claude_dir / "CLAUDE.md").write_text("Claude global config")
        
        dist_opencode_dir = tmp_path / "dist" / "cli" / "opencode"
        dist_opencode_dir.mkdir(parents=True)
        (dist_opencode_dir / "AGENTS.md").write_text("OpenCode config")
        
        dist_github_dir = tmp_path / "dist" / "cli" / "github"
        dist_github_dir.mkdir(parents=True)
        (dist_github_dir / "copilot-instructions.md").write_text("Copilot config")
        
        dist_rules_dir = tmp_path / "dist" / "rules"
        dist_rules_dir.mkdir(parents=True)
        (dist_rules_dir / "rule1.md").write_text("Rule 1")
        (dist_rules_dir / "rule2.md").write_text("Rule 2")
        
        monkeypatch.setattr(install, 'DIST_CLAUDE_DIR', dist_claude_dir)
        monkeypatch.setattr(install, 'DIST_OPENCODE_DIR', dist_opencode_dir)
        monkeypatch.setattr(install, 'DIST_GITHUB_DIR', dist_github_dir)
        monkeypatch.setattr(install, 'DIST_RULES_DIR', dist_rules_dir)
        
        install.install_rules_global()
        
        # Check global config files
        assert (mock_paths['claude'] / "CLAUDE.md").is_symlink()
        assert (mock_paths['opencode'] / "AGENTS.md").is_symlink()
        assert (mock_paths['github'] / "copilot-instructions.md").is_symlink()
        
        # Check rules
        assert (mock_paths['claude'] / "rules" / "rule1.md").is_symlink()
        assert (mock_paths['claude'] / "rules" / "rule2.md").is_symlink()
    
    def test_install_rules_local(self, tmp_path, monkeypatch):
        """Should install local config and rules."""
        # Setup files
        dist_claude_dir = tmp_path / "dist" / "cli" / "claude"
        dist_claude_dir.mkdir(parents=True)
        (dist_claude_dir / "CLAUDE.md").write_text("Claude global config")
        
        dist_opencode_dir = tmp_path / "dist" / "cli" / "opencode"
        dist_opencode_dir.mkdir(parents=True)
        (dist_opencode_dir / "AGENTS.md").write_text("OpenCode config")
        
        dist_rules_dir = tmp_path / "dist" / "rules"
        dist_rules_dir.mkdir(parents=True)
        (dist_rules_dir / "rule1.md").write_text("Rule 1")
        
        monkeypatch.setattr(install, 'DIST_CLAUDE_DIR', dist_claude_dir)
        monkeypatch.setattr(install, 'DIST_OPENCODE_DIR', dist_opencode_dir)
        monkeypatch.setattr(install, 'DIST_RULES_DIR', dist_rules_dir)
        
        # Change to temp directory
        original_cwd = Path.cwd()
        monkeypatch.chdir(tmp_path)
        
        try:
            install.install_rules_local()
            
            # Check local config files
            assert (tmp_path / "CLAUDE.md").is_symlink()
            assert (tmp_path / "AGENTS.md").is_symlink()
            assert (tmp_path / ".claude" / "rules" / "rule1.md").is_symlink()
        finally:
            monkeypatch.chdir(original_cwd)


class TestUninstall:
    """Test uninstall functions."""
    
    def test_remove_symlink(self, tmp_path, capsys):
        """Should remove symlink and print message."""
        src = tmp_path / "source.txt"
        src.write_text("content")
        
        link = tmp_path / "link.txt"
        link.symlink_to(src)
        
        install.remove_symlink(link)
        
        assert not link.exists()
        captured = capsys.readouterr()
        assert "REMOVED" in captured.out
    
    def test_skip_non_symlink(self, tmp_path, capsys):
        """Should skip non-symlink files."""
        regular_file = tmp_path / "regular.txt"
        regular_file.write_text("content")
        
        install.remove_symlink(regular_file)
        
        assert regular_file.exists()
        assert regular_file.read_text() == "content"
        captured = capsys.readouterr()
        assert "SKIP" in captured.out


class TestCountFunctions:
    """Test counting functions."""
    
    def test_count_skills(self, tmp_path, monkeypatch):
        """Should count skill directories."""
        skill1 = tmp_path / "skill1"
        skill1.mkdir()
        (skill1 / "SKILL.md").write_text("skill")
        
        skill2 = tmp_path / "skill2"
        skill2.mkdir()
        (skill2 / "SKILL.md").write_text("skill")
        
        with patch('agent_notes.install.find_skill_dirs', return_value=[skill1, skill2]):
            count = install.count_skills()
            assert count == 2
    
    def test_count_agents_claude(self, tmp_path, monkeypatch):
        """Should count Claude agent files."""
        agents_dir = tmp_path / "dist" / "cli" / "claude" / "agents"
        agents_dir.mkdir(parents=True)
        (agents_dir / "agent1.md").write_text("agent1")
        (agents_dir / "agent2.md").write_text("agent2")
        (agents_dir / "not_agent.txt").write_text("not an agent")
        
        monkeypatch.setattr(install, 'DIST_CLAUDE_DIR', tmp_path / "dist" / "cli" / "claude")
        
        count = install.count_agents_claude()
        assert count == 2
    
    def test_count_agents_opencode(self, tmp_path, monkeypatch):
        """Should count OpenCode agent files."""
        agents_dir = tmp_path / "dist" / "cli" / "opencode" / "agents"
        agents_dir.mkdir(parents=True)
        (agents_dir / "agent1.md").write_text("agent1")
        (agents_dir / "agent2.md").write_text("agent2")
        
        monkeypatch.setattr(install, 'DIST_OPENCODE_DIR', tmp_path / "dist" / "cli" / "opencode")
        
        count = install.count_agents_opencode()
        assert count == 2
    
    def test_count_global(self, tmp_path, monkeypatch):
        """Should count global config files."""
        dist_claude_dir = tmp_path / "dist" / "cli" / "claude"
        dist_claude_dir.mkdir(parents=True)
        (dist_claude_dir / "CLAUDE.md").write_text("claude")
        
        dist_opencode_dir = tmp_path / "dist" / "cli" / "opencode"
        dist_opencode_dir.mkdir(parents=True)
        (dist_opencode_dir / "AGENTS.md").write_text("agents")
        
        dist_github_dir = tmp_path / "dist" / "cli" / "github"
        dist_github_dir.mkdir(parents=True)
        (dist_github_dir / "copilot-instructions.md").write_text("copilot")
        
        dist_rules_dir = tmp_path / "dist" / "rules"
        dist_rules_dir.mkdir(parents=True)
        (dist_rules_dir / "rule1.md").write_text("rule1")
        (dist_rules_dir / "rule2.md").write_text("rule2")
        
        monkeypatch.setattr(install, 'DIST_CLAUDE_DIR', dist_claude_dir)
        monkeypatch.setattr(install, 'DIST_OPENCODE_DIR', dist_opencode_dir)
        monkeypatch.setattr(install, 'DIST_GITHUB_DIR', dist_github_dir)
        monkeypatch.setattr(install, 'DIST_RULES_DIR', dist_rules_dir)
        
        count = install.count_global()
        assert count == 5  # CLAUDE.md + AGENTS.md + copilot-instructions.md + rule1.md + rule2.md


class TestInstallFunction:
    """Test main install function."""
    
    def test_rejects_copy_without_local(self, capsys):
        """Should reject --copy without --local."""
        install.install(local=False, copy=True)
        
        captured = capsys.readouterr()
        assert "Error: --copy is only valid with --local installs" in captured.out
    
    def test_runs_build_first(self, mock_paths, monkeypatch):
        """Should run build before installing."""
        build_called = False
        
        def mock_build():
            nonlocal build_called
            build_called = True
            
        with patch('agent_notes.install.build', mock_build):
            with patch('agent_notes.install.install_skills_global'):
                with patch('agent_notes.install.install_agents_global'):
                    with patch('agent_notes.install.install_rules_global'):
                        install.install(local=False, copy=False)
        
        assert build_called
    
    def test_handles_build_failure(self, mock_paths, monkeypatch, capsys):
        """Should handle build failure gracefully."""
        def mock_build():
            raise Exception("Build failed")
            
        with patch('agent_notes.install.build', mock_build):
            install.install(local=False, copy=False)
        
        captured = capsys.readouterr()
        assert "Build failed" in captured.out


class TestShowInfo:
    """Test show_info function."""
    
    def test_shows_version_and_counts(self, mock_paths, tmp_path, monkeypatch, capsys):
        """Should show version and component counts."""
        # Mock version
        with patch('agent_notes.install.get_version', return_value="1.2.3"):
            # Mock counts
            with patch('agent_notes.install.count_skills', return_value=5):
                with patch('agent_notes.install.count_agents_claude', return_value=10):
                    with patch('agent_notes.install.count_agents_opencode', return_value=10):
                        with patch('agent_notes.install.count_global', return_value=3):
                            install.show_info()
        
        captured = capsys.readouterr()
        assert "agent-notes 1.2.3" in captured.out
        assert "Skills:              5" in captured.out
        assert "Agents (Claude):     10" in captured.out
        assert "Agents (OpenCode):   10" in captured.out
        assert "Global config:       3 files" in captured.out
        assert "Claude Code:   ~/.claude/" in captured.out
        assert "OpenCode:      ~/.config/opencode/" in captured.out
    
    def test_shows_install_status(self, mock_paths, tmp_path, monkeypatch, capsys):
        """Should show installation status."""
        # Create some agents to simulate installation
        claude_agents = mock_paths['claude'] / "agents"
        claude_agents.mkdir()
        (claude_agents / "test-agent.md").write_text("test")
        
        with patch('agent_notes.install.get_version', return_value="1.0.0"):
            with patch('agent_notes.install.count_skills', return_value=0):
                with patch('agent_notes.install.count_agents_claude', return_value=0):
                    with patch('agent_notes.install.count_agents_opencode', return_value=0):
                        with patch('agent_notes.install.count_global', return_value=0):
                            install.show_info()
        
        captured = capsys.readouterr()
        assert "installed" in captured.out  # Should detect global installation