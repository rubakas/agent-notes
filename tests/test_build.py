"""Test build module."""
import pytest
import yaml
from pathlib import Path
from unittest.mock import patch, mock_open

import agent_notes.build as build
import agent_notes.config as config


class TestStripMemorySection:
    """Test strip_memory_section function."""
    
    def test_removes_memory_section(self):
        """Should remove ## Memory section completely."""
        content = """# Agent
        
## Instructions

Follow these rules.

## Memory

This should be removed.

## Examples

This should remain.
"""
        result = build.strip_memory_section(content)
        
        assert "## Memory" not in result
        assert "This should be removed" not in result
        assert "## Instructions" in result
        assert "## Examples" in result
        assert "Follow these rules" in result
        assert "This should remain" in result
    
    def test_handles_no_memory_section(self):
        """Should handle content without memory section."""
        content = """# Agent
        
## Instructions

Follow these rules.

## Examples

Some examples.
"""
        result = build.strip_memory_section(content)
        assert result == content.strip()
    
    def test_handles_memory_at_end(self):
        """Should handle memory section at end of file."""
        content = """# Agent

## Instructions

Follow these rules.

## Memory

This should be removed.
"""
        result = build.strip_memory_section(content)
        
        assert "## Memory" not in result
        assert "This should be removed" not in result
        assert "Follow these rules" in result
    
    def test_removes_trailing_empty_lines(self):
        """Should remove trailing empty lines."""
        content = """# Agent

## Instructions

Follow these rules.

## Memory

Remove this.



"""
        result = build.strip_memory_section(content)
        
        # Should not end with multiple newlines
        assert not result.endswith('\n\n')
        assert result.endswith('Follow these rules.')


class TestGenerateClaudeFrontmatter:
    """Test generate_claude_frontmatter function."""
    
    def test_generates_basic_frontmatter(self):
        """Should generate basic Claude frontmatter."""
        agent_config = {
            'description': 'Test agent',
            'tier': 'sonnet',
            'color': 'blue',
            'effort': 'medium'
        }
        tiers = {
            'sonnet': {'claude': 'claude-3-5-sonnet-20241022'}
        }
        
        result = build.generate_claude_frontmatter('test-agent', agent_config, tiers)
        
        assert 'name: test-agent' in result
        assert 'description: Test agent' in result
        assert 'model: claude-3-5-sonnet-20241022' in result
        assert 'color: blue' in result
        assert 'effort: medium' in result
        assert result.startswith('---')
        assert result.endswith('---')
    
    def test_includes_claude_specific_settings(self):
        """Should include Claude-specific settings when present."""
        agent_config = {
            'description': 'Test agent',
            'tier': 'opus',
            'color': 'red',
            'effort': 'high',
            'claude': {
                'tools': 'Read, Write',
                'disallowedTools': 'Bash',
                'memory': 'user'
            }
        }
        tiers = {
            'opus': {'claude': 'claude-3-opus-20240229'}
        }
        
        result = build.generate_claude_frontmatter('test-agent', agent_config, tiers)
        
        assert 'tools: Read, Write' in result
        assert 'disallowedTools: Bash' in result
        assert 'memory: user' in result


class TestGenerateOpencodeFrontmatter:
    """Test generate_opencode_frontmatter function."""
    
    def test_generates_basic_frontmatter(self):
        """Should generate basic OpenCode frontmatter."""
        agent_config = {
            'description': 'Test agent',
            'mode': 'primary',
            'tier': 'sonnet'
        }
        tiers = {
            'sonnet': {'opencode': 'github-copilot/claude-sonnet-4'}
        }
        
        result = build.generate_opencode_frontmatter('test-agent', agent_config, tiers)
        
        assert 'description: Test agent' in result
        assert 'mode: primary' in result
        assert 'model: github-copilot/claude-sonnet-4' in result
        assert result.startswith('---')
        assert result.endswith('---')
    
    def test_includes_simple_permissions(self):
        """Should include simple permissions."""
        agent_config = {
            'description': 'Test agent',
            'mode': 'subagent',
            'tier': 'haiku',
            'opencode': {
                'permission': {
                    'edit': 'allow'
                }
            }
        }
        tiers = {
            'haiku': {'opencode': 'github-copilot/claude-haiku-4.5'}
        }
        
        result = build.generate_opencode_frontmatter('test-agent', agent_config, tiers)
        
        assert 'permission:' in result
        assert 'edit: allow' in result
    
    def test_includes_bash_permissions_string(self):
        """Should include bash permissions as string."""
        agent_config = {
            'description': 'Test agent',
            'mode': 'subagent',
            'tier': 'haiku',
            'opencode': {
                'permission': {
                    'bash': 'allow'
                }
            }
        }
        tiers = {
            'haiku': {'opencode': 'github-copilot/claude-haiku-4.5'}
        }
        
        result = build.generate_opencode_frontmatter('test-agent', agent_config, tiers)
        
        assert 'bash: allow' in result
    
    def test_includes_bash_permissions_dict(self):
        """Should include bash permissions as dict with proper quoting."""
        agent_config = {
            'description': 'Test agent',
            'mode': 'subagent',
            'tier': 'haiku',
            'opencode': {
                'permission': {
                    'bash': {
                        '*': 'deny',
                        'git log*': 'allow',
                        'normal_command': 'allow'
                    }
                }
            }
        }
        tiers = {
            'haiku': {'opencode': 'github-copilot/claude-haiku-4.5'}
        }
        
        result = build.generate_opencode_frontmatter('test-agent', agent_config, tiers)
        
        assert 'bash:' in result
        assert '"*": deny' in result  # Should quote keys with special chars
        assert '"git log*": allow' in result  # Should quote keys with spaces/special chars
        assert 'normal_command: allow' in result  # Should not quote normal keys


class TestGenerateAgentFiles:
    """Test generate_agent_files function."""
    
    def test_generates_both_formats(self, tmp_path, monkeypatch, sample_agents_yaml, sample_agent_content):
        """Should generate both Claude and OpenCode format files."""
        # Setup temporary directories
        source_agents_dir = tmp_path / "source" / "agents"
        source_agents_dir.mkdir(parents=True)
        
        dist_claude_dir = tmp_path / "dist" / "cli" / "claude"
        dist_opencode_dir = tmp_path / "dist" / "cli" / "opencode"
        
        # Create source agent file
        (source_agents_dir / "test-agent.md").write_text(sample_agent_content)
        
        # Mock paths
        monkeypatch.setattr(build, 'AGENTS_DIR', source_agents_dir)
        monkeypatch.setattr(build, 'DIST_CLAUDE_DIR', dist_claude_dir)
        monkeypatch.setattr(build, 'DIST_OPENCODE_DIR', dist_opencode_dir)
        
        # Parse config
        config_data = yaml.safe_load(sample_agents_yaml)
        agents_config = config_data['agents']
        tiers = config_data['tiers']
        
        # Generate files
        generated = build.generate_agent_files(agents_config, tiers)
        
        # Check files were created
        claude_file = dist_claude_dir / 'agents' / 'test-agent.md'
        opencode_file = dist_opencode_dir / 'agents' / 'test-agent.md'
        
        assert claude_file.exists()
        assert opencode_file.exists()
        assert claude_file in generated
        assert opencode_file in generated
        
        # Check Claude content
        claude_content = claude_file.read_text()
        assert 'name: test-agent' in claude_content
        assert 'model: sonnet' in claude_content
        assert 'tools: Read, Write' in claude_content
        assert 'memory: user' in claude_content
        assert '## Memory' in claude_content  # Should keep memory section
        
        # Check OpenCode content
        opencode_content = opencode_file.read_text()
        assert 'description: Test agent description' in opencode_content
        assert 'mode: primary' in opencode_content
        assert 'model: github-copilot/claude-sonnet-4' in opencode_content
        assert 'edit: allow' in opencode_content
        assert 'bash: allow' in opencode_content
        assert '## Memory' not in opencode_content  # Should strip memory section
    
    def test_warns_on_missing_source_file(self, tmp_path, monkeypatch, capsys):
        """Should warn when source file is missing."""
        source_agents_dir = tmp_path / "source" / "agents"
        source_agents_dir.mkdir(parents=True)
        
        monkeypatch.setattr(build, 'AGENTS_DIR', source_agents_dir)
        
        agents_config = {
            'missing-agent': {
                'description': 'Missing agent',
                'tier': 'sonnet',
                'mode': 'primary',
                'color': 'blue',
                'effort': 'medium'
            }
        }
        tiers = {'sonnet': {'claude': 'sonnet', 'opencode': 'github-copilot/claude-sonnet-4'}}
        
        generated = build.generate_agent_files(agents_config, tiers)
        
        captured = capsys.readouterr()
        assert "Warning: Missing source file" in captured.out
        assert "missing-agent.md" in captured.out
        assert generated == []


class TestCopyGlobalFiles:
    """Test copy_global_files function."""
    
    def test_copies_all_global_files(self, tmp_path, monkeypatch):
        """Should copy all global files to correct locations."""
        # Setup source files
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        
        (source_dir / "global.md").write_text("Global config content")
        (source_dir / "global-copilot.md").write_text("Copilot config content")
        
        source_rules_dir = source_dir / "rules"
        source_rules_dir.mkdir()
        (source_rules_dir / "rule1.md").write_text("Rule 1")
        (source_rules_dir / "rule2.md").write_text("Rule 2")
        
        # Setup dest directories
        dist_claude_dir = tmp_path / "dist" / "cli" / "claude"
        dist_opencode_dir = tmp_path / "dist" / "cli" / "opencode"
        dist_github_dir = tmp_path / "dist" / "cli" / "github"
        dist_rules_dir = tmp_path / "dist" / "rules"
        
        # Mock paths
        monkeypatch.setattr(build, 'GLOBAL_MD', source_dir / "global.md")
        monkeypatch.setattr(build, 'GLOBAL_COPILOT_MD', source_dir / "global-copilot.md")
        monkeypatch.setattr(build, 'RULES_DIR', source_rules_dir)
        monkeypatch.setattr(build, 'DIST_CLAUDE_DIR', dist_claude_dir)
        monkeypatch.setattr(build, 'DIST_OPENCODE_DIR', dist_opencode_dir)
        monkeypatch.setattr(build, 'DIST_GITHUB_DIR', dist_github_dir)
        monkeypatch.setattr(build, 'DIST_RULES_DIR', dist_rules_dir)
        
        # Copy files
        copied = build.copy_global_files()
        
        # Check files were created
        claude_global = dist_claude_dir / 'CLAUDE.md'
        agents_global = dist_opencode_dir / 'AGENTS.md'
        copilot_global = dist_github_dir / 'copilot-instructions.md'
        rule1_file = dist_rules_dir / 'rule1.md'
        rule2_file = dist_rules_dir / 'rule2.md'
        
        assert claude_global.exists()
        assert agents_global.exists()
        assert copilot_global.exists()
        assert rule1_file.exists()
        assert rule2_file.exists()
        
        # Check content
        assert claude_global.read_text() == "Global config content"
        assert agents_global.read_text() == "Global config content"
        assert copilot_global.read_text() == "Copilot config content"
        assert rule1_file.read_text() == "Rule 1"
        assert rule2_file.read_text() == "Rule 2"
        
        # Check all files are in returned list
        assert len(copied) == 5
        assert claude_global in copied
        assert agents_global in copied
        assert copilot_global in copied
        assert rule1_file in copied
        assert rule2_file in copied


class TestCountLines:
    """Test count_lines function."""
    
    def test_counts_lines_correctly(self, tmp_path):
        """Should count lines in file correctly."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("line 1\nline 2\nline 3")
        
        count = build.count_lines(test_file)
        assert count == 3
    
    def test_handles_missing_file(self, tmp_path):
        """Should return 0 for missing file."""
        missing_file = tmp_path / "missing.txt"
        
        count = build.count_lines(missing_file)
        assert count == 0


class TestBuild:
    """Test build function."""
    
    def test_full_build_process(self, tmp_path, monkeypatch, capsys, sample_agents_yaml, sample_agent_content):
        """Should perform full build process."""
        # Setup source structure
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        
        agents_yaml = source_dir / "agents.yaml"
        agents_yaml.write_text(sample_agents_yaml)
        
        source_agents_dir = source_dir / "agents"
        source_agents_dir.mkdir()
        (source_agents_dir / "test-agent.md").write_text(sample_agent_content)
        
        (source_dir / "global.md").write_text("Global content")
        (source_dir / "global-copilot.md").write_text("Copilot content")
        
        # Mock ROOT and paths
        monkeypatch.setattr(config, 'ROOT', tmp_path)
        monkeypatch.setattr(build, 'ROOT', tmp_path)
        monkeypatch.setattr(build, 'AGENTS_YAML', agents_yaml)
        monkeypatch.setattr(build, 'AGENTS_DIR', source_agents_dir)
        monkeypatch.setattr(build, 'GLOBAL_MD', source_dir / "global.md")
        monkeypatch.setattr(build, 'GLOBAL_COPILOT_MD', source_dir / "global-copilot.md")
        monkeypatch.setattr(build, 'RULES_DIR', source_dir / "rules")  # Non-existent
        
        dist_dir = tmp_path / "dist"
        monkeypatch.setattr(build, 'DIST_CLAUDE_DIR', dist_dir / "cli" / "claude")
        monkeypatch.setattr(build, 'DIST_OPENCODE_DIR', dist_dir / "cli" / "opencode")
        monkeypatch.setattr(build, 'DIST_GITHUB_DIR', dist_dir / "cli" / "github")
        monkeypatch.setattr(build, 'DIST_RULES_DIR', dist_dir / "rules")
        
        # Mock find_skill_dirs to return empty list for test
        monkeypatch.setattr(build, 'find_skill_dirs', lambda: [])
        
        # Run build
        build.build()
        
        # Check output
        captured = capsys.readouterr()
        assert "Generating agent files..." in captured.out
        assert "Copying global files..." in captured.out
        assert "Generated" in captured.out
        assert "files:" in captured.out
        
        # Check files were created
        assert (dist_dir / "cli" / "claude" / "agents" / "test-agent.md").exists()
        assert (dist_dir / "cli" / "opencode" / "agents" / "test-agent.md").exists()
        assert (dist_dir / "cli" / "claude" / "CLAUDE.md").exists()
        assert (dist_dir / "cli" / "opencode" / "AGENTS.md").exists()
        assert (dist_dir / "cli" / "github" / "copilot-instructions.md").exists()
    
    def test_handles_missing_agents_yaml(self, tmp_path, monkeypatch, capsys):
        """Should handle missing agents.yaml gracefully."""
        agents_yaml = tmp_path / "nonexistent" / "agents.yaml"
        
        monkeypatch.setattr(build, 'AGENTS_YAML', agents_yaml)
        
        build.build()
        
        captured = capsys.readouterr()
        assert "Error:" in captured.out
        assert "agents.yaml not found" in captured.out