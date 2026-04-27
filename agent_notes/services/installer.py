"""Generic install/uninstall engine driven by the CLI backend registry."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from ..cli_backend import CLIBackend, CLIRegistry, load_registry
from .. import config
from .fs import (
    place_file, place_dir_contents,
    remove_symlink, remove_all_symlinks_in_dir, remove_dir_if_empty,
)

# Helper to get DIST_DIR - check if the main installer module has a patched version
def _get_dist_dir():
    try:
        import agent_notes.installer as installer_mod
        return getattr(installer_mod, 'DIST_DIR', config.DIST_DIR)
    except (ImportError, AttributeError):
        return config.DIST_DIR

def _get_dist_rules_dir():
    try:
        import agent_notes.installer as installer_mod
        return getattr(installer_mod, 'DIST_RULES_DIR', config.DIST_RULES_DIR)
    except (ImportError, AttributeError):
        return config.DIST_RULES_DIR

def _get_dist_skills_dir():
    try:
        import agent_notes.installer as installer_mod
        return getattr(installer_mod, 'DIST_SKILLS_DIR', config.DIST_SKILLS_DIR)
    except (ImportError, AttributeError):
        return config.DIST_SKILLS_DIR

def _get_agents_home():
    try:
        import agent_notes.installer as installer_mod
        return getattr(installer_mod, 'AGENTS_HOME', config.AGENTS_HOME)
    except (ImportError, AttributeError):
        return config.AGENTS_HOME
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
        p = _get_dist_dir() / backend.name / "agents"
        return p if p.exists() else None
    if component == "config":
        # The config FILE lives directly under DIST_DIR / backend.name / <filename>
        # Caller resolves the filename via backend.layout["config"].
        p = _get_dist_dir() / backend.name
        return p if p.exists() else None
    if component == "rules":
        dist_rules_dir = _get_dist_rules_dir()
        return dist_rules_dir if dist_rules_dir.exists() else None
    if component == "skills":
        dist_skills_dir = _get_dist_skills_dir()
        return dist_skills_dir if dist_skills_dir.exists() else None
    if component == "commands":
        p = _get_dist_dir() / backend.name / "commands"
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
    # Import installer to get potentially-mocked functions
    import agent_notes.installer as installer_mod
    
    src = installer_mod.dist_source_for(backend, component)
    if src is None:
        return
    dst = installer_mod.target_dir_for(backend, component, scope)
    if dst is None:
        return

    if component == "config":
        filename = installer_mod.config_filename_for(backend)
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
    scope: str
) -> None:
    """Uninstall one component for one backend."""
    # Import installer to get potentially-mocked functions
    import agent_notes.installer as installer_mod
    
    dst = installer_mod.target_dir_for(backend, component, scope)
    if dst is None or not dst.exists():
        return
    
    if component == "config":
        filename = installer_mod.config_filename_for(backend)
        if filename:
            config_file = dst / filename
            print(f"Removing {backend.label} config from {dst} ...")
            remove_symlink(config_file)
    else:
        # Only print if directory exists and has content
        if any(dst.iterdir()):
            print(f"Removing {backend.label} {component} from {dst} ...")
        remove_all_symlinks_in_dir(dst)
        remove_dir_if_empty(dst)


def install_all(scope: str, copy_mode: bool, registry: Optional[CLIRegistry] = None) -> None:
    """Top-level: install scripts (global only) + every (backend, component) combo."""
    if registry is None:
        registry = load_registry()
    
    if scope == "global":
        install_scripts_global()
    
    for backend in registry.all():
        for component in COMPONENT_TYPES:
            # Import installer to get the potentially-mocked version
            import agent_notes.installer as installer_mod
            installer_mod.install_component_for_backend(backend, component, scope, copy_mode)
    
    # Universal skills mirror: keep existing behavior — also install skills
    # to ~/.agents/skills/ for any backend that supports skills, only for global scope.
    if scope == "global":
        # Import installer to get the potentially-mocked version
        import agent_notes.installer as installer_mod
        installer_mod._install_universal_skills(copy_mode, registry)

    # SessionStart hook for Claude Code only
    try:
        claude_backend = registry.get("claude")
        _install_session_hook(claude_backend, scope)
    except KeyError:
        pass


def _install_universal_skills(copy_mode: bool, registry: CLIRegistry) -> None:
    """Mirror skills to ~/.agents/skills/ for backwards compatibility."""
    
    dist_skills_dir = _get_dist_skills_dir()
    if not dist_skills_dir.exists():
        return []
    
    config.info(f"Installing universal skills...")
    target = _get_agents_home() / "skills"
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
    
    if scope == "global":
        uninstall_scripts_global()
    
    for backend in registry.all():
        for component in COMPONENT_TYPES:
            # Import installer to get the potentially-mocked version  
            import agent_notes.installer as installer_mod
            installer_mod.uninstall_component_for_backend(backend, component, scope)
    
    if scope == "global":
        # Import installer to get the potentially-mocked version
        import agent_notes.installer as installer_mod
        installer_mod._uninstall_universal_skills()

    # Remove SessionStart hook for Claude Code only
    try:
        claude_backend = registry.get("claude")
        _uninstall_session_hook(claude_backend, scope)
    except KeyError:
        pass


def _uninstall_universal_skills() -> None:
    
    target = _get_agents_home() / "skills"
    if target.exists() and any(target.iterdir()):
        print(f"Removing universal skills from {target} ...")
        remove_all_symlinks_in_dir(target)
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
    from .settings_writer import install_hook
    from .session_context import write_context
    from .. import config

    settings_path, context_file, hook_command = _session_hook_paths(backend, scope)

    # Gather installed agent names from dist directory
    agents: list[str] = []
    agents_dist = _get_dist_dir() / backend.name / backend.layout.get("agents", "agents")
    if agents_dist.exists():
        agents = sorted(p.stem for p in agents_dist.glob("*.md"))

    version = config.get_version()
    print(f"Installing Claude Code SessionStart hook ...")
    write_context(context_file, agents, version)
    install_hook(settings_path, "SessionStart", hook_command)


def _uninstall_session_hook(backend, scope: str) -> None:
    """Remove the SessionStart hook and context file for Claude Code."""
    from .settings_writer import remove_hook

    settings_path, context_file, hook_command = _session_hook_paths(backend, scope)
    print(f"Removing Claude Code SessionStart hook ...")
    context_file.unlink(missing_ok=True)
    remove_hook(settings_path, "SessionStart", hook_command)


def install_scripts_global() -> None:
    """Install scripts to ~/.local/bin/."""
    from .fs import place_file
    
    dist_scripts_dir = _get_dist_dir() / "scripts"
    bin_home = Path.home() / ".local" / "bin"
    
    if not dist_scripts_dir.exists():
        return
    print(f"Installing scripts to {bin_home} ...")
    bin_home.mkdir(parents=True, exist_ok=True)
    for script in sorted(dist_scripts_dir.iterdir()):
        if script.is_file():
            place_file(script, bin_home / script.name)
            (bin_home / script.name).chmod(0o755)


def uninstall_scripts_global() -> None:
    """Uninstall scripts from ~/.local/bin/."""
    from .fs import remove_symlink
    
    dist_scripts_dir = _get_dist_dir() / "scripts"
    bin_home = Path.home() / ".local" / "bin"
    
    if not dist_scripts_dir.exists():
        return
    print(f"Removing scripts from {bin_home} ...")
    for script in sorted(dist_scripts_dir.iterdir()):
        if script.is_file():
            remove_symlink(bin_home / script.name)