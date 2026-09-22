"""Unit tests for the pure effort-selection helpers used by
_select_models_per_role: _effort_provider_for_model and _effort_default_choice.

No interactive-test scaffolding needed — these are pure functions extracted
specifically for testability (see checklist B10(e))."""
from pathlib import Path

import agent_notes.commands.wizard as wiz
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
        role = Role(name="worker", label="Worker", description="", typical_effort="medium")
        assert _effort_default_choice(role, ANTHROPIC) == "medium"

    def test_falls_back_to_provider_default_when_role_effort_not_in_provider_vocab(self):
        role = Role(name="worker", label="Worker", description="", typical_effort="none")  # "none" is an openai value, not anthropic's
        assert _effort_default_choice(role, ANTHROPIC) == ANTHROPIC.default_effort

    def test_falls_back_to_provider_default_when_role_has_no_typical_effort(self):
        role = Role(name="worker", label="Worker", description="", typical_effort="")
        assert _effort_default_choice(role, ANTHROPIC) == ANTHROPIC.default_effort


def _run_wizard(monkeypatch, cli, prefer_model=None):
    """Drive _select_models_per_role, recording every effort option list offered.

    Effort radios are the ones whose options are (value, value) pairs; model
    radios carry a rendered column label. Returns (role_efforts, offered)."""
    offered = []

    def fake_radio(title, options, default=0, **k):
        if all(label == value for label, value in options):
            offered.append([value for _label, value in options])
            return options[default][1]
        if prefer_model and any(value == prefer_model for _label, value in options):
            return prefer_model
        return options[default][1]

    monkeypatch.setattr(wiz, "_can_interactive", lambda: True)
    monkeypatch.setattr(wiz, "_select_accept_all_models", lambda **k: False)
    monkeypatch.setattr(wiz, "_radio_select", fake_radio)

    _models, role_efforts = wiz._select_models_per_role({cli}, step=2, total=9, version="x")
    return role_efforts.get(cli, {}), offered


class TestEffortOptionsNarrowedToBackend:
    """codex.yaml declares its own `efforts:` list; openai's vocabulary is wider.
    Offering a value codex rejects means render-time silently substitutes another."""

    def test_codex_options_exclude_provider_values_the_cli_rejects(self, monkeypatch):
        role_efforts, offered = _run_wizard(monkeypatch, "codex")
        assert offered, "no effort prompts were offered — the assertion is a no-op"
        for options in offered:
            assert "none" not in options
            assert "max" not in options
            assert set(options) <= {"minimal", "low", "medium", "high", "xhigh"}
        assert role_efforts

    def test_claude_keeps_the_full_provider_vocabulary(self, monkeypatch):
        role_efforts, offered = _run_wizard(monkeypatch, "claude", prefer_model="claude-opus-5")
        assert offered, "no effort prompts were offered — the assertion is a no-op"
        for options in offered:
            assert options == ["low", "medium", "high", "xhigh", "max"]
        assert role_efforts

    def test_model_without_effort_support_records_no_effort(self, monkeypatch):
        role_efforts, offered = _run_wizard(monkeypatch, "claude", prefer_model="claude-haiku-4-5")
        assert offered == []
        assert role_efforts == {}
