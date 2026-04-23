"""Test cli_backend module."""

import pytest
import yaml
from pathlib import Path

from agent_notes.cli_backend import load_registry, CLIBackend, CLIRegistry


class TestCLIBackend:
    """Test CLIBackend class."""
    
    def test_supports_feature(self):
        """Test supports() method."""
        backend = CLIBackend(
            name="test",
            label="Test CLI",
            global_home=Path.home() / ".test",
            local_dir=".test",
            layout={"config": "CONFIG.md"},
            features={"agents": True, "skills": False, "frontmatter": "test"},
            global_template="global-test.md"
        )
        
        assert backend.supports("agents") is True
        assert backend.supports("skills") is False
        assert backend.supports("nonexistent") is False
        # Non-boolean values should be truthy/falsy
        assert backend.supports("frontmatter") is True  # "test" is truthy
    
    def test_local_path(self):
        """Test local_path() method."""
        backend = CLIBackend(
            name="test",
            label="Test CLI",
            global_home=Path.home() / ".test",
            local_dir=".test",
            layout={},
            features={},
            global_template=None
        )
        
        assert backend.local_path() == Path(".test")


class TestCLIRegistry:
    """Test CLIRegistry class."""
    
    def test_registry_operations(self):
        """Test basic registry operations."""
        backend1 = CLIBackend(
            name="claude",
            label="Claude Code",
            global_home=Path.home() / ".claude",
            local_dir=".claude",
            layout={"agents": "agents/"},
            features={"agents": True, "rules": True},
            global_template="global-claude.md"
        )
        
        backend2 = CLIBackend(
            name="opencode",
            label="OpenCode",
            global_home=Path.home() / ".config/opencode",
            local_dir=".opencode",
            layout={"agents": "agents/"},
            features={"agents": True, "rules": False},
            global_template="global-opencode.md"
        )
        
        registry = CLIRegistry([backend1, backend2])
        
        # Test all()
        assert len(registry.all()) == 2
        assert backend1 in registry.all()
        assert backend2 in registry.all()
        
        # Test get()
        assert registry.get("claude") == backend1
        assert registry.get("opencode") == backend2
        with pytest.raises(KeyError):
            registry.get("nonexistent")
        
        # Test names()
        assert registry.names() == ["claude", "opencode"]  # sorted
        
        # Test with_feature()
        agents_backends = registry.with_feature("agents")
        assert len(agents_backends) == 2
        
        rules_backends = registry.with_feature("rules")
        assert len(rules_backends) == 1
        assert rules_backends[0] == backend1
        
        missing_backends = registry.with_feature("nonexistent")
        assert len(missing_backends) == 0


class TestLoadRegistry:
    """Test load_registry function."""
    
    def test_load_default_registry(self):
        """Test loading the default registry returns 3 backends."""
        registry = load_registry()
        
        # Should have claude, opencode, copilot
        assert len(registry.all()) == 3
        names = registry.names()
        assert "claude" in names
        assert "opencode" in names
        assert "copilot" in names
    
    def test_claude_backend_properties(self):
        """Test specific properties of the claude backend."""
        registry = load_registry()
        claude = registry.get("claude")
        
        assert claude.label == "Claude Code"
        assert claude.global_home == Path.home() / ".claude"
        assert claude.supports("agents") is True
        assert claude.supports("rules") is True
        assert claude.exclude_flag == "claude_exclude"
    
    def test_opencode_backend_properties(self):
        """Test specific properties of the opencode backend."""
        registry = load_registry()
        opencode = registry.get("opencode")
        
        assert opencode.label == "OpenCode"
        assert opencode.global_home == Path.home() / ".config/opencode"
        assert opencode.supports("agents") is True
        assert opencode.supports("rules") is False
        assert opencode.strip_memory_section is True
        assert opencode.exclude_flag == "opencode_exclude"
    
    def test_copilot_backend_properties(self):
        """Test specific properties of the copilot backend."""
        registry = load_registry()
        copilot = registry.get("copilot")
        
        assert copilot.label == "GitHub Copilot"
        assert copilot.global_home == Path.home() / ".github"
        assert copilot.supports("agents") is False
        assert copilot.supports("skills") is False
        assert copilot.exclude_flag is None
    
    def test_with_feature_filtering(self):
        """Test filtering by features."""
        registry = load_registry()
        
        # Only claude should support rules
        rules_backends = registry.with_feature("rules")
        assert len(rules_backends) == 1
        assert rules_backends[0].name == "claude"
        
        # Claude and opencode should support agents
        agents_backends = registry.with_feature("agents")
        assert len(agents_backends) == 2
        agent_names = {b.name for b in agents_backends}
        assert agent_names == {"claude", "opencode"}
    
    def test_load_custom_directory(self, tmp_path):
        """Test loading from a custom directory."""
        # Create a minimal valid YAML
        cli_dir = tmp_path / "cli"
        cli_dir.mkdir()
        
        yaml_content = {
            "name": "test",
            "label": "Test CLI",
            "global_home": "~/.test",
            "local_dir": ".test",
            "layout": {"config": "CONFIG.md"},
            "features": {"agents": True}
        }
        
        yaml_file = cli_dir / "test.yaml"
        yaml_file.write_text(yaml.dump(yaml_content))
        
        registry = load_registry(cli_dir)
        assert len(registry.all()) == 1
        
        backend = registry.get("test")
        assert backend.name == "test"
        assert backend.label == "Test CLI"
        assert backend.global_home == Path.home() / ".test"
    
    def test_missing_directory_error(self, tmp_path):
        """Test error when CLI directory doesn't exist."""
        nonexistent_dir = tmp_path / "nonexistent"
        
        with pytest.raises(ValueError, match="CLI directory not found"):
            load_registry(nonexistent_dir)
    
    def test_missing_required_field_error(self, tmp_path):
        """Test error when YAML is missing required fields."""
        cli_dir = tmp_path / "cli"
        cli_dir.mkdir()
        
        # YAML missing 'features' field
        incomplete_yaml = {
            "name": "test",
            "label": "Test CLI",
            "global_home": "~/.test",
            "layout": {"config": "CONFIG.md"}
            # missing 'features'
        }
        
        yaml_file = cli_dir / "incomplete.yaml"
        yaml_file.write_text(yaml.dump(incomplete_yaml))
        
        with pytest.raises(ValueError, match="Missing required field 'features'"):
            load_registry(cli_dir)
    
    def test_sorted_names(self):
        """Test that names() returns sorted list."""
        registry = load_registry()
        names = registry.names()
        
        # Should be ["claude", "copilot", "opencode"] (alphabetical)
        assert names == sorted(names)
        expected = ["claude", "copilot", "opencode"]
        assert names == expected
    
    def test_accepted_providers_parsing(self):
        """Test that accepted_providers is parsed correctly."""
        registry = load_registry()
        
        # Test claude
        claude = registry.get("claude")
        assert claude.accepted_providers == ("anthropic", "bedrock", "vertex")
        
        # Test opencode
        opencode = registry.get("opencode")
        expected = ("github-copilot", "anthropic", "openrouter", "openai", "google", "moonshot")
        assert opencode.accepted_providers == expected
        
        # Test copilot
        copilot = registry.get("copilot")
        assert copilot.accepted_providers == ("github-copilot",)
    
    def test_first_alias_for_method(self):
        """Test first_alias_for method."""
        registry = load_registry()
        claude = registry.get("claude")
        
        # Test with compatible aliases
        aliases = {"anthropic": "claude-opus-4-7", "openai": "gpt-4"}
        result = claude.first_alias_for(aliases)
        assert result == ("anthropic", "claude-opus-4-7")
        
        # Test with no compatible aliases
        aliases = {"openai": "gpt-4", "google": "gemini"}
        result = claude.first_alias_for(aliases)
        assert result is None
        
        # Test empty aliases
        result = claude.first_alias_for({})
        assert result is None
    
    def test_first_alias_for_ordering(self):
        """Test that first_alias_for respects provider ordering."""
        registry = load_registry()
        opencode = registry.get("opencode")
        
        # opencode accepted_providers: [github-copilot, anthropic, openrouter, ...]
        aliases = {
            "anthropic": "claude-opus-4-7",
            "github-copilot": "github-copilot/claude-opus-4.7",
            "openai": "gpt-4"
        }
        
        # Should return github-copilot (first in accepted_providers list)
        result = opencode.first_alias_for(aliases)
        assert result == ("github-copilot", "github-copilot/claude-opus-4.7")
    
    def test_first_alias_for_claude_vs_opencode(self):
        """Test first_alias_for behaves differently for claude vs opencode."""
        registry = load_registry()
        claude = registry.get("claude")
        opencode = registry.get("opencode")
        
        # Same aliases for both
        aliases = {
            "anthropic": "claude-opus-4-7",
            "github-copilot": "github-copilot/claude-opus-4.7"
        }
        
        # Claude should prefer anthropic (first in its accepted_providers)
        claude_result = claude.first_alias_for(aliases)
        assert claude_result == ("anthropic", "claude-opus-4-7")
        
        # OpenCode should prefer github-copilot (first in its accepted_providers)
        opencode_result = opencode.first_alias_for(aliases)
        assert opencode_result == ("github-copilot", "github-copilot/claude-opus-4.7")