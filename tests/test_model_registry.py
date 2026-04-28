"""Test model_registry module."""

import pytest
import yaml
from pathlib import Path

from agent_notes.model_registry import (
    load_model_registry, 
    Model, 
    ModelRegistry,
    default_registry
)


class TestModel:
    """Test Model class."""
    
    def test_has_alias_for(self):
        """Test has_alias_for method."""
        model = Model(
            id="test-model",
            label="Test Model",
            family="test",
            model_class="opus",
            aliases={"anthropic": "model-1", "github-copilot": "model-2"}
        )
        
        assert model.has_alias_for("anthropic") is True
        assert model.has_alias_for("github-copilot") is True
        assert model.has_alias_for("openai") is False
    
    def test_resolve_for_providers(self):
        """Test resolve_for_providers method."""
        model = Model(
            id="test-model",
            label="Test Model",
            family="test",
            model_class="opus",
            aliases={"anthropic": "model-1", "github-copilot": "model-2"}
        )
        
        # First matching provider
        result = model.resolve_for_providers(["anthropic"])
        assert result == ("anthropic", "model-1")
        
        # First matching provider from ordered list
        result = model.resolve_for_providers(["openai", "anthropic", "github-copilot"])
        assert result == ("anthropic", "model-1")
        
        # No matching provider
        result = model.resolve_for_providers(["openai", "openrouter"])
        assert result is None
    
    def test_model_frozen(self):
        """Test that Model is frozen."""
        model = Model(
            id="test-model",
            label="Test Model",
            family="test",
            model_class="opus",
            aliases={}
        )
        
        with pytest.raises(Exception):  # FrozenInstanceError or AttributeError
            model.id = "new-id"


class TestModelRegistry:
    """Test ModelRegistry class."""
    
    def test_registry_operations(self):
        """Test basic registry operations."""
        model1 = Model(
            id="claude-opus-4-7",
            label="Claude Opus 4.7",
            family="claude",
            model_class="opus",
            aliases={"anthropic": "claude-opus-4-7"}
        )
        
        model2 = Model(
            id="claude-sonnet-4",
            label="Claude Sonnet 4",
            family="claude",
            model_class="sonnet",
            aliases={"anthropic": "sonnet"}
        )
        
        registry = ModelRegistry([model1, model2])
        
        # Test all() - returns sorted by id
        models = registry.all()
        assert len(models) == 2
        assert models[0].id == "claude-opus-4-7"
        assert models[1].id == "claude-sonnet-4"
        
        # Test get()
        assert registry.get("claude-opus-4-7") == model1
        assert registry.get("claude-sonnet-4") == model2
        
        # Test get() with unknown model
        with pytest.raises(KeyError, match="Model 'unknown' not found"):
            registry.get("unknown")
        
        # Test ids()
        assert registry.ids() == ["claude-opus-4-7", "claude-sonnet-4"]
    
    def test_by_class(self):
        """Test by_class method."""
        opus_model = Model(
            id="claude-opus-4-7",
            label="Claude Opus 4.7",
            family="claude",
            model_class="opus",
            aliases={}
        )
        
        sonnet_model = Model(
            id="claude-sonnet-4",
            label="Claude Sonnet 4",
            family="claude",
            model_class="sonnet",
            aliases={}
        )
        
        haiku_model = Model(
            id="claude-haiku-4-5",
            label="Claude Haiku 4.5",
            family="claude",
            model_class="haiku",
            aliases={}
        )
        
        registry = ModelRegistry([opus_model, sonnet_model, haiku_model])
        
        opus_models = registry.by_class("opus")
        assert len(opus_models) == 1
        assert opus_models[0] == opus_model
        
        sonnet_models = registry.by_class("sonnet")
        assert len(sonnet_models) == 1
        assert sonnet_models[0] == sonnet_model
        
        haiku_models = registry.by_class("haiku")
        assert len(haiku_models) == 1
        assert haiku_models[0] == haiku_model
        
        # Non-existent class
        unknown_models = registry.by_class("unknown")
        assert len(unknown_models) == 0
    
    def test_compatible_with_providers(self):
        """Test compatible_with_providers method."""
        anthropic_model = Model(
            id="claude-opus-4-7",
            label="Claude Opus 4.7",
            family="claude",
            model_class="opus",
            aliases={"anthropic": "claude-opus-4-7"}
        )
        
        copilot_model = Model(
            id="claude-sonnet-4",
            label="Claude Sonnet 4",
            family="claude",
            model_class="sonnet",
            aliases={"github-copilot": "github-copilot/claude-sonnet-4"}
        )
        
        both_model = Model(
            id="claude-haiku-4-5",
            label="Claude Haiku 4.5", 
            family="claude",
            model_class="haiku",
            aliases={
                "anthropic": "haiku",
                "github-copilot": "github-copilot/claude-haiku-4.5"
            }
        )
        
        registry = ModelRegistry([anthropic_model, copilot_model, both_model])
        
        # Only anthropic
        anthropic_compat = registry.compatible_with_providers(["anthropic"])
        assert len(anthropic_compat) == 2
        ids = [m.id for m in anthropic_compat]
        assert "claude-opus-4-7" in ids
        assert "claude-haiku-4-5" in ids
        
        # Only github-copilot
        copilot_compat = registry.compatible_with_providers(["github-copilot"])
        assert len(copilot_compat) == 2
        ids = [m.id for m in copilot_compat]
        assert "claude-sonnet-4" in ids
        assert "claude-haiku-4-5" in ids
        
        # No compatibility
        empty_compat = registry.compatible_with_providers(["openai"])
        assert len(empty_compat) == 0


class TestLoadModelRegistry:
    """Test load_model_registry function."""
    
    def test_load_default_registry(self):
        """Test loading the default registry returns 4 models."""
        registry = load_model_registry()
        
        # Should have 8 claude models (current + legacy)
        assert len(registry.all()) == 8
        ids = registry.ids()
        assert "claude-haiku-4-5" in ids
        assert "claude-opus-4-1" in ids
        assert "claude-opus-4-5" in ids
        assert "claude-opus-4-6" in ids
        assert "claude-opus-4-7" in ids
        assert "claude-sonnet-4" in ids
        assert "claude-sonnet-4-5" in ids
        assert "claude-sonnet-4-6" in ids
    
    def test_get_specific_models(self):
        """Test getting specific models from default registry."""
        registry = load_model_registry()
        
        # Test claude-opus-4-7
        opus = registry.get("claude-opus-4-7")
        assert opus.label == "Claude Opus 4.7"
        assert opus.family == "claude"
        assert opus.model_class == "opus"
        assert opus.aliases["anthropic"] == "opus"
        assert opus.aliases["github-copilot"] == "github-copilot/claude-opus-4.7"
        
        # Test claude-sonnet-4 (deprecated, full ID alias)
        sonnet = registry.get("claude-sonnet-4")
        assert sonnet.label == "Claude Sonnet 4"
        assert sonnet.model_class == "sonnet"
        assert sonnet.aliases["anthropic"] == "claude-sonnet-4-20250514"

        # Test claude-sonnet-4-6 (current sonnet)
        sonnet46 = registry.get("claude-sonnet-4-6")
        assert sonnet46.label == "Claude Sonnet 4.6"
        assert sonnet46.model_class == "sonnet"
        assert sonnet46.aliases["anthropic"] == "sonnet"
    
    def test_get_unknown_model_raises_error(self):
        """Test that getting unknown model raises KeyError."""
        registry = load_model_registry()
        
        with pytest.raises(KeyError, match="Model 'unknown' not found"):
            registry.get("unknown")
    
    def test_by_class_filtering(self):
        """Test filtering models by class."""
        registry = load_model_registry()
        
        # Test opus models
        opus_models = registry.by_class("opus")
        assert len(opus_models) == 4
        opus_ids = [m.id for m in opus_models]
        assert "claude-opus-4-1" in opus_ids
        assert "claude-opus-4-5" in opus_ids
        assert "claude-opus-4-6" in opus_ids
        assert "claude-opus-4-7" in opus_ids

        # Test sonnet models
        sonnet_models = registry.by_class("sonnet")
        assert len(sonnet_models) == 3
        sonnet_ids = [m.id for m in sonnet_models]
        assert "claude-sonnet-4" in sonnet_ids
        assert "claude-sonnet-4-5" in sonnet_ids
        assert "claude-sonnet-4-6" in sonnet_ids
        
        # Test haiku models
        haiku_models = registry.by_class("haiku")
        assert len(haiku_models) == 1
        assert haiku_models[0].id == "claude-haiku-4-5"
    
    def test_anthropic_compatibility(self):
        """Test filtering by anthropic provider."""
        registry = load_model_registry()
        
        anthropic_models = registry.compatible_with_providers(["anthropic"])
        assert len(anthropic_models) == 8
        
        # All claude models should be compatible
        for model in anthropic_models:
            assert model.has_alias_for("anthropic")
    
    def test_github_copilot_compatibility(self):
        """Test filtering by github-copilot provider."""
        registry = load_model_registry()
        
        copilot_models = registry.compatible_with_providers(["github-copilot"])
        assert len(copilot_models) == 8
        
        # All claude models should be compatible
        for model in copilot_models:
            assert model.has_alias_for("github-copilot")
    
    def test_openrouter_compatibility(self):
        """Test filtering by openrouter provider (should be empty for now)."""
        registry = load_model_registry()
        
        openrouter_models = registry.compatible_with_providers(["openrouter"])
        assert len(openrouter_models) == 0
    
    def test_resolve_for_providers_ordering(self):
        """Test that resolve_for_providers respects ordering."""
        registry = load_model_registry()
        opus = registry.get("claude-opus-4-7")
        
        # Should prefer first in list
        result = opus.resolve_for_providers(["openrouter", "anthropic"])
        assert result == ("anthropic", "opus")
        
        result = opus.resolve_for_providers(["github-copilot", "anthropic"])
        assert result == ("github-copilot", "github-copilot/claude-opus-4.7")
    
    def test_resolve_no_compatibility(self):
        """Test resolve_for_providers returns None when no compatibility."""
        registry = load_model_registry()
        opus = registry.get("claude-opus-4-7")
        
        result = opus.resolve_for_providers(["openai"])
        assert result is None
    
    def test_load_malformed_yaml_error(self, tmp_path):
        """Test error when YAML file is malformed."""
        models_dir = tmp_path / "models"
        models_dir.mkdir()
        
        # Create malformed YAML
        yaml_file = models_dir / "bad.yaml"
        yaml_file.write_text("invalid: yaml: content: [\n")
        
        with pytest.raises(ValueError, match="Invalid YAML in bad.yaml"):
            load_model_registry(models_dir)
    
    def test_load_missing_field_error(self, tmp_path):
        """Test error when required field is missing."""
        models_dir = tmp_path / "models"
        models_dir.mkdir()
        
        # Create YAML missing required field
        incomplete_model = {
            "id": "test-model",
            "label": "Test Model",
            "family": "test"
            # missing "class" and "aliases"
        }
        
        yaml_file = models_dir / "incomplete.yaml"
        yaml_file.write_text(yaml.dump(incomplete_model))
        
        with pytest.raises(ValueError, match="Missing field 'class' in incomplete.yaml"):
            load_model_registry(models_dir)


class TestDefaultRegistry:
    """Test default_registry function."""
    
    def test_default_registry_cached(self):
        """Test that default_registry returns cached instance."""
        registry1 = default_registry()
        registry2 = default_registry()
        
        # Should be the same instance due to caching
        assert registry1 is registry2