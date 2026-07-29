"""Interactive install wizard for agent-notes."""

import sys
from pathlib import Path
from typing import List, Dict, Set, Optional

from ...config import Color
from ...constants import DEFAULT_VAULT_DIR, DEFAULT_VAULT_NAME, Obsidian
from ...services.ui import (
    _can_interactive, _safe_input, _path_input, _checkbox_select, _radio_select,
    _checkbox_select_fallback, _radio_select_fallback,
)
from ._common import _ROLE_ANSI, _get_skill_groups, _count_rules, _role_sort_key
from .execute import (
    install_skills_filtered,
    install_agents_filtered,
    install_config_filtered,
    _execute_install,
)
from .orchestrator import interactive_install, _interactive_install


def _select_profile(step: int = 0, total: int = 0, version: str = '') -> tuple:
    """Step: Optional profile configuration for multi-subscription setups.

    Returns (profile_label, folder_overrides, global_home_override):
      - profile_label: str, e.g. "work" or "" for default
      - folder_overrides: dict or None, e.g. {"claude": ".claude-work"}
      - global_home_override: str or "", e.g. "~/.claude-work"
    """
    options = [
        ("No, use default .claude folder", "no"),
        ("Yes, set up a named profile (e.g. work, personal)", "yes"),
    ]
    if _can_interactive():
        result = _radio_select("Set up a named profile? (for multi-subscription setups)", options, default=0,
                               step=step, total=total, version=version)
    else:
        result = _radio_select_fallback("Set up a named profile? (for multi-subscription setups)", options, default=0,
                                         step=step, total=total, version=version)

    if result == "no":
        print(f"  {Color.GREEN}✓{Color.NC} Profile: default")
        return ("", None, "")

    label = _safe_input(f"  Profile label (e.g. work, personal): ").strip()
    if not label:
        print(f"  {Color.GREEN}✓{Color.NC} Profile: default")
        return ("", None, "")

    default_folder = f".claude-{label}"
    default_home = f"~/.claude-{label}"

    folder = _safe_input(f"  Local folder [{default_folder}]: ").strip() or default_folder
    home = _safe_input(f"  Global home [{default_home}]: ").strip() or default_home

    folder_overrides = {"claude": folder}
    print(f"  {Color.GREEN}✓{Color.NC} Profile: {label} (local={folder}, global={home})")
    return (label, folder_overrides, home)


def _select_cli(step: int = 0, total: int = 0, version: str = '') -> Set[str]:
    """Step 1: CLI selection."""
    from ...registries.cli_registry import load_registry
    registry = load_registry()
    options = []
    for backend in sorted(registry.all(), key=lambda b: b.name):
        options.append((backend.label, backend.name))

    safe_defaults = {"claude"}

    if _can_interactive():
        result = _checkbox_select("Which CLI do you use?", options, defaults=safe_defaults,
                                  step=step, total=total, version=version)
    else:
        result = _checkbox_select_fallback("Which CLI do you use?", options, defaults=safe_defaults,
                                           step=step, total=total, version=version)

    labels = [label for label, val in options if val in result]
    print(f"  {Color.GREEN}✓{Color.NC} CLI: {', '.join(labels) if labels else 'None'}")
    return result


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


def _select_models_per_role(clis: Set[str], step: int = 0, total: int = 0, version: str = ''
                            ) -> tuple[Dict[str, Dict[str, str]], Dict[str, Dict[str, str]]]:
    """For each CLI that supports agents, ask user to pick a model per role, then
    (if the picked model's provider has a provider-registry entry) an effort.

    Returns: (role_models, role_efforts), each shaped {cli_name: {role_name: value}}.
    Config-only CLIs are skipped (no entry). Roles/CLIs whose provider has no
    effort registry entry are skipped for effort selection (not present in role_efforts).
    """
    from ...registries.cli_registry import load_registry
    from ...registries.model_registry import load_model_registry
    from ...registries.role_registry import load_role_registry
    from ...registries.provider_registry import default_provider_registry

    registry = load_registry()
    models = load_model_registry().all()
    roles = load_role_registry().all()
    provider_registry = default_provider_registry()

    roles_sorted = sorted(roles, key=_role_sort_key)

    result = {}
    effort_result = {}
    for backend_name in sorted(clis):
        backend = registry.get(backend_name)
        if backend is None or not backend.supports("agents"):
            continue

        compatible = [m for m in models if backend.first_alias_for(m.aliases) is not None]
        if not compatible:
            print(
                f"  {Color.YELLOW}Warning:{Color.NC} no compatible models found for "
                f"{backend.label} (accepted providers: "
                f"{list(backend.accepted_providers) or 'none'}). Skipping model selection; "
                f"this CLI will rely on legacy tier resolution."
            )
            continue

        cli_role_models = {}
        cli_role_efforts = {}
        for role in roles_sorted:
            # Claude Code controls its own lead model via `/model` — configuring
            # the orchestrator role here would be misleading and create a stale
            # "Configured: orchestrator=…" entry in cost-report.
            if backend_name == "claude" and role.name == "orchestrator":
                continue

            default_model = next(
                (m for m in reversed(compatible) if m.model_class == role.typical_class and not m.deprecated and not m.never_default),
                next(
                    (m for m in reversed(compatible) if m.model_class == role.typical_class and not m.never_default),
                    next(
                        (m for m in reversed(compatible) if not m.never_default),
                        compatible[0],
                    ),
                ),
            )
            default_idx = compatible.index(default_model)

            options = []
            for m in compatible:
                prov_alias = backend.first_alias_for(m.aliases)
                provider = prov_alias[0] if prov_alias else "?"
                options.append((f"{m.label} (via {provider})", m.id))

            role_color = (_ROLE_ANSI.get(role.color, '') if sys.stdout.isatty() else '') if role.color else ''
            role_label_colored = f"{role_color}{role.label}{Color.NC}" if role_color else role.label
            title = (
                f"{Color.DIM}CLI{Color.NC}          {Color.YELLOW}{backend.label}{Color.NC}\n"
                f"  {Color.DIM}Role{Color.NC}         {role_label_colored}\n"
                f"  {Color.DIM}Description{Color.NC}  {role.description}"
            )
            if _can_interactive():
                picked = _radio_select(title, options, default=default_idx,
                                       step=step, total=total, version=version)
            else:
                picked = _radio_select_fallback(title, options, default=default_idx,
                                                step=step, total=total, version=version)
            cli_role_models[role.name] = picked

            picked_label = next(label for label, mid in options if mid == picked)
            print(f"  {Color.GREEN}✓{Color.NC} {role_label_colored}: {picked_label}")

            picked_model = next(m for m in compatible if m.id == picked)
            provider_name = _effort_provider_for_model(backend, picked_model)
            provider = None
            if provider_name is not None:
                try:
                    provider = provider_registry.get(provider_name)
                except KeyError:
                    provider = None

            if provider is not None:
                effort_options = [(e, e) for e in provider.efforts]
                default_effort = _effort_default_choice(role, provider)
                default_effort_idx = provider.efforts.index(default_effort)
                effort_title = (
                    f"{Color.DIM}CLI{Color.NC}          {Color.YELLOW}{backend.label}{Color.NC}\n"
                    f"  {Color.DIM}Role{Color.NC}         {role_label_colored}\n"
                    f"  {Color.DIM}Effort{Color.NC}       for {picked_label} (via {provider_name})"
                )
                if _can_interactive():
                    picked_effort = _radio_select(effort_title, effort_options, default=default_effort_idx,
                                                   step=step, total=total, version=version)
                else:
                    picked_effort = _radio_select_fallback(effort_title, effort_options, default=default_effort_idx,
                                                            step=step, total=total, version=version)
                cli_role_efforts[role.name] = picked_effort
                print(f"  {Color.GREEN}✓{Color.NC} {role_label_colored} effort: {picked_effort}")

        result[backend_name] = cli_role_models
        effort_result[backend_name] = cli_role_efforts
    return result, effort_result


def _select_scope(clis: Set[str] = None, step: int = 0, total: int = 0, version: str = '') -> str:
    """Step 3: Install scope."""
    from ...registries.cli_registry import load_registry

    registry = load_registry()
    selected_backends = [b for b in registry.all() if (not clis or b.name in clis)]

    def _path_lines(backends, path_fn) -> str:
        parts = [f"\n      {Color.DIM}{b.label}  →  {path_fn(b)}{Color.NC}" for b in backends]
        return "".join(parts)

    global_label = "Global" + _path_lines(selected_backends, lambda b: str(b.global_home))
    local_label = "Local" + _path_lines(selected_backends, lambda b: str(Path.cwd() / b.local_dir))

    options = [
        (global_label, "global"),
        (local_label, "local"),
    ]
    if _can_interactive():
        result = _radio_select("Where to install?", options, default=0,
                               step=step, total=total, version=version)
    else:
        result = _radio_select_fallback("Where to install?", options, default=0,
                                        step=step, total=total, version=version)

    label = "Global" if result == "global" else "Local"
    print(f"  {Color.GREEN}✓{Color.NC} Scope: {label}")
    return result


def _select_mode(step: int = 0, total: int = 0, version: str = '') -> bool:
    """Step 4: Install mode."""
    options = [
        ("Symlink (auto-updates when source changes)", "symlink"),
        ("Copy (standalone, allows local customization)", "copy"),
    ]
    if _can_interactive():
        result = _radio_select("How to install?", options, default=0,
                               step=step, total=total, version=version)
    else:
        result = _radio_select_fallback("How to install?", options, default=0,
                                        step=step, total=total, version=version)

    label = "Symlink" if result == "symlink" else "Copy"
    print(f"  {Color.GREEN}✓{Color.NC} Mode: {label}")
    return result == "copy"


def _select_skills(step: int = 0, total: int = 0, version: str = '') -> List[str]:
    """Step 5: Skill selection."""
    skill_groups = _get_skill_groups()

    if not skill_groups:
        return []

    process_skills = skill_groups.get("process", [])
    tech_groups = {k: v for k, v in skill_groups.items() if k != "process"}

    descriptions = {
        "rails": "models, controllers, views, routes, testing",
        "docker": "Dockerfile, Compose patterns",
        "kamal": "deployment with Kamal",
        "git": "commit workflow, conventional commits",
    }

    selected_skills = list(process_skills)

    if tech_groups:
        options = []
        all_skill_names = set()
        for group_name, skills in tech_groups.items():
            for skill_name in skills:
                desc = descriptions.get(skill_name, skill_name)
                label = f"{skill_name.capitalize()} — {desc}"
                options.append((label, skill_name))
                all_skill_names.add(skill_name)

        title = "Which domain skills to include?\n  (process skills are always included)"
        if _can_interactive():
            selected_domain_skills = _checkbox_select(title, options, defaults=all_skill_names,
                                                      step=step, total=total, version=version)
        else:
            selected_domain_skills = _checkbox_select_fallback(title, options, defaults=all_skill_names,
                                                               step=step, total=total, version=version)

        skill_summary_parts = [f"process ({len(process_skills)})"] if process_skills else []
        for skill_name in selected_domain_skills:
            selected_skills.append(skill_name)
            skill_summary_parts.append(skill_name.capitalize())
    else:
        skill_summary_parts = [f"process ({len(process_skills)})"] if process_skills else []

    summary = ", ".join(skill_summary_parts) if skill_summary_parts else "None"
    print(f"  {Color.GREEN}✓{Color.NC} Skills: {summary}")
    return selected_skills


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


def _select_memory(step: int, total: int, version: str = '') -> tuple:
    """Step N: choose memory backend. Returns (backend, path)."""
    storage_options = [
        ("default - Claude Code built-in md files", "local"),
        ("Obsidian - session", "obsidian"),
        ("None  (disable memory)", "none"),
    ]

    if _can_interactive():
        storage = _radio_select("How should agents store memory?", storage_options, default=0,
                                step=step, total=total, version=version)
    else:
        storage = _radio_select_fallback("How should agents store memory?", storage_options, default=0,
                                         step=step, total=total, version=version)

    backend = storage
    path = ""

    if backend == "obsidian":
        subfolder = Obsidian.SUBFOLDER
        candidates = _detect_obsidian_vaults()
        default_vault = str(candidates[0]) if candidates else str(Path.home() / DEFAULT_VAULT_DIR / DEFAULT_VAULT_NAME)
        if candidates:
            print(f"  {Color.DIM}Detected vaults:{Color.NC}")
            for c in candidates[:3]:
                print(f"    {c}")
        print(f"  {Color.DIM}Folder name: {subfolder}{Color.NC}")
        print(f"  {Color.DIM}Press Tab to autocomplete paths{Color.NC}")
        raw = _path_input(f"  Vault path [{default_vault}]: ", default_vault)
        vault = raw.strip() or default_vault
        path = str(Path(vault) / subfolder)
        print(f"  {Color.DIM}→ {path}{Color.NC}")

    label = {"local": "Local markdown", "obsidian": f"Obsidian (session)  ({path})", "none": "Disabled"}[backend]
    print(f"  {Color.GREEN}✓{Color.NC} Memory: {label}")
    return backend, path


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


def _render_install_summary(clis: Set[str], scope: str, copy_mode: bool, selected_skills: List[str], role_models: Dict[str, Dict[str, str]], skill_groups: Dict, registry, memory_backend: str = '', memory_path: str = '', role_efforts: Optional[Dict[str, Dict[str, str]]] = None) -> None:
    """Print the confirmation summary in per-CLI format with role colors."""
    from ...services.installer import config_filename_for as _cfg_filename
    from ...registries.model_registry import load_model_registry
    from ...registries.role_registry import load_role_registry
    from .._install_helpers import count_agents

    selected_backends = [b for b in registry.all() if b.name in clis]
    models_registry = load_model_registry()
    role_registry = load_role_registry()
    role_map = {r.name: r for r in role_registry.all()}

    print("")
    scope_label = "Global" if scope == "global" else "Local"
    print(f"  {Color.DIM}Scope{Color.NC}     {scope_label}")
    print(f"  {Color.DIM}Mode{Color.NC}      {'Copy' if copy_mode else 'Symlink'}")

    if selected_skills:
        all_grouped = {s for gs in skill_groups.values() for s in gs}
        parts = []
        for gname, gskills in skill_groups.items():
            cnt = sum(1 for s in selected_skills if s in gskills)
            if cnt:
                parts.append(f"{gname.capitalize()} ({cnt})")
        ungrouped = sum(1 for s in selected_skills if s not in all_grouped)
        if ungrouped:
            parts.append(f"Other ({ungrouped})")
        print(f"  {Color.DIM}Skills{Color.NC}    {', '.join(parts) if parts else 'none'}")

    if memory_backend and memory_backend != "none":
        if memory_backend == "obsidian":
            mem_label = f"Obsidian (session)  →  {memory_path}" if memory_path else "Obsidian (session)"
        else:
            mem_label = "Local markdown"
        print(f"  {Color.DIM}Memory{Color.NC}    {mem_label}")

    rules_count = _count_rules()

    for backend in selected_backends:
        print(f"\n  {Color.CYAN}{backend.label}{Color.NC}")

        if backend.name in role_models and role_models[backend.name]:
            print(f"    {Color.DIM}Agent roles:{Color.NC}")
            cli_efforts = (role_efforts or {}).get(backend.name, {})
            role_items = sorted(role_models[backend.name].items(),
                                key=lambda kv: _role_sort_key(role_map.get(kv[0]), kv[0]))
            for role_name, model_id in role_items:
                role = role_map.get(role_name)
                role_label = role.label if role else role_name
                role_ansi = (_ROLE_ANSI.get(role.color, "") if role and role.color else "") if Color.CYAN else ""
                colored_role = f"{role_ansi}{role_label}{Color.NC}" if role_ansi else role_label
                padding = " " * max(0, 28 - len(role_label))
                display = _format_role_model_display(role, model_id, models_registry,
                                                     picked_effort=cli_efforts.get(role_name))
                print(f"      {colored_role}{padding} {Color.DIM}{display}{Color.NC}")

        if backend.supports("agents"):
            n_agents = count_agents(backend)
            print(f"    {Color.DIM}Agents:{Color.NC}      {n_agents}")

        cfg = _cfg_filename(backend)
        if cfg:
            cfg_desc = cfg
            if rules_count:
                cfg_desc += f" + {rules_count} rules"
            print(f"    {Color.DIM}Config:{Color.NC}      {cfg_desc}")

    print("")


def _confirm_install(clis: Set[str], scope: str, copy_mode: bool, selected_skills: List[str], role_models: Dict[str, Dict[str, str]], role_efforts: Optional[Dict[str, Dict[str, str]]] = None, version: str = '', memory_backend: str = 'local', memory_path: str = '', step: int = 0, total: int = 0, folder_overrides: Optional[dict] = None, global_home_override: str = '') -> bool:
    """Step: Confirmation — shows pre-flight summary including files to be backed up."""
    import logging
    from ...services.ui import _clear_screen, _render_step_header
    from ...registries.cli_registry import load_registry
    from ...services.installer import plan_install, summarize_plan
    _clear_screen()
    _render_step_header(step, total, version)
    skill_groups = _get_skill_groups()
    registry = load_registry()

    _render_install_summary(clis, scope, copy_mode, selected_skills, role_models, skill_groups, registry,
                            memory_backend=memory_backend, memory_path=memory_path, role_efforts=role_efforts)

    try:
        # selected_skills is passed as-is: an empty selection must plan zero
        # skills (None would mean "all skills", which the install won't write).
        manifest = plan_install(
            scope=scope,
            registry=registry,
            selected_clis=set(clis),
            selected_skills=selected_skills,
            copy_mode=copy_mode,
            folder_overrides=folder_overrides,
            global_home_override=global_home_override or None,
        )
        summary = summarize_plan(manifest)

        print(f"  {Color.DIM}Files to install:{Color.NC}  {len(summary.to_install)}")
        if summary.overwrites:
            print(f"  {Color.YELLOW}Files to back up ({len(summary.overwrites)}):{Color.NC}")
            for a in summary.overwrites:
                print(f"    {Color.DIM}{a.dst}{Color.NC}  →  {a.backup_path}")
        print("")
    except Exception:
        logging.getLogger(__name__).debug("plan_install failed during pre-flight", exc_info=True)

    choice = _safe_input("Proceed? [Y/n]: ", "Y").strip().lower()
    return choice not in ("n", "no")


__all__ = [
    "interactive_install",
    "_interactive_install",
    "_select_cli",
    "_select_models_per_role",
    "_select_scope",
    "_select_mode",
    "_select_skills",
    "_select_memory",
    "_render_install_summary",
    "_detect_obsidian_vaults",
    "_confirm_install",
    "install_skills_filtered",
    "install_agents_filtered",
    "install_config_filtered",
    "_execute_install",
    "_get_skill_groups",
    "_count_rules",
    "_role_sort_key",
]
