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
    def test_worker_role_resolves_to_gpt_model_for_codex(self):
        """Worker role (typical_class=sonnet) should resolve to a gpt-* model for codex."""
        from agent_notes.registries.model_registry import load_model_registry
        from agent_notes.registries.role_registry import load_role_registry

        model_registry = load_model_registry()
        role_registry = load_role_registry()
        registry = load_registry()
        codex = registry.get("codex")

        role = role_registry.get("worker")
        resolved_model = None
        for model in reversed(model_registry.all()):
            if model.model_class != role.typical_class:
                continue
            result = model.resolve_for_providers(list(codex.accepted_providers))
            if result is not None:
                _provider, alias_str = result
                resolved_model = alias_str
                break

        assert resolved_model is not None, (
            "No model resolved for worker role + codex backend (openai provider)"
        )
        assert "gpt" in resolved_model.lower(), (
            f"Resolved model '{resolved_model}' for codex/worker should contain 'gpt'"
        )

    def test_scout_role_resolves_to_gpt_model_for_codex(self):
        """Scout role (typical_class=haiku) should resolve to a gpt-* model for codex."""
        from agent_notes.registries.model_registry import load_model_registry
        from agent_notes.registries.role_registry import load_role_registry

        model_registry = load_model_registry()
        role_registry = load_role_registry()
        registry = load_registry()
        codex = registry.get("codex")

        role = role_registry.get("scout")
        resolved_model = None
        for model in reversed(model_registry.all()):
            if model.model_class != role.typical_class:
                continue
            result = model.resolve_for_providers(list(codex.accepted_providers))
            if result is not None:
                _provider, alias_str = result
                resolved_model = alias_str
                break

        assert resolved_model is not None, (
            "No model resolved for scout role + codex backend (openai provider)"
        )
        assert "gpt" in resolved_model.lower(), (
            f"Resolved model '{resolved_model}' for codex/scout should contain 'gpt'"
        )

    def test_claude_backend_does_not_resolve_gpt_models(self):
        """Claude backend (anthropic provider) must not select gpt-* models."""
        from agent_notes.registries.model_registry import load_model_registry
        from agent_notes.registries.role_registry import load_role_registry

        model_registry = load_model_registry()
        role_registry = load_role_registry()
        registry = load_registry()

        try:
            claude = registry.get("claude")
        except KeyError:
            pytest.skip("claude backend not in registry")

        role = role_registry.get("worker")
        for model in model_registry.all():
            if model.model_class != role.typical_class:
                continue
            result = model.resolve_for_providers(list(claude.accepted_providers))
            if result is not None:
                _provider, alias_str = result
                assert "gpt" not in alias_str.lower(), (
                    f"Claude backend resolved to '{alias_str}' — gpt models must not be selected"
                )
