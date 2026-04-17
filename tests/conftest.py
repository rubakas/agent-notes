"""Shared test fixtures."""
import os
import pytest
from pathlib import Path
from unittest.mock import patch


@pytest.fixture
def project_root():
    """Return the project root directory."""
    return Path(__file__).parent.parent


@pytest.fixture
def tmp_home(tmp_path):
    """Create a temporary home directory for install tests."""
    home = tmp_path / "home"
    home.mkdir()
    return home


@pytest.fixture
def tmp_project(tmp_path):
    """Create a temporary project directory for local install tests."""
    project = tmp_path / "project"
    project.mkdir()
    return project


@pytest.fixture
def mock_paths(tmp_path, monkeypatch):
    """Mock all config paths to use temporary directories."""
    # Create temp directories
    tmp_claude = tmp_path / "claude"
    tmp_opencode = tmp_path / "opencode" 
    tmp_github = tmp_path / "github"
    tmp_agents = tmp_path / "agents"
    tmp_memory = tmp_path / "memory"
    tmp_backup = tmp_path / "backup"
    
    tmp_claude.mkdir()
    tmp_opencode.mkdir()
    tmp_github.mkdir()
    tmp_agents.mkdir()
    tmp_memory.mkdir()
    tmp_backup.mkdir()
    
    # Mock paths in config module
    import agent_notes.config as config
    monkeypatch.setattr(config, 'CLAUDE_HOME', tmp_claude)
    monkeypatch.setattr(config, 'OPENCODE_HOME', tmp_opencode)
    monkeypatch.setattr(config, 'GITHUB_HOME', tmp_github)
    monkeypatch.setattr(config, 'AGENTS_HOME', tmp_agents)
    monkeypatch.setattr(config, 'MEMORY_DIR', tmp_memory)
    monkeypatch.setattr(config, 'BACKUP_DIR', tmp_backup)
    
    # Also patch modules that import from config at module level
    import agent_notes.memory as memory
    monkeypatch.setattr(memory, 'MEMORY_DIR', tmp_memory)
    monkeypatch.setattr(memory, 'BACKUP_DIR', tmp_backup)
    
    import agent_notes.install as inst
    monkeypatch.setattr(inst, 'CLAUDE_HOME', tmp_claude)
    monkeypatch.setattr(inst, 'OPENCODE_HOME', tmp_opencode)
    monkeypatch.setattr(inst, 'GITHUB_HOME', tmp_github)
    monkeypatch.setattr(inst, 'AGENTS_HOME', tmp_agents)
    
    # Patch validate module paths (only attrs it actually imports)
    import agent_notes.validate as validate_mod
    monkeypatch.setattr(validate_mod, 'ROOT', tmp_path)
    tmp_dist = tmp_path / "dist"
    monkeypatch.setattr(validate_mod, 'DIST_CLAUDE_DIR', tmp_dist / "claude")
    monkeypatch.setattr(validate_mod, 'DIST_OPENCODE_DIR', tmp_dist / "opencode")
    monkeypatch.setattr(validate_mod, 'DIST_RULES_DIR', tmp_dist / "rules")
    
    return {
        'claude': tmp_claude,
        'opencode': tmp_opencode,
        'github': tmp_github,
        'agents': tmp_agents,
        'memory': tmp_memory,
        'backup': tmp_backup
    }


@pytest.fixture
def disable_colors(monkeypatch):
    """Disable colors in output for cleaner test assertions."""
    import agent_notes.config as config
    config.Color.disable()


@pytest.fixture
def sample_agents_yaml():
    """Sample agents.yaml content for testing."""
    return """
agents:
  test-agent:
    description: "Test agent description"
    tier: sonnet
    mode: primary
    color: blue
    effort: medium
    claude:
      tools: "Read, Write"
      memory: user
    opencode:
      permission:
        edit: allow
        bash: allow

  test-reviewer:
    description: "Test reviewer description"
    tier: haiku
    mode: subagent
    color: yellow
    effort: low
    claude:
      disallowedTools: "Write, Edit"
    opencode:
      permission:
        edit: deny
        bash:
          "*": deny
          "git log*": allow

tiers:
  opus:
    claude: opus
    opencode: "github-copilot/claude-opus-4.7"
  sonnet:
    claude: sonnet
    opencode: "github-copilot/claude-sonnet-4"
  haiku:
    claude: haiku
    opencode: "github-copilot/claude-haiku-4.5"
"""


@pytest.fixture
def sample_agent_content():
    """Sample agent markdown content."""
    return """You are a test agent for testing purposes.

## Instructions

Follow these rules:
- Be helpful
- Be accurate
- Be concise

## Memory

Remember important context between conversations.

## Examples

Here's how to be helpful:

```python
def hello():
    return "Hello, World!"
```

That's all!
"""