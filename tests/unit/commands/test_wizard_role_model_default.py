"""Tests that the wizard model default for a role picks the newest non-deprecated model.

All tests use a fixture ModelRegistry so catalog changes cannot force test changes.
"""
import pytest

from agent_notes.domain.model import Model
from agent_notes.registries.model_registry import ModelRegistry


def _make_model(id_, model_class, deprecated=False, never_default=False):
    """Build a minimal Model for use in fixture registries."""
    return Model(
        id=id_,
        label=id_,
        family="claude",
        model_class=model_class,
        aliases={"anthropic": id_},
        deprecated=deprecated,
        never_default=never_default,
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

    def test_wizard_picks_non_deprecated_even_when_newer_model_is_deprecated(self, monkeypatch):
        """When the newest model of a class is deprecated but an older one is not,
        the wizard must default to the non-deprecated option.

        Natural sort ensures opus-test-2 > opus-test-1, so reversed iteration
        visits opus-test-2 first — the test verifies the wizard skips it.
        """
        older_non_deprecated = _make_model("opus-test-1", "opus", deprecated=False)
        newer_deprecated = _make_model("opus-test-2", "opus", deprecated=True)
        fixture = _make_registry(older_non_deprecated, newer_deprecated)

        result = self._run_model_selection(monkeypatch, fixture)

        assert "claude" in result
        assert "reasoner" in result["claude"]
        chosen = result["claude"]["reasoner"]
        assert chosen == "opus-test-1", (
            f"Expected non-deprecated 'opus-test-1' but got '{chosen}' — "
            f"wizard should prefer non-deprecated even when a newer deprecated model exists"
        )

    def test_wizard_falls_back_to_newest_deprecated_when_all_are_deprecated(self, monkeypatch):
        """When every model of the role's class is deprecated, the wizard must fall
        back to the newest deprecated option rather than refusing to pick."""
        older_deprecated = _make_model("opus-test-1", "opus", deprecated=True)
        newer_deprecated = _make_model("opus-test-2", "opus", deprecated=True)
        fixture = _make_registry(older_deprecated, newer_deprecated)

        result = self._run_model_selection(monkeypatch, fixture)

        assert "claude" in result
        assert "reasoner" in result["claude"]
        chosen = result["claude"]["reasoner"]
        assert chosen == "opus-test-2", (
            f"Expected newest deprecated 'opus-test-2' but got '{chosen}' — "
            f"wizard should fall back to newest deprecated when no non-deprecated option exists"
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


class TestWizardNeverDefault:
    """Verify that _select_models_per_role never pre-selects a never_default model."""

    def _run_model_selection(self, monkeypatch, fixture_registry):
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

    def test_wizard_skips_never_default_when_matching_class_exists(self, monkeypatch):
        """When a newer never_default model and an older normal model share the same
        class, the wizard must default to the normal model."""
        older_normal = _make_model("opus-test-1", "opus", never_default=False)
        newer_never_default = _make_model("opus-test-2", "opus", never_default=True)
        fixture = _make_registry(older_normal, newer_never_default)

        result = self._run_model_selection(monkeypatch, fixture)

        assert "claude" in result
        assert "reasoner" in result["claude"]
        chosen = result["claude"]["reasoner"]
        assert chosen == "opus-test-1", (
            f"Expected normal 'opus-test-1' but got '{chosen}' — "
            f"wizard must never pre-select a never_default model"
        )

    def test_wizard_falls_through_to_other_compatible_when_class_is_only_never_default(self, monkeypatch):
        """When the only model of the role's class is never_default, the wizard falls
        through to another compatible model rather than picking the never_default one."""
        sonnet_normal = _make_model("sonnet-test-1", "sonnet", never_default=False)
        opus_never_default = _make_model("opus-test-1", "opus", never_default=True)
        fixture = _make_registry(sonnet_normal, opus_never_default)

        result = self._run_model_selection(monkeypatch, fixture)

        assert "claude" in result
        assert "reasoner" in result["claude"]
        chosen = result["claude"]["reasoner"]
        assert chosen != "opus-test-1", (
            f"Got '{chosen}' — wizard must not pre-select never_default model even as last resort"
        )

    def test_never_default_field_loaded_from_yaml(self, tmp_path):
        """never_default: true in YAML loads as bool True; omitting it defaults to False."""
        from agent_notes.registries.model_registry import load_model_registry

        (tmp_path / "test-fable.yaml").write_text(
            "id: test-fable\nlabel: Test Fable\nfamily: test\nclass: fable\n"
            "never_default: true\naliases:\n  anthropic: test-fable\n"
        )
        (tmp_path / "test-sonnet.yaml").write_text(
            "id: test-sonnet\nlabel: Test Sonnet\nfamily: test\nclass: sonnet\n"
            "aliases:\n  anthropic: test-sonnet\n"
        )
        registry = load_model_registry(tmp_path)

        assert registry.get("test-fable").never_default is True
        assert registry.get("test-sonnet").never_default is False

    def test_claude_fable_5_is_never_default_in_real_registry(self):
        """Smoke test: claude-fable-5 has never_default=True in the real catalog."""
        from agent_notes.registries.model_registry import load_model_registry
        registry = load_model_registry()
        fable = registry.get("claude-fable-5")
        assert fable.never_default is True, "claude-fable-5 must have never_default=True in the catalog"

    def test_claude_fable_5_still_in_registry(self):
        """claude-fable-5 must remain in the catalog and be listable."""
        from agent_notes.registries.model_registry import load_model_registry
        registry = load_model_registry()
        ids = registry.ids()
        assert "claude-fable-5" in ids, "claude-fable-5 must still be present in the registry"
