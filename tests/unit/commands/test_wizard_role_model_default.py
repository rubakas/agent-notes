"""Tests that the wizard model default for a role picks the newest non-deprecated model."""
import pytest


class TestWizardRoleModelDefault:
    """Verify that _select_models_per_role defaults to non-deprecated models."""

    def _make_model(self, id_, model_class, deprecated=False):
        """Build a minimal Model-like object for testing."""
        from agent_notes.domain.model import Model
        return Model(
            id=id_,
            label=id_,
            family="claude",
            model_class=model_class,
            aliases={"anthropic": id_},
            deprecated=deprecated,
        )

    def test_reasoner_role_defaults_to_non_deprecated_opus(self, monkeypatch):
        """For the reasoner role (typical_class=opus), the wizard default must be
        the newest non-deprecated opus model (claude-opus-4-8), not a deprecated one."""
        monkeypatch.setattr("agent_notes.services.ui._can_interactive", lambda: False)

        captured_defaults = {}

        def fake_radio(title, options, default=0, **kwargs):
            # Extract role from the title so we can associate default per role
            for line in title.splitlines():
                stripped = line.strip()
                if "reasoner" in stripped.lower() or "Reasoner" in stripped:
                    captured_defaults["reasoner_default_idx"] = default
                    captured_defaults["reasoner_options"] = options
                    break
            return options[default][1]

        monkeypatch.setattr("agent_notes.commands.wizard._radio_select_fallback", fake_radio)
        monkeypatch.setattr("agent_notes.commands.wizard._radio_select", fake_radio)

        from agent_notes.commands.wizard import _select_models_per_role

        result, _ = _select_models_per_role({"claude"})

        assert "claude" in result
        assert "reasoner" in result["claude"], "reasoner role should be configured"

        chosen_model_id = result["claude"]["reasoner"]
        assert chosen_model_id == "claude-opus-4-8", (
            f"Expected reasoner default to be claude-opus-4-8 (newest non-deprecated opus), "
            f"got: {chosen_model_id}"
        )

    def test_wizard_default_skips_deprecated_models(self):
        """Unit test: the selection logic picks newest non-deprecated over deprecated."""
        from agent_notes.domain.model import Model

        # Simulate a compatible list sorted by id: older deprecated, newer deprecated,
        # then newest non-deprecated (as reversed(compatible) would yield newest first)
        compatible = [
            self._make_model("opus-4-1", "opus", deprecated=True),
            self._make_model("opus-4-5", "opus", deprecated=True),
            self._make_model("opus-4-8", "opus", deprecated=False),
        ]

        # Replicate the wizard's selection expression
        default_model = next(
            (m for m in reversed(compatible) if m.model_class == "opus" and not m.deprecated),
            next(
                (m for m in reversed(compatible) if m.model_class == "opus"),
                compatible[0],
            ),
        )

        assert default_model.id == "opus-4-8", (
            f"Expected opus-4-8 (non-deprecated), got {default_model.id}"
        )

    def test_wizard_default_falls_back_to_deprecated_if_all_deprecated(self):
        """If all class-matching models are deprecated, fall back to the newest deprecated."""
        compatible = [
            self._make_model("opus-4-1", "opus", deprecated=True),
            self._make_model("opus-4-5", "opus", deprecated=True),
        ]

        default_model = next(
            (m for m in reversed(compatible) if m.model_class == "opus" and not m.deprecated),
            next(
                (m for m in reversed(compatible) if m.model_class == "opus"),
                compatible[0],
            ),
        )

        # Should pick the newest deprecated (opus-4-5 is last in list, first in reversed)
        assert default_model.id == "opus-4-5", (
            f"Expected opus-4-5 (newest deprecated fallback), got {default_model.id}"
        )

    def test_model_deprecated_field_loaded_from_registry(self):
        """The model registry correctly loads the deprecated field from YAML."""
        from agent_notes.registries.model_registry import load_model_registry

        registry = load_model_registry()

        opus_4_7 = registry.get("claude-opus-4-7")
        assert opus_4_7.deprecated is True, "claude-opus-4-7 should be deprecated=True"

        opus_4_8 = registry.get("claude-opus-4-8")
        assert opus_4_8.deprecated is False, "claude-opus-4-8 should be deprecated=False"
