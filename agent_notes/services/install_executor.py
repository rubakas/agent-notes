"""Install executor: pure worker functions that place/remove files.

This module owns the single-component and universal-skills helpers that do
actual file I/O but have no top-level state or registry dependencies.
Functions that need load_state / load_registry (install_all, uninstall_all,
_install_session_hook, _uninstall_session_hook) live in installer.py so that
the tests' patch("agent_notes.services.installer.load_state") targets work.
"""

from __future__ import annotations

from pathlib import Path

from ..domain.cli_backend import CLIBackend
from .fs import (
    place_file, place_dir_contents,
    remove_symlink, remove_all_symlinks_in_dir, remove_dir_if_empty,
)
from .. import config
from .install_plan import (
    _agent_glob,
    dist_source_for,
    target_dir_for,
    config_filename_for,
)


# ---------------------------------------------------------------------------
# Single-component install / uninstall
# ---------------------------------------------------------------------------

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
        # Directory of agent/rule/command files — flat copy
        # Only print if there are files to install
        glob = _agent_glob(backend) if component == "agents" else "*.md"
        files = list(src.glob(glob))
        if not files:
            return
        print(f"Installing {backend.label} {component} to {dst} ...")
        place_dir_contents(src, dst, glob, copy_mode)
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
) -> int:
    """Uninstall one component for one backend. Returns count of files removed."""
    dst = target_dir_for(backend, component, scope)
    if dst is None or not dst.exists():
        return 0

    if component == "config":
        filename = config_filename_for(backend)
        if filename:
            config_file = dst / filename
            removed = remove_symlink(config_file, copy_mode)
            return 1 if removed else 0
        return 0
    else:
        count = remove_all_symlinks_in_dir(dst, copy_mode)
        remove_dir_if_empty(dst)
        return count


# ---------------------------------------------------------------------------
# Universal skills helpers
# ---------------------------------------------------------------------------

def _install_universal_skills(copy_mode: bool, registry) -> None:
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


def _uninstall_universal_skills(copy_mode: bool = False) -> int:
    """Remove universal skills. Returns count of files removed."""
    target = config.AGENTS_HOME / "skills"
    if not target.exists():
        return 0
    count = remove_all_symlinks_in_dir(target, copy_mode)
    remove_dir_if_empty(target)
    return count


# ---------------------------------------------------------------------------
# Skill-filtering helper
# ---------------------------------------------------------------------------

def _filter_skills_by_backend(skills, memory_backend: str):
    result = []
    for skill in skills:
        if skill.requires_memory is None:
            result.append(skill)
        else:
            allowed = {b.strip() for b in skill.requires_memory.split(",")}
            if memory_backend in allowed:
                result.append(skill)
    return result
