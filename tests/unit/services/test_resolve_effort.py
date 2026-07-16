"""Tests for agent_notes.services.rendering._resolve_effort — the effort
resolution + provider-validation chain:

  1. State-driven pin (scope_state.clis[backend].role_efforts[role]) — wins
  2. Agent's own 'effort' (agents.yaml)
  3. Role's 'typical_effort'
  4. None

...then validated against the resolved model's provider effort vocabulary:
invalid value -> provider.default_effort; no provider registry entry -> None.
"""
from __future__ import annotations

from pathlib import Path

from agent_notes.domain.model import Model
from agent_notes.domain.role import Role
from agent_notes.domain.provider import Provider
from agent_notes.domain.cli_backend import CLIBackend
from agent_notes.domain.state import ScopeState, BackendState
from agent_notes.registries.model_registry import ModelRegistry
from agent_notes.registries.provider_registry import ProviderRegistry
from agent_notes.services.rendering import _resolve_effort, _resolve_provider_for_model_str


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

def _make_backend(name="claude", accepted_providers=("anthropic",), use_model_class=False,
                  preferred_family=None) -> CLIBackend:
    return CLIBackend(
        name=name,
        label=name,
        global_home=Path("/tmp"),
        local_dir=".claude",
        layout={},
        features={"agents": True, "frontmatter": "claude"},
        global_template=None,
        exclude_flag=None,
        accepted_providers=accepted_providers,
        use_model_class=use_model_class,
        preferred_family=preferred_family,
    )


def _make_model(model_id="claude-sonnet-5", model_class="sonnet", aliases=None, family="claude"):
    return Model(
        id=model_id, label=model_id, family=family, model_class=model_class,
        aliases=aliases or {"anthropic": model_id},
    )


def _make_scope_state(backend_name, role_efforts):
    return ScopeState(clis={backend_name: BackendState(role_efforts=role_efforts)})


def _patch_role_registry(monkeypatch, typical_effort="medium", role_name="worker"):
    role = Role(name=role_name, label="Worker", description="", typical_class="sonnet",
                typical_effort=typical_effort)

    class FakeRegistry:
        def get(self, name):
            if name != role_name:
                raise KeyError(name)
            return role

    monkeypatch.setattr(
        "agent_notes.registries.role_registry.default_role_registry",
        lambda: FakeRegistry(),
    )


def _patch_provider_registry(monkeypatch, providers):
    registry = ProviderRegistry(providers)
    monkeypatch.setattr(
        "agent_notes.registries.provider_registry.default_provider_registry",
        lambda: registry,
    )


ANTHROPIC = Provider(name="anthropic", efforts=("low", "medium", "high", "xhigh", "max"), default_effort="high")


class TestResolveEffort:
    def test_state_pin_wins_over_agent_own_effort(self, monkeypatch):
        _patch_role_registry(monkeypatch, typical_effort="low")
        _patch_provider_registry(monkeypatch, [ANTHROPIC])

        backend = _make_backend()
        model = _make_model(aliases={"anthropic": "my-model"})
        model_registry = ModelRegistry([model])
        scope_state = _make_scope_state("claude", {"worker": "max"})

        agent_config = {"effort": "high", "role": "worker"}
        result = _resolve_effort("coder", agent_config, backend, scope_state, {}, "my-model", model_registry)
        assert result == "max"

    def test_agent_own_effort_wins_over_role_default_when_no_pin(self, monkeypatch):
        _patch_role_registry(monkeypatch, typical_effort="low")
        _patch_provider_registry(monkeypatch, [ANTHROPIC])

        backend = _make_backend()
        model = _make_model(aliases={"anthropic": "my-model"})
        model_registry = ModelRegistry([model])

        agent_config = {"effort": "high", "role": "worker"}
        result = _resolve_effort("coder", agent_config, backend, None, {}, "my-model", model_registry)
        assert result == "high"

    def test_falls_back_to_role_typical_effort_when_agent_effort_absent(self, monkeypatch):
        _patch_role_registry(monkeypatch, typical_effort="medium")
        _patch_provider_registry(monkeypatch, [ANTHROPIC])

        backend = _make_backend()
        model = _make_model(aliases={"anthropic": "my-model"})
        model_registry = ModelRegistry([model])

        agent_config = {"role": "worker"}
        result = _resolve_effort("coder", agent_config, backend, None, {}, "my-model", model_registry)
        assert result == "medium"

    def test_returns_none_when_nothing_resolves(self, monkeypatch):
        _patch_role_registry(monkeypatch, typical_effort="")
        _patch_provider_registry(monkeypatch, [ANTHROPIC])

        backend = _make_backend()
        model = _make_model(aliases={"anthropic": "my-model"})
        model_registry = ModelRegistry([model])

        agent_config = {"role": "worker"}
        result = _resolve_effort("coder", agent_config, backend, None, {}, "my-model", model_registry)
        assert result is None

    def test_returns_none_when_no_role_declared(self, monkeypatch):
        _patch_provider_registry(monkeypatch, [ANTHROPIC])
        backend = _make_backend()
        model = _make_model(aliases={"anthropic": "my-model"})
        model_registry = ModelRegistry([model])

        result = _resolve_effort("coder", {}, backend, None, {}, "my-model", model_registry)
        assert result is None

    def test_invalid_effort_value_falls_back_to_provider_default(self, monkeypatch):
        """An effort not in the provider's vocabulary is replaced with the
        provider's own default_effort — never translated to another value."""
        _patch_role_registry(monkeypatch, typical_effort="medium")
        _patch_provider_registry(monkeypatch, [ANTHROPIC])

        backend = _make_backend()
        model = _make_model(aliases={"anthropic": "my-model"})
        model_registry = ModelRegistry([model])

        agent_config = {"effort": "not-a-real-effort", "role": "worker"}
        result = _resolve_effort("coder", agent_config, backend, None, {}, "my-model", model_registry)
        assert result == ANTHROPIC.default_effort

    def test_no_provider_registry_entry_resolves_to_none(self, monkeypatch):
        """github-copilot/openrouter etc. have no provider registry entry —
        effort resolves to None regardless of role/agent effort declared."""
        _patch_role_registry(monkeypatch, typical_effort="medium")
        _patch_provider_registry(monkeypatch, [ANTHROPIC])  # no entry for "openrouter"

        backend = _make_backend(name="opencode", accepted_providers=("openrouter",))
        model = _make_model(aliases={"openrouter": "my-model"})
        model_registry = ModelRegistry([model])

        agent_config = {"effort": "high", "role": "worker"}
        result = _resolve_effort("coder", agent_config, backend, None, {}, "my-model", model_registry)
        assert result is None

    def test_unresolvable_provider_from_model_str_returns_none(self, monkeypatch):
        """model_str that can't be traced back to any registry model (e.g. legacy
        tier fallback) means no provider can be determined -> None."""
        _patch_role_registry(monkeypatch, typical_effort="medium")
        _patch_provider_registry(monkeypatch, [ANTHROPIC])

        backend = _make_backend()
        model_registry = ModelRegistry([])  # empty — nothing to reverse-lookup against

        agent_config = {"effort": "high", "role": "worker"}
        result = _resolve_effort("coder", agent_config, backend, None, {}, "some-tier-string", model_registry)
        assert result is None

    def test_effective_role_honors_user_config_override(self, monkeypatch):
        """agent_roles override in user_config determines which role_efforts key is
        checked, mirroring ModelResolver._effective_role."""
        _patch_role_registry(monkeypatch, typical_effort="low", role_name="scout")
        _patch_provider_registry(monkeypatch, [ANTHROPIC])

        backend = _make_backend()
        model = _make_model(aliases={"anthropic": "my-model"})
        model_registry = ModelRegistry([model])
        scope_state = _make_scope_state("claude", {"scout": "max"})
        user_config = {"agent_roles": {"coder": "scout"}}

        agent_config = {"role": "worker"}  # declared role — overridden by user_config
        result = _resolve_effort("coder", agent_config, backend, scope_state, user_config, "my-model", model_registry)
        assert result == "max"


class TestResolveProviderForModelStrClassAmbiguity:
    """_resolve_provider_for_model_str with use_model_class=True: a model_class
    alone is ambiguous when accepted_providers span families (e.g. claude-sonnet-4-6
    and gpt-5-4 are both class 'sonnet') — backend.preferred_family disambiguates."""

    def _make_multi_family_registry(self):
        claude_model = _make_model(model_id="claude-sonnet-4-6", family="claude",
                                   aliases={"anthropic": "claude-sonnet-4-6"})
        gpt_model = _make_model(model_id="gpt-5-4", family="gpt",
                                aliases={"openai": "gpt-5.4"})
        return ModelRegistry([claude_model, gpt_model])

    def test_preferred_family_wins_over_alphabetically_first_class_match(self):
        """claude-sonnet-4-6 sorts first in the registry scan, but the backend
        prefers the gpt family — its provider must win."""
        backend = _make_backend(name="codex", accepted_providers=("anthropic", "openai"),
                                use_model_class=True, preferred_family="gpt")
        registry = self._make_multi_family_registry()

        result = _resolve_provider_for_model_str("sonnet", backend, registry)
        assert result == "openai"

    def test_falls_back_to_first_class_match_when_no_preferred_family_match(self):
        """No model of the preferred family matches the class — current behavior
        (first class match in registry order) is kept."""
        backend = _make_backend(name="codex", accepted_providers=("anthropic", "openai"),
                                use_model_class=True, preferred_family="kimi")
        registry = self._make_multi_family_registry()

        result = _resolve_provider_for_model_str("sonnet", backend, registry)
        assert result == "anthropic"

    def test_falls_back_to_first_class_match_when_preferred_family_unset(self):
        backend = _make_backend(name="codex", accepted_providers=("anthropic", "openai"),
                                use_model_class=True, preferred_family=None)
        registry = self._make_multi_family_registry()

        result = _resolve_provider_for_model_str("sonnet", backend, registry)
        assert result == "anthropic"

    def test_exact_alias_matches_on_use_model_class_backend(self):
        """State-pinned models render exact alias strings even on use_model_class
        backends; the provider reverse-lookup must trace those back so effort
        resolution keeps working (regression: only model_class was matched)."""
        backend = _make_backend(accepted_providers=("anthropic",),
                                use_model_class=True, preferred_family="claude")
        registry = self._make_multi_family_registry()

        result = _resolve_provider_for_model_str("claude-sonnet-4-6", backend, registry)
        assert result == "anthropic"


class TestResolveEffortWithExactPinnedModelStr:
    def test_state_effort_pin_lands_for_exact_pinned_model_on_use_model_class_backend(self, monkeypatch):
        """End-to-end for the claude backend: pinned model renders an exact alias;
        the effort pin must still resolve through the provider lookup."""
        _patch_role_registry(monkeypatch, typical_effort="low")
        _patch_provider_registry(monkeypatch, [ANTHROPIC])

        backend = _make_backend(use_model_class=True, preferred_family="claude")
        model = _make_model(model_id="claude-sonnet-4-6",
                            aliases={"anthropic": "claude-sonnet-4-6"})
        model_registry = ModelRegistry([model])
        scope_state = _make_scope_state("claude", {"worker": "xhigh"})

        result = _resolve_effort("coder", {"role": "worker"}, backend, scope_state,
                                 {}, "claude-sonnet-4-6", model_registry)
        assert result == "xhigh"
