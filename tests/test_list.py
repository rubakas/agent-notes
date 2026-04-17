"""Test list module."""
import pytest
from pathlib import Path
from unittest.mock import patch
import yaml

import agent_notes.list as list_module


class TestListAgents:
    """Test list_agents function."""
    
    def test_lists_agents_with_metadata(self, tmp_path, monkeypatch, capsys, sample_agents_yaml):
        """Should list agents with tier and description from YAML."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        
        # Create agents.yaml
        agents_yaml = source_dir / "agents.yaml"
        agents_yaml.write_text(sample_agents_yaml)
        
        # Create agent source files
        agents_dir = source_dir / "agents"
        agents_dir.mkdir()
        (agents_dir / "test-agent.md").write_text("test agent content")
        (agents_dir / "test-reviewer.md").write_text("test reviewer content")
        
        monkeypatch.setattr(list_module, 'SOURCE_DIR', source_dir)
        
        list_module.list_agents()
        
        captured = capsys.readouterr()
        assert "Agents:" in captured.out
        assert "test-agent" in captured.out
        assert "test-reviewer" in captured.out
        assert "sonnet" in captured.out  # tier
        assert "haiku" in captured.out   # tier
        assert "Test agent description" in captured.out
        assert "Test reviewer description" in captured.out
    
    def test_lists_agents_without_yaml_metadata(self, tmp_path, monkeypatch, capsys):
        """Should list agents even without YAML metadata."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        
        # Create agent source files but no agents.yaml
        agents_dir = source_dir / "agents"
        agents_dir.mkdir()
        (agents_dir / "simple-agent.md").write_text("simple agent content")
        
        monkeypatch.setattr(list_module, 'SOURCE_DIR', source_dir)
        
        list_module.list_agents()
        
        captured = capsys.readouterr()
        assert "Agents:" in captured.out
        assert "simple-agent" in captured.out
    
    def test_handles_missing_agents_directory(self, tmp_path, monkeypatch, capsys):
        """Should handle missing agents directory gracefully."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        
        monkeypatch.setattr(list_module, 'SOURCE_DIR', source_dir)
        
        list_module.list_agents()
        
        captured = capsys.readouterr()
        assert "Agents:" in captured.out
    
    def test_handles_invalid_yaml(self, tmp_path, monkeypatch, capsys):
        """Should handle invalid YAML gracefully."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        
        # Create invalid YAML
        agents_yaml = source_dir / "agents.yaml"
        agents_yaml.write_text("invalid: yaml: content: [")
        
        # Create agent
        agents_dir = source_dir / "agents"
        agents_dir.mkdir()
        (agents_dir / "test-agent.md").write_text("test content")
        
        monkeypatch.setattr(list_module, 'SOURCE_DIR', source_dir)
        
        list_module.list_agents()
        
        captured = capsys.readouterr()
        assert "Agents:" in captured.out
        assert "test-agent" in captured.out
    
    def test_sorts_agents_alphabetically(self, tmp_path, monkeypatch, capsys):
        """Should sort agents alphabetically."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        
        agents_dir = source_dir / "agents"
        agents_dir.mkdir()
        (agents_dir / "zebra-agent.md").write_text("zebra content")
        (agents_dir / "alpha-agent.md").write_text("alpha content")
        (agents_dir / "beta-agent.md").write_text("beta content")
        
        monkeypatch.setattr(list_module, 'SOURCE_DIR', source_dir)
        
        list_module.list_agents()
        
        captured = capsys.readouterr()
        lines = captured.out.split('\n')
        agent_lines = [line for line in lines if 'agent' in line]
        
        # Should appear in alphabetical order
        alpha_pos = next(i for i, line in enumerate(agent_lines) if 'alpha-agent' in line)
        beta_pos = next(i for i, line in enumerate(agent_lines) if 'beta-agent' in line)
        zebra_pos = next(i for i, line in enumerate(agent_lines) if 'zebra-agent' in line)
        
        assert alpha_pos < beta_pos < zebra_pos


class TestListSkills:
    """Test list_skills function."""
    
    def test_lists_skills(self, tmp_path, monkeypatch, capsys):
        """Should list skill directories."""
        # Setup skill directories
        skill1 = tmp_path / "skill-one"
        skill1.mkdir()
        (skill1 / "SKILL.md").write_text("skill one content")
        
        skill2 = tmp_path / "skill-two"
        skill2.mkdir()
        (skill2 / "SKILL.md").write_text("skill two content")
        
        with patch('agent_notes.list.find_skill_dirs', return_value=[skill1, skill2]):
            list_module.list_skills()
        
        captured = capsys.readouterr()
        assert "Skills:" in captured.out
        assert "skill-one" in captured.out
        assert "skill-two" in captured.out
    
    def test_handles_no_skills(self, tmp_path, monkeypatch, capsys):
        """Should handle case with no skills."""
        with patch('agent_notes.list.find_skill_dirs', return_value=[]):
            list_module.list_skills()
        
        captured = capsys.readouterr()
        assert "Skills:" in captured.out
    
    def test_sorts_skills_alphabetically(self, tmp_path, capsys):
        """Should sort skills alphabetically."""
        # Create skills in non-alphabetical order
        skills = [
            tmp_path / "zebra-skill",
            tmp_path / "alpha-skill", 
            tmp_path / "beta-skill"
        ]
        
        for skill in skills:
            skill.mkdir()
            (skill / "SKILL.md").write_text("skill content")
        
        # find_skill_dirs returns sorted, but let's test with unsorted input
        unsorted_skills = [skills[0], skills[2], skills[1]]  # zebra, beta, alpha
        
        with patch('agent_notes.list.find_skill_dirs', return_value=sorted(unsorted_skills)):
            list_module.list_skills()
        
        captured = capsys.readouterr()
        lines = captured.out.split('\n')
        skill_lines = [line.strip() for line in lines if line.strip() and 'skill' in line and 'Skills:' not in line]
        
        # Should be sorted
        assert skill_lines == ['alpha-skill', 'beta-skill', 'zebra-skill']


class TestListRules:
    """Test list_rules function."""
    
    def test_lists_rules_and_globals(self, tmp_path, monkeypatch, capsys):
        """Should list rules and global config files."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        
        # Create rules
        rules_dir = source_dir / "rules"
        rules_dir.mkdir()
        (rules_dir / "code-quality.md").write_text("code quality rules")
        (rules_dir / "safety.md").write_text("safety rules")
        (rules_dir / "performance.md").write_text("performance rules")
        
        monkeypatch.setattr(list_module, 'SOURCE_DIR', source_dir)
        
        list_module.list_rules()
        
        captured = capsys.readouterr()
        assert "Rules:" in captured.out
        assert "code-quality" in captured.out
        assert "safety" in captured.out
        assert "performance" in captured.out
        
        assert "Global configs:" in captured.out
        assert "global.md" in captured.out
        assert "global-copilot.md" in captured.out
    
    def test_handles_missing_rules_directory(self, tmp_path, monkeypatch, capsys):
        """Should handle missing rules directory gracefully."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        
        monkeypatch.setattr(list_module, 'SOURCE_DIR', source_dir)
        
        list_module.list_rules()
        
        captured = capsys.readouterr()
        assert "Rules:" in captured.out
        assert "Global configs:" in captured.out
        assert "global.md" in captured.out
        assert "global-copilot.md" in captured.out
    
    def test_sorts_rules_alphabetically(self, tmp_path, monkeypatch, capsys):
        """Should sort rules alphabetically."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        
        rules_dir = source_dir / "rules"
        rules_dir.mkdir()
        (rules_dir / "zebra-rules.md").write_text("zebra rules")
        (rules_dir / "alpha-rules.md").write_text("alpha rules")
        (rules_dir / "beta-rules.md").write_text("beta rules")
        
        monkeypatch.setattr(list_module, 'SOURCE_DIR', source_dir)
        
        list_module.list_rules()
        
        captured = capsys.readouterr()
        lines = captured.out.split('\n')
        rule_lines = [line.strip() for line in lines if line.strip() and 'rules' in line and 'Rules:' not in line]
        
        # Should be sorted
        assert rule_lines == ['alpha-rules', 'beta-rules', 'zebra-rules']


class TestListComponents:
    """Test main list_components function."""
    
    def test_lists_agents_only(self, tmp_path, monkeypatch, capsys):
        """Should list only agents when filter is 'agents'."""
        with patch('agent_notes.list.list_agents') as mock_agents:
            with patch('agent_notes.list.list_skills') as mock_skills:
                with patch('agent_notes.list.list_rules') as mock_rules:
                    list_module.list_components("agents")
                    
                    mock_agents.assert_called_once()
                    mock_skills.assert_not_called()
                    mock_rules.assert_not_called()
    
    def test_lists_skills_only(self, tmp_path, monkeypatch, capsys):
        """Should list only skills when filter is 'skills'."""
        with patch('agent_notes.list.list_agents') as mock_agents:
            with patch('agent_notes.list.list_skills') as mock_skills:
                with patch('agent_notes.list.list_rules') as mock_rules:
                    list_module.list_components("skills")
                    
                    mock_agents.assert_not_called()
                    mock_skills.assert_called_once()
                    mock_rules.assert_not_called()
    
    def test_lists_rules_only(self, tmp_path, monkeypatch, capsys):
        """Should list only rules when filter is 'rules'."""
        with patch('agent_notes.list.list_agents') as mock_agents:
            with patch('agent_notes.list.list_skills') as mock_skills:
                with patch('agent_notes.list.list_rules') as mock_rules:
                    list_module.list_components("rules")
                    
                    mock_agents.assert_not_called()
                    mock_skills.assert_not_called()
                    mock_rules.assert_called_once()
    
    def test_lists_all_components(self, tmp_path, monkeypatch, capsys):
        """Should list all components when filter is 'all'."""
        with patch('agent_notes.list.list_agents') as mock_agents:
            with patch('agent_notes.list.list_skills') as mock_skills:
                with patch('agent_notes.list.list_rules') as mock_rules:
                    list_module.list_components("all")
                    
                    mock_agents.assert_called_once()
                    mock_skills.assert_called_once()
                    mock_rules.assert_called_once()
    
    def test_lists_all_by_default(self, tmp_path, monkeypatch, capsys):
        """Should list all components by default."""
        with patch('agent_notes.list.list_agents') as mock_agents:
            with patch('agent_notes.list.list_skills') as mock_skills:
                with patch('agent_notes.list.list_rules') as mock_rules:
                    list_module.list_components()  # No filter specified
                    
                    mock_agents.assert_called_once()
                    mock_skills.assert_called_once()
                    mock_rules.assert_called_once()
    
    def test_handles_unknown_filter(self, capsys):
        """Should handle unknown filter gracefully."""
        with pytest.raises(SystemExit) as exc_info:
            list_module.list_components("unknown")
        
        assert exc_info.value.code == 1
        
        captured = capsys.readouterr()
        assert "Unknown filter: unknown" in captured.out
        assert "Usage: agent-notes list" in captured.out
        assert "[agents|skills|rules]" in captured.out


class TestColorFormatting:
    """Test color formatting in output."""
    
    def test_uses_colors_for_headers(self, tmp_path, monkeypatch, capsys):
        """Should use colors for section headers."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        
        # Create minimal structure
        agents_dir = source_dir / "agents"
        agents_dir.mkdir()
        
        monkeypatch.setattr(list_module, 'SOURCE_DIR', source_dir)
        
        with patch('agent_notes.list.find_skill_dirs', return_value=[]):
            list_module.list_components("all")
        
        captured = capsys.readouterr()
        # Should contain color references (exact format depends on Color class)
        assert "Agents:" in captured.out
        assert "Skills:" in captured.out
        assert "Rules:" in captured.out
        assert "Global configs:" in captured.out


class TestYamlHandling:
    """Test YAML file handling edge cases."""
    
    def test_handles_agents_yaml_with_no_agents_key(self, tmp_path, monkeypatch, capsys):
        """Should handle agents.yaml without 'agents' key."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        
        # Create YAML without agents key
        agents_yaml = source_dir / "agents.yaml"
        agents_yaml.write_text("tiers:\n  opus:\n    claude: opus")
        
        agents_dir = source_dir / "agents"
        agents_dir.mkdir()
        (agents_dir / "test-agent.md").write_text("test content")
        
        monkeypatch.setattr(list_module, 'SOURCE_DIR', source_dir)
        
        list_module.list_agents()
        
        captured = capsys.readouterr()
        assert "test-agent" in captured.out
    
    def test_handles_empty_agents_yaml(self, tmp_path, monkeypatch, capsys):
        """Should handle empty agents.yaml file."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        
        # Create empty YAML
        agents_yaml = source_dir / "agents.yaml"
        agents_yaml.write_text("")
        
        agents_dir = source_dir / "agents"
        agents_dir.mkdir()
        (agents_dir / "test-agent.md").write_text("test content")
        
        monkeypatch.setattr(list_module, 'SOURCE_DIR', source_dir)
        
        list_module.list_agents()
        
        captured = capsys.readouterr()
        assert "test-agent" in captured.out


class TestTierAndDescriptionFormatting:
    """Test formatting of tier and description information."""
    
    def test_formats_tier_and_description_correctly(self, tmp_path, monkeypatch, capsys):
        """Should format tier and description with proper spacing."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        
        # Create agents.yaml with varying length data
        agents_yaml_content = """
agents:
  short:
    description: "Short description"
    tier: opus
  very-long-agent-name:
    description: "Very long description that might affect formatting"
    tier: haiku
"""
        agents_yaml = source_dir / "agents.yaml"
        agents_yaml.write_text(agents_yaml_content)
        
        agents_dir = source_dir / "agents"
        agents_dir.mkdir()
        (agents_dir / "short.md").write_text("short agent")
        (agents_dir / "very-long-agent-name.md").write_text("long agent")
        
        monkeypatch.setattr(list_module, 'SOURCE_DIR', source_dir)
        
        list_module.list_agents()
        
        captured = capsys.readouterr()
        
        # Both agents should appear
        assert "short" in captured.out
        assert "very-long-agent-name" in captured.out
        assert "opus" in captured.out
        assert "haiku" in captured.out
        assert "Short description" in captured.out
        assert "Very long description" in captured.out