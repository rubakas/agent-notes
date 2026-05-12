"""Install execution functions for the wizard."""

from pathlib import Path
from typing import Dict, List, Set

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


def install_agents_filtered(clis: Set[str], scope: str, copy_mode: bool = False) -> None:
    """Install agents for selected CLIs (filtered by the wizard)."""
    from ...services import installer
    from ...registries.cli_registry import load_registry

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

        files = list(src.glob("*.md"))
        if not files:
            continue

        place_dir_contents(src, dst, "*.md", copy_mode)


def install_config_filtered(clis: Set[str], scope: str, copy_mode: bool = False) -> None:
    """Install config + rules for selected CLIs."""
    from ...services import installer
    from ...registries.cli_registry import load_registry

    registry = load_registry()

    for backend in registry.all():
        if backend.name not in clis:
            continue

        config_src = installer.dist_source_for(backend, "config")
        config_dst = installer.target_dir_for(backend, "config", scope)
        if config_src is not None and config_dst is not None:
            filename = installer.config_filename_for(backend)
            if filename:
                src_file = config_src / filename
                if src_file.exists():
                    place_file(src_file, config_dst / filename, copy_mode)

        rules_src = installer.dist_source_for(backend, "rules")
        rules_dst = installer.target_dir_for(backend, "rules", scope)
        if rules_src is not None and rules_dst is not None:
            files = list(rules_src.glob("*.md"))
            if files:
                place_dir_contents(rules_src, rules_dst, "*.md", copy_mode)


def _execute_install(
    clis: Set[str],
    scope: str,
    copy_mode: bool,
    selected_skills: List[str],
    role_models: Dict[str, Dict[str, str]],
    memory_backend: str,
    memory_path: str,
) -> None:
    """Run all installation steps after parameters have been collected and the build is done."""
    print(f"\nInstalling ({scope}, {'copy' if copy_mode else 'symlink'}) ...\n")

    from ...services import fs as _fs
    _fs.silent_file_ops = True

    from ...registries.cli_registry import load_registry as _load_registry
    from ...services import installer as _installer
    _registry = _load_registry()

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
    from ...services.installer import install_component_for_backend as _install_component
    for _backend in _registry.all():
        if _backend.name in clis:
            _install_component(_backend, "commands", scope, copy_mode)
    _cmd_names = [f.stem for f in (PKG_DIR / "dist" / "commands").glob("*.md")] if (PKG_DIR / "dist" / "commands").exists() else []
    if _cmd_names:
        print(f"  {Color.GREEN}✓{Color.NC} Commands   {', '.join(sorted(_cmd_names))}")

    # SessionStart hook (Claude Code only)
    from ...services.installer import _install_session_hook
    try:
        _claude = _registry.get("claude")
        if _claude.name in clis:
            _install_session_hook(_claude, scope, memory_backend=memory_backend, memory_path=memory_path or "")
    except (KeyError, Exception):
        pass

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
            selected_clis=set(clis),
        )
        st.memory = MemoryConfig(backend=memory_backend, path=memory_path)
        record_install_state(st)
    except Exception as e:
        print(f"{Color.YELLOW}Warning: failed to write state.json: {e}{Color.NC}")

    # Initialize memory vault / directory on disk
    if memory_backend != "none":
        from ...config import memory_dir_for_backend
        from ...services.obsidian_backend import obsidian_init
        from ...services.local_backend import local_init
        _mem_path = memory_dir_for_backend(memory_backend, memory_path)
        try:
            if memory_backend == "obsidian":
                obsidian_init(_mem_path)
                memory_label = f"Obsidian (session)  →  {_mem_path}"
            elif memory_backend == "wiki":
                from ...services.wiki_backend import wiki_init
                wiki_init(_mem_path)
                memory_label = f"Obsidian (wiki)  →  {_mem_path}"
            else:
                local_init(_mem_path)
                memory_label = f"Local markdown  →  {_mem_path}"
        except Exception as e:
            memory_label = f"(init failed: {e})"
        print(f"  {Color.GREEN}✓{Color.NC} Memory    {memory_label}")

    print(f"\n{Color.GREEN}Done.{Color.NC} Restart Claude Code / OpenCode to pick up changes.")
