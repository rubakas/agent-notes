"""Interactive install wizard for agent-notes."""

import sys
from pathlib import Path
from typing import List, Dict, Set, Optional

from .build import build
from ._install_helpers import (
    count_agents, count_global, count_skills
)
from ..services.fs import place_file, place_dir_contents
from ..services.ui import (
    _can_interactive, _safe_input, _checkbox_select, _radio_select,
    _checkbox_select_fallback, _radio_select_fallback
)
from ..config import (
    Color, AGENTS_HOME, PKG_DIR, get_version,
    DIST_SKILLS_DIR, DIST_RULES_DIR, DIST_CLAUDE_DIR, DIST_OPENCODE_DIR,
)

# Maps role color names (from roles/*.yaml) to ANSI Color attributes.
_ROLE_COLOR_MAP = {
    'purple': Color.MAGENTA,
    'red':    Color.RED,
    'cyan':   Color.CYAN,
    'blue':   Color.BLUE,
    'green':  Color.GREEN,
    'yellow': Color.YELLOW,
    'orange': Color.YELLOW,
}


def _get_skill_groups() -> Dict[str, List[str]]:
    """Get skill names grouped by technology."""
    # For testing, allow bypassing the registry
    import os
    if os.environ.get('_WIZARD_TEST_MODE'):
        if not DIST_SKILLS_DIR.exists():
            return {}
        all_skills = [d.name for d in DIST_SKILLS_DIR.iterdir() if d.is_dir()]
    else:
        try:
            from ..registries import default_skill_registry
            registry = default_skill_registry()

            # If the registry has per-skill grouping (skill.group field), use it.
            # If every skill falls into "uncategorized" (the default), fall through
            # to the hardcoded prefix-based grouping below so the wizard still
            # presents meaningful groups.
            if hasattr(registry, 'by_group'):
                groups = registry.by_group()
                real_groups = {
                    gn: [s.name for s in skills]
                    for gn, skills in groups.items()
                    if gn != "uncategorized" and skills
                }
                if real_groups:
                    return real_groups
                # else fall through to hardcoded grouping with registry's skill list
                all_skills = [s.name for s in registry.all()]
            else:
                # Fallback to old hardcoded grouping
                all_skills = [skill.name for skill in registry.all()]
        except Exception:
            # Fallback to old behavior if registry fails
            if not DIST_SKILLS_DIR.exists():
                return {}
            all_skills = [d.name for d in DIST_SKILLS_DIR.iterdir() if d.is_dir()]

    # Hardcoded grouping for backward compatibility
    groups = {
        "Rails": [s for s in all_skills if s.startswith("rails-") and s != "rails-kamal"],
        "Docker": [s for s in all_skills if s.startswith("docker-")],
        "Kamal": [s for s in all_skills if s == "rails-kamal"],
        "Git": [s for s in all_skills if s == "git"]
    }

    return {k: v for k, v in groups.items() if v}


def _count_rules() -> int:
    """Count rule files."""
    # For testing, allow bypassing the registry
    import os
    if os.environ.get('_WIZARD_TEST_MODE'):
        if not DIST_RULES_DIR.exists():
            return 0
        return len(list(DIST_RULES_DIR.glob("*.md")))
    else:
        try:
            from ..registries import default_rule_registry
            registry = default_rule_registry()
            return len(registry.all())
        except Exception:
            # Fallback to old behavior if registry fails
            if not DIST_RULES_DIR.exists():
                return 0
            return len(list(DIST_RULES_DIR.glob("*.md")))


def _select_cli(step: int = 0, total: int = 0, version: str = '') -> Set[str]:
    """Step 1: CLI selection."""
    from ..registries.cli_registry import load_registry
    registry = load_registry()
    # Show only CLIs that have a global_template (i.e. are meant to be user-selectable)
    # AND support at least one meaningful component (not just copilot which is config-only).
    options = []
    for backend in sorted(registry.all(), key=lambda b: b.name):
        options.append((backend.label, backend.name))

    # Default to Claude Code only
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


def _select_models_per_role(clis: Set[str], step: int = 0, total: int = 0, version: str = '') -> Dict[str, Dict[str, str]]:
    """For each CLI that supports agents, ask user to pick a model per role.

    Returns: {cli_name: {role_name: model_id}}. Config-only CLIs are skipped (no entry).
    """
    from ..registries.cli_registry import load_registry
    from ..registries.model_registry import load_model_registry
    from ..registries.role_registry import load_role_registry

    registry = load_registry()
    models = load_model_registry().all()
    roles = load_role_registry().all()

    # Sort roles by name for deterministic UI (registry already returns sorted)
    roles_sorted = sorted(roles, key=lambda r: r.name)

    result = {}
    for backend_name in sorted(clis):
        backend = registry.get(backend_name)
        if backend is None or not backend.supports("agents"):
            continue

        # Compatible models = those with at least one alias in backend.accepted_providers
        compatible = [m for m in models if backend.first_alias_for(m.aliases) is not None]
        if not compatible:
            # Could be: empty accepted_providers, or no models declare an alias for
            # any accepted provider. Either way, we can't drive this CLI — skip it
            # with a clear warning rather than hard-crashing the wizard.
            print(
                f"  {Color.YELLOW}Warning:{Color.NC} no compatible models found for "
                f"{backend.label} (accepted providers: "
                f"{list(backend.accepted_providers) or 'none'}). Skipping model selection; "
                f"this CLI will rely on legacy tier resolution."
            )
            continue

        cli_role_models = {}
        for role in roles_sorted:
            # Default: newest model (by registry order; iterate reversed so e.g.
            # claude-opus-4-7 wins over claude-opus-4-6) whose class == role.typical_class.
            # Fallback to first compatible if nothing matches.
            default_model = next(
                (m for m in reversed(compatible) if m.model_class == role.typical_class),
                compatible[0],
            )
            default_idx = compatible.index(default_model)

            # Build options: "Claude Opus 4.7 (via anthropic)" style
            options = []
            for m in compatible:
                prov_alias = backend.first_alias_for(m.aliases)
                provider = prov_alias[0] if prov_alias else "?"
                options.append((f"{m.label} (via {provider})", m.id))

            role_color = _ROLE_COLOR_MAP.get(role.color, '')
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

        result[backend_name] = cli_role_models
    return result


def _select_scope(clis: Set[str] = None, step: int = 0, total: int = 0, version: str = '') -> str:
    """Step 3: Install scope."""
    from ..registries.cli_registry import load_registry

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

    # Process skills are always included — separate them from tech skill groups.
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
        for group_name, skills in tech_groups.items():
            desc = descriptions.get(group_name, group_name.lower())
            count = len(skills)
            label = f"{group_name.capitalize()} — {desc} ({count} {'skill' if count == 1 else 'skills'})"
            options.append((label, group_name))

        all_group_names = set(tech_groups.keys())

        title = "Which domain skills to include?\n  (process skills are always included)"
        if _can_interactive():
            selected_groups = _checkbox_select(title, options, defaults=all_group_names,
                                               step=step, total=total, version=version)
        else:
            selected_groups = _checkbox_select_fallback(title, options, defaults=all_group_names,
                                                        step=step, total=total, version=version)

        skill_summary_parts = [f"process ({len(process_skills)})"] if process_skills else []
        for group_name, skills in tech_groups.items():
            if group_name in selected_groups:
                selected_skills.extend(skills)
                skill_summary_parts.append(f"{group_name.capitalize()} ({len(skills)})")
    else:
        skill_summary_parts = [f"process ({len(process_skills)})"] if process_skills else []

    summary = ", ".join(skill_summary_parts) if skill_summary_parts else "None"
    print(f"  {Color.GREEN}✓{Color.NC} Skills: {summary}")
    return selected_skills


def _render_install_summary(clis: Set[str], scope: str, copy_mode: bool, selected_skills: List[str], role_models: Dict[str, Dict[str, str]], skill_groups: Dict, registry) -> None:
    """Print the install summary table (CLI, scope, mode, models, skills, agents, config/rules)."""
    from ..services.installer import config_filename_for as _cfg_filename

    selected_backends = [b for b in registry.all() if b.name in clis]

    print("\nReady to install:\n")

    # CLI
    selected_labels = [b.label for b in selected_backends]
    print(f"  CLI       {', '.join(selected_labels) if selected_labels else '(none)'}")

    # Scope + paths
    if scope == "global":
        paths = [str(b.global_home) for b in selected_backends]
        scope_desc = "Global  →  " + ",  ".join(paths) if paths else "Global"
    else:
        paths = [b.local_dir for b in selected_backends]
        scope_desc = "Local  →  " + ",  ".join(paths) if paths else "Local"
    print(f"  Scope     {scope_desc}")

    # Mode
    print(f"  Mode      {'Copy' if copy_mode else 'Symlink'}")

    # Models (role label → model alias)
    if role_models:
        from ..registries.model_registry import load_model_registry
        from ..registries.role_registry import load_role_registry
        models_registry = load_model_registry()
        role_registry = load_role_registry()
        role_label_map = {r.name: r.label for r in role_registry.all()}
        print(f"\n  Models")
        for backend_name in sorted(role_models.keys()):
            backend = registry.get(backend_name)
            print(f"    {backend.label}:")
            for role_name, model_id in sorted(role_models[backend_name].items()):
                role_label = role_label_map.get(role_name, role_name)
                try:
                    model = models_registry.get(model_id)
                    prov_alias = backend.first_alias_for(model.aliases)
                    alias = prov_alias[1] if prov_alias else model_id
                    print(f"      {role_label:<16} {alias}")
                except KeyError:
                    print(f"      {role_label:<16} {model_id}")
        print("")

    # Skills
    if selected_skills:
        skill_counts = {}
        for group_name, group_skills in skill_groups.items():
            count = sum(1 for skill in selected_skills if skill in group_skills)
            if count > 0:
                skill_counts[group_name] = count
        skill_desc = ", ".join(f"{n.capitalize()} ({c})" for n, c in skill_counts.items()) if skill_counts else "None"
    else:
        skill_desc = "None"
    print(f"  Skills    {skill_desc}")

    # Agents
    agent_parts = []
    for backend in selected_backends:
        if not backend.supports("agents"):
            continue
        count = count_agents(backend)
        agent_parts.append(f"{count} ({backend.label})")
    if agent_parts:
        print(f"  Agents    {' + '.join(agent_parts)}")

    # Config + Rules
    config_files = [_cfg_filename(b) for b in selected_backends if _cfg_filename(b)]
    if config_files:
        print(f"  Config    {', '.join(config_files)}")
    rules_count = _count_rules()
    if rules_count:
        print(f"  Rules     {rules_count} files")

    print("")


def _detect_project_name() -> str:
    """Return git repo name, or cwd name as fallback."""
    import subprocess
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=3,
        )
        if result.returncode == 0:
            return Path(result.stdout.strip()).name
    except (OSError, subprocess.TimeoutExpired):
        pass
    return Path.cwd().name


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
    from ..config import Color

    options = [
        ("Local markdown files  (~/.claude/agent-memory/)", "local"),
        ("Obsidian vault", "obsidian"),
        ("None  (disable memory)", "none"),
    ]

    if _can_interactive():
        backend = _radio_select("How should agents store memory?", options, default=0,
                                step=step, total=total, version=version)
    else:
        backend = _radio_select_fallback("How should agents store memory?", options, default=0,
                                         step=step, total=total, version=version)

    path = ""

    if backend == "obsidian":
        project_name = _detect_project_name()
        candidates = _detect_obsidian_vaults()
        if candidates:
            _hint_suffix = f"agent-notes/{project_name}" if project_name != "agent-notes" else "agent-notes"
            print(f"  {Color.DIM}Detected vaults (notes go into {_hint_suffix}/ inside):{Color.NC}")
            for c in candidates[:3]:
                print(f"    {c}/{_hint_suffix}")
        _mem_base = candidates[0] if candidates else Path.home() / "Documents" / "Obsidian Vault"
        _mem_full = _mem_base / "agent-notes" / project_name
        # Avoid agent-notes/agent-notes when project name matches parent folder
        if _mem_full.parent.name == _mem_full.name:
            _mem_full = _mem_full.parent
        default_path = str(_mem_full)
        raw = _safe_input(f"  Memory folder path [{default_path}]: ", default_path)
        path = raw.strip() or default_path

    label = {"local": "Local markdown", "obsidian": f"Obsidian ({path})", "none": "Disabled"}[backend]
    print(f"  {Color.GREEN}✓{Color.NC} Memory: {label}")
    return backend, path


def _confirm_install(clis: Set[str], scope: str, copy_mode: bool, selected_skills: List[str], role_models: Dict[str, Dict[str, str]], version: str = '', memory_backend: str = 'local', memory_path: str = '') -> bool:
    """Step 7: Confirmation."""
    from ..services.ui import _clear_screen, _render_step_header
    from ..registries.cli_registry import load_registry
    _clear_screen()
    _render_step_header(7, 7, version)
    skill_groups = _get_skill_groups()
    registry = load_registry()

    _render_install_summary(clis, scope, copy_mode, selected_skills, role_models, skill_groups, registry)

    # Show memory config in summary
    if memory_backend == "obsidian":
        memory_label = f"Obsidian ({memory_path})" if memory_path else "Obsidian (~~/agent-memory)"
    elif memory_backend == "none":
        memory_label = "Disabled"
    else:
        memory_label = "Local markdown"
    print(f"  Memory    {memory_label}")
    print("")

    choice = _safe_input("Proceed? [Y/n]: ", "Y").lower()
    return choice != "n"


def install_skills_filtered(skill_names: List[str], targets: List[Path], copy_mode: bool = False) -> None:
    """Install only specified skills to target directories."""
    if not skill_names or not DIST_SKILLS_DIR.exists():
        return

    for target_dir in targets:
        target_dir.mkdir(parents=True, exist_ok=True)

        for skill_name in sorted(skill_names):
            skill_dir = DIST_SKILLS_DIR / skill_name
            if skill_dir.is_dir():
                place_file(skill_dir, target_dir / skill_name, copy_mode)


def install_agents_filtered(clis: Set[str], scope: str, copy_mode: bool = False) -> None:
    """Install agents for selected CLIs (filtered by the wizard)."""
    from ..services import installer
    from ..registries.cli_registry import load_registry

    registry = load_registry()
    for backend in registry.all():
        if backend.name not in clis:
            continue
        src = installer.dist_source_for(backend, "agents")
        if src is None:
            continue
        dst = installer.target_dir_for(backend, "agents", scope)
        if dst is None:
            continue

        # Only install if there are files to install
        files = list(src.glob("*.md"))
        if not files:
            continue


        place_dir_contents(src, dst, "*.md", copy_mode)


def install_config_filtered(clis: Set[str], scope: str, copy_mode: bool = False) -> None:
    """Install config + rules for selected CLIs."""
    from ..services import installer
    from ..registries.cli_registry import load_registry

    registry = load_registry()

    for backend in registry.all():
        if backend.name not in clis:
            continue

        # Install config file (CLAUDE.md / AGENTS.md / copilot-instructions.md)
        config_src = installer.dist_source_for(backend, "config")
        config_dst = installer.target_dir_for(backend, "config", scope)
        if config_src is not None and config_dst is not None:
            filename = installer.config_filename_for(backend)
            if filename:
                src_file = config_src / filename
                if src_file.exists():
                    place_file(src_file, config_dst / filename, copy_mode)

        # Install rules (only backends that support it — currently just claude)
        rules_src = installer.dist_source_for(backend, "rules")
        rules_dst = installer.target_dir_for(backend, "rules", scope)
        if rules_src is not None and rules_dst is not None:
            files = list(rules_src.glob("*.md"))
            if files:
                place_dir_contents(rules_src, rules_dst, "*.md", copy_mode)



def interactive_install() -> None:
    """Run the interactive install wizard."""
    try:
        _interactive_install()
    except KeyboardInterrupt:
        from ..config import Color
        print(f"\n\n  {Color.YELLOW}Cancelled.{Color.NC}")


def _interactive_install() -> None:
    """Inner implementation — called by interactive_install() with KeyboardInterrupt guard."""
    from ..services.ui import _clear_screen
    version = get_version()
    from ..registries.cli_registry import load_registry
    registry = load_registry()

    # Get total agent count across all backends that support agents
    total_agents = 0
    for backend in registry.all():
        if backend.supports("agents"):
            total_agents += count_agents(backend)

    n_skills = count_skills()
    n_rules = _count_rules()

    TOTAL_STEPS = 7

    _clear_screen()
    print(f"\n  {Color.BOLD}AgentNotes{Color.NC} {Color.CYAN}v{version}{Color.NC}")
    print(f"  {Color.DIM}AI agent configuration manager for Claude Code and OpenCode.{Color.NC}\n")
    print(f"  Includes {total_agents} agents, {n_skills} skills, and {n_rules} rules.\n")

    # Step 1: CLI selection
    clis = _select_cli(step=1, total=TOTAL_STEPS, version=version)

    if not clis:
        print("No CLI selected. Installation cancelled.")
        return

    # Step 2: Model selection per role (for CLIs that support agents)
    role_models = _select_models_per_role(clis, step=2, total=TOTAL_STEPS, version=version)

    # Step 3: Install scope
    scope = _select_scope(clis=clis, step=3, total=TOTAL_STEPS, version=version)

    # Step 4: Install mode (always shown)
    copy_mode = _select_mode(step=4, total=TOTAL_STEPS, version=version)

    # Step 5: Skill selection
    selected_skills = _select_skills(step=5, total=TOTAL_STEPS, version=version)

    # Step 6: Memory backend
    memory_backend, memory_path = _select_memory(step=6, total=TOTAL_STEPS, version=version)

    # Step 7: Confirmation
    if not _confirm_install(clis, scope, copy_mode, selected_skills, role_models, version=version,
                            memory_backend=memory_backend, memory_path=memory_path):
        print("Installation cancelled.")
        return

    # Build first
    print("\nBuilding from source...")
    try:
        build()
    except Exception as e:
        print(f"{Color.RED}Build failed: {e}{Color.NC}")
        return

    # Execute installation
    print(f"\nInstalling ({scope}, {'copy' if copy_mode else 'symlink'}) ...\n")

    from ..registries.cli_registry import load_registry as _load_registry
    from ..services import installer as _installer
    _registry = _load_registry()

    # Scripts (global only)
    if scope == "global":
        from ..services.installer import install_scripts_global
        install_scripts_global()

    # Skills
    if selected_skills:
        targets = []
        for _b in _registry.all():
            if _b.name in clis and _b.supports("skills"):
                _t = _installer.target_dir_for(_b, "skills", scope)
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
        print(f"  {Color.GREEN}✓{Color.NC} Skills     {', '.join(_group_parts) if _group_parts else str(len(selected_skills)) + ' skills'}")

    # Agents
    install_agents_filtered(clis, scope, copy_mode)
    _agent_parts = []
    for _b in _registry.all():
        if _b.name in clis and _b.supports("agents"):
            _cnt = count_agents(_b)
            if _cnt:
                _agent_parts.append(f"{_b.label} ({_cnt})")
    if _agent_parts:
        print(f"  {Color.GREEN}✓{Color.NC} Agents     {', '.join(_agent_parts)}")

    # Config + Rules
    install_config_filtered(clis, scope, copy_mode)
    _rules_n = _count_rules()
    _cfg_files = [_installer.config_filename_for(_b) for _b in _registry.all() if _b.name in clis and _installer.config_filename_for(_b)]
    _cfg_desc = ", ".join(_cfg_files) if _cfg_files else "config"
    _cfg_desc += f" + {_rules_n} rules" if _rules_n else ""
    print(f"  {Color.GREEN}✓{Color.NC} Config     {_cfg_desc}")

    # Commands
    from ..services.installer import install_component_for_backend as _install_component
    for _backend in _registry.all():
        if _backend.name in clis:
            _install_component(_backend, "commands", scope, copy_mode)
    _cmd_names = [f.stem for f in (PKG_DIR / "dist" / "commands").glob("*.md")] if (PKG_DIR / "dist" / "commands").exists() else []
    if _cmd_names:
        print(f"  {Color.GREEN}✓{Color.NC} Commands   {', '.join(sorted(_cmd_names))}")

    # SessionStart hook (Claude Code only)
    from ..services.installer import _install_session_hook
    try:
        _claude = _registry.get("claude")
        if _claude.name in clis:
            _install_session_hook(_claude, scope)
    except (KeyError, Exception):
        pass

    print(f"\n{Color.GREEN}Done.{Color.NC} Restart Claude Code / OpenCode to pick up changes.")

    # Write state.json
    from ..services.install_state_builder import build_install_state
    from ..services.state_store import record_install_state
    from ..domain.state import MemoryConfig
    project_path = Path.cwd() if scope == "local" else None
    try:
        st = build_install_state(
            mode="copy" if copy_mode else "symlink",
            scope=scope,
            repo_root=PKG_DIR.parent,
            project_path=project_path,
            role_models=role_models,
            selected_clis=set(clis),
        )
        st.memory = MemoryConfig(backend=memory_backend, path=memory_path)
        record_install_state(st)
    except Exception as e:
        print(f"{Color.YELLOW}Warning: failed to write state.json: {e}{Color.NC}")

    # Initialize memory vault / directory on disk
    if memory_backend != "none":
        from ..config import memory_dir_for_backend
        from ..services.memory_backend import obsidian_init, local_init
        _mem_path = memory_dir_for_backend(memory_backend, memory_path)
        try:
            if memory_backend == "obsidian":
                obsidian_init(_mem_path)
                memory_label = f"Obsidian  →  {_mem_path}"
            else:
                local_init(_mem_path)
                memory_label = f"Local markdown  →  {_mem_path}"
        except Exception as e:
            memory_label = f"(init failed: {e})"
        print(f"  {Color.GREEN}✓{Color.NC} Memory    {memory_label}")
