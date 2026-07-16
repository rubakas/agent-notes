"""Unit tests for _format_role_model_display — the pure row-formatting helper
extracted from _render_install_summary's model-map display (registry-hit vs.
registry-miss paths), per checklist A2."""
from agent_notes.commands.wizard import _format_role_model_display
from agent_notes.domain.model import Model
from agent_notes.domain.role import Role
from agent_notes.registries.model_registry import ModelRegistry


def _make_role(typical_effort=""):
    return Role(name="worker", label="Worker", description="", typical_class="sonnet",
                typical_effort=typical_effort)


def _make_registry_with(model_id="claude-sonnet-5", label="Claude Sonnet 5"):
    model = Model(id=model_id, label=label, family="claude", model_class="sonnet",
                  aliases={"anthropic": model_id})
    return ModelRegistry([model])


class TestFormatRoleModelDisplay:
    def test_registry_hit_shows_label_and_effort(self):
        registry = _make_registry_with()
        role = _make_role(typical_effort="medium")
        result = _format_role_model_display(role, "claude-sonnet-5", registry)
        assert result == "Claude Sonnet 5 · medium"

    def test_registry_hit_no_effort_shows_label_only(self):
        registry = _make_registry_with()
        role = _make_role(typical_effort="")
        result = _format_role_model_display(role, "claude-sonnet-5", registry)
        assert result == "Claude Sonnet 5"

    def test_registry_miss_falls_back_to_raw_model_id(self):
        """user-config overrides can be arbitrary strings not in the registry."""
        registry = _make_registry_with(model_id="claude-sonnet-5")
        role = _make_role(typical_effort="high")
        result = _format_role_model_display(role, "some-custom-model-id", registry)
        assert result == "some-custom-model-id · high"

    def test_registry_miss_no_effort_shows_raw_model_id_only(self):
        registry = _make_registry_with(model_id="claude-sonnet-5")
        role = _make_role(typical_effort="")
        result = _format_role_model_display(role, "some-custom-model-id", registry)
        assert result == "some-custom-model-id"

    def test_role_none_shows_label_only(self):
        """When role_map.get(role_name) misses (unknown role), role is None."""
        registry = _make_registry_with()
        result = _format_role_model_display(None, "claude-sonnet-5", registry)
        assert result == "Claude Sonnet 5"

    def test_picked_effort_wins_over_typical_effort(self):
        """The effort the user actually picked in the wizard must be shown on the
        confirmation screen, not the role's typical_effort."""
        registry = _make_registry_with()
        role = _make_role(typical_effort="medium")
        result = _format_role_model_display(role, "claude-sonnet-5", registry, picked_effort="max")
        assert result == "Claude Sonnet 5 · max"

    def test_no_picked_effort_falls_back_to_typical_effort(self):
        registry = _make_registry_with()
        role = _make_role(typical_effort="medium")
        result = _format_role_model_display(role, "claude-sonnet-5", registry, picked_effort=None)
        assert result == "Claude Sonnet 5 · medium"

    def test_picked_effort_shown_even_when_role_has_no_typical_effort(self):
        registry = _make_registry_with()
        role = _make_role(typical_effort="")
        result = _format_role_model_display(role, "claude-sonnet-5", registry, picked_effort="low")
        assert result == "Claude Sonnet 5 · low"
