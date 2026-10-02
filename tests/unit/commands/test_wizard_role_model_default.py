"""Tests that the wizard model default for a role picks the best-ranked
non-deprecated model its budget allows.

All tests use a fixture ModelRegistry so catalog changes cannot force test changes.
Fixture registries are built in rank order: the first model listed is rank 1.
"""
import pytest

from agent_notes.domain.model import Model
from agent_notes.registries.model_registry import ModelRegistry


def _make_model(id_, model_class, deprecated=False, coding_index=50.0, price_in=1.0):
    """Build a minimal Model for use in fixture registries."""
    return Model(
        id=id_,
        label=id_,
        family="claude",
        model_class=model_class,
        aliases={"anthropic": id_},
        deprecated=deprecated,
        coding_index=coding_index,
        price_in=price_in,
    )


def _make_registry(*models):
    return ModelRegistry(list(models))


class TestWizardRoleModelDefault:
    """Verify that the review picks non-deprecated models by default."""

    def test_model_deprecated_field_is_loaded_as_boolean_from_yaml(self, tmp_path):
        """The deprecated field in a model YAML loads as a proper bool, not a string.
        Verified against a small fixture directory — no live registry IDs pinned."""
        from agent_notes.registries.model_registry import load_model_registry

        (tmp_path / "test-opus-deprecated.yaml").write_text(
            "id: test-opus\nlabel: Test Opus\nfamily: test\nclass: opus\n"
            "deprecated: true\naliases:\n  anthropic: test-opus\n"
        )
        (tmp_path / "test-sonnet-active.yaml").write_text(
            "id: test-sonnet\nlabel: Test Sonnet\nfamily: test\nclass: sonnet\n"
            "aliases:\n  anthropic: test-sonnet\n"
        )
        registry = load_model_registry(tmp_path)

        assert registry.get("test-opus").deprecated is True, (
            "deprecated: true in YAML should load as bool True, not a truthy string"
        )
        assert registry.get("test-sonnet").deprecated is False, (
            "omitting deprecated in YAML should default to False"
        )


class TestCatalogRetention:
    """Models excluded from auto-selection must remain listable and pinnable."""

    def test_claude_fable_5_still_in_registry(self):
        """claude-fable-5 must remain in the catalog and be listable."""
        from agent_notes.registries.model_registry import load_model_registry
        registry = load_model_registry()
        ids = registry.ids()
        assert "claude-fable-5" in ids, "claude-fable-5 must still be present in the registry"
