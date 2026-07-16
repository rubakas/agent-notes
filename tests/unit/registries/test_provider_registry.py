"""Tests for agent_notes.registries.provider_registry."""
import pytest

from agent_notes.registries.provider_registry import load_provider_registry, default_provider_registry


class TestProviderRegistryLoads:
    def test_loads_anthropic_and_openai(self):
        registry = load_provider_registry()
        names = registry.names()
        assert "anthropic" in names
        assert "openai" in names

    def test_anthropic_efforts_and_default(self):
        registry = load_provider_registry()
        anthropic = registry.get("anthropic")
        assert anthropic.efforts == ("low", "medium", "high", "xhigh", "max")
        assert anthropic.default_effort == "high"

    def test_openai_efforts_and_default(self):
        registry = load_provider_registry()
        openai = registry.get("openai")
        assert openai.efforts == ("none", "minimal", "low", "medium", "high", "xhigh")
        assert openai.default_effort == "medium"

    def test_default_effort_is_in_own_efforts_list(self):
        """Each provider's default_effort must be a member of its own efforts
        list — otherwise the fallback-to-default would itself be invalid."""
        registry = load_provider_registry()
        for provider in registry.all():
            assert provider.default_effort in provider.efforts

    def test_get_unknown_provider_raises_key_error(self):
        registry = load_provider_registry()
        with pytest.raises(KeyError, match="not found in registry"):
            registry.get("does-not-exist")

    def test_names_are_sorted(self):
        registry = load_provider_registry()
        assert registry.names() == sorted(registry.names())

    def test_no_entry_for_providers_without_effort_support(self):
        """github-copilot, openrouter, google, moonshot deliberately have no
        provider effort file yet."""
        registry = load_provider_registry()
        names = registry.names()
        for unsupported in ("github-copilot", "openrouter", "google", "moonshot"):
            assert unsupported not in names


class TestDefaultProviderRegistry:
    def test_returns_provider_registry_instance(self):
        registry = default_provider_registry()
        assert "anthropic" in registry.names()

    def test_is_cached_singleton(self):
        assert default_provider_registry() is default_provider_registry()
