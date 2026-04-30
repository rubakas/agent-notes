"""Generic install/uninstall engine driven by the CLI backend registry."""

from __future__ import annotations

from pathlib import Path
from typing import List, NamedTuple, Optional

from ..domain.cli_backend import CLIBackend
from ..registries.cli_registry import CLIRegistry, load_registry
from .. import config
from .fs import (
    place_file, place_dir_contents,
    remove_symlink, remove_all_symlinks_in_dir, remove_dir_if_empty,
    files_identical, _timestamped_backup_path,
)
from .state_store import load_state, get_scope


class InstallAction(NamedTuple):
    """Describes a single file placement that plan_install would perform."""

    action: str          # "install", "overwrite", or "skip"
    src: Path
    dst: Path
    backup_path: Optional[Path]  # set when action == "overwrite"

# Re-import the atomic helpers from install (they stay in install.py):
# We intentionally avoid circular import by lazy-importing inside functions.

COMPONENT_TYPES = ("agents", "skills", "rules", "commands", "config")
# Note: "scripts" is handled separately, not per-backend.


def dist_source_for(backend: CLIBackend, component: str) -> Optional[Path]:
    """Return dist source path for a (backend, component) pair, or None if N/A.
    
    For "config" returns the directory containing the config file (the file
    itself is named per backend.layout["config"]).
    """
    if component == "agents":
        p = config.DIST_DIR / backend.name / "agents"
        return p if p.exists() else None
    if component == "config":
        # The config FILE lives directly under DIST_DIR / backend.name / <filename>
        # Caller resolves the filename via backend.layout["config"].
        p = config.DIST_DIR / backend.name
        return p if p.exists() else None
    if component == "rules":
        dist_rules_dir = config.DIST_RULES_DIR
        return dist_rules_dir if dist_rules_dir.exists() else None
    if component == "skills":
        dist_skills_dir = config.DIST_SKILLS_DIR
        return dist_skills_dir if dist_skills_dir.exists() else None
    if component == "commands":
        p = config.DIST_DIR / backend.name / "commands"
        return p if p.exists() else None
    return None


def target_dir_for(backend: CLIBackend, component: str, scope: str) -> Optional[Path]:
    """Return destination directory for a (backend, component, scope).

    scope: "global" or "local"
    Returns None if backend doesn't support this component.
    """
    # Special case for config: check layout instead of features
    if component == "config":
        if not backend.layout.get("config"):
            return None
    else:
        if not backend.supports(component):
            return None
    
    layout_value = backend.layout.get(component)
    if not layout_value:
        return None
    home = backend.global_home if scope == "global" else Path(backend.local_dir)
    if component == "config":
        # config layout is a filename like "CLAUDE.md"; target is the home dir
        return home
    # All others are subdirectories
    return home / layout_value.rstrip("/")


def config_filename_for(backend: CLIBackend) -> Optional[str]:
    """Return e.g. 'CLAUDE.md', 'AGENTS.md', 'copilot-instructions.md'."""
    return backend.layout.get("config")


def install_component_for_backend(
    backend: CLIBackend,
    component: str,
    scope: str,
    copy_mode: bool,
) -> None:
    """Install one component for one backend. No-op if unsupported or no source."""
    src = dist_source_for(backend, component)
    if src is None:
        return
    dst = target_dir_for(backend, component, scope)
    if dst is None:
        return

    if component == "config":
        filename = config_filename_for(backend)
        if not filename:
            return
        src_file = src / filename
        if not src_file.exists():
            return
        print(f"Installing {backend.label} config to {dst} ...")
        place_file(src_file, dst / filename, copy_mode)
    elif component in ("agents", "rules", "commands"):
        # Directory of *.md files — flat copy
        # Only print if there are files to install
        files = list(src.glob("*.md"))
        if not files:
            return
        print(f"Installing {backend.label} {component} to {dst} ...")
        place_dir_contents(src, dst, "*.md", copy_mode)
    elif component == "skills":
        # Each top-level subdir of src is a skill — install each as a directory
        # Only print if there are skills to install
        skill_dirs = [d for d in src.iterdir() if d.is_dir()]
        if not skill_dirs:
            return
        print(f"Installing {backend.label} skills to {dst} ...")
        for skill_dir in sorted(skill_dirs):
            place_file(skill_dir, dst / skill_dir.name, copy_mode)


def uninstall_component_for_backend(
    backend: CLIBackend,
    component: str,
    scope: str,
    copy_mode: bool = False,
) -> None:
    """Uninstall one component for one backend."""
    dst = target_dir_for(backend, component, scope)
    if dst is None or not dst.exists():
        return

    if component == "config":
        filename = config_filename_for(backend)
        if filename:
            config_file = dst / filename
            print(f"Removing {backend.label} config from {dst} ...")
            remove_symlink(config_file, copy_mode)
    else:
        # Only print if directory exists and has content
        if any(dst.iterdir()):
            print(f"Removing {backend.label} {component} from {dst} ...")
        remove_all_symlinks_in_dir(dst, copy_mode)
        remove_dir_if_empty(dst)


def _plan_file(src: Path, dst: Path, copy_mode: bool = False) -> InstallAction:
    """Return the InstallAction for a single src→dst placement."""
    if copy_mode and dst.is_symlink() and dst.resolve() == src.resolve():
        return InstallAction(action="skip", src=src, dst=dst, backup_path=None)
    if dst.exists() and not dst.is_symlink():
        if files_identical(src, dst):
            return InstallAction(action="skip", src=src, dst=dst, backup_path=None)
        backup_path = _timestamped_backup_path(dst)
        return InstallAction(action="overwrite", src=src, dst=dst, backup_path=backup_path)
    return InstallAction(action="install", src=src, dst=dst, backup_path=None)


def _plan_component(
    backend: CLIBackend,
    component: str,
    scope: str,
    copy_mode: bool = False,
) -> List[InstallAction]:
    """Return InstallActions for one (backend, component, scope) without writing."""
    src = dist_source_for(backend, component)
    if src is None:
        return []
    dst = target_dir_for(backend, component, scope)
    if dst is None:
        return []

    actions: List[InstallAction] = []

    if component == "config":
        filename = config_filename_for(backend)
        if not filename:
            return []
        src_file = src / filename
        if not src_file.exists():
            return []
        actions.append(_plan_file(src_file, dst / filename, copy_mode))
    elif component in ("agents", "rules", "commands"):
        for src_file in sorted(src.glob("*.md")):
            if src_file.exists():
                actions.append(_plan_file(src_file, dst / src_file.name, copy_mode))
    elif component == "skills":
        if not src.exists():
            return []
        for skill_dir in sorted(d for d in src.iterdir() if d.is_dir()):
            actions.append(_plan_file(skill_dir, dst / skill_dir.name, copy_mode))

    return actions


def _plan_session_hook(
    backend,
    scope: str,
) -> List[InstallAction]:
    """Return InstallActions for the settings.json SessionStart hook write.

    The hook is injected via merge (never a full overwrite), so:
      - If settings.json does not exist: action="install"
      - If settings.json exists but hook is absent: action="modify"
      - If settings.json exists and hook is already present: action="skip"
    """
    from .settings_writer import has_hook

    settings_path, _context_file, hook_command = _session_hook_paths(backend, scope)

    if not settings_path.exists():
        # Fresh write — settings.json will be created
        return [InstallAction(action="install", src=settings_path, dst=settings_path, backup_path=None)]

    if has_hook(settings_path, "SessionStart", hook_command):
        # Already installed — no-op
        return [InstallAction(action="skip", src=settings_path, dst=settings_path, backup_path=None)]

    # Merge inject — file exists but hook is absent; classified as modify
    return [InstallAction(action="modify", src=settings_path, dst=settings_path, backup_path=None)]


def plan_install(
    scope: str,
    registry: Optional[CLIRegistry] = None,
    selected_clis: Optional[set] = None,
    selected_skills: Optional[List[str]] = None,
    copy_mode: bool = False,
) -> List[InstallAction]:
    """Return a manifest of what install_all would do, without writing any files.

    Each entry is an InstallAction(action, src, dst, backup_path) where:
      action == "install"   — dst does not yet exist (fresh placement)
      action == "modify"    — dst exists and will be merge-updated (e.g. settings.json hook)
      action == "overwrite" — dst exists and differs; backup_path is the timestamped path
      action == "skip"      — dst exists and is byte-identical (or symlink unchanged); no write needed
    """
    if registry is None:
        registry = load_registry()

    actions: List[InstallAction] = []

    for backend in registry.all():
        if selected_clis is not None and backend.name not in selected_clis:
            continue
        for component in COMPONENT_TYPES:
            if component == "skills" and selected_skills is not None:
                # Skills are filtered — plan them separately below
                continue
            actions.extend(_plan_component(backend, component, scope, copy_mode))

    # Skills: respect the selected_skills filter (mirrors wizard's install_skills_filtered)
    if scope == "global" or selected_skills is not None:
        dist_skills_dir = config.DIST_SKILLS_DIR
        if dist_skills_dir.exists():
            skill_dirs = {d.name: d for d in dist_skills_dir.iterdir() if d.is_dir()}
            names_to_plan = selected_skills if selected_skills is not None else list(skill_dirs.keys())

            # Per-backend skill targets
            for backend in registry.all():
                if selected_clis is not None and backend.name not in selected_clis:
                    continue
                if not backend.supports("skills"):
                    continue
                dst_dir = target_dir_for(backend, "skills", scope)
                if dst_dir is None:
                    continue
                for name in sorted(names_to_plan):
                    skill_dir = skill_dirs.get(name)
                    if skill_dir:
                        actions.append(_plan_file(skill_dir, dst_dir / name, copy_mode))

            # Universal skills mirror (~/.agents/skills/)
            if scope == "global":
                target = config.AGENTS_HOME / "skills"
                for name in sorted(names_to_plan):
                    skill_dir = skill_dirs.get(name)
                    if skill_dir:
                        actions.append(_plan_file(skill_dir, target / name, copy_mode))

    # SessionStart hook for Claude Code — always planned when claude backend is selected
    try:
        claude_backend = registry.get("claude")
        if selected_clis is None or claude_backend.name in selected_clis:
            actions.extend(_plan_session_hook(claude_backend, scope))
    except KeyError:
        pass

    return actions


def install_all(scope: str, copy_mode: bool, registry: Optional[CLIRegistry] = None) -> None:
    """Top-level: install every (backend, component) combo."""
    if registry is None:
        registry = load_registry()

    for backend in registry.all():
        for component in COMPONENT_TYPES:
            install_component_for_backend(backend, component, scope, copy_mode)

    # Universal skills mirror: keep existing behavior — also install skills
    # to ~/.agents/skills/ for any backend that supports skills, only for global scope.
    if scope == "global":
        _install_universal_skills(copy_mode, registry)

    # SessionStart hook for Claude Code only
    try:
        claude_backend = registry.get("claude")
        _install_session_hook(claude_backend, scope)
    except KeyError:
        pass


def _install_universal_skills(copy_mode: bool, registry: CLIRegistry) -> None:
    """Mirror skills to ~/.agents/skills/ for backwards compatibility."""
    
    dist_skills_dir = config.DIST_SKILLS_DIR
    if not dist_skills_dir.exists():
        return

    target = config.AGENTS_HOME / "skills"
    target.mkdir(parents=True, exist_ok=True)
    skill_dirs = [d for d in dist_skills_dir.iterdir() if d.is_dir()]
    if not skill_dirs:
        return
    print(f"Installing universal skills to {target} ...")
    for skill_dir in sorted(skill_dirs):
        place_file(skill_dir, target / skill_dir.name, copy_mode)


def uninstall_all(scope: str, registry: Optional[CLIRegistry] = None) -> None:
    """Top-level uninstall."""
    if registry is None:
        registry = load_registry()

    # Determine copy_mode from state so plain copy-installed files are removed too
    copy_mode = False
    state = load_state()
    if state is not None:
        scope_state = get_scope(state, scope)
        if scope_state is not None:
            copy_mode = (scope_state.mode == "copy")

    for backend in registry.all():
        for component in COMPONENT_TYPES:
            uninstall_component_for_backend(backend, component, scope, copy_mode)

    if scope == "global":
        _uninstall_universal_skills(copy_mode)

    # Remove SessionStart hook for Claude Code only
    try:
        claude_backend = registry.get("claude")
        _uninstall_session_hook(claude_backend, scope)
    except KeyError:
        pass


def _uninstall_universal_skills(copy_mode: bool = False) -> None:

    target = config.AGENTS_HOME / "skills"
    if target.exists() and any(target.iterdir()):
        print(f"Removing universal skills from {target} ...")
        remove_all_symlinks_in_dir(target, copy_mode)
        remove_dir_if_empty(target)


def _session_hook_paths(backend, scope: str):
    """Return (settings_path, context_file, hook_command) for the given scope."""
    home = backend.global_home if scope == "global" else Path(backend.local_dir)
    if scope == "global":
        settings_path = home / "settings.json"
        context_file = home / "agent-notes-context.md"
        hook_command = "cat ~/.claude/agent-notes-context.md 2>/dev/null || true"
    else:
        settings_path = home / "settings.json"
        context_file = home / "agent-notes-context.md"
        hook_command = "cat .claude/agent-notes-context.md 2>/dev/null || true"
    return settings_path, context_file, hook_command


def _install_session_hook(backend, scope: str) -> None:
    """Install the SessionStart hook and write the context file for Claude Code."""
    from .settings_writer import install_hook, install_allow_entry, remove_allow_entry
    from .session_context import write_context
    from .. import config

    settings_path, context_file, hook_command = _session_hook_paths(backend, scope)

    # Gather installed agent names from dist directory
    agents: list[str] = []
    agents_dist = config.DIST_DIR / backend.name / backend.layout.get("agents", "agents")
    if agents_dist.exists():
        agents = sorted(p.stem for p in agents_dist.glob("*.md"))

    version = config.get_version()
    print(f"Installing Claude Code SessionStart hook ...")
    write_context(context_file, agents, version)
    install_hook(settings_path, "SessionStart", hook_command)
    # Remove old standalone entry if present (backward compat cleanup)
    remove_allow_entry(settings_path, "Bash(cost-report)")
    install_allow_entry(settings_path, "Bash(agent-notes cost-report)")


def _uninstall_session_hook(backend, scope: str) -> None:
    """Remove the SessionStart hook and context file for Claude Code."""
    from .settings_writer import remove_hook, remove_allow_entry

    settings_path, context_file, hook_command = _session_hook_paths(backend, scope)
    print(f"Removing Claude Code SessionStart hook ...")
    context_file.unlink(missing_ok=True)
    remove_hook(settings_path, "SessionStart", hook_command)
    remove_allow_entry(settings_path, "Bash(cost-report)")
    remove_allow_entry(settings_path, "Bash(agent-notes cost-report)")


