"""Test doctor module."""
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import os

import agent_notes.doctor as doctor


class TestIssueAndFixAction:
    """Test Issue and FixAction classes."""
    
    def test_issue_creation(self):
        """Should create issue with type, file, and message."""
        issue = doctor.Issue("stale", "/path/to/file", "Test message")
        assert issue.type == "stale"
        assert issue.file == "/path/to/file"
        assert issue.message == "Test message"
    
    def test_fix_action_creation(self):
        """Should create fix action with action, file, and details."""
        action = doctor.FixAction("DELETE", "/path/to/file", "Test details")
        assert action.action == "DELETE"
        assert action.file == "/path/to/file"
        assert action.details == "Test details"


class TestFindDistSource:
    """Test _find_dist_source function."""
    
    def test_finds_skill_source(self, tmp_path, monkeypatch):
        """Should find skill source directory."""
        # Create dist skill directory
        dist_skills = tmp_path / "dist" / "skills"
        dist_skills.mkdir(parents=True)
        skill_dir = dist_skills / "test-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("skill content")
        
        monkeypatch.setattr(doctor, 'DIST_SKILLS_DIR', dist_skills)
        
        # Test global skill path
        symlink = Path.home() / ".claude" / "skills" / "test-skill"
        source = doctor._find_dist_source(symlink, "global")
        
        assert source == skill_dir
    
    def test_finds_agent_source(self, tmp_path, monkeypatch):
        """Should find agent source file."""
        # Create dist agent file
        dist_claude = tmp_path / "dist" / "claude"
        dist_claude.mkdir(parents=True)
        agents_dir = dist_claude / "agents"
        agents_dir.mkdir()
        agent_file = agents_dir / "test-agent.md"
        agent_file.write_text("agent content")
        
        monkeypatch.setattr(doctor, 'DIST_CLAUDE_DIR', dist_claude)
        monkeypatch.setattr(doctor, 'DIST_OPENCODE_DIR', tmp_path / "dist" / "opencode")
        
        # Test global agent path
        symlink = Path.home() / ".claude" / "agents" / "test-agent.md"
        source = doctor._find_dist_source(symlink, "global")
        
        assert source == agent_file
    
    def test_finds_config_source(self, tmp_path, monkeypatch):
        """Should find config source files."""
        # Create dist config files
        dist_claude = tmp_path / "dist" / "claude"
        dist_claude.mkdir(parents=True)
        claude_config = dist_claude / "CLAUDE.md"
        claude_config.write_text("claude config")
        
        dist_opencode = tmp_path / "dist" / "opencode"
        dist_opencode.mkdir(parents=True)
        agents_config = dist_opencode / "AGENTS.md"
        agents_config.write_text("agents config")
        
        monkeypatch.setattr(doctor, 'DIST_CLAUDE_DIR', dist_claude)
        monkeypatch.setattr(doctor, 'DIST_OPENCODE_DIR', dist_opencode)
        
        # Test CLAUDE.md mapping
        symlink = Path.home() / ".claude" / "CLAUDE.md"
        source = doctor._find_dist_source(symlink, "global")
        assert source == claude_config
        
        # Test AGENTS.md mapping
        symlink = Path.home() / ".config" / "opencode" / "AGENTS.md"
        source = doctor._find_dist_source(symlink, "global")
        assert source == agents_config
    
    def test_returns_none_when_no_source(self, tmp_path, monkeypatch):
        """Should return None when no matching source exists."""
        # Setup empty dist directories
        dist_skills = tmp_path / "dist" / "skills"
        dist_skills.mkdir(parents=True)
        
        monkeypatch.setattr(doctor, 'DIST_SKILLS_DIR', dist_skills)
        
        # Test with non-existent skill
        symlink = Path.home() / ".claude" / "skills" / "nonexistent-skill"
        source = doctor._find_dist_source(symlink, "global")
        
        assert source is None
    
    def test_finds_rules_source(self, tmp_path, monkeypatch):
        """Should find rules source files."""
        # Create dist rule file
        dist_rules = tmp_path / "dist" / "rules"
        dist_rules.mkdir(parents=True)
        rule_file = dist_rules / "test-rule.md"
        rule_file.write_text("rule content")
        
        monkeypatch.setattr(doctor, 'DIST_RULES_DIR', dist_rules)
        
        # Test global rule path
        symlink = Path.home() / ".claude" / "rules" / "test-rule.md"
        source = doctor._find_dist_source(symlink, "global")
        
        assert source == rule_file
    
    def test_local_scope_mappings(self, tmp_path, monkeypatch):
        """Should handle local scope mappings."""
        # Create dist skill directory
        dist_skills = tmp_path / "dist" / "skills"
        dist_skills.mkdir(parents=True)
        skill_dir = dist_skills / "local-skill"
        skill_dir.mkdir()
        
        monkeypatch.setattr(doctor, 'DIST_SKILLS_DIR', dist_skills)
        
        # Test local skill path
        symlink = Path(".claude") / "skills" / "local-skill"
        source = doctor._find_dist_source(symlink, "local")
        
        assert source == skill_dir


class TestCheckStaleFiles:
    """Test symlink utility functions."""
    
    def test_resolve_symlink(self, tmp_path):
        """Should resolve symlink target."""
        src = tmp_path / "source.txt"
        src.write_text("content")
        
        link = tmp_path / "link.txt"
        link.symlink_to(src)
        
        target = doctor.resolve_symlink(link)
        assert target == src
    
    def test_resolve_non_symlink(self, tmp_path):
        """Should return None for non-symlink."""
        regular_file = tmp_path / "regular.txt"
        regular_file.write_text("content")
        
        target = doctor.resolve_symlink(regular_file)
        assert target is None
    
    def test_symlink_target_exists(self, tmp_path):
        """Should check if symlink target exists."""
        src = tmp_path / "source.txt"
        src.write_text("content")
        
        link = tmp_path / "link.txt"
        link.symlink_to(src)
        
        assert doctor.symlink_target_exists(link)
        
        # Remove source and check again
        src.unlink()
        assert not doctor.symlink_target_exists(link)
    
    def test_symlink_target_exists_relative(self, tmp_path, monkeypatch):
        """Should handle relative symlink targets."""
        # Change to temp directory
        monkeypatch.chdir(tmp_path)
        
        src = tmp_path / "source.txt"
        src.write_text("content")
        
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        
        link = subdir / "link.txt"
        link.symlink_to("../source.txt")  # Relative path
        
        assert doctor.symlink_target_exists(link)
    
    def test_symlink_target_exists_non_symlink(self, tmp_path):
        """Should return False for non-symlink."""
        regular_file = tmp_path / "regular.txt"
        regular_file.write_text("content")
        
        assert not doctor.symlink_target_exists(regular_file)


class TestFilesDiffer:
    """Test files_differ function."""
    
    def test_identical_files(self, tmp_path):
        """Should return False for identical files."""
        file1 = tmp_path / "file1.txt"
        file1.write_text("same content")
        
        file2 = tmp_path / "file2.txt"
        file2.write_text("same content")
        
        assert not doctor.files_differ(file1, file2)
    
    def test_different_files(self, tmp_path):
        """Should return True for different files."""
        file1 = tmp_path / "file1.txt"
        file1.write_text("content 1")
        
        file2 = tmp_path / "file2.txt" 
        file2.write_text("content 2")
        
        assert doctor.files_differ(file1, file2)
    
    def test_missing_file(self, tmp_path):
        """Should return True for missing file."""
        file1 = tmp_path / "file1.txt"
        file1.write_text("content")
        
        file2 = tmp_path / "missing.txt"
        
        assert doctor.files_differ(file1, file2)


class TestCheckStaleFiles:
    """Test check_stale_files function."""
    
    def test_detects_stale_agents(self, tmp_path, monkeypatch):
        """Should detect stale agent files."""
        # Setup mock paths
        home_claude = tmp_path / "home" / ".claude"
        home_claude.mkdir(parents=True)
        
        # Create installed agent file
        agents_dir = home_claude / "agents"
        agents_dir.mkdir()
        (agents_dir / "old-agent.md").write_text("old agent")
        
        # Setup mock dist directory (no matching source)
        dist_claude = tmp_path / "dist" / "claude"
        dist_claude.mkdir(parents=True)
        (dist_claude / "agents").mkdir()
        # Note: no old-agent.md in source
        
        # Mock Path.home() and DIST dirs
        with patch('pathlib.Path.home', return_value=tmp_path / "home"):
            monkeypatch.setattr(doctor, 'DIST_CLAUDE_DIR', dist_claude)
            
            issues = []
            fix_actions = []
            
            doctor.check_stale_files("global", issues, fix_actions)
            
            assert len(issues) == 1
            assert issues[0].type == "stale"
            assert "old-agent.md" in issues[0].file
            
            assert len(fix_actions) == 1
            assert fix_actions[0].action == "DELETE"
    
    def test_detects_stale_skills(self, tmp_path, monkeypatch):
        """Should detect stale skill directories."""
        # Setup mock paths
        home_claude = tmp_path / "home" / ".claude"
        home_claude.mkdir(parents=True)
        
        # Create installed skill
        skills_dir = home_claude / "skills"
        skills_dir.mkdir()
        old_skill = skills_dir / "old-skill"
        old_skill.mkdir()
        (old_skill / "SKILL.md").write_text("old skill")
        
        # Mock Path.home() and DIST_SKILLS_DIR (no matching source skill)
        with patch('pathlib.Path.home', return_value=tmp_path / "home"):
            monkeypatch.setattr(doctor, 'DIST_SKILLS_DIR', tmp_path / "dist" / "skills")
            
            issues = []
            fix_actions = []
            
            doctor.check_stale_files("global", issues, fix_actions)
            
            assert len(issues) == 1
            assert issues[0].type == "stale"
            assert "old-skill" in issues[0].file
    
    def test_local_mode(self, tmp_path, monkeypatch):
        """Should check local directories in local mode."""
        # Change to temp directory
        monkeypatch.chdir(tmp_path)
        
        # Create local installation
        local_claude = tmp_path / ".claude"
        local_claude.mkdir()
        agents_dir = local_claude / "agents"
        agents_dir.mkdir()
        (agents_dir / "local-agent.md").write_text("local agent")
        
        # Setup empty dist directory
        dist_claude = tmp_path / "dist" / "claude"
        dist_claude.mkdir(parents=True)
        (dist_claude / "agents").mkdir()
        
        monkeypatch.setattr(doctor, 'DIST_CLAUDE_DIR', dist_claude)
        
        issues = []
        fix_actions = []
        
        doctor.check_stale_files("local", issues, fix_actions)
        
        assert len(issues) == 1
        assert issues[0].type == "stale"


class TestCheckBrokenSymlinks:
    """Test check_broken_symlinks function."""
    
    def test_detects_broken_symlinks(self, tmp_path, monkeypatch):
        """Should detect broken symlinks."""
        # Create broken symlink
        home_claude = tmp_path / "home" / ".claude"
        home_claude.mkdir(parents=True)
        
        agents_dir = home_claude / "agents"
        agents_dir.mkdir()
        
        # Create symlink to non-existent target
        broken_link = agents_dir / "broken-agent.md"
        broken_link.symlink_to("/nonexistent/path")
        
        with patch('pathlib.Path.home', return_value=tmp_path / "home"):
            issues = []
            fix_actions = []
            
            doctor.check_broken_symlinks("global", issues, fix_actions)
            
            assert len(issues) == 1
            assert issues[0].type == "broken"
            assert "broken-agent.md" in issues[0].file
            
            assert len(fix_actions) == 1
            assert fix_actions[0].action == "DELETE"
    
    def test_ignores_valid_symlinks(self, tmp_path, monkeypatch):
        """Should ignore valid symlinks."""
        # Create valid symlink
        src = tmp_path / "source.txt"
        src.write_text("content")
        
        home_claude = tmp_path / "home" / ".claude"
        home_claude.mkdir(parents=True)
        
        agents_dir = home_claude / "agents"
        agents_dir.mkdir()
        
        valid_link = agents_dir / "valid-agent.md"
        valid_link.symlink_to(src)
        
        with patch('pathlib.Path.home', return_value=tmp_path / "home"):
            issues = []
            fix_actions = []
            
            doctor.check_broken_symlinks("global", issues, fix_actions)
            
            assert len(issues) == 0
            assert len(fix_actions) == 0
    
    def test_emits_relink_when_source_exists(self, tmp_path, monkeypatch):
        """Should emit RELINK action when source exists."""
        # Create broken symlink
        home_claude = tmp_path / "home" / ".claude"
        home_claude.mkdir(parents=True)
        agents_dir = home_claude / "agents"
        agents_dir.mkdir()
        
        broken_link = agents_dir / "test-agent.md"
        broken_link.symlink_to("/nonexistent/path")
        
        # Create source that exists
        dist_claude = tmp_path / "dist" / "claude"
        dist_claude.mkdir(parents=True)
        dist_agents_dir = dist_claude / "agents"
        dist_agents_dir.mkdir()
        source_file = dist_agents_dir / "test-agent.md"
        source_file.write_text("agent content")
        
        with patch('pathlib.Path.home', return_value=tmp_path / "home"):
            monkeypatch.setattr(doctor, 'DIST_CLAUDE_DIR', dist_claude)
            monkeypatch.setattr(doctor, 'DIST_OPENCODE_DIR', tmp_path / "dist" / "opencode")
            
            issues = []
            fix_actions = []
            
            doctor.check_broken_symlinks("global", issues, fix_actions)
            
            assert len(issues) == 1
            assert issues[0].type == "broken"
            
            assert len(fix_actions) == 1
            assert fix_actions[0].action == "RELINK"
            assert str(source_file) in fix_actions[0].details
    
    def test_emits_delete_when_no_source(self, tmp_path, monkeypatch):
        """Should emit DELETE action when no source exists."""
        # Create broken symlink
        home_claude = tmp_path / "home" / ".claude"
        home_claude.mkdir(parents=True)
        agents_dir = home_claude / "agents"
        agents_dir.mkdir()
        
        broken_link = agents_dir / "orphan-agent.md"
        broken_link.symlink_to("/nonexistent/path")
        
        # Setup empty dist directories (no source exists)
        dist_claude = tmp_path / "dist" / "claude"
        dist_claude.mkdir(parents=True)
        (dist_claude / "agents").mkdir()
        
        with patch('pathlib.Path.home', return_value=tmp_path / "home"):
            monkeypatch.setattr(doctor, 'DIST_CLAUDE_DIR', dist_claude)
            monkeypatch.setattr(doctor, 'DIST_OPENCODE_DIR', tmp_path / "dist" / "opencode")
            
            issues = []
            fix_actions = []
            
            doctor.check_broken_symlinks("global", issues, fix_actions)
            
            assert len(issues) == 1
            assert issues[0].type == "broken"
            
            assert len(fix_actions) == 1
            assert fix_actions[0].action == "DELETE"
            assert "no source available" in fix_actions[0].details


class TestCheckShadowedFiles:
    """Test check_shadowed_files function."""
    
    def test_detects_shadowed_files(self, tmp_path, monkeypatch):
        """Should detect regular files that should be symlinks."""
        # Setup regular file where symlink expected
        home_claude = tmp_path / "home" / ".claude"
        home_claude.mkdir(parents=True)
        
        # Create regular file instead of symlink
        (home_claude / "CLAUDE.md").write_text("regular file")
        
        # Setup corresponding source file
        dist_claude = tmp_path / "dist" / "claude"
        dist_claude.mkdir(parents=True)
        (dist_claude / "CLAUDE.md").write_text("source file")
        
        with patch('pathlib.Path.home', return_value=tmp_path / "home"):
            monkeypatch.setattr(doctor, 'DIST_CLAUDE_DIR', dist_claude)
            
            issues = []
            fix_actions = []
            
            doctor.check_shadowed_files("global", issues, fix_actions)
            
            assert len(issues) == 1
            assert issues[0].type == "shadowed"
            assert "CLAUDE.md" in issues[0].file
            
            assert len(fix_actions) == 1
            assert fix_actions[0].action == "RELINK"
    
    def test_ignores_symlinks(self, tmp_path, monkeypatch):
        """Should ignore existing symlinks."""
        # Setup valid symlink
        src = tmp_path / "source.txt"
        src.write_text("source")
        
        home_claude = tmp_path / "home" / ".claude"
        home_claude.mkdir(parents=True)
        
        link = home_claude / "CLAUDE.md"
        link.symlink_to(src)
        
        dist_claude = tmp_path / "dist" / "claude"
        dist_claude.mkdir(parents=True)
        (dist_claude / "CLAUDE.md").write_text("source")
        
        with patch('pathlib.Path.home', return_value=tmp_path / "home"):
            monkeypatch.setattr(doctor, 'DIST_CLAUDE_DIR', dist_claude)
            
            issues = []
            fix_actions = []
            
            doctor.check_shadowed_files("global", issues, fix_actions)
            
            assert len(issues) == 0
            assert len(fix_actions) == 0


class TestCheckMissingFiles:
    """Test check_missing_files function."""
    
    def test_detects_missing_files(self, tmp_path, monkeypatch):
        """Should detect missing files that should be installed."""
        # Setup source file but no installed file
        dist_claude = tmp_path / "dist" / "claude"
        dist_claude.mkdir(parents=True)
        (dist_claude / "CLAUDE.md").write_text("source content")
        
        # Create empty directories to avoid finding real files
        dist_opencode = tmp_path / "dist" / "opencode"
        dist_opencode.mkdir(parents=True)
        dist_github = tmp_path / "dist" / "github"
        dist_github.mkdir(parents=True)
        dist_rules = tmp_path / "dist" / "rules"
        dist_rules.mkdir(parents=True)
        dist_skills = tmp_path / "dist" / "skills"
        dist_skills.mkdir(parents=True)
        
        # Setup home directories
        home_claude = tmp_path / "home" / ".claude"
        home_claude.mkdir(parents=True)
        
        home_opencode = tmp_path / "home" / ".config" / "opencode"
        home_opencode.mkdir(parents=True)
        (home_opencode / "AGENTS.md").write_text("existing")
        
        home_github = tmp_path / "home" / ".github"
        home_github.mkdir(parents=True)
        (home_github / "copilot-instructions.md").write_text("existing")
        
        # Patch module-level constants used by new helpers
        monkeypatch.setattr(doctor, 'CLAUDE_HOME', home_claude)
        monkeypatch.setattr(doctor, 'OPENCODE_HOME', home_opencode)
        monkeypatch.setattr(doctor, 'GITHUB_HOME', home_github)
        monkeypatch.setattr(doctor, 'DIST_CLAUDE_DIR', dist_claude)
        monkeypatch.setattr(doctor, 'DIST_OPENCODE_DIR', dist_opencode)
        monkeypatch.setattr(doctor, 'DIST_GITHUB_DIR', dist_github)
        monkeypatch.setattr(doctor, 'DIST_RULES_DIR', dist_rules)
        monkeypatch.setattr(doctor, 'DIST_SKILLS_DIR', dist_skills)
        
        issues = []
        fix_actions = []
        
        doctor.check_missing_files("global", issues, fix_actions)
        
        # Should detect missing CLAUDE.md config
        missing_issues = [i for i in issues if i.type == "missing" and "CLAUDE.md" in i.file]
        assert len(missing_issues) == 1
        
        install_actions = [a for a in fix_actions if a.action == "INSTALL" and "CLAUDE.md" in a.file]
        assert len(install_actions) == 1
    
    def test_skips_local_mode(self, tmp_path):
        """Should skip missing file checks in local mode."""
        issues = []
        fix_actions = []
        
        doctor.check_missing_files("local", issues, fix_actions)
        
        assert len(issues) == 0
        assert len(fix_actions) == 0


class TestCheckContentDrift:
    """Test check_content_drift function."""
    
    def test_detects_content_drift(self, tmp_path, monkeypatch):
        """Should detect when copied files differ from source."""
        # Setup regular file (not symlink) with different content
        home_claude = tmp_path / "home" / ".claude"
        home_claude.mkdir(parents=True)
        (home_claude / "CLAUDE.md").write_text("modified content")
        
        # Setup source with different content  
        dist_claude = tmp_path / "dist" / "claude"
        dist_claude.mkdir(parents=True)
        (dist_claude / "CLAUDE.md").write_text("original content")
        
        with patch('pathlib.Path.home', return_value=tmp_path / "home"):
            monkeypatch.setattr(doctor, 'DIST_CLAUDE_DIR', dist_claude)
            
            issues = []
            fix_actions = []
            
            doctor.check_content_drift("global", issues, fix_actions)
            
            assert len(issues) == 1
            assert issues[0].type == "drift"
            assert "CLAUDE.md" in issues[0].file
    
    def test_ignores_symlinks(self, tmp_path, monkeypatch):
        """Should ignore symlinks even if content differs."""
        # Setup symlink
        src = tmp_path / "source.txt"
        src.write_text("source content")
        
        home_claude = tmp_path / "home" / ".claude"
        home_claude.mkdir(parents=True)
        
        link = home_claude / "CLAUDE.md"
        link.symlink_to(src)
        
        # Different source file
        dist_claude = tmp_path / "dist" / "claude"
        dist_claude.mkdir(parents=True)
        (dist_claude / "CLAUDE.md").write_text("different content")
        
        with patch('pathlib.Path.home', return_value=tmp_path / "home"):
            monkeypatch.setattr(doctor, 'DIST_CLAUDE_DIR', dist_claude)
            
            issues = []
            fix_actions = []
            
            doctor.check_content_drift("global", issues, fix_actions)
            
            assert len(issues) == 0


class TestDoFix:
    """Test updated do_fix function."""
    
    def test_deletes_broken_symlinks(self, tmp_path, capsys):
        """Should delete broken symlinks."""
        # Create broken symlink
        broken_link = tmp_path / "broken-link.md"
        broken_link.symlink_to("/nonexistent/path")
        
        # Create DELETE action
        fix_actions = [doctor.FixAction("DELETE", str(broken_link), "broken symlink")]
        
        with patch('builtins.input', return_value='y'):
            result = doctor.do_fix([], fix_actions)
        
        assert result is True
        assert not broken_link.exists()  # Symlink should be deleted
        
        captured = capsys.readouterr()
        assert "DELETED" in captured.out
    
    def test_deletes_regular_files(self, tmp_path, capsys):
        """Should delete regular files."""
        # Create regular file
        regular_file = tmp_path / "regular-file.txt"
        regular_file.write_text("content")
        
        # Create DELETE action
        fix_actions = [doctor.FixAction("DELETE", str(regular_file), "stale file")]
        
        with patch('builtins.input', return_value='y'):
            result = doctor.do_fix([], fix_actions)
        
        assert result is True
        assert not regular_file.exists()  # File should be deleted
        
        captured = capsys.readouterr()
        assert "DELETED" in captured.out
    
    def test_deletes_directories(self, tmp_path, capsys):
        """Should delete directories."""
        # Create directory
        test_dir = tmp_path / "test-dir"
        test_dir.mkdir()
        (test_dir / "file.txt").write_text("content")
        
        # Create DELETE action
        fix_actions = [doctor.FixAction("DELETE", str(test_dir), "stale directory")]
        
        with patch('builtins.input', return_value='y'):
            result = doctor.do_fix([], fix_actions)
        
        assert result is True
        assert not test_dir.exists()  # Directory should be deleted
        
        captured = capsys.readouterr()
        assert "DELETED" in captured.out


class TestDoctorFunction:
    """Test main doctor function."""
    
    def test_runs_all_checks(self, mock_paths, tmp_path, monkeypatch, capsys):
        """Should run all health checks."""
        # Mock all check functions to verify they're called
        checks_called = []
        
        def mock_check(name):
            def _check(scope, issues, fix_actions):
                checks_called.append(name)
            return _check
        
        def mock_build_check(name):
            def _check(issues, fix_actions):  # build check doesn't take scope
                checks_called.append(name)
            return _check
        
        with patch('agent_notes.doctor.check_stale_files', mock_check('stale')):
            with patch('agent_notes.doctor.check_broken_symlinks', mock_check('broken')):
                with patch('agent_notes.doctor.check_shadowed_files', mock_check('shadowed')):
                    with patch('agent_notes.doctor.check_missing_files', mock_check('missing')):
                        with patch('agent_notes.doctor.check_content_drift', mock_check('drift')):
                            with patch('agent_notes.doctor.check_build_freshness', mock_build_check('build')):
                                doctor.doctor(local=False, fix=False)
        
        expected_checks = ['stale', 'broken', 'shadowed', 'missing', 'drift', 'build']
        assert all(check in checks_called for check in expected_checks)
        
        captured = capsys.readouterr()
        assert "Checking AgentNotes global installation" in captured.out
    
    def test_local_mode(self, mock_paths, tmp_path, monkeypatch, capsys):
        """Should run in local mode when requested."""
        checks_called = []
        
        def mock_check(name):
            def _check(scope, issues, fix_actions):
                checks_called.append((name, scope))
            return _check
        
        def mock_build_check(name):
            def _check(issues, fix_actions):  # build check doesn't take scope
                checks_called.append((name, 'none'))  # mark as 'none' for build check
            return _check
        
        with patch('agent_notes.doctor.check_stale_files', mock_check('stale')):
            with patch('agent_notes.doctor.check_broken_symlinks', mock_check('broken')):
                with patch('agent_notes.doctor.check_shadowed_files', mock_check('shadowed')):
                    with patch('agent_notes.doctor.check_content_drift', mock_check('drift')):
                        with patch('agent_notes.doctor.check_build_freshness', mock_build_check('build')):
                            doctor.doctor(local=True, fix=False)
        
        # Should call local-specific checks
        local_checks = [call for call in checks_called if call[1] == 'local']
        assert len(local_checks) > 0
        
        captured = capsys.readouterr()
        assert "Checking AgentNotes local installation" in captured.out
    
    def test_fix_mode_prompts_user(self, mock_paths, tmp_path, monkeypatch, capsys):
        """Should prompt user in fix mode."""
        # Create an issue to fix
        issues = [doctor.Issue("stale", "/test/file", "test issue")]
        fix_actions = [doctor.FixAction("DELETE", "/test/file", "test fix")]
        
        with patch('agent_notes.doctor.check_stale_files') as mock_stale:
            mock_stale.side_effect = lambda scope, i, f: (i.extend(issues), f.extend(fix_actions))
            with patch('agent_notes.doctor.check_broken_symlinks'):
                with patch('agent_notes.doctor.check_shadowed_files'):
                    with patch('agent_notes.doctor.check_missing_files'):
                        with patch('agent_notes.doctor.check_content_drift'):
                            with patch('agent_notes.doctor.check_build_freshness'):
                                with patch('builtins.input', return_value='n'):  # User says no
                                    doctor.doctor(local=False, fix=True)
        
        captured = capsys.readouterr()
        assert "The following changes will be made" in captured.out
        assert "DELETE" in captured.out
        assert "Aborted" in captured.out


class TestCountFunctions:
    """Test counting functions."""
    
    def test_count_agents(self, tmp_path, monkeypatch):
        """Should count installed agents per CLI."""
        # Setup agent files for claude
        home_claude = tmp_path / "home" / ".claude"
        home_claude.mkdir(parents=True)
        agents_dir = home_claude / "agents"
        agents_dir.mkdir()
        (agents_dir / "agent1.md").write_text("agent1")
        (agents_dir / "agent2.md").write_text("agent2")
        
        # Setup dist
        dist_claude = tmp_path / "dist" / "claude"
        dist_claude.mkdir(parents=True)
        dist_agents = dist_claude / "agents"
        dist_agents.mkdir()
        (dist_agents / "agent1.md").write_text("a1")
        (dist_agents / "agent2.md").write_text("a2")
        (dist_agents / "agent3.md").write_text("a3")
        
        monkeypatch.setattr(doctor, 'CLAUDE_HOME', home_claude)
        monkeypatch.setattr(doctor, 'DIST_CLAUDE_DIR', dist_claude)
        
        installed, expected = doctor._count_agents("claude", "global")
        assert installed == 2
        assert expected == 3
    
    def test_count_skills(self, tmp_path, monkeypatch):
        """Should count installed skills per CLI."""
        home_claude = tmp_path / "home" / ".claude"
        home_claude.mkdir(parents=True)
        skills_dir = home_claude / "skills"
        skills_dir.mkdir()
        
        skill1 = skills_dir / "skill1"
        skill1.mkdir()
        skill2 = skills_dir / "skill2"
        skill2.mkdir()
        
        dist_skills = tmp_path / "dist" / "skills"
        dist_skills.mkdir(parents=True)
        (dist_skills / "skill1").mkdir()
        (dist_skills / "skill2").mkdir()
        
        monkeypatch.setattr(doctor, 'CLAUDE_HOME', home_claude)
        monkeypatch.setattr(doctor, 'DIST_SKILLS_DIR', dist_skills)
        
        installed, expected = doctor._count_skills("claude", "global")
        assert installed == 2
        assert expected == 2
    
    def test_count_stale(self):
        """Should count stale issues correctly."""
        issues = [
            doctor.Issue("stale", "/agents/old1.md", "stale agent"),
            doctor.Issue("stale", "/agents/old2.md", "stale agent"),
            doctor.Issue("broken", "/agents/broken.md", "broken link"),
            doctor.Issue("stale", "/skills/old-skill", "stale skill")
        ]
        
        agent_stale = doctor.count_stale(issues, "agents")
        skill_stale = doctor.count_stale(issues, "skills")
        
        assert agent_stale == 2
        assert skill_stale == 1