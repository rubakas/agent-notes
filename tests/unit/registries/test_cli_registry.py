"""Tests for the CLI registry, focusing on codex backend."""
import pytest
from pathlib import Path

from agent_notes.registries.cli_registry import load_registry


# ---------------------------------------------------------------------------
# codex backend resolves
# ---------------------------------------------------------------------------

class TestCodexBackendExists:
    def test_registry_resolves_codex(self):
        registry = load_registry()
        backend = registry.get("codex")
        assert backend is not None

    def test_codex_name(self):
        registry = load_registry()
        backend = registry.get("codex")
        assert backend.name == "codex"

    def test_codex_global_home_ends_with_dot_codex(self):
        registry = load_registry()
        backend = registry.get("codex")
        assert str(backend.global_home).endswith(".codex"), (
            f"global_home '{backend.global_home}' should end with '.codex'"
        )


# ---------------------------------------------------------------------------
# Feature flags
# ---------------------------------------------------------------------------

class TestCodexFeatures:
    def test_supports_agents(self):
        registry = load_registry()
        backend = registry.get("codex")
        assert backend.supports("agents") is True

    def test_supports_skills(self):
        registry = load_registry()
        backend = registry.get("codex")
        assert backend.supports("skills") is True

    def test_does_not_support_rules(self):
        registry = load_registry()
        backend = registry.get("codex")
        assert backend.supports("rules") is False

    def test_does_not_support_commands(self):
        registry = load_registry()
        backend = registry.get("codex")
        assert backend.supports("commands") is False

    def test_does_not_support_memory(self):
        registry = load_registry()
        backend = registry.get("codex")
        assert backend.supports("memory") is False

    def test_frontmatter_feature_is_codex(self):
        registry = load_registry()
        backend = registry.get("codex")
        assert backend.features.get("frontmatter") == "codex"


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

class TestCodexLayout:
    def test_config_is_agents_md(self):
        registry = load_registry()
        backend = registry.get("codex")
        assert backend.layout.get("config") == "AGENTS.md"

    def test_layout_has_hooks(self):
        registry = load_registry()
        backend = registry.get("codex")
        assert "hooks" in backend.layout, "codex layout must include 'hooks' key"
        assert backend.layout["hooks"] == "hooks.json"


# ---------------------------------------------------------------------------
# Providers
# ---------------------------------------------------------------------------

class TestCodexProviders:
    def test_accepted_providers_is_openai(self):
        registry = load_registry()
        backend = registry.get("codex")
        assert "openai" in backend.accepted_providers

    def test_accepted_providers_tuple(self):
        registry = load_registry()
        backend = registry.get("codex")
        assert isinstance(backend.accepted_providers, tuple)


# ---------------------------------------------------------------------------
# Model resolution: codex resolves openai models, not claude models
# ---------------------------------------------------------------------------

class TestModelResolutionForCodex:
    """Exercise production selection (select_model_for_role), not a re-implementation."""

    def _select(self, role_name, cli_name):
        from agent_notes.registries.model_registry import load_model_registry
        from agent_notes.registries.role_registry import load_role_registry
        from agent_notes.services.model_resolver import select_model_for_role

        backend = load_registry().get(cli_name)
        role = load_role_registry().get(role_name)
        return select_model_for_role(load_model_registry().all(), role, backend)

    @pytest.mark.parametrize("role_name", ["orchestrator", "reasoner", "worker", "scout"])
    def test_every_role_resolves_to_a_gpt_model_for_codex(self, role_name):
        matched, resolved = self._select(role_name, "codex")

        assert matched is not None, (
            f"No model resolved for {role_name} role + codex backend (openai provider)"
        )
        provider, alias_str = resolved
        assert provider == "openai"
        assert "gpt" in alias_str.lower(), (
            f"Resolved model '{alias_str}' for codex/{role_name} should contain 'gpt'"
        )

    @pytest.mark.parametrize("role_name", ["orchestrator", "reasoner", "worker", "scout"])
    def test_claude_backend_never_resolves_gpt_models(self, role_name):
        matched, resolved = self._select(role_name, "claude")

        assert matched is not None
        provider, alias_str = resolved
        assert provider == "anthropic"
        assert "gpt" not in alias_str.lower(), (
            f"Claude backend resolved to '{alias_str}' — gpt models must not be selected"
        )
