"""Interactive install for agent-notes: the review screen (spec 005).

The flow is in orchestrator.py and the rows in review.py / role_models.py.
This module keeps the helpers they and the post-install summary share.
"""

from pathlib import Path
from typing import List, Optional

from ._common import _get_skill_groups, _count_rules, _role_sort_key
from .execute import (
    install_skills_filtered,
    install_agents_filtered,
    install_config_filtered,
    _execute_install,
)
from .orchestrator import interactive_install, _interactive_install


def _default_model_for_role(role, compatible, backend):
    """The pre-selected default model for a role given the backend's compatible models.

    Delegates to the resolver's selection so the wizard's pre-selection and a
    live build always agree. Falls back to the first compatible model when
    nothing is rated and within budget, since the wizard must offer some default.
    """
    from ...services.model_resolver import select_model_for_role

    matched, _resolved = select_model_for_role(compatible, role, backend)
    return matched if matched is not None else compatible[0]


def _effort_provider_for_model(backend, model) -> Optional[str]:
    """Pure helper: return the provider name resolved for model on backend, or None."""
    resolved = backend.first_alias_for(model.aliases)
    return resolved[0] if resolved else None


def _effort_default_choice(role, provider) -> str:
    """Pure helper: default effort to preselect for a role given its provider.

    role.typical_effort wins if it's a valid value for this provider's effort
    vocabulary; otherwise falls back to the provider's own default_effort.
    NO cross-provider mapping/translation — the value is used as-is or not at all.
    """
    if role.typical_effort and role.typical_effort in provider.efforts:
        return role.typical_effort
    return provider.default_effort


def _validate_vault_path(path):
    """Return (is_ok, reason). ok if the dir exists and contains an .obsidian/ folder."""
    p = Path(path).expanduser()
    if not p.exists():
        return False, "that folder doesn't exist yet"
    if not (p / ".obsidian").is_dir():
        return False, "that folder isn't an Obsidian vault (no .obsidian/ inside)"
    return True, ""


def _detect_obsidian_vaults() -> List[Path]:
    """Scan common locations for Obsidian vaults (dirs containing .obsidian/)."""
    candidates = []
    search_roots = [Path.home() / "Documents", Path.home() / "Desktop", Path.home()]
    for root in search_roots:
        if not root.exists():
            continue
        try:
            for d in root.iterdir():
                try:
                    if d.is_dir() and (d / ".obsidian").exists():
                        candidates.append(d)
                except (PermissionError, OSError):
                    continue
        except (PermissionError, OSError):
            continue
    return candidates[:5]


def _format_role_model_display(role, model_id: str, models_registry, picked_effort: Optional[str] = None) -> str:
    """Pure helper: the 'Label · effort' display string for one role's model-map
    row (no color codes — caller applies those). Falls back to the raw model_id
    when the registry has no entry for it (user-config overrides can be
    arbitrary strings). The user's picked effort (when present) wins over the
    role's typical_effort; falls back to just the label when neither exists."""
    try:
        model = models_registry.get(model_id)
        display = model.label
    except KeyError:
        display = model_id
    effort = picked_effort or (role.typical_effort if role and role.typical_effort else None)
    if effort:
        display = f"{display} · {effort}"
    return display


__all__ = [
    "interactive_install",
    "_interactive_install",
    "_default_model_for_role",
    "_effort_provider_for_model",
    "_effort_default_choice",
    "_validate_vault_path",
    "_detect_obsidian_vaults",
    "_format_role_model_display",
    "install_skills_filtered",
    "install_agents_filtered",
    "install_config_filtered",
    "_execute_install",
    "_get_skill_groups",
    "_count_rules",
    "_role_sort_key",
]
