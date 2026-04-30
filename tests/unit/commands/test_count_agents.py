"""Regression tests for count_agents() — must work even when dist/ is absent."""
import pytest
from pathlib import Path
from unittest.mock import patch


class TestCountAgents:
    def test_count_agents_without_dist_directory(self, tmp_path):
        """count_agents must not return 0 just because dist/ doesn't exist."""
        from agent_notes.commands._install_helpers import count_agents
        from agent_notes.registries.cli_registry import load_registry

        registry = load_registry()
        claude = registry.get("claude")

        # Verify dist/ NOT touching is guaranteed by using a patched DIST_DIR
        # that points to a nonexistent path.
        with patch("agent_notes.config.DIST_DIR", tmp_path / "dist_does_not_exist"):
            count = count_agents(claude)

        # agents.yaml has agents; at least one must be included for claude backend
        assert count > 0, "count_agents returned 0 even though agents.yaml exists"

    def test_count_agents_does_not_touch_dist(self, tmp_path):
        """count_agents must NOT read from dist/ at all."""
        from agent_notes.commands._install_helpers import count_agents
        from agent_notes.registries.cli_registry import load_registry

        registry = load_registry()
        claude = registry.get("claude")

        # tmp_path/dist/ is absent — if count_agents tried to glob it, it would return 0
        absent_dist = tmp_path / "dist"
        assert not absent_dist.exists()

        with patch("agent_notes.config.DIST_DIR", absent_dist):
            count = count_agents(claude)

        # Should still reflect the YAML count, not 0
        assert count > 0

    def test_count_agents_respects_backend_exclusions(self):
        """Agents with claude_exclude: true must not be counted for claude backend."""
        from agent_notes.commands._install_helpers import count_agents
        from agent_notes.registries.cli_registry import load_registry
        from agent_notes.registries.agent_registry import load_agent_registry

        registry = load_registry()
        claude = registry.get("claude")
        agent_reg = load_agent_registry()

        expected = sum(1 for a in agent_reg.all() if not a.excluded_from("claude"))
        actual = count_agents(claude)
        assert actual == expected

    def test_count_agents_returns_zero_for_no_agents_backend(self):
        """Returns 0 for a backend that doesn't support agents."""
        from agent_notes.commands._install_helpers import count_agents
        from agent_notes.registries.cli_registry import load_registry

        registry = load_registry()
        # copilot doesn't support agents
        try:
            copilot = registry.get("copilot")
            assert count_agents(copilot) == 0
        except KeyError:
            pytest.skip("copilot backend not in registry")
