"""Tests for agent registry."""

import pytest
from pathlib import Path
from agent_notes.registries.agent_registry import load_agent_registry, AgentRegistry
from agent_notes.domain.agent import AgentSpec


class TestAgentRegistry:
    def test_load_from_valid_yaml(self, tmp_path):
        """Should load agents from valid agents.yaml."""
        agents_file = tmp_path / "agents.yaml"
        agents_file.write_text("""
agents:
  test-agent:
    description: "Test agent"
    role: worker
    mode: subagent
    color: blue
    claude:
      tools: "Read, Write"
  simple-agent:
    description: "Simple agent"
    role: scout
    mode: primary
""")
        
        registry = load_agent_registry(agents_file)
        
        assert len(registry.all()) == 2
        assert sorted(registry.names()) == ["simple-agent", "test-agent"]
        
        test_agent = registry.get("test-agent")
        assert test_agent.name == "test-agent"
        assert test_agent.description == "Test agent"
        assert test_agent.role == "worker"
        assert test_agent.mode == "subagent"
        assert test_agent.color == "blue"
        assert test_agent.backend_config("claude") == {"tools": "Read, Write"}
        
        simple_agent = registry.get("simple-agent")
        assert simple_agent.role == "scout"
        assert simple_agent.mode == "primary"
        assert simple_agent.color is None
    
    def test_with_role_filter(self, tmp_path):
        """Should filter agents by role."""
        agents_file = tmp_path / "agents.yaml"
        agents_file.write_text("""
agents:
  worker1:
    description: "Worker 1"
    role: worker
    mode: subagent
  worker2:
    description: "Worker 2" 
    role: worker
    mode: subagent
  scout1:
    description: "Scout 1"
    role: scout
    mode: subagent
""")
        
        registry = load_agent_registry(agents_file)
        
        workers = registry.with_role("worker")
        assert len(workers) == 2
        assert sorted([a.name for a in workers]) == ["worker1", "worker2"]
        
        scouts = registry.with_role("scout")
        assert len(scouts) == 1
        assert scouts[0].name == "scout1"
        
        orchestrators = registry.with_role("orchestrator")
        assert len(orchestrators) == 0
    
    def test_missing_file_raises_error(self, tmp_path):
        """Should raise ValueError if agents.yaml doesn't exist."""
        missing_file = tmp_path / "nonexistent.yaml"
        
        with pytest.raises(ValueError, match="Agents file not found"):
            load_agent_registry(missing_file)
    
    def test_empty_agents_section(self, tmp_path):
        """Should handle empty agents section."""
        agents_file = tmp_path / "agents.yaml"
        agents_file.write_text("agents: {}")
        
        registry = load_agent_registry(agents_file)
        assert len(registry.all()) == 0
    
    def test_missing_agents_key(self, tmp_path):
        """Should handle YAML without agents key."""
        agents_file = tmp_path / "agents.yaml"
        agents_file.write_text("other: data")
        
        registry = load_agent_registry(agents_file)
        assert len(registry.all()) == 0
    
    def test_missing_required_field_raises_error(self, tmp_path):
        """Should raise error for missing required fields."""
        agents_file = tmp_path / "agents.yaml"
        agents_file.write_text("""
agents:
  invalid-agent:
    description: "Missing role field"
    mode: subagent
""")
        
        with pytest.raises(ValueError, match="Missing 'role' field"):
            load_agent_registry(agents_file)
    
    def test_get_unknown_agent_raises_keyerror(self, tmp_path):
        """Should raise KeyError for unknown agent."""
        agents_file = tmp_path / "agents.yaml"
        agents_file.write_text("agents: {}")
        
        registry = load_agent_registry(agents_file)
        
        with pytest.raises(KeyError, match="Agent 'unknown' not found"):
            registry.get("unknown")