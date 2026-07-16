"""Single-responsibility model resolution.

ModelResolver is the ONE place that answers "what model string does this
agent get for this backend?".  All other call sites delegate here.

Resolution precedence (in order):
  1. State-driven pin   — scope_state.clis[backend].role_models[role]
                          → look up model in registry → provider alias.
                            ALWAYS the exact alias string, never model_class:
                            a pin is an explicit user choice of a specific
                            model version, so it must survive into frontmatter
                            verbatim even on use_model_class backends.
  2. User-config override — user_config["role_models"][backend_name][role]
                            → returned verbatim (no registry lookup)
  3. Role typical_class   — load role registry, match role.typical_class
                            against model registry (newest id first).
                            When backend.preferred_family is set, prefer
                            models of that family; fall back to any-family
                            if no preferred match found.
                            Returns alias (or model_class if use_model_class).
  4. Legacy tier fallback — agent_config["tier"] → tiers[tier][backend.name]
                            Raises ValueError if tier key absent or backend
                            not in tier dict.

Role resolution:
  Before any of the above, the effective agent role is determined by
  user_config["agent_roles"][agent_name] (override) falling back to
  agent_config["role"] (declared). This mirrors resolve_agent_role().

Note: Role.typical_class drives both the wizard default pre-selection and
Branch 3 of this resolver. The wizard selects the newest non-deprecated
model of the matching class; this resolver picks newest (any deprecation
status) when serving a live build.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:
    from ..domain.cli_backend import CLIBackend
    from ..domain.state import ScopeState
    from ..registries.model_registry import ModelRegistry


class ModelResolver:
    """Resolve the model string for an agent+backend pair.

    Constructed once per build invocation with all the inputs it needs;
    the public API is a single method: ``resolve()``.
    """

    def __init__(
        self,
        scope_state: Optional["ScopeState"],
        user_config: Dict[str, Any],
        tiers: Dict[str, Any],
        model_registry: Optional["ModelRegistry"] = None,
    ) -> None:
        self._scope_state = scope_state
        self._user_config = user_config
        self._tiers = tiers
        self._model_registry = model_registry  # may be None; loaded lazily on first need

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def resolve(
        self,
        agent_name: str,
        agent_config: Dict[str, Any],
        backend: "CLIBackend",
    ) -> str:
        """Return the model string for *agent_name* on *backend*.

        Mutates internal cached model_registry if it is loaded lazily.
        Raises ValueError if resolution fails at all branches.
        """
        agent_role = self._effective_role(agent_name, agent_config)

        # Branch 1: state-driven pin
        model_str = self._from_state(agent_role, backend)
        if model_str is not None:
            return model_str

        # Branch 2: user config override
        model_str = self._from_user_config(agent_role, backend.name)
        if model_str is not None:
            return model_str

        # Branch 3: role typical_class fallback
        if agent_role is not None:
            model_str = self._from_typical_class(agent_role, backend)
            if model_str is not None:
                return model_str

        # Branch 4: legacy tier fallback
        return self._from_tier(agent_name, agent_config, backend)

    # ------------------------------------------------------------------
    # Internal helpers — one per branch
    # ------------------------------------------------------------------

    def _effective_role(self, agent_name: str, agent_config: Dict[str, Any]) -> Optional[str]:
        """Return the effective role for agent_name (user override > declared)."""
        default_role = agent_config.get("role")
        return self._user_config.get("agent_roles", {}).get(agent_name, default_role)

    def _from_state(self, agent_role: Optional[str], backend: "CLIBackend") -> Optional[str]:
        """Branch 1: state-driven model pin."""
        if self._scope_state is None or agent_role is None:
            return None
        if backend.name not in self._scope_state.clis:
            return None
        role_models = self._scope_state.clis[backend.name].role_models
        if agent_role not in role_models:
            return None

        model_id = role_models[agent_role]
        registry = self._ensure_registry()
        try:
            model = registry.get(model_id)
        except KeyError:
            return None  # unknown model id — fall through

        resolved = model.resolve_for_providers(list(backend.accepted_providers))
        if resolved is None:
            return None  # no alias for this backend's providers — fall through
        _provider, alias_str = resolved
        # DECISION: state pins always render the exact alias string, even on
        # use_model_class backends (claude). Class-based rendering remains only
        # for the UNPINNED typical_class fallback (Branch 3) — a pin is an
        # explicit version choice and flattening it to "sonnet" would let the
        # harness silently substitute its own default version.
        return alias_str

    def _from_user_config(self, agent_role: Optional[str], backend_name: str) -> Optional[str]:
        """Branch 2: user-config explicit role→model override."""
        if agent_role is None:
            return None
        return (
            self._user_config
            .get("role_models", {})
            .get(backend_name, {})
            .get(agent_role)
        )

    def _from_typical_class(self, agent_role: str, backend: "CLIBackend") -> Optional[str]:
        """Branch 3: role.typical_class → newest matching model."""
        from ..registries.role_registry import load_role_registry

        try:
            role_registry = load_role_registry()
            role = role_registry.get(agent_role)
        except (KeyError, FileNotFoundError, ValueError):
            return None

        registry = self._ensure_registry()
        all_models_reversed = list(reversed(registry.all()))
        preferred_family = backend.preferred_family

        def _find_class_match(models, family_filter=None):
            for model in models:
                if model.model_class != role.typical_class:
                    continue
                if family_filter is not None and model.family != family_filter:
                    continue
                resolved = model.resolve_for_providers(list(backend.accepted_providers))
                if resolved is not None:
                    return model, resolved
            return None, None

        if preferred_family is not None:
            matched_model, resolved = _find_class_match(all_models_reversed, preferred_family)
            if matched_model is None:
                matched_model, resolved = _find_class_match(all_models_reversed)
        else:
            matched_model, resolved = _find_class_match(all_models_reversed)

        if matched_model is None or resolved is None:
            return None

        _provider, alias_str = resolved
        return matched_model.model_class if backend.use_model_class else alias_str

    def _from_tier(
        self,
        agent_name: str,
        agent_config: Dict[str, Any],
        backend: "CLIBackend",
    ) -> str:
        """Branch 4: legacy tier fallback. Raises ValueError on failure."""
        agent_role = self._effective_role(agent_name, agent_config)
        if "tier" not in agent_config:
            # Provide a helpful error explaining what was tried
            role_class = "?"
            if agent_role is not None:
                try:
                    from ..registries.role_registry import load_role_registry
                    role_registry = load_role_registry()
                    role = role_registry.get(agent_role)
                    role_class = role.typical_class
                except (KeyError, FileNotFoundError, ValueError):
                    pass
            raise ValueError(
                f"Agent '{agent_name}' has role='{agent_role}' but no model could be "
                f"resolved for backend '{backend.name}'. Tried: state.role_models, "
                f"role.typical_class->model.class matching, and legacy 'tier' fallback. "
                f"Check that data/roles/{agent_role}.yaml exists and that at least one "
                f"model in data/models/*.yaml has class={role_class} "
                f"with an alias for one of {list(backend.accepted_providers)}."
            )

        tier = agent_config["tier"]
        if backend.name not in self._tiers.get(tier, {}):
            raise ValueError(
                f"tier '{tier}' missing model for CLI '{backend.name}' in agents.yaml"
            )
        return self._tiers[tier][backend.name]

    # ------------------------------------------------------------------
    # Registry lazy-load
    # ------------------------------------------------------------------

    def _ensure_registry(self) -> "ModelRegistry":
        """Load and cache the model registry on first access."""
        if self._model_registry is None:
            from ..registries.model_registry import load_model_registry
            self._model_registry = load_model_registry()
        return self._model_registry
