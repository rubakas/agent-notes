"""Unit tests for the pure effort-selection helpers used by
_select_models_per_role: _effort_provider_for_model and _effort_default_choice.

No interactive-test scaffolding needed — these are pure functions extracted
specifically for testability (see checklist B10(e))."""
from pathlib import Path

from agent_notes.commands.wizard import _effort_provider_for_model, _effort_default_choice
from agent_notes.domain.cli_backend import CLIBackend
from agent_notes.domain.model import Model
from agent_notes.domain.role import Role
from agent_notes.domain.provider import Provider


def _make_backend(accepted_providers=("anthropic",)) -> CLIBackend:
    return CLIBackend(
        name="claude",
        label="Claude Code",
        global_home=Path("/tmp"),
        local_dir=".claude",
        layout={},
        features={"agents": True, "frontmatter": "claude"},
        global_template=None,
        accepted_providers=accepted_providers,
    )


def _make_model(aliases):
    return Model(id="m", label="M", family="claude", model_class="sonnet", aliases=aliases)


class TestEffortProviderForModel:
    def test_returns_first_matching_provider(self):
        backend = _make_backend(accepted_providers=("anthropic", "bedrock"))
        model = _make_model({"anthropic": "claude-sonnet-5", "bedrock": "anthropic.claude-sonnet-5"})
        assert _effort_provider_for_model(backend, model) == "anthropic"

    def test_returns_none_when_no_compatible_provider(self):
        backend = _make_backend(accepted_providers=("openai",))
        model = _make_model({"anthropic": "claude-sonnet-5"})
        assert _effort_provider_for_model(backend, model) is None


ANTHROPIC = Provider(name="anthropic", efforts=("low", "medium", "high", "xhigh", "max"), default_effort="high")


class TestEffortDefaultChoice:
    def test_role_typical_effort_wins_when_valid_for_provider(self):
        role = Role(name="worker", label="Worker", description="", typical_class="sonnet",
                    typical_effort="medium")
        assert _effort_default_choice(role, ANTHROPIC) == "medium"

    def test_falls_back_to_provider_default_when_role_effort_not_in_provider_vocab(self):
        role = Role(name="worker", label="Worker", description="", typical_class="sonnet",
                    typical_effort="none")  # "none" is an openai value, not anthropic's
        assert _effort_default_choice(role, ANTHROPIC) == ANTHROPIC.default_effort

    def test_falls_back_to_provider_default_when_role_has_no_typical_effort(self):
        role = Role(name="worker", label="Worker", description="", typical_class="sonnet",
                    typical_effort="")
        assert _effort_default_choice(role, ANTHROPIC) == ANTHROPIC.default_effort
