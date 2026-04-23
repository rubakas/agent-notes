"""Shared test fixtures."""
import os
import json
import pytest
from pathlib import Path
from unittest.mock import patch
from dataclasses import dataclass


@dataclass(frozen=True) 
class MockCLIBackend:
    """Mock CLI backend for testing."""
    name: str
    label: str
    global_home: Path
    local_dir: str 
    layout: dict
    features: dict
    global_template: str = None
    exclude_flag: str = None
    strip_memory_section: bool = False
    settings_template: str = None

    def supports(self, feature: str) -> bool:
        """Return True if the backend has that feature enabled."""
        val = self.features.get(feature)
        return bool(val)

    def local_path(self) -> Path:
        """Return Path(self.local_dir) relative to cwd."""
        return Path(self.local_dir)


class MockCLIRegistry:
    """Mock CLI registry for testing."""
    def __init__(self, backends):
        self._backends = backends
        self._by_name = {b.name: b for b in backends}
    
    def all(self):
        return self._backends.copy()
    
    def get(self, name: str):
        return self._by_name[name]
    
    def names(self):
        return sorted(self._by_name.keys())
    
    def with_feature(self, feature: str):
        return [b for b in self._backends if b.supports(feature)]


@pytest.fixture
def mock_registry(tmp_path):
    """Mock CLI registry with claude and opencode backends."""
    claude_home = tmp_path / "claude"
    opencode_home = tmp_path / "opencode"
    
    claude = MockCLIBackend(
        name="claude",
        label="Claude Code",
        global_home=claude_home,
        local_dir=".claude",
        layout={
            "agents": "agents/",
            "skills": "skills/",
            "rules": "rules/",
            "config": "CLAUDE.md"
        },
        features={
            "agents": True,
            "skills": True,
            "rules": True,
            "config": True
        }
    )
    
    opencode = MockCLIBackend(
        name="opencode",
        label="OpenCode",
        global_home=opencode_home,
        local_dir=".opencode",
        layout={
            "agents": "agents/",
            "skills": "skills/",
            "config": "AGENTS.md"
        },
        features={
            "agents": True,
            "skills": True,
            "config": True
        }
    )
    
    return MockCLIRegistry([claude, opencode])


@pytest.fixture
def seeded_state(tmp_path, monkeypatch):
    """Create a minimal state.json in an isolated XDG_CONFIG_HOME."""
    # Isolate XDG_CONFIG_HOME
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    
    from agent_notes.state import State, BackendState, InstalledItem, save, now_iso
    
    claude_home = tmp_path / "claude"
    
    state = State(
        installed_at=now_iso(),
        updated_at=now_iso(),
        mode="symlink", 
        scope="global",
        cli_backends=["claude", "opencode"],
        installed={
            "claude": BackendState(
                agents={"lead.md": InstalledItem(sha="a"*64, target=str(claude_home / "agents" / "lead.md"), mode="symlink")},
            ),
        },
    )
    save(state)
    return state


@pytest.fixture
def seeded_copy_state(tmp_path, monkeypatch):
    """State with mode=copy to enable drift checking."""
    # Isolate XDG_CONFIG_HOME 
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    
    from agent_notes.state import State, BackendState, InstalledItem, save, now_iso
    
    claude_home = tmp_path / "claude" 
    
    # Create the actual target file
    claude_home.mkdir(parents=True)
    (claude_home / "agents").mkdir()
    (claude_home / "CLAUDE.md").write_text("original content")
    
    state = State(
        installed_at=now_iso(),
        updated_at=now_iso(),
        mode="copy",  # key difference
        scope="global",
        cli_backends=["claude"],
        installed={
            "claude": BackendState(
                config={"CLAUDE.md": InstalledItem(sha="original_sha", target=str(claude_home / "CLAUDE.md"), mode="copy")},
            ),
        },
    )
    save(state)
    return state


@pytest.fixture
def mock_load_registry(mock_registry):
    """Mock cli_backend.load_registry to return our test registry."""
    with patch('agent_notes.cli_backend.load_registry', return_value=mock_registry):
        yield mock_registry


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


@pytest.fixture(autouse=True)
def mock_paths(tmp_path, monkeypatch):
    """Mock all config paths to use temporary directories.
    
    Autouse ensures NO test can ever write to real ~/.claude/ or ~/.config/opencode/.
    """
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
    
    # Patch commands modules instead of the shim modules
    import agent_notes.commands._install_helpers as inst_helpers
    monkeypatch.setattr(inst_helpers, 'CLAUDE_HOME', tmp_claude)
    monkeypatch.setattr(inst_helpers, 'OPENCODE_HOME', tmp_opencode)
    monkeypatch.setattr(inst_helpers, 'GITHUB_HOME', tmp_github)
    monkeypatch.setattr(inst_helpers, 'AGENTS_HOME', tmp_agents)
    
    # Also patch installer module paths
    import agent_notes.installer as installer_mod
    monkeypatch.setattr(installer_mod, 'AGENTS_HOME', tmp_agents)
    
    # Patch top-level shims — they snapshot config constants at import time,
    # and commands/* read via _shim.<const>, so the shims must be patched too.
    for shim_name in ('install', 'validate', 'doctor', 'wizard', 'list',
                      'update', 'regenerate', 'build', 'memory', 'set_role'):
        try:
            shim_mod = __import__(f'agent_notes.{shim_name}', fromlist=[shim_name])
        except ImportError:
            continue
        for attr, val in (('CLAUDE_HOME', tmp_claude),
                          ('OPENCODE_HOME', tmp_opencode),
                          ('GITHUB_HOME', tmp_github),
                          ('AGENTS_HOME', tmp_agents),
                          ('MEMORY_DIR', tmp_memory),
                          ('BACKUP_DIR', tmp_backup)):
            if hasattr(shim_mod, attr):
                monkeypatch.setattr(shim_mod, attr, val)
    
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