"""Interactive install wizard for agent-notes."""

import sys
from pathlib import Path
from typing import List, Dict, Set, Optional

from .build import build
from ._install_helpers import (
    count_agents, count_global, count_skills
)
from ..services.fs import place_file, place_dir_contents
from ..services.ui import Color as _Color

# Maps role color names (from roles/*.yaml) to ANSI Color attributes.
_ROLE_COLOR_MAP = {
    'purple': _Color.MAGENTA,
    'red':    _Color.RED,
    'cyan':   _Color.CYAN,
    'blue':   _Color.BLUE,
    'green':  _Color.GREEN,
    'yellow': _Color.YELLOW,
    'orange': _Color.YELLOW,
}


def _get_skill_groups() -> Dict[str, List[str]]:
    """Get skill names grouped by technology."""
    from .. import wizard as parent_module
    
    # For testing, allow bypassing the registry
    import os
    if os.environ.get('_WIZARD_TEST_MODE'):
        if not parent_module.DIST_SKILLS_DIR.exists():
            return {}
        all_skills = [d.name for d in parent_module.DIST_SKILLS_DIR.iterdir() if d.is_dir()]
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
            from .. import wizard as _shim
            if not _shim.DIST_SKILLS_DIR.exists():
                return {}
            all_skills = [d.name for d in _shim.DIST_SKILLS_DIR.iterdir() if d.is_dir()]
    
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
    from .. import wizard as parent_module
    
    # For testing, allow bypassing the registry
    import os
    if os.environ.get('_WIZARD_TEST_MODE'):
        if not parent_module.DIST_RULES_DIR.exists():
            return 0
        return len(list(parent_module.DIST_RULES_DIR.glob("*.md")))
    else:
        try:
            from ..registries import default_rule_registry
            registry = default_rule_registry()
            return len(registry.all())
        except Exception:
            # Fallback to old behavior if registry fails
            if not parent_module.DIST_RULES_DIR.exists():
                return 0
            return len(list(parent_module.DIST_RULES_DIR.glob("*.md")))


def _select_cli(step: int = 0, total: int = 0, version: str = '') -> Set[str]:
    """Step 1: CLI selection."""
    from ..cli_backend import load_registry
    registry = load_registry()
    # Show only CLIs that have a global_template (i.e. are meant to be user-selectable)
    # AND support at least one meaningful component (not just copilot which is config-only).
    options = []
    for backend in sorted(registry.all(), key=lambda b: b.name):
        options.append((backend.label, backend.name))

    # Safe defaults - all available backends that support agents
    safe_defaults = {b.name for b in registry.all() if b.supports("agents")}

    from .. import wizard as _shim

    if _shim._can_interactive():
        result = _shim._checkbox_select("Which CLI do you use?", options, defaults=safe_defaults,
                                        step=step, total=total, version=version)
    else:
        result = _shim._checkbox_select_fallback("Which CLI do you use?", options, defaults=safe_defaults,
                                                 step=step, total=total, version=version)

    labels = [label for label, val in options if val in result]
    print(f"  {_shim.Color.GREEN}✓{_shim.Color.NC} CLI: {', '.join(labels) if labels else 'None'}")
    return result


def _select_models_per_role(clis: Set[str], step: int = 0, total: int = 0, version: str = '') -> Dict[str, Dict[str, str]]:
    """For each CLI that supports agents, ask user to pick a model per role.

    Returns: {cli_name: {role_name: model_id}}. Config-only CLIs are skipped (no entry).
    """
    from ..cli_backend import load_registry
    from ..model_registry import load_model_registry
    from ..role_registry import load_role_registry
    from .. import wizard as _shim

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
                f"  {_shim.Color.YELLOW}Warning:{_shim.Color.NC} no compatible models found for "
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
            role_label_colored = f"{role_color}{role.label}{_shim.Color.NC}" if role_color else role.label
            title = (
                f"{_shim.Color.DIM}CLI{_shim.Color.NC}          {_shim.Color.YELLOW}{backend.label}{_shim.Color.NC}\n"
                f"  {_shim.Color.DIM}Role{_shim.Color.NC}         {role_label_colored}\n"
                f"  {_shim.Color.DIM}Description{_shim.Color.NC}  {role.description}"
            )
            if _shim._can_interactive():
                picked = _shim._radio_select(title, options, default=default_idx,
                                             step=step, total=total, version=version)
            else:
                picked = _shim._radio_select_fallback(title, options, default=default_idx,
                                                      step=step, total=total, version=version)
            cli_role_models[role.name] = picked

            picked_label = next(label for label, mid in options if mid == picked)
            print(f"  {_shim.Color.GREEN}✓{_shim.Color.NC} {role_label_colored}: {picked_label}")

        result[backend_name] = cli_role_models
    return result


def _select_scope(clis: Set[str] = None, step: int = 0, total: int = 0, version: str = '') -> str:
    """Step 3: Install scope."""
    from .. import wizard as _shim
    from ..cli_backend import load_registry

    registry = load_registry()
    if clis:
        global_paths = [str(b.global_home) for b in registry.all() if b.name in clis]
        local_paths = [b.local_dir for b in registry.all() if b.name in clis]
    else:
        global_paths = [str(b.global_home) for b in registry.all()]
        local_paths = [b.local_dir for b in registry.all()]

    global_detail = "\n    ".join(global_paths)
    global_label = f"Global\n    {global_detail}" if global_paths else "Global"
    local_detail = "\n    ".join(local_paths)
    local_label = f"Local\n    {local_detail}" if local_paths else "Local"

    options = [
        (global_label, "global"),
        (local_label, "local"),
    ]
    if _shim._can_interactive():
        result = _shim._radio_select("Where to install?", options, default=0,
                                     step=step, total=total, version=version)
    else:
        result = _shim._radio_select_fallback("Where to install?", options, default=0,
                                              step=step, total=total, version=version)

    label = "Global" if result == "global" else "Local"
    print(f"  {_shim.Color.GREEN}✓{_shim.Color.NC} Scope: {label}")
    return result


def _select_mode(step: int = 0, total: int = 0, version: str = '') -> bool:
    """Step 4: Install mode."""
    from .. import wizard as _shim

    options = [
        ("Symlink (auto-updates when source changes)", "symlink"),
        ("Copy (standalone, allows local customization)", "copy"),
    ]
    if _shim._can_interactive():
        result = _shim._radio_select("How to install?", options, default=0,
                                     step=step, total=total, version=version)
    else:
        result = _shim._radio_select_fallback("How to install?", options, default=0,
                                              step=step, total=total, version=version)

    label = "Symlink" if result == "symlink" else "Copy"
    print(f"  {_shim.Color.GREEN}✓{_shim.Color.NC} Mode: {label}")
    return result == "copy"


def _select_skills(step: int = 0, total: int = 0, version: str = '') -> List[str]:
    """Step 5: Skill selection."""
    from .. import wizard as _shim
    skill_groups = _shim._get_skill_groups()

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
        if _shim._can_interactive():
            selected_groups = _shim._checkbox_select(title, options, defaults=all_group_names,
                                                     step=step, total=total, version=version)
        else:
            selected_groups = _shim._checkbox_select_fallback(title, options, defaults=all_group_names,
                                                              step=step, total=total, version=version)

        skill_summary_parts = [f"process ({len(process_skills)})"] if process_skills else []
        for group_name, skills in tech_groups.items():
            if group_name in selected_groups:
                selected_skills.extend(skills)
                skill_summary_parts.append(f"{group_name.capitalize()} ({len(skills)})")
    else:
        skill_summary_parts = [f"process ({len(process_skills)})"] if process_skills else []

    summary = ", ".join(skill_summary_parts) if skill_summary_parts else "None"
    print(f"  {_shim.Color.GREEN}✓{_shim.Color.NC} Skills: {summary}")
    return selected_skills


def _confirm_install(clis: Set[str], scope: str, copy_mode: bool, selected_skills: List[str], role_models: Dict[str, Dict[str, str]], version: str = '') -> bool:
    """Step 6: Confirmation."""
    from ..services.ui import _clear_screen, _render_step_header
    from .. import wizard as _shim
    _clear_screen()
    _render_step_header(6, 6, version)
    skill_groups = _shim._get_skill_groups()

    print("\nReady to install:\n")

    from ..cli_backend import load_registry
    from .. import installer as _installer
    registry = load_registry()
    selected_backends = [b for b in registry.all() if b.name in clis]

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
        from ..model_registry import load_model_registry
        from ..role_registry import load_role_registry
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
        count = _shim.count_agents(backend)
        agent_parts.append(f"{count} ({backend.label})")
    if agent_parts:
        print(f"  Agents    {' + '.join(agent_parts)}")

    # Config + Rules
    config_files = [_installer.config_filename_for(b) for b in selected_backends if _installer.config_filename_for(b)]
    if config_files:
        print(f"  Config    {', '.join(config_files)}")
    rules_count = _count_rules()
    if rules_count:
        print(f"  Rules     {rules_count} files")

    print("")
    from .. import wizard as _shim
    choice = _shim._safe_input("Proceed? [Y/n]: ", "Y").lower()
    return choice != "n"


def install_skills_filtered(skill_names: List[str], targets: List[Path], copy_mode: bool = False) -> None:
    """Install only specified skills to target directories."""
    from .. import wizard as parent_module
    
    if not skill_names or not parent_module.DIST_SKILLS_DIR.exists():
        return

    for target_dir in targets:
        print(f"Installing skills to {target_dir} ...")
        target_dir.mkdir(parents=True, exist_ok=True)

        for skill_name in sorted(skill_names):
            skill_dir = parent_module.DIST_SKILLS_DIR / skill_name
            if skill_dir.is_dir():
                parent_module.place_file(skill_dir, target_dir / skill_name, copy_mode)


def install_agents_filtered(clis: Set[str], scope: str, copy_mode: bool = False) -> None:
    """Install agents for selected CLIs (filtered by the wizard)."""
    from .. import installer
    from ..cli_backend import load_registry
    from .. import wizard as _shim  # Import shim for test compatibility
    
    registry = load_registry()
    for backend in registry.all():
        if backend.name not in clis:
            continue
        # Use installer module but import the functions locally to preserve test compatibility
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
        
        print(f"Installing {backend.label} agents to {dst} ...")
        
        _shim.place_dir_contents(src, dst, "*.md", copy_mode)


def install_config_filtered(clis: Set[str], scope: str, copy_mode: bool = False) -> None:
    """Install config + rules for selected CLIs."""
    from .. import installer
    from ..cli_backend import load_registry
    from .. import wizard as _shim  # Import shim for test compatibility
    
    registry = load_registry()
    
    header = "Installing global config ..." if scope == "global" else "Installing project rules ..."
    print(header)
    
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
                    _shim.place_file(src_file, config_dst / filename, copy_mode)
        
        # Install rules (only backends that support it — currently just claude)
        rules_src = installer.dist_source_for(backend, "rules")
        rules_dst = installer.target_dir_for(backend, "rules", scope)
        if rules_src is not None and rules_dst is not None:
            files = list(rules_src.glob("*.md"))
            if files:
                _shim.place_dir_contents(rules_src, rules_dst, "*.md", copy_mode)



def interactive_install() -> None:
    """Run the interactive install wizard."""
    # Welcome
    from .. import wizard as _shim
    from ..services.ui import _clear_screen
    version = _shim.get_version()
    from ..cli_backend import load_registry
    registry = load_registry()

    # Get total agent count across all backends that support agents
    total_agents = 0
    for backend in registry.all():
        if backend.supports("agents"):
            total_agents += _shim.count_agents(backend)

    n_skills = _shim.count_skills()
    n_rules = _shim._count_rules()

    TOTAL_STEPS = 6

    _clear_screen()
    print(f"\n  {_shim.Color.BOLD}AgentNotes{_shim.Color.NC} {_shim.Color.CYAN}v{version}{_shim.Color.NC}")
    print(f"  {_shim.Color.DIM}AI agent configuration manager for Claude Code and OpenCode.{_shim.Color.NC}\n")
    print(f"  Includes {total_agents} agents, {n_skills} skills, and {n_rules} rules.\n")

    # Step 1: CLI selection
    clis = _shim._select_cli(step=1, total=TOTAL_STEPS, version=version)

    if not clis:
        print("No CLI selected. Installation cancelled.")
        return

    # Step 2: Model selection per role (for CLIs that support agents)
    role_models = _shim._select_models_per_role(clis, step=2, total=TOTAL_STEPS, version=version)

    # Step 3: Install scope
    scope = _shim._select_scope(clis=clis, step=3, total=TOTAL_STEPS, version=version)

    # Step 4: Install mode (always shown)
    copy_mode = _shim._select_mode(step=4, total=TOTAL_STEPS, version=version)

    # Step 5: Skill selection
    selected_skills = _shim._select_skills(step=5, total=TOTAL_STEPS, version=version)

    # Step 6: Confirmation
    if not _shim._confirm_install(clis, scope, copy_mode, selected_skills, role_models, version=version):
        print("Installation cancelled.")
        return

    # Build first
    print("\nBuilding from source...")
    try:
        _shim.build()
    except Exception as e:
        print(f"{_shim.Color.RED}Build failed: {e}{_shim.Color.NC}")
        return

    # Execute installation
    print(f"\nInstalling ({scope}, {'copy' if copy_mode else 'symlink'}) ...")
    print("")

    # Install shared scripts (global scope only). These are CLI-agnostic —
    # they live under ~/.local/bin/ and serve any AI CLI (e.g. cost-report).
    if scope == "global":
        from ..services.installer import install_scripts_global
        install_scripts_global()

    # Install skills
    if selected_skills:
        from ..cli_backend import load_registry
        from .. import installer
        registry = load_registry()
        targets = []
        for backend in registry.all():
            if backend.name in clis and backend.supports("skills"):
                target = installer.target_dir_for(backend, "skills", scope)
                if target is not None:
                    targets.append(target)
        # Plus the universal ~/.agents/skills if global scope (current behavior)
        if scope == "global":
            targets.append(_shim.AGENTS_HOME / "skills")

        _shim.install_skills_filtered(selected_skills, targets, copy_mode)

    # Install agents
    _shim.install_agents_filtered(clis, scope, copy_mode)

    # Install config
    _shim.install_config_filtered(clis, scope, copy_mode)

    # Install commands (slash commands like /plan, /review, /debug, /brainstorm)
    from ..cli_backend import load_registry as _load_registry
    from .. import installer as _installer
    _registry = _load_registry()
    for _backend in _registry.all():
        if _backend.name in clis:
            _installer.install_component_for_backend(_backend, "commands", scope, copy_mode)

    # Install SessionStart hook + context file (Claude Code only)
    from ..services.installer import _install_session_hook
    try:
        _claude = _registry.get("claude")
        if _claude.name in clis:
            _install_session_hook(_claude, scope)
    except (KeyError, Exception):
        pass

    print("")
    print(f"{_shim.Color.GREEN}Done.{_shim.Color.NC} Restart Claude Code / OpenCode to pick up changes.")
    
    # Write state.json
    from .. import install_state
    project_path = Path.cwd() if scope == "local" else None
    try:
        st = install_state.build_install_state(
            mode="copy" if copy_mode else "symlink",
            scope=scope,
            repo_root=_shim.PKG_DIR.parent,
            project_path=project_path,
            role_models=role_models,
            selected_clis=set(clis),
        )
        install_state.record_install_state(st)
    except Exception as e:
        print(f"{_shim.Color.YELLOW}Warning: failed to write state.json: {e}{_shim.Color.NC}")
