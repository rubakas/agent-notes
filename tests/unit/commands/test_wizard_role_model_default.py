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
    """Verify that _select_models_per_role defaults to non-deprecated models."""

    def _run_model_selection(self, monkeypatch, fixture_registry):
        """Call _select_models_per_role with a fixture registry and return the picks.

        Both _radio_select and _radio_select_fallback are patched to return the
        default option, so the result equals whatever default the wizard computes.
        load_model_registry is patched at its module location so the lazy import
        inside _select_models_per_role picks up the fixture.
        """
        monkeypatch.setattr("agent_notes.services.ui._can_interactive", lambda: False)

        def fake_radio(title, options, default=0, **kwargs):
            return options[default][1]

        monkeypatch.setattr("agent_notes.commands.wizard._radio_select_fallback", fake_radio)
        monkeypatch.setattr("agent_notes.commands.wizard._radio_select", fake_radio)
        monkeypatch.setattr(
            "agent_notes.registries.model_registry.load_model_registry",
            lambda: fixture_registry,
        )

        from agent_notes.commands.wizard import _select_models_per_role
        result, _ = _select_models_per_role({"claude"})
        return result

    def test_wizard_picks_non_deprecated_even_when_better_ranked_model_is_deprecated(self, monkeypatch):
        """When the best-ranked model of a class is deprecated but a lower-ranked one
        is not, the wizard must default to the non-deprecated option."""
        better_deprecated = _make_model("opus-test-2", "opus", deprecated=True)
        worse_non_deprecated = _make_model("opus-test-1", "opus", deprecated=False)
        fixture = _make_registry(better_deprecated, worse_non_deprecated)

        result = self._run_model_selection(monkeypatch, fixture)

        assert "claude" in result
        assert "reasoner" in result["claude"]
        chosen = result["claude"]["reasoner"]
        assert chosen == "opus-test-1", (
            f"Expected non-deprecated 'opus-test-1' but got '{chosen}' — "
            f"wizard should prefer non-deprecated even when a better-ranked deprecated model exists"
        )

    def test_wizard_falls_back_to_best_ranked_deprecated_when_all_are_deprecated(self, monkeypatch):
        """When every candidate is deprecated, the wizard must fall back to the
        best-ranked deprecated option rather than refusing to pick."""
        better_deprecated = _make_model("opus-test-2", "opus", deprecated=True)
        worse_deprecated = _make_model("opus-test-1", "opus", deprecated=True)
        fixture = _make_registry(better_deprecated, worse_deprecated)

        result = self._run_model_selection(monkeypatch, fixture)

        assert "claude" in result
        assert "reasoner" in result["claude"]
        chosen = result["claude"]["reasoner"]
        assert chosen == "opus-test-2", (
            f"Expected best-ranked deprecated 'opus-test-2' but got '{chosen}' — "
            f"wizard should fall back to the best-ranked deprecated model when no "
            f"non-deprecated option exists"
        )

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
