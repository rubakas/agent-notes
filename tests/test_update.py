"""Test update module."""
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import subprocess

import agent_notes.update as update


class TestUpdateFunction:
    """Test main update function."""
    
    def test_requires_git_repository(self, tmp_path, monkeypatch, capsys):
        """Should require git repository to update."""
        # Mock ROOT without .git directory
        monkeypatch.setattr(update, 'ROOT', tmp_path)
        
        update.update(skip_pull=False)  # Use new signature
        
        captured = capsys.readouterr()
        assert "Not a git repository" in captured.out
        assert "Update requires a git-based install" in captured.out
    
    def test_pulls_latest_changes(self, tmp_path, monkeypatch, capsys):
        """Should pull latest changes from git."""
        # Setup git directory
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        
        monkeypatch.setattr(update, 'ROOT', tmp_path)
        
        # Mock git commands
        commit_before = "abc123"
        commit_after = "def456" 
        log_output = "def456 Latest commit\nabc124 Previous commit"
        
        mock_results = [
            MagicMock(stdout=commit_before, returncode=0),  # git rev-parse HEAD (before)
            MagicMock(stdout="", returncode=0),             # git pull --ff-only
            MagicMock(stdout=commit_after, returncode=0),   # git rev-parse HEAD (after)
            MagicMock(stdout=log_output, returncode=0)      # git log --oneline
        ]
        
        with patch('subprocess.run', side_effect=mock_results):
            with patch('agent_notes.update.run_build'):
                with patch('agent_notes.install_state.build_install_state') as mock_build_state:
                    with patch('agent_notes.install_state.load_current_state', return_value=None):
                        with patch('agent_notes.update_diff.diff_states') as mock_diff:
                            with patch('agent_notes.update_diff.render_diff_report', return_value="No changes."):
                                # Mock empty diff
                                mock_diff.return_value = MagicMock()
                                mock_diff.return_value.has_changes.return_value = False
                                
                                update.update(skip_pull=False)
        
        captured = capsys.readouterr()
        assert "Updating agent-notes" in captured.out
        assert "Updated 2 commits" in captured.out
    
    def test_handles_already_up_to_date(self, tmp_path, monkeypatch, capsys):
        """Should handle case when already up to date."""
        # Setup git directory
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        
        monkeypatch.setattr(update, 'ROOT', tmp_path)
        
        # Mock git commands - same commit before and after
        same_commit = "abc123"
        
        mock_results = [
            MagicMock(stdout=same_commit, returncode=0),  # git rev-parse HEAD (before)
            MagicMock(stdout="", returncode=0),           # git pull --ff-only
            MagicMock(stdout=same_commit, returncode=0)   # git rev-parse HEAD (after)
        ]
        
        with patch('subprocess.run', side_effect=mock_results):
            with patch('agent_notes.update.run_build'):
                with patch('agent_notes.install_state.build_install_state'):
                    with patch('agent_notes.install_state.load_current_state', return_value=None):
                        with patch('agent_notes.update_diff.diff_states') as mock_diff:
                            with patch('agent_notes.update_diff.render_diff_report', return_value="No changes."):
                                mock_diff.return_value = MagicMock()
                                mock_diff.return_value.has_changes.return_value = False
                                
                                update.update(skip_pull=False)
        
        captured = capsys.readouterr()
        assert "Already up to date (no new commits)" in captured.out
    
    def test_shows_commit_log(self, tmp_path, monkeypatch, capsys):
        """Should show commit log for updates."""
        # Setup git directory
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        
        monkeypatch.setattr(update, 'ROOT', tmp_path)
        
        # Mock git commands with multiple commits
        commit_before = "abc123"
        commit_after = "def456"
        log_output = "def456 Add new feature\nabc124 Fix bug\n111111 Update docs"
        
        mock_results = [
            MagicMock(stdout=commit_before, returncode=0),
            MagicMock(stdout="", returncode=0),
            MagicMock(stdout=commit_after, returncode=0),
            MagicMock(stdout=log_output, returncode=0)
        ]
        
        with patch('subprocess.run', side_effect=mock_results):
            with patch('agent_notes.update.run_build'):
                with patch('agent_notes.install_state.build_install_state'):
                    with patch('agent_notes.install_state.load_current_state', return_value=None):
                        with patch('agent_notes.update_diff.diff_states') as mock_diff:
                            with patch('agent_notes.update_diff.render_diff_report', return_value="No changes."):
                                mock_diff.return_value = MagicMock()
                                mock_diff.return_value.has_changes.return_value = False
                                
                                update.update(skip_pull=False)
        
        captured = capsys.readouterr()
        assert "Updated 3 commits" in captured.out
        assert "Add new feature" in captured.out
        assert "Fix bug" in captured.out
        assert "Update docs" in captured.out
    
    def test_limits_commit_display(self, tmp_path, monkeypatch, capsys):
        """Should limit commit display to 5 commits."""
        # Setup git directory
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        
        monkeypatch.setattr(update, 'ROOT', tmp_path)
        
        # Mock git commands with many commits
        commit_before = "abc123"
        commit_after = "def456"
        
        # Create 7 commits
        commits = [f"{i:06d} Commit {i}" for i in range(7, 0, -1)]
        log_output = "\n".join(commits)
        
        mock_results = [
            MagicMock(stdout=commit_before, returncode=0),
            MagicMock(stdout="", returncode=0),
            MagicMock(stdout=commit_after, returncode=0),
            MagicMock(stdout=log_output, returncode=0)
        ]
        
        with patch('subprocess.run', side_effect=mock_results):
            with patch('agent_notes.update.run_build'):
                with patch('agent_notes.install_state.build_install_state'):
                    with patch('agent_notes.install_state.load_current_state', return_value=None):
                        with patch('agent_notes.update_diff.diff_states') as mock_diff:
                            with patch('agent_notes.update_diff.render_diff_report', return_value="No changes."):
                                mock_diff.return_value = MagicMock()
                                mock_diff.return_value.has_changes.return_value = False
                                
                                update.update(skip_pull=False)
        
        captured = capsys.readouterr()
        assert "Updated 7 commits" in captured.out
        
        # Should show only first 5 commits
        for i in range(7, 2, -1):  # 7, 6, 5, 4, 3
            assert f"Commit {i}" in captured.out
        
        # Should not show commits 1 and 2
        assert "Commit 1" not in captured.out
        assert "Commit 2" not in captured.out
    
    def test_handles_empty_log_output(self, tmp_path, monkeypatch, capsys):
        """Should handle empty log output gracefully."""
        # Setup git directory
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        
        monkeypatch.setattr(update, 'ROOT', tmp_path)
        
        commit_before = "abc123"
        commit_after = "def456"
        
        mock_results = [
            MagicMock(stdout=commit_before, returncode=0),
            MagicMock(stdout="", returncode=0),
            MagicMock(stdout=commit_after, returncode=0),
            MagicMock(stdout="", returncode=0)  # Empty log output
        ]
        
        with patch('subprocess.run', side_effect=mock_results):
            with patch('agent_notes.update.run_build'):
                with patch('agent_notes.install_state.build_install_state'):
                    with patch('agent_notes.install_state.load_current_state', return_value=None):
                        with patch('agent_notes.update_diff.diff_states') as mock_diff:
                            with patch('agent_notes.update_diff.render_diff_report', return_value="No changes."):
                                mock_diff.return_value = MagicMock()
                                mock_diff.return_value.has_changes.return_value = False
                                
                                update.update(skip_pull=False)
        
        captured = capsys.readouterr()
        # With empty log output, no commit count is shown (function returns early)
        assert "Updating agent-notes" in captured.out
        assert "Rebuilding" in captured.out
    
    def test_handles_git_pull_failure(self, tmp_path, monkeypatch, capsys):
        """Should handle git pull failure gracefully."""
        # Setup git directory
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        
        monkeypatch.setattr(update, 'ROOT', tmp_path)
        
        # Mock successful first command, then failure
        mock_results = [
            MagicMock(stdout="abc123", returncode=0),       # git rev-parse HEAD (before)
            subprocess.CalledProcessError(1, "git pull")    # git pull fails
        ]
        
        with patch('subprocess.run', side_effect=mock_results):
            update.update(skip_pull=False)
        
        captured = capsys.readouterr()
        assert "Could not fast-forward" in captured.out
        assert "git status" in captured.out
    
    def test_handles_git_rev_parse_failure(self, tmp_path, monkeypatch, capsys):
        """Should handle git rev-parse failure gracefully."""
        # Setup git directory
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        
        monkeypatch.setattr(update, 'ROOT', tmp_path)
        
        # Mock failing first command
        with patch('subprocess.run', side_effect=subprocess.CalledProcessError(1, "git rev-parse")):
            update.update(skip_pull=False)
        
        captured = capsys.readouterr()
        assert "Could not fast-forward" in captured.out
    
    def test_calls_install_after_update_with_changes(self, tmp_path, monkeypatch):
        """Should call install function after successful update when there are changes."""
        # Setup git directory
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        
        monkeypatch.setattr(update, 'ROOT', tmp_path)
        
        # Mock successful git operations
        same_commit = "abc123"
        mock_results = [
            MagicMock(stdout=same_commit, returncode=0),
            MagicMock(stdout="", returncode=0),
            MagicMock(stdout=same_commit, returncode=0)
        ]
        
        with patch('subprocess.run', side_effect=mock_results):
            with patch('agent_notes.update.run_build'):
                with patch('agent_notes.install_state.build_install_state'):
                    with patch('agent_notes.install_state.load_current_state', return_value=None):
                        with patch('agent_notes.update_diff.diff_states') as mock_diff:
                            with patch('agent_notes.update_diff.render_diff_report', return_value="Changes found"):
                                with patch('agent_notes.install.install') as mock_install:
                                    # Mock diff with changes
                                    mock_diff.return_value = MagicMock()
                                    mock_diff.return_value.has_changes.return_value = True
                                    
                                    update.update(skip_pull=False, yes=True)  # Auto-approve
                                    mock_install.assert_called_once()
    
    def test_uses_correct_git_commands(self, tmp_path, monkeypatch):
        """Should use correct git commands with proper arguments."""
        # Setup git directory
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        
        monkeypatch.setattr(update, 'ROOT', tmp_path)
        
        # Track all subprocess calls
        subprocess_calls = []
        
        def mock_run(*args, **kwargs):
            subprocess_calls.append((args, kwargs))
            # Return mock result based on command
            if "rev-parse" in args[0]:
                return MagicMock(stdout="abc123", returncode=0)
            elif "pull" in args[0]:
                return MagicMock(stdout="", returncode=0)
            elif "log" in args[0]:
                return MagicMock(stdout="", returncode=0)
            return MagicMock(stdout="", returncode=0)
        
        with patch('subprocess.run', side_effect=mock_run):
            with patch('agent_notes.update.run_build'):
                with patch('agent_notes.install_state.build_install_state'):
                    with patch('agent_notes.install_state.load_current_state', return_value=None):
                        with patch('agent_notes.update_diff.diff_states') as mock_diff:
                            with patch('agent_notes.update_diff.render_diff_report', return_value="No changes."):
                                mock_diff.return_value = MagicMock()
                                mock_diff.return_value.has_changes.return_value = False
                                
                                update.update(skip_pull=False)
        
        # Check git commands used
        commands = [call[0][0] for call in subprocess_calls]
        
        # Should use git rev-parse HEAD
        assert any("rev-parse" in cmd and "HEAD" in cmd for cmd in commands)
        
        # Should use git pull --ff-only  
        assert any("pull" in cmd and "--ff-only" in cmd for cmd in commands)
        
        # Should set working directory
        for call in subprocess_calls:
            kwargs = call[1]
            assert kwargs.get('cwd') == tmp_path
            assert kwargs.get('capture_output') is True
            assert kwargs.get('text') is True
            assert kwargs.get('check') is True

    def test_skip_pull_flag_works(self, tmp_path, monkeypatch, capsys):
        """Should skip git pull when skip_pull=True."""
        monkeypatch.setattr(update, 'ROOT', tmp_path)
        
        with patch('subprocess.run') as mock_run:
            with patch('agent_notes.update.run_build'):
                with patch('agent_notes.install_state.build_install_state'):
                    with patch('agent_notes.install_state.load_current_state', return_value=None):
                        with patch('agent_notes.update_diff.diff_states') as mock_diff:
                            with patch('agent_notes.update_diff.render_diff_report', return_value="No changes."):
                                mock_diff.return_value = MagicMock()
                                mock_diff.return_value.has_changes.return_value = False
                                
                                update.update(skip_pull=True)
                                
                                # Should not have called any git commands
                                mock_run.assert_not_called()

    def test_dry_run_flag_works(self, tmp_path, monkeypatch, capsys):
        """Should not call install when dry_run=True."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        
        monkeypatch.setattr(update, 'ROOT', tmp_path)
        
        with patch('subprocess.run', return_value=MagicMock(stdout="abc123", returncode=0)):
            with patch('agent_notes.update.run_build'):
                with patch('agent_notes.install_state.build_install_state'):
                    with patch('agent_notes.install_state.load_current_state', return_value=None):
                        with patch('agent_notes.update_diff.diff_states') as mock_diff:
                            with patch('agent_notes.update_diff.render_diff_report', return_value="Changes found"):
                                with patch('agent_notes.install.install') as mock_install:
                                    mock_diff.return_value = MagicMock()
                                    mock_diff.return_value.has_changes.return_value = True
                                    
                                    update.update(skip_pull=True, dry_run=True)
                                    
                                    mock_install.assert_not_called()
        
        captured = capsys.readouterr()
        assert "Dry run" in captured.out


class TestGitOperationDetails:
    """Test specific git operation details."""
    
    def test_git_commands_run_in_correct_directory(self, tmp_path, monkeypatch):
        """Should run git commands in the ROOT directory."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        
        monkeypatch.setattr(update, 'ROOT', tmp_path)
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(stdout="abc123", returncode=0)
            
            with patch('agent_notes.update.run_build'):
                with patch('agent_notes.install_state.build_install_state'):
                    with patch('agent_notes.install_state.load_current_state', return_value=None):
                        with patch('agent_notes.update_diff.diff_states') as mock_diff:
                            with patch('agent_notes.update_diff.render_diff_report', return_value="No changes."):
                                mock_diff.return_value = MagicMock()
                                mock_diff.return_value.has_changes.return_value = False
                                
                                try:
                                    update.update(skip_pull=False)
                                except:
                                    pass  # We expect it to fail on subsequent calls
            
            # Check that cwd parameter is set correctly
            for call in mock_run.call_args_list:
                kwargs = call[1]
                assert kwargs.get('cwd') == tmp_path
    
    def test_uses_fast_forward_only_pull(self, tmp_path, monkeypatch):
        """Should use --ff-only flag for git pull."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        
        monkeypatch.setattr(update, 'ROOT', tmp_path)
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(stdout="abc123", returncode=0)
            
            with patch('agent_notes.update.run_build'):
                with patch('agent_notes.install_state.build_install_state'):
                    with patch('agent_notes.install_state.load_current_state', return_value=None):
                        with patch('agent_notes.update_diff.diff_states') as mock_diff:
                            with patch('agent_notes.update_diff.render_diff_report', return_value="No changes."):
                                mock_diff.return_value = MagicMock()
                                mock_diff.return_value.has_changes.return_value = False
                                
                                try:
                                    update.update(skip_pull=False)
                                except:
                                    pass
            
            # Find the git pull command
            pull_calls = [call for call in mock_run.call_args_list 
                         if call[0] and len(call[0]) > 0 and "git" in call[0][0] and "pull" in call[0][0]]
            
            assert len(pull_calls) > 0
            pull_command = pull_calls[0][0][0]
            assert "--ff-only" in pull_command
    
    def test_commit_range_calculation(self, tmp_path, monkeypatch, capsys):
        """Should use correct commit range for log."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        
        monkeypatch.setattr(update, 'ROOT', tmp_path)
        
        commit_before = "abc123"
        commit_after = "def456"
        
        log_calls = []
        
        def mock_run(*args, **kwargs):
            if "log" in args[0] and "--oneline" in args[0]:
                log_calls.append(args[0])
                return MagicMock(stdout="def456 New commit", returncode=0)
            elif "rev-parse" in args[0]:
                # First call returns before, second call returns after
                if not hasattr(mock_run, 'call_count'):
                    mock_run.call_count = 0
                mock_run.call_count += 1
                if mock_run.call_count == 1:
                    return MagicMock(stdout=commit_before, returncode=0)
                else:
                    return MagicMock(stdout=commit_after, returncode=0)
            else:
                return MagicMock(stdout="", returncode=0)
        
        with patch('subprocess.run', side_effect=mock_run):
            with patch('agent_notes.update.run_build'):
                with patch('agent_notes.install_state.build_install_state'):
                    with patch('agent_notes.install_state.load_current_state', return_value=None):
                        with patch('agent_notes.update_diff.diff_states') as mock_diff:
                            with patch('agent_notes.update_diff.render_diff_report', return_value="No changes."):
                                mock_diff.return_value = MagicMock()
                                mock_diff.return_value.has_changes.return_value = False
                                
                                update.update(skip_pull=False)
        
        # Should call git log with commit range
        assert len(log_calls) == 1
        log_command = log_calls[0]
        assert f"{commit_before}..{commit_after}" in log_command


class TestErrorHandling:
    """Test error handling in various scenarios."""
    
    def test_provides_helpful_error_messages(self, tmp_path, monkeypatch, capsys):
        """Should provide helpful error messages for common issues."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        
        monkeypatch.setattr(update, 'ROOT', tmp_path)
        
        with patch('subprocess.run', side_effect=subprocess.CalledProcessError(1, "git pull")):
            update.update(skip_pull=False)
        
        captured = capsys.readouterr()
        assert "Could not fast-forward" in captured.out
        assert str(tmp_path) in captured.out  # Should show the directory path
        assert "git status" in captured.out
    
    def test_includes_root_path_in_error_message(self, tmp_path, monkeypatch, capsys):
        """Should include ROOT path in error message for manual resolution."""
        custom_root = tmp_path / "custom" / "root" / "path"
        custom_root.mkdir(parents=True)
        (custom_root / ".git").mkdir()
        
        monkeypatch.setattr(update, 'ROOT', custom_root)
        
        with patch('subprocess.run', side_effect=subprocess.CalledProcessError(1, "git pull")):
            update.update(skip_pull=False)
        
        captured = capsys.readouterr()
        assert str(custom_root) in captured.out