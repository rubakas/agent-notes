"""Install execution functions for the wizard."""

from pathlib import Path
from typing import Dict, List, Optional, Set

from ...config import Color, AGENTS_HOME, PKG_DIR
from ...services.fs import place_file, place_dir_contents
from .._install_helpers import count_agents
from ._common import _get_skill_groups, _count_rules


def install_skills_filtered(skill_names: List[str], targets: List[Path], copy_mode: bool = False) -> None:
    """Install only specified skills to target directories."""
    from ...config import DIST_SKILLS_DIR
    if not skill_names or not DIST_SKILLS_DIR.exists():
        return

    for target_dir in targets:
        target_dir.mkdir(parents=True, exist_ok=True)

        for skill_name in sorted(skill_names):
            skill_dir = DIST_SKILLS_DIR / skill_name
            if skill_dir.is_dir():
                place_file(skill_dir, target_dir / skill_name, copy_mode)


def install_agents_filtered(clis: Set[str], scope: str, copy_mode: bool = False,
                            folder_overrides: dict = None, global_home_override: str = "") -> None:
    """Install agents for selected CLIs (filtered by the wizard)."""
    from ...services import installer
    from ...services.installer import _apply_overrides, _agent_glob
    from ...registries.cli_registry import load_registry

    registry = load_registry()
    for backend in registry.all():
        if backend.name not in clis:
            continue
        effective = _apply_overrides(backend, folder_overrides, global_home_override or None)
        src = installer.dist_source_for(effective, "agents")
        if src is None:
            continue
        dst = installer.target_dir_for(effective, "agents", scope)
        if dst is None:
            continue

        glob = _agent_glob(effective)
        files = list(src.glob(glob))
        if not files:
            continue

        place_dir_contents(src, dst, glob, copy_mode)


def install_config_filtered(clis: Set[str], scope: str, copy_mode: bool = False,
                            folder_overrides: dict = None, global_home_override: str = "") -> None:
    """Install config + rules for selected CLIs."""
    from ...services import installer
    from ...services.installer import _apply_overrides
    from ...registries.cli_registry import load_registry

    registry = load_registry()

    for backend in registry.all():
        if backend.name not in clis:
            continue
        effective = _apply_overrides(backend, folder_overrides, global_home_override or None)

        config_src = installer.dist_source_for(effective, "config")
        config_dst = installer.target_dir_for(effective, "config", scope)
        if config_src is not None and config_dst is not None:
            filename = installer.config_filename_for(effective)
            if filename:
                src_file = config_src / filename
                if src_file.exists():
                    place_file(src_file, config_dst / filename, copy_mode)

        rules_src = installer.dist_source_for(effective, "rules")
        rules_dst = installer.target_dir_for(effective, "rules", scope)
        if rules_src is not None and rules_dst is not None:
            files = list(rules_src.glob("*.md"))
            if files:
                place_dir_contents(rules_src, rules_dst, "*.md", copy_mode)


def _display_path(path: Path) -> str:
    """Render a filesystem path with the home directory shortened to ~."""
    return str(path).replace(str(Path.home()), "~")


def _step_line(label: str, desc: str, width: int) -> str:
    """One aligned '✓ Label  desc' install-progress row."""
    return f"  {Color.GREEN}✓{Color.NC} {label:<{width}}  {desc}"


def _render_configuration(role_models: Dict[str, Dict[str, str]],
                          role_efforts: Optional[Dict[str, Dict[str, str]]]) -> None:
    """Print the post-install Configuration section: role → model · effort,
    one row per role in canonical role order, using the effort the user picked
    (state pin) with fallback to the role's typical_effort — the same display
    logic as the confirmation summary (_format_role_model_display)."""
    from . import _format_role_model_display
    from ._common import _ROLE_ANSI, _role_sort_key
    from ...registries.cli_registry import load_registry
    from ...registries.model_registry import load_model_registry
    from ...registries.role_registry import load_role_registry

    if not any(role_models.get(cli) for cli in role_models):
        return

    registry = load_registry()
    models_registry = load_model_registry()
    role_map = {r.name: r for r in load_role_registry().all()}

    print("\nConfiguration")
    for cli_name, cli_models in role_models.items():
        if not cli_models:
            continue
        try:
            cli_label = registry.get(cli_name).label
        except KeyError:
            cli_label = cli_name
        print(f"\n  {Color.CYAN}{cli_label}{Color.NC}")
        cli_efforts = (role_efforts or {}).get(cli_name, {})
        role_items = sorted(cli_models.items(),
                            key=lambda kv: _role_sort_key(role_map.get(kv[0]), kv[0]))
        for role_name, model_id in role_items:
            role = role_map.get(role_name)
            role_label = role.label if role else role_name
            role_ansi = (_ROLE_ANSI.get(role.color, "") if role and role.color else "") if Color.CYAN else ""
            colored_role = f"{role_ansi}{role_label}{Color.NC}" if role_ansi else role_label
            padding = " " * max(0, 28 - len(role_label))
            display = _format_role_model_display(role, model_id, models_registry,
                                                 picked_effort=cli_efforts.get(role_name))
            print(f"    {colored_role}{padding} {Color.DIM}{display}{Color.NC}")

    print(f"\n  {Color.DIM}Change anytime:{Color.NC} agent-notes config role-model "
          f"{Color.DIM}·{Color.NC} agent-notes config role-effort")


def _execute_install(
    clis: Set[str],
    scope: str,
    copy_mode: bool,
    selected_skills: List[str],
    role_models: Dict[str, Dict[str, str]],
    memory_backend: str,
    memory_path: str,
    role_efforts: Optional[Dict[str, Dict[str, str]]] = None,
    profile_label: str = "",
    folder_overrides: dict = None,
    global_home_override: str = "",
    cost_report_enabled: bool = False,
) -> None:
    """Run all installation steps after parameters have been collected and the build is done."""
    label_msg = f", profile={profile_label}" if profile_label else ""
    print(f"\nInstalling ({scope}, {'copy' if copy_mode else 'symlink'}{label_msg}) ...\n")

    from ...services import fs as _fs
    _fs.silent_file_ops = True

    from ...registries.cli_registry import load_registry as _load_registry
    from ...services import installer as _installer
    from ...services.installer import _apply_overrides
    _registry = _load_registry()

    _selected_backends = [_b for _b in _registry.all() if _b.name in clis]

    # Align all '✓ Label  desc' rows on one label column (CLI labels included).
    _fixed_labels = ("Skills", "Agents", "Config", "Commands", "Hook", "Memory")
    _label_w = max(len(l) for l in
                   [*(_b.label for _b in _selected_backends), *_fixed_labels])

    # Install destination per CLI (the real target the files land in)
    for _b in _selected_backends:
        _eff = _apply_overrides(_b, folder_overrides, global_home_override or None)
        _dest = _eff.global_home if scope == "global" else Path.cwd() / _eff.local_dir
        print(_step_line(_b.label, f"→  {_display_path(_dest)}", _label_w))

    # Skills
    if selected_skills:
        targets = []
        for _b in _selected_backends:
            if _b.supports("skills"):
                _eff = _apply_overrides(_b, folder_overrides, global_home_override or None)
                _t = _installer.target_dir_for(_eff, "skills", scope)
                if _t is not None:
                    targets.append(_t)
        if scope == "global":
            targets.append(AGENTS_HOME / "skills")
        install_skills_filtered(selected_skills, targets, copy_mode)
        _skill_groups = _get_skill_groups()
        _group_parts = []
        for _gn, _gs in _skill_groups.items():
            _cnt = sum(1 for s in selected_skills if s in _gs)
            if _cnt:
                _group_parts.append(f"{_gn} ({_cnt})")
        _all_grouped = {s for gs in _skill_groups.values() for s in gs}
        _ungrouped = sum(1 for s in selected_skills if s not in _all_grouped)
        if _ungrouped:
            _group_parts.append(f"Other ({_ungrouped})")
        print(_step_line("Skills", ', '.join(_group_parts) if _group_parts else f"{len(selected_skills)} skills", _label_w))

    # Agents
    install_agents_filtered(clis, scope, copy_mode,
                            folder_overrides=folder_overrides, global_home_override=global_home_override)
    _agent_parts = []
    for _b in _selected_backends:
        if _b.supports("agents"):
            _cnt = count_agents(_b)
            if _cnt:
                _agent_parts.append(f"{_b.label} ({_cnt})")
    if _agent_parts:
        print(_step_line("Agents", ', '.join(_agent_parts), _label_w))

    # Config + Rules
    install_config_filtered(clis, scope, copy_mode,
                            folder_overrides=folder_overrides, global_home_override=global_home_override)
    _rules_n = _count_rules()
    _cfg_files = [_installer.config_filename_for(_b) for _b in _selected_backends if _installer.config_filename_for(_b)]
    _cfg_desc = ", ".join(_cfg_files) if _cfg_files else "config"
    _cfg_desc += f" + {_rules_n} rules" if _rules_n else ""
    print(_step_line("Config", _cfg_desc, _label_w))

    # Commands
    from ...services.installer import install_component_for_backend as _install_component
    _cmd_names = set()
    for _backend in _selected_backends:
        _eff_cmd = _apply_overrides(_backend, folder_overrides, global_home_override or None)
        _install_component(_eff_cmd, "commands", scope, copy_mode)
        if _backend.supports("commands"):
            _cmd_src = _installer.dist_source_for(_backend, "commands")
            if _cmd_src is not None:
                _cmd_names.update(f.stem for f in _cmd_src.glob("*.md"))
    if _cmd_names:
        print(_step_line("Commands", ', '.join(sorted(_cmd_names)), _label_w))

    # SessionStart hooks — for every backend with features.session_hook == true
    from ...services.installer import _install_session_hook
    _hooked_labels = []
    for _hook_backend in _registry.with_feature("session_hook"):
        if _hook_backend.name not in clis:
            continue
        try:
            _hook_eff = _apply_overrides(_hook_backend, folder_overrides, global_home_override or None)
            _install_session_hook(_hook_eff, scope, memory_backend=memory_backend, memory_path=memory_path or "")
            _hooked_labels.append(_hook_backend.label)
        except Exception:
            pass
    if _hooked_labels:
        print(_step_line("Hook", f"SessionStart ({', '.join(_hooked_labels)})", _label_w))

    _fs.silent_file_ops = False

    # Write state.json
    from ...services.install_state_builder import build_install_state
    from ...services.state_store import record_install_state
    from ...domain.state import MemoryConfig
    project_path = Path.cwd() if scope == "local" else None
    try:
        st = build_install_state(
            mode="copy" if copy_mode else "symlink",
            scope=scope,
            repo_root=PKG_DIR.parent,
            project_path=project_path,
            role_models=role_models,
            role_efforts=role_efforts,
            selected_clis=set(clis),
            profile_label=profile_label,
            folder_overrides=folder_overrides,
            global_home_override=global_home_override or None,
        )
        st.memory = MemoryConfig(backend=memory_backend, path=memory_path)
        record_install_state(st)
    except Exception as e:
        print(f"{Color.YELLOW}Warning: failed to write state.json: {e}{Color.NC}")

    # Persist cost_report_enabled preference to user config
    try:
        from ...services.user_config import load_user_config as _load_user_config, save_user_config as _save_user_config
        _ucfg = _load_user_config()
        _ucfg["cost_report_enabled"] = cost_report_enabled
        _save_user_config(_ucfg)
    except Exception as e:
        print(f"{Color.YELLOW}Warning: failed to save cost-report preference: {e}{Color.NC}")

    # Initialize memory vault / directory on disk
    if memory_backend != "none":
        from ...config import memory_dir_for_backend
        from ...services.memory_router import memory_init
        _mem_path = memory_dir_for_backend(memory_backend, memory_path)
        try:
            memory_init(memory_backend, _mem_path)
            if memory_backend == "obsidian":
                memory_label = f"Obsidian (session)  →  {_mem_path}"
            elif memory_backend == "wiki":
                memory_label = f"Obsidian (wiki)  →  {_mem_path}"
            else:
                memory_label = f"Local markdown  →  {_mem_path}"
        except Exception as e:
            memory_label = f"(init failed: {e})"
        print(_step_line("Memory", memory_label, _label_w))

    _render_configuration(role_models, role_efforts)

    print(f"\n{Color.GREEN}Done.{Color.NC} Restart Claude Code / OpenCode to pick up changes.")
