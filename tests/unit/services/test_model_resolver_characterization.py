"""Characterization tests for model resolution — golden-master tests that
lock in the current behavior of _resolve_model_str before it is refactored
into ModelResolver.

These tests exercise each branch of the resolution chain:
  1. State-driven pin  (scope_state.clis[backend].role_models[role])
  2. User config override  (user_config["role_models"][backend][role])
  3. Role typical_class fallback (newest model whose class matches role.typical_class)
  4. Legacy tier fallback  (agent_config["tier"])

The tests use lightweight fakes (dataclasses + dicts) rather than disk I/O.
"""
from __future__ import annotations

import pytest
from dataclasses import dataclass, field
from typing import Optional
from unittest.mock import patch

from agent_notes.domain.model import Model
from agent_notes.domain.role import Role
from agent_notes.domain.cli_backend import CLIBackend
from agent_notes.registries.model_registry import ModelRegistry
from agent_notes.registries.role_registry import RoleRegistry
from agent_notes.domain.state import ScopeState, BackendState


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

def _make_backend(
    name="claude",
    accepted_providers=("anthropic",),
    use_model_class=False,
    preferred_family=None,
) -> CLIBackend:
    return CLIBackend(
        name=name,
        label=name,
        global_home=__import__("pathlib").Path("/tmp"),
        local_dir=".claude",
        layout={},
        features={"agents": True, "frontmatter": "claude"},
        global_template=None,
        exclude_flag=None,
        accepted_providers=accepted_providers,
        use_model_class=use_model_class,
        preferred_family=preferred_family,
    )


def _make_model(
    model_id: str,
    family: str = "claude",
    model_class: str = "opus",
    aliases: Optional[dict] = None,
) -> Model:
    return Model(
        id=model_id,
        label=model_id,
        family=family,
        model_class=model_class,
        aliases=aliases or {"anthropic": model_id},
    )


def _make_scope_state(backend_name: str, role_models: dict) -> ScopeState:
    backend_state = BackendState(role_models=role_models, installed={})
    return ScopeState(
        installed_at="2024-01-01T00:00:00Z",
        updated_at="2024-01-01T00:00:00Z",
        mode="symlink",
        installed_version="1.0.0",
        clis={backend_name: backend_state},
    )


def _resolve(
    agent_name="lead",
    agent_config=None,
    backend=None,
    scope_state=None,
    model_registry=None,
    user_config=None,
    tiers=None,
):
    """Thin wrapper around _resolve_model_str to reduce boilerplate."""
    from agent_notes.services.rendering import _resolve_model_str

    return _resolve_model_str(
        agent_name=agent_name,
        agent_config=agent_config or {},
        backend=backend or _make_backend(),
        scope_state=scope_state,
        model_registry=model_registry,
        user_config=user_config or {},
        tiers=tiers or {},
    )


# ---------------------------------------------------------------------------
# Branch 1: State-driven pin
# ---------------------------------------------------------------------------

class TestStateDrivenPin:
    """scope_state.clis[backend].role_models[role] takes highest precedence."""

    def test_state_pin_resolves_alias(self):
        """State pin returns the alias string when use_model_class is False."""
        opus = _make_model("claude-opus-4-8", model_class="opus",
                           aliases={"anthropic": "my-opus-alias"})
        registry = ModelRegistry([opus])
        scope_state = _make_scope_state("claude", {"orchestrator": "claude-opus-4-8"})

        model_str, _ = _resolve(
            agent_config={"role": "orchestrator"},
            scope_state=scope_state,
            model_registry=registry,
        )
        assert model_str == "my-opus-alias"

    def test_state_pin_returns_exact_alias_even_when_use_model_class(self):
        """A state pin is an explicit version choice: it must render the exact
        alias string even on use_model_class backends (claude), never be
        flattened to the class ('opus'), which would let the harness pick its
        own default version."""
        opus = _make_model("claude-opus-4-8", model_class="opus",
                           aliases={"anthropic": "my-opus-alias"})
        registry = ModelRegistry([opus])
        backend = _make_backend(use_model_class=True)
        scope_state = _make_scope_state("claude", {"orchestrator": "claude-opus-4-8"})

        model_str, _ = _resolve(
            agent_config={"role": "orchestrator"},
            backend=backend,
            scope_state=scope_state,
            model_registry=registry,
        )
        assert model_str == "my-opus-alias"

    def test_state_pin_falls_through_on_unknown_model_id(self):
        """If the pinned model id is not in the registry, falls through to next branch."""
        registry = ModelRegistry([])  # empty
        scope_state = _make_scope_state("claude", {"orchestrator": "nonexistent-model"})

        # No user config, no role registry matches => falls to tier
        model_str, _ = _resolve(
            agent_config={"role": "orchestrator", "tier": "senior"},
            scope_state=scope_state,
            model_registry=registry,
            tiers={"senior": {"claude": "fallback-tier-model"}},
        )
        assert model_str == "fallback-tier-model"

    def test_state_pin_ignored_when_provider_not_accepted(self):
        """If model has no alias for any accepted_provider, falls to next branch."""
        opus = _make_model("claude-opus-4-8", aliases={"openai": "gpt4-alias"})
        registry = ModelRegistry([opus])
        backend = _make_backend(accepted_providers=("anthropic",))
        scope_state = _make_scope_state("claude", {"orchestrator": "claude-opus-4-8"})

        # Falls through to tier
        model_str, _ = _resolve(
            agent_config={"role": "orchestrator", "tier": "senior"},
            backend=backend,
            scope_state=scope_state,
            model_registry=registry,
            tiers={"senior": {"claude": "tier-fallback"}},
        )
        assert model_str == "tier-fallback"

    def test_state_pin_missing_role_falls_to_typical_class(self):
        """Role not in state.role_models falls through to typical_class branch (not tier).

        The typical_class branch runs next — tier is only the final fallback
        when there is no matching role at all.
        """
        opus = _make_model("claude-opus-4-8", model_class="opus",
                           aliases={"anthropic": "opus-alias"})
        registry = ModelRegistry([opus])
        scope_state = _make_scope_state("claude", {"other-role": "claude-opus-4-8"})

        # orchestrator -> typical_class=opus -> matches claude-opus-4-8 -> alias "opus-alias"
        model_str, _ = _resolve(
            agent_config={"role": "orchestrator", "tier": "senior"},
            scope_state=scope_state,
            model_registry=registry,
            tiers={"senior": {"claude": "tier-fallback"}},
        )
        assert model_str == "opus-alias"


# ---------------------------------------------------------------------------
# Branch 2: User config override
# ---------------------------------------------------------------------------

class TestUserConfigOverride:
    """user_config["role_models"][backend][role] is second in precedence."""

    def test_user_config_override_used_when_no_state(self):
        user_config = {"role_models": {"claude": {"orchestrator": "user-pinned-model"}}}
        model_str, _ = _resolve(
            agent_config={"role": "orchestrator"},
            user_config=user_config,
        )
        assert model_str == "user-pinned-model"

    def test_user_config_override_beats_role_fallback(self):
        """User config beats the typical_class fallback even when roles are resolvable."""
        opus = _make_model("claude-opus-4-8", model_class="opus",
                           aliases={"anthropic": "opus-alias"})

        user_config = {"role_models": {"claude": {"orchestrator": "user-explicit"}}}

        opus_role = Role(
            name="orchestrator", label="Orchestrator", description="",
            typical_class="opus",
        )

        with patch(
            "agent_notes.registries.role_registry.load_role_registry",
            return_value=RoleRegistry([opus_role]),
        ):
            model_str, _ = _resolve(
                agent_config={"role": "orchestrator"},
                model_registry=ModelRegistry([opus]),
                user_config=user_config,
            )
        assert model_str == "user-explicit"

    def test_user_config_override_uses_verbatim_string(self):
        """The override string is returned as-is, not looked up in model registry."""
        user_config = {"role_models": {"claude": {"orchestrator": "my-custom-model-v9"}}}
        model_str, _ = _resolve(
            agent_config={"role": "orchestrator"},
            user_config=user_config,
        )
        assert model_str == "my-custom-model-v9"

    def test_agent_role_override_from_user_config(self):
        """user_config["agent_roles"][agent_name] overrides the agent's declared role."""
        user_config = {
            "agent_roles": {"lead": "scout"},
            "role_models": {"claude": {"scout": "scout-model"}},
        }
        model_str, _ = _resolve(
            agent_name="lead",
            agent_config={"role": "orchestrator"},  # declared orchestrator
            user_config=user_config,
        )
        assert model_str == "scout-model"


# ---------------------------------------------------------------------------
# Branch 3: Role typical_class fallback
# ---------------------------------------------------------------------------

class TestTypicalClassFallback:
    """Role typical_class matched against model registry, newest-first."""

    def test_typical_class_fallback_picks_newest_model(self):
        """When multiple models match typical_class, the highest id (newest) wins."""
        opus_old = _make_model("claude-opus-4-6", model_class="opus",
                               aliases={"anthropic": "old-alias"})
        opus_new = _make_model("claude-opus-4-8", model_class="opus",
                               aliases={"anthropic": "new-alias"})
        registry = ModelRegistry([opus_old, opus_new])

        opus_role = Role(
            name="orchestrator", label="Orchestrator", description="",
            typical_class="opus",
        )
        with patch(
            "agent_notes.registries.role_registry.load_role_registry",
            return_value=RoleRegistry([opus_role]),
        ):
            model_str, _ = _resolve(
                agent_config={"role": "orchestrator"},
                model_registry=registry,
            )
        assert model_str == "new-alias"

    def test_typical_class_fallback_filters_by_accepted_providers(self):
        """Only models that have an alias for an accepted_provider are considered."""
        opus_anthropic = _make_model(
            "claude-opus-4-8", model_class="opus",
            aliases={"anthropic": "anthropic-opus"},
        )
        opus_openai = _make_model(
            "gpt-opus-99", model_class="opus",
            aliases={"openai": "gpt-opus"},
        )
        registry = ModelRegistry([opus_anthropic, opus_openai])
        backend = _make_backend(accepted_providers=("anthropic",))

        opus_role = Role(
            name="orchestrator", label="Orchestrator", description="",
            typical_class="opus",
        )
        with patch(
            "agent_notes.registries.role_registry.load_role_registry",
            return_value=RoleRegistry([opus_role]),
        ):
            model_str, _ = _resolve(
                agent_config={"role": "orchestrator"},
                backend=backend,
                model_registry=registry,
            )
        assert model_str == "anthropic-opus"

    def test_typical_class_fallback_respects_preferred_family(self):
        """preferred_family filters model family before falling back to any-family."""
        claude_sonnet = _make_model(
            "claude-sonnet-4-6", family="claude", model_class="sonnet",
            aliases={"anthropic": "claude-sonnet"},
        )
        gpt_sonnet = _make_model(
            "gpt-sonnet-99", family="openai", model_class="sonnet",
            aliases={"anthropic": "gpt-sonnet"},
        )
        # gpt-sonnet-99 > claude-sonnet-4-6 lexicographically — without family filter it would win
        registry = ModelRegistry([claude_sonnet, gpt_sonnet])
        backend = _make_backend(accepted_providers=("anthropic",), preferred_family="claude")

        worker_role = Role(
            name="worker", label="Worker", description="", typical_class="sonnet",
        )
        with patch(
            "agent_notes.registries.role_registry.load_role_registry",
            return_value=RoleRegistry([worker_role]),
        ):
            model_str, _ = _resolve(
                agent_config={"role": "worker"},
                backend=backend,
                model_registry=registry,
            )
        assert model_str == "claude-sonnet"

    def test_typical_class_fallback_falls_back_any_family_when_preferred_not_found(self):
        """If no model matches preferred_family, any-family is tried."""
        gpt_sonnet = _make_model(
            "gpt-sonnet-99", family="openai", model_class="sonnet",
            aliases={"anthropic": "gpt-sonnet"},
        )
        registry = ModelRegistry([gpt_sonnet])
        backend = _make_backend(accepted_providers=("anthropic",), preferred_family="claude")

        worker_role = Role(
            name="worker", label="Worker", description="", typical_class="sonnet",
        )
        with patch(
            "agent_notes.registries.role_registry.load_role_registry",
            return_value=RoleRegistry([worker_role]),
        ):
            model_str, _ = _resolve(
                agent_config={"role": "worker"},
                backend=backend,
                model_registry=registry,
            )
        assert model_str == "gpt-sonnet"

    def test_typical_class_fallback_uses_model_class_string_when_flag_set(self):
        """use_model_class=True returns model.model_class rather than alias."""
        haiku = _make_model("claude-haiku-4-5", model_class="haiku",
                            aliases={"anthropic": "haiku-alias"})
        registry = ModelRegistry([haiku])
        backend = _make_backend(use_model_class=True)

        scout_role = Role(
            name="scout", label="Scout", description="", typical_class="haiku",
        )
        with patch(
            "agent_notes.registries.role_registry.load_role_registry",
            return_value=RoleRegistry([scout_role]),
        ):
            model_str, _ = _resolve(
                agent_config={"role": "scout"},
                backend=backend,
                model_registry=registry,
            )
        assert model_str == "haiku"


# ---------------------------------------------------------------------------
# Branch 4: Legacy tier fallback
# ---------------------------------------------------------------------------

class TestLegacyTierFallback:
    """agent_config["tier"] is the final fallback when no role resolves a model."""

    def test_tier_fallback_used_when_no_role(self):
        """Agent with no role and no state uses tier directly."""
        model_str, _ = _resolve(
            agent_config={"tier": "standard"},
            tiers={"standard": {"claude": "tier-model-id"}},
        )
        assert model_str == "tier-model-id"

    def test_tier_fallback_raises_when_backend_not_in_tier(self):
        from agent_notes.services.rendering import _resolve_model_str
        backend = _make_backend(name="opencode")
        with pytest.raises(ValueError, match="missing model for CLI 'opencode'"):
            _resolve_model_str(
                agent_name="lead",
                agent_config={"tier": "standard"},
                backend=backend,
                scope_state=None,
                model_registry=None,
                user_config={},
                tiers={"standard": {"claude": "some-model"}},
            )

    def test_raises_when_no_tier_and_no_role_resolves(self):
        """Error raised when no tier key and resolution fully fails."""
        from agent_notes.services.rendering import _resolve_model_str
        with pytest.raises(ValueError, match="no model could be resolved"):
            _resolve_model_str(
                agent_name="lead",
                agent_config={"role": "orchestrator"},  # role exists but no model matches
                backend=_make_backend(),
                scope_state=None,
                model_registry=ModelRegistry([]),  # empty registry
                user_config={},
                tiers={},
            )


# ---------------------------------------------------------------------------
# Integration: real registries — verify concrete agent+tier resolution ids
# ---------------------------------------------------------------------------

class TestRealRegistryResolution:
    """Smoke-tests against the real on-disk data to catch regressions.
    These pin the actual resolved model ids for representative agents.
    """

    def test_orchestrator_role_resolves_opus_for_claude_backend(self):
        """orchestrator (typical_class=opus) should resolve to the newest opus model."""
        from agent_notes.registries.model_registry import load_model_registry
        from agent_notes.registries.role_registry import load_role_registry
        from agent_notes.registries.cli_registry import load_registry

        model_registry = load_model_registry()
        role_registry = load_role_registry()
        cli_registry = load_registry()

        backend = cli_registry.get("claude")
        role = role_registry.get("orchestrator")

        # Find what the fallback would pick (newest opus with anthropic alias)
        all_models = list(reversed(model_registry.all()))
        expected = None
        for m in all_models:
            if m.model_class == role.typical_class:
                resolved = m.resolve_for_providers(list(backend.accepted_providers))
                if resolved is not None:
                    _, alias = resolved
                    expected = m.model_class if backend.use_model_class else alias
                    break

        assert expected is not None, "No opus model found for claude backend"

        model_str, _ = _resolve(
            agent_config={"role": "orchestrator"},
            backend=backend,
            model_registry=model_registry,
        )
        assert model_str == expected

    def test_worker_role_resolves_sonnet_for_claude_backend(self):
        """worker (typical_class=sonnet) should resolve to the newest sonnet model."""
        from agent_notes.registries.model_registry import load_model_registry
        from agent_notes.registries.role_registry import load_role_registry
        from agent_notes.registries.cli_registry import load_registry

        model_registry = load_model_registry()
        role_registry = load_role_registry()
        cli_registry = load_registry()

        backend = cli_registry.get("claude")
        role = role_registry.get("worker")

        all_models = list(reversed(model_registry.all()))
        expected = None
        for m in all_models:
            if m.model_class == role.typical_class:
                resolved = m.resolve_for_providers(list(backend.accepted_providers))
                if resolved is not None:
                    _, alias = resolved
                    expected = m.model_class if backend.use_model_class else alias
                    break

        assert expected is not None, "No sonnet model found for claude backend"

        model_str, _ = _resolve(
            agent_config={"role": "worker"},
            backend=backend,
            model_registry=model_registry,
        )
        assert model_str == expected

    def test_scout_role_resolves_haiku_for_claude_backend(self):
        """scout (typical_class=haiku) should resolve to the newest haiku model."""
        from agent_notes.registries.model_registry import load_model_registry
        from agent_notes.registries.role_registry import load_role_registry
        from agent_notes.registries.cli_registry import load_registry

        model_registry = load_model_registry()
        role_registry = load_role_registry()
        cli_registry = load_registry()

        backend = cli_registry.get("claude")
        role = role_registry.get("scout")

        all_models = list(reversed(model_registry.all()))
        expected = None
        for m in all_models:
            if m.model_class == role.typical_class:
                resolved = m.resolve_for_providers(list(backend.accepted_providers))
                if resolved is not None:
                    _, alias = resolved
                    expected = m.model_class if backend.use_model_class else alias
                    break

        assert expected is not None, "No haiku model found for claude backend"

        model_str, _ = _resolve(
            agent_config={"role": "scout"},
            backend=backend,
            model_registry=model_registry,
        )
        assert model_str == expected
