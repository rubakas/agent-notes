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
  3. Role budget + rank  — walk the catalog frontier first (globally, across
                            providers) and take the first model that is rated,
                            priced within role.budget, and servable by the
                            backend. When backend.preferred_family is set it
                            wins outright unless no model of that family is
                            eligible at all.
                            Returns alias (or model_class if use_model_class).
  4. Error — raises ValueError with a diagnostic message.

Role resolution:
  Before any of the above, the effective agent role is determined by
  user_config["agent_roles"][agent_name] (override) falling back to
  agent_config["role"] (declared). This mirrors resolve_agent_role().

Note: select_model_for_role() below is the single implementation of "which
model does this role get" — Branch 3 and the install wizard both call it, so
the wizard's pre-selection and a live build can never disagree.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:
    from ..domain.cli_backend import CLIBackend
    from ..domain.state import ScopeState
    from ..registries.model_registry import ModelRegistry


def select_model_for_role(models, role, backend):
    """The one implementation of "which model does this role get?".

    Walks *models* in the registry's global frontier-first order and returns the first
    ``(model, (provider, alias))`` that the backend can serve, is rated by the
    benchmark, and costs no more than ``role.budget`` per 1M input tokens.
    An unrated model (``coding_index is None``) is never auto-selected; a
    ``None`` budget is unbounded. Returns ``(None, None)`` when nothing fits.

    Family and deprecation are applied as a widening ladder:
    ``(preferred_family, non-deprecated)`` → ``(any family, non-deprecated)`` →
    ``(preferred_family, any)`` → ``(any family, any)``. Because rung 1 is tried
    first over the whole catalog, backend.preferred_family behaves as a hard
    filter whenever *any* eligible model of that family exists — another family
    is only ever reachable when the preferred one has no eligible model at all.
    """
    providers = list(backend.accepted_providers)

    def _eligible(model) -> bool:
        if model.coding_index is None:
            return False
        if role.budget is None:
            return True
        return model.price_in is not None and model.price_in <= role.budget

    def _first(family_filter=None, skip_deprecated=False):
        for model in models:
            if not _eligible(model):
                continue
            if family_filter is not None and model.family != family_filter:
                continue
            if skip_deprecated and model.deprecated:
                continue
            resolved = model.resolve_for_providers(providers)
            if resolved is not None:
                return model, resolved
        return None, None

    preferred = backend.preferred_family
    if preferred is not None:
        ladder = [(preferred, True), (None, True), (preferred, False), (None, False)]
    else:
        ladder = [(None, True), (None, False)]

    for family_filter, skip_deprecated in ladder:
        matched, resolved = _first(family_filter, skip_deprecated)
        if matched is not None:
            return matched, resolved
    return None, None


class ModelResolver:
    """Resolve the model string for an agent+backend pair.

    Constructed once per build invocation with all the inputs it needs;
    the public API is a single method: ``resolve()``.
    """

    def __init__(
        self,
        scope_state: Optional["ScopeState"],
        user_config: Dict[str, Any],
        model_registry: Optional["ModelRegistry"] = None,
    ) -> None:
        self._scope_state = scope_state
        self._user_config = user_config
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

        # Branch 3: role budget + catalog rank
        if agent_role is not None:
            model_str = self._from_budget_rank(agent_role, backend)
            if model_str is not None:
                return model_str

        # Branch 4: error — no resolution succeeded
        return self._unresolvable(agent_name, agent_config, backend)

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
        # for the UNPINNED budget+rank fallback (Branch 3) — a pin is an
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

    def _from_budget_rank(self, agent_role: str, backend: "CLIBackend") -> Optional[str]:
        """Branch 3: best-ranked rated model within the role's budget."""
        from ..registries.role_registry import load_role_registry

        try:
            role_registry = load_role_registry()
            role = role_registry.get(agent_role)
        except (KeyError, FileNotFoundError, ValueError):
            return None

        registry = self._ensure_registry()
        matched_model, resolved = select_model_for_role(registry.all(), role, backend)
        if matched_model is None or resolved is None:
            return None

        _provider, alias_str = resolved
        return matched_model.model_class if backend.use_model_class else alias_str

    def _unresolvable(
        self,
        agent_name: str,
        agent_config: Dict[str, Any],
        backend: "CLIBackend",
    ) -> str:
        """Branch 4: no model could be resolved. Raises ValueError."""
        agent_role = self._effective_role(agent_name, agent_config)
        role_budget = "?"
        if agent_role is not None:
            try:
                from ..registries.role_registry import load_role_registry
                role_registry = load_role_registry()
                role = role_registry.get(agent_role)
                role_budget = "unbounded" if role.budget is None else f"${role.budget}/M in"
            except (KeyError, FileNotFoundError, ValueError):
                pass
        raise ValueError(
            f"Agent '{agent_name}' has role='{agent_role}' but no model could be "
            f"resolved for backend '{backend.name}'. Tried: state.role_models, "
            f"user config, and budget+rank selection. "
            f"Check that data/roles/{agent_role}.yaml exists and that at least one "
            f"rated model within the role's budget ({role_budget}) "
            f"has an alias for one of {list(backend.accepted_providers)}."
        )

    # ------------------------------------------------------------------
    # Registry lazy-load
    # ------------------------------------------------------------------

    def _ensure_registry(self) -> "ModelRegistry":
        """Load and cache the model registry on first access."""
        if self._model_registry is None:
            from ..registries.model_registry import load_model_registry
            self._model_registry = load_model_registry()
        return self._model_registry
