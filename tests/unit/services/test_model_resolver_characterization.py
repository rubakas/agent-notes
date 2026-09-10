"""Characterization tests for model resolution — golden-master tests that
lock in the current behavior of _resolve_model_str.

These tests exercise each branch of the resolution chain:
  1. State-driven pin  (scope_state.clis[backend].role_models[role])
  2. User config override  (user_config["role_models"][backend][role])
  3. Role budget + rank fallback (best-ranked rated model within role.budget)
  4. Unresolvable — raises ValueError

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
    coding_index: Optional[float] = 50.0,
    price_in: Optional[float] = 1.0,
) -> Model:
    """Fixture Model. Registries are built in rank order — first listed is rank 1."""
    return Model(
        id=model_id,
        label=model_id,
        family=family,
        model_class=model_class,
        aliases=aliases or {"anthropic": model_id},
        coding_index=coding_index,
        price_in=price_in,
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
        """If the pinned model id is not in the registry, falls through and raises."""
        registry = ModelRegistry([])  # empty
        scope_state = _make_scope_state("claude", {"orchestrator": "nonexistent-model"})

        # No user config, no role registry matches, no tier fallback => ValueError
        with pytest.raises(ValueError, match="no model could be resolved"):
            _resolve(
                agent_config={"role": "orchestrator"},
                scope_state=scope_state,
                model_registry=registry,
            )

    def test_state_pin_ignored_when_provider_not_accepted(self):
        """If model has no alias for any accepted_provider, falls through and raises."""
        opus = _make_model("claude-opus-4-8", aliases={"openai": "gpt4-alias"})
        registry = ModelRegistry([opus])
        backend = _make_backend(accepted_providers=("anthropic",))
        scope_state = _make_scope_state("claude", {"orchestrator": "claude-opus-4-8"})

        # Falls through to error — no model is compatible with anthropic
        with pytest.raises(ValueError, match="no model could be resolved"):
            _resolve(
                agent_config={"role": "orchestrator"},
                backend=backend,
                scope_state=scope_state,
                model_registry=registry,
            )

    def test_state_pin_missing_role_falls_to_budget_rank(self):
        """Role not in state.role_models falls through to the budget+rank branch."""
        opus = _make_model("claude-opus-4-8", model_class="opus",
                           aliases={"anthropic": "opus-alias"})
        registry = ModelRegistry([opus])
        scope_state = _make_scope_state("claude", {"other-role": "claude-opus-4-8"})

        # orchestrator -> unbounded budget -> best-ranked rated model -> alias "opus-alias"
        model_str, _ = _resolve(
            agent_config={"role": "orchestrator"},
            scope_state=scope_state,
            model_registry=registry,
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
        """User config beats the budget+rank fallback even when roles are resolvable."""
        opus = _make_model("claude-opus-4-8", model_class="opus",
                           aliases={"anthropic": "opus-alias"})

        user_config = {"role_models": {"claude": {"orchestrator": "user-explicit"}}}

        opus_role = Role(
            name="orchestrator", label="Orchestrator", description="",
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
# Branch 3: Role budget + catalog rank
# ---------------------------------------------------------------------------

class TestBudgetRankFallback:
    """Best-ranked rated model the role's budget allows."""

    def test_fallback_picks_best_ranked_model_not_the_worst(self):
        """The catalog is walked frontier-first: rank 1 wins, not the tail."""
        opus_best = _make_model("claude-opus-4-8", model_class="opus",
                                aliases={"anthropic": "best-alias"}, coding_index=80.0)
        opus_worse = _make_model("claude-opus-4-6", model_class="opus",
                                 aliases={"anthropic": "worse-alias"}, coding_index=40.0)
        registry = ModelRegistry([opus_best, opus_worse])

        opus_role = Role(
            name="orchestrator", label="Orchestrator", description="",
            )
        with patch(
            "agent_notes.registries.role_registry.load_role_registry",
            return_value=RoleRegistry([opus_role]),
        ):
            model_str, _ = _resolve(
                agent_config={"role": "orchestrator"},
                model_registry=registry,
            )
        assert model_str == "best-alias"

    def test_budget_skips_models_priced_above_it(self):
        """A cheaper, lower-ranked model wins when the frontier is over budget."""
        expensive = _make_model("claude-opus-5", model_class="opus",
                                aliases={"anthropic": "expensive-alias"},
                                coding_index=80.0, price_in=10.0)
        affordable = _make_model("claude-sonnet-5", model_class="sonnet",
                                 aliases={"anthropic": "affordable-alias"},
                                 coding_index=70.0, price_in=2.0)
        registry = ModelRegistry([expensive, affordable])

        worker_role = Role(
            name="worker", label="Worker", description="", budget=2.0,
        )
        with patch(
            "agent_notes.registries.role_registry.load_role_registry",
            return_value=RoleRegistry([worker_role]),
        ):
            model_str, _ = _resolve(
                agent_config={"role": "worker"},
                model_registry=registry,
            )
        assert model_str == "affordable-alias"

    def test_null_budget_is_unbounded(self):
        """budget=None takes the frontier model no matter how expensive."""
        expensive = _make_model("claude-fable-5-1", model_class="fable",
                                aliases={"anthropic": "expensive-alias"},
                                coding_index=90.0, price_in=1000.0)
        cheap = _make_model("claude-haiku-4-5", model_class="haiku",
                            aliases={"anthropic": "cheap-alias"},
                            coding_index=40.0, price_in=0.5)
        registry = ModelRegistry([expensive, cheap])

        role = Role(
            name="orchestrator", label="Orchestrator", description="", budget=None,
        )
        with patch(
            "agent_notes.registries.role_registry.load_role_registry",
            return_value=RoleRegistry([role]),
        ):
            model_str, _ = _resolve(
                agent_config={"role": "orchestrator"},
                model_registry=registry,
            )
        assert model_str == "expensive-alias"

    def test_unpriced_model_is_skipped_when_the_role_has_a_budget(self):
        """A null price cannot be proven within budget, so it is not auto-selected."""
        unpriced = _make_model("claude-opus-5", model_class="opus",
                               aliases={"anthropic": "unpriced-alias"},
                               coding_index=80.0, price_in=None)
        priced = _make_model("claude-sonnet-5", model_class="sonnet",
                             aliases={"anthropic": "priced-alias"},
                             coding_index=70.0, price_in=1.0)
        registry = ModelRegistry([unpriced, priced])

        worker_role = Role(
            name="worker", label="Worker", description="", budget=2.0,
        )
        with patch(
            "agent_notes.registries.role_registry.load_role_registry",
            return_value=RoleRegistry([worker_role]),
        ):
            model_str, _ = _resolve(
                agent_config={"role": "worker"},
                model_registry=registry,
            )
        assert model_str == "priced-alias"

    def test_unrated_model_is_never_auto_selected(self):
        """coding_index=None means the benchmark has no opinion — skip it."""
        unrated = _make_model("claude-opus-4-6", model_class="opus",
                              aliases={"anthropic": "unrated-alias"}, coding_index=None)
        rated = _make_model("claude-opus-4-5", model_class="opus",
                            aliases={"anthropic": "rated-alias"}, coding_index=10.0)
        registry = ModelRegistry([unrated, rated])

        opus_role = Role(
            name="orchestrator", label="Orchestrator", description="",
            )
        with patch(
            "agent_notes.registries.role_registry.load_role_registry",
            return_value=RoleRegistry([opus_role]),
        ):
            model_str, _ = _resolve(
                agent_config={"role": "orchestrator"},
                model_registry=registry,
            )
        assert model_str == "rated-alias"

    def test_unrated_sole_candidate_raises_rather_than_being_selected(self):
        """Exclusion of unrated models is hard — there is no last-resort fallback."""
        unrated = _make_model("claude-opus-4-6", model_class="opus",
                              aliases={"anthropic": "unrated-alias"}, coding_index=None)
        registry = ModelRegistry([unrated])

        opus_role = Role(
            name="orchestrator", label="Orchestrator", description="",
            )
        with patch(
            "agent_notes.registries.role_registry.load_role_registry",
            return_value=RoleRegistry([opus_role]),
        ):
            with pytest.raises(ValueError, match="no model could be resolved"):
                _resolve(
                    agent_config={"role": "orchestrator"},
                    model_registry=registry,
                )

    def test_explicit_pin_to_an_unrated_model_still_resolves(self):
        """Rating and budget gate automatic selection only, not explicit user choices."""
        unrated = _make_model(
            "claude-fable-5", model_class="fable",
            aliases={"anthropic": "claude-fable-5"},
            coding_index=None, price_in=None,
        )
        registry = ModelRegistry([unrated])

        scope_state = _make_scope_state("claude", {"orchestrator": "claude-fable-5"})

        model_str, _ = _resolve(
            agent_config={"role": "orchestrator"},
            scope_state=scope_state,
            model_registry=registry,
        )
        assert model_str == "claude-fable-5", (
            "Explicit pin to an unrated model must still resolve"
        )

    def test_fallback_filters_by_accepted_providers(self):
        """Only models that have an alias for an accepted_provider are considered."""
        opus_openai = _make_model(
            "gpt-opus-99", model_class="opus",
            aliases={"openai": "gpt-opus"},
        )
        opus_anthropic = _make_model(
            "claude-opus-4-8", model_class="opus",
            aliases={"anthropic": "anthropic-opus"},
        )
        registry = ModelRegistry([opus_openai, opus_anthropic])
        backend = _make_backend(accepted_providers=("anthropic",))

        opus_role = Role(
            name="orchestrator", label="Orchestrator", description="",
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

    def test_fallback_respects_preferred_family(self):
        """preferred_family filters model family before falling back to any-family."""
        gpt_sonnet = _make_model(
            "gpt-sonnet-99", family="openai", model_class="sonnet",
            aliases={"anthropic": "gpt-sonnet"},
        )
        claude_sonnet = _make_model(
            "claude-sonnet-4-6", family="claude", model_class="sonnet",
            aliases={"anthropic": "claude-sonnet"},
        )
        # gpt-sonnet-99 ranks first — without the family filter it would win
        registry = ModelRegistry([gpt_sonnet, claude_sonnet])
        backend = _make_backend(accepted_providers=("anthropic",), preferred_family="claude")

        worker_role = Role(
            name="worker", label="Worker", description="", )
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

    def test_fallback_falls_back_any_family_when_preferred_not_found(self):
        """If no model matches preferred_family, any-family is tried."""
        gpt_sonnet = _make_model(
            "gpt-sonnet-99", family="openai", model_class="sonnet",
            aliases={"anthropic": "gpt-sonnet"},
        )
        registry = ModelRegistry([gpt_sonnet])
        backend = _make_backend(accepted_providers=("anthropic",), preferred_family="claude")

        worker_role = Role(
            name="worker", label="Worker", description="", )
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

    def test_fallback_uses_model_class_string_when_flag_set(self):
        """use_model_class=True returns model.model_class rather than alias."""
        haiku = _make_model("claude-haiku-4-5", model_class="haiku",
                            aliases={"anthropic": "haiku-alias"})
        registry = ModelRegistry([haiku])
        backend = _make_backend(use_model_class=True)

        scout_role = Role(
            name="scout", label="Scout", description="", )
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

    def test_prefers_non_deprecated_over_better_ranked_deprecated(self):
        """Deprecation is a soft preference applied before rank widens."""
        from dataclasses import replace

        opus_deprecated = _make_model(
            "claude-opus-4-9", model_class="opus",
            aliases={"anthropic": "opus-deprecated-alias"},
        )
        opus_deprecated = replace(opus_deprecated, deprecated=True)

        opus_current = _make_model(
            "claude-opus-4-7", model_class="opus",
            aliases={"anthropic": "opus-current-alias"},
        )
        # the deprecated model ranks first — without the filter it would win
        registry = ModelRegistry([opus_deprecated, opus_current])

        opus_role = Role(
            name="orchestrator", label="Orchestrator", description="",
            )
        with patch(
            "agent_notes.registries.role_registry.load_role_registry",
            return_value=RoleRegistry([opus_role]),
        ):
            model_str, _ = _resolve(
                agent_config={"role": "orchestrator"},
                model_registry=registry,
            )
        assert model_str == "opus-current-alias", (
            "Expected non-deprecated model, got deprecated one"
        )

    def test_falls_back_to_deprecated_when_only_candidate(self):
        """When only deprecated models exist, one is still returned rather than
        failing outright."""
        from dataclasses import replace

        opus_deprecated = _make_model(
            "claude-opus-4-7", model_class="opus",
            aliases={"anthropic": "only-opus-alias"},
        )
        opus_deprecated = replace(opus_deprecated, deprecated=True)
        registry = ModelRegistry([opus_deprecated])

        opus_role = Role(
            name="orchestrator", label="Orchestrator", description="",
            )
        with patch(
            "agent_notes.registries.role_registry.load_role_registry",
            return_value=RoleRegistry([opus_role]),
        ):
            model_str, _ = _resolve(
                agent_config={"role": "orchestrator"},
                model_registry=registry,
            )
        assert model_str == "only-opus-alias", (
            "Expected deprecated model to be returned as fallback when it is the only candidate"
        )


# ---------------------------------------------------------------------------
# Branch 4: Unresolvable — raises ValueError
# ---------------------------------------------------------------------------

class TestUnresolvable:
    """When all branches fail, a descriptive ValueError is raised."""

    def test_raises_when_no_role_resolves(self):
        """Error raised when resolution fully fails."""
        from agent_notes.services.rendering import _resolve_model_str
        with pytest.raises(ValueError, match="no model could be resolved"):
            _resolve_model_str(
                agent_name="lead",
                agent_config={"role": "orchestrator"},  # role exists but no model matches
                backend=_make_backend(),
                scope_state=None,
                model_registry=ModelRegistry([]),  # empty registry
                user_config={},
            )


# ---------------------------------------------------------------------------
# Integration: real registries — verify concrete agent resolution ids
# ---------------------------------------------------------------------------

class TestRealRegistryResolution:
    """Smoke-tests against the real on-disk data to catch regressions.
    These pin the model each role resolves to with no state pin and no user config.
    """

    CLAUDE_DEFAULTS = {
        "orchestrator": ("claude-fable-5-1", "fable"),
        "reasoner": ("claude-opus-5", "opus"),
        "worker": ("claude-sonnet-5", "sonnet"),
        "scout": ("claude-haiku-4-5", "haiku"),
    }

    CODEX_DEFAULTS = {
        "orchestrator": ("gpt-5-6-sol", "gpt-5.6-sol"),
        "reasoner": ("gpt-5-6-sol", "gpt-5.6-sol"),
        "worker": ("gpt-5-6-sol", "gpt-5.6-sol"),
        "scout": ("gpt-5-6-luna", "gpt-5.6-luna"),
    }

    @staticmethod
    def _registries():
        from agent_notes.registries.model_registry import load_model_registry
        from agent_notes.registries.role_registry import load_role_registry
        from agent_notes.registries.cli_registry import load_registry
        return load_model_registry(), load_role_registry(), load_registry()

    @pytest.mark.parametrize("backend_name,expected", [
        ("claude", CLAUDE_DEFAULTS),
        ("codex", CODEX_DEFAULTS),
    ])
    def test_role_defaults_are_pinned(self, backend_name, expected):
        """The four role defaults each backend ships with must not drift silently."""
        model_registry, _role_registry, cli_registry = self._registries()
        backend = cli_registry.get(backend_name)

        for role_name, (_model_id, rendered) in expected.items():
            model_str, _ = _resolve(
                agent_config={"role": role_name},
                backend=backend,
                model_registry=model_registry,
            )
            assert model_str == rendered, (
                f"{backend_name}/{role_name}: expected {rendered!r}, got {model_str!r}"
            )

    @pytest.mark.parametrize("backend_name,expected", [
        ("claude", CLAUDE_DEFAULTS),
        ("codex", CODEX_DEFAULTS),
    ])
    def test_wizard_and_resolver_agree(self, backend_name, expected):
        """The wizard's pre-selection is the same model the resolver would build."""
        from agent_notes.commands.config import compatible_models_for
        from agent_notes.commands.wizard import _default_model_for_role
        from agent_notes.services.model_resolver import select_model_for_role

        model_registry, role_registry, cli_registry = self._registries()
        backend = cli_registry.get(backend_name)
        compatible = compatible_models_for(backend)

        for role_name, (model_id, _rendered) in expected.items():
            role = role_registry.get(role_name)
            resolver_pick, _ = select_model_for_role(model_registry.all(), role, backend)
            wizard_pick = _default_model_for_role(role, compatible, backend)

            assert resolver_pick.id == model_id, (
                f"{backend_name}/{role_name}: resolver picked {resolver_pick.id!r}"
            )
            assert wizard_pick.id == resolver_pick.id, (
                f"{backend_name}/{role_name}: wizard picked {wizard_pick.id!r} but "
                f"the resolver picked {resolver_pick.id!r}"
            )
