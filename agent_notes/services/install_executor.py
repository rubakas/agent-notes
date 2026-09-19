"""Install executor: pure worker functions that place/remove files.

This module owns the single-component and universal-skills helpers that do
actual file I/O but have no top-level state or registry dependencies.
Functions that need load_state / load_registry (install_all, uninstall_all,
_install_session_hook, _uninstall_session_hook) live in installer.py so that
the tests' patch("agent_notes.services.installer.load_state") targets work.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from ..domain.cli_backend import CLIBackend
from . import fs as _fs
from .fs import (
    place_file, place_dir_contents,
    remove_symlink, remove_all_symlinks_in_dir, remove_dir_if_empty,
)
from .. import config
from .install_plan import (
    _agent_glob,
    dist_source_for,
    legacy_skills_dir_for,
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
    if component == "skills":
        _sweep_legacy_skills_dir(backend, scope)
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
        if not _fs.silent_file_ops:
            print(f"Installing {backend.label} config to {dst} ...")
        place_file(src_file, dst / filename, copy_mode)
    elif component in ("agents", "rules", "commands"):
        # Directory of agent/rule/command files — flat copy
        # Only print if there are files to install
        glob = _agent_glob(backend) if component == "agents" else "*.md"
        files = list(src.glob(glob))
        if not files:
            return
        if not _fs.silent_file_ops:
            print(f"Installing {backend.label} {component} to {dst} ...")
        place_dir_contents(src, dst, glob, copy_mode)
    elif component == "skills":
        # Each top-level subdir of src is a skill — install each as a directory
        # Only print if there are skills to install
        skill_dirs = [d for d in src.iterdir() if d.is_dir()]
        if not skill_dirs:
            return
        if not _fs.silent_file_ops:
            print(f"Installing {backend.label} skills to {dst} ...")
        for skill_dir in sorted(skill_dirs):
            place_file(skill_dir, dst / skill_dir.name, copy_mode)


def _scope_root_for(backend: CLIBackend, scope: str) -> Path:
    """Return the directory every managed path for (backend, scope) must live under."""
    return backend.global_home if scope == "global" else Path(backend.local_dir)


def _is_sweepable_dir(dst: Path, backend: CLIBackend, scope: str) -> bool:
    """True if *dst* may be swept: a real directory confined to the backend's root.

    A symlinked dst would make the sweep enumerate — and under copy_mode delete —
    the children of whatever the link points at, outside anything agent-notes owns.
    """
    root = _scope_root_for(backend, scope)
    if dst.is_symlink() or not dst.is_dir():
        print(
            f"Refusing to clean {dst}: not a real directory "
            f"(symlink or file). Remove it manually if it is no longer needed."
        )
        return False
    try:
        resolved = dst.resolve()
        root_resolved = root.resolve()
    except OSError:
        print(f"Refusing to clean {dst}: path could not be resolved.")
        return False
    if root_resolved != resolved and root_resolved not in resolved.parents:
        print(
            f"Refusing to clean {dst}: it resolves to {resolved}, "
            f"outside {root_resolved}."
        )
        return False
    return True


def _managed_skill_names() -> set:
    """Names of the skill directories agent-notes ships."""
    dist_skills_dir = config.DIST_SKILLS_DIR
    if not dist_skills_dir.exists():
        return set()
    return {d.name for d in dist_skills_dir.iterdir() if d.is_dir()}


def _remove_managed_skills(dst: Path, copy_mode: bool) -> int:
    """Remove only the skills agent-notes ships; report anything left behind."""
    managed = _managed_skill_names()
    foreign = []
    count = 0
    for item in sorted(dst.iterdir()):
        if item.name not in managed:
            foreign.append(item.name)
            continue
        if _remove_skill_entry(item, copy_mode):
            count += 1
    if foreign:
        print(
            f"  Left in place under {dst}: {', '.join(foreign)} "
            f"(not installed by agent-notes)"
        )
    return count


def _remove_skill_entry(item: Path, copy_mode: bool) -> bool:
    """Remove one installed skill (a symlink, or a whole tree under copy installs)."""
    if not item.is_symlink() and copy_mode and item.is_dir():
        shutil.rmtree(item)
        _fs._removed(str(item))
        return True
    return remove_symlink(item, copy_mode)


def _sweep_legacy_skills_dir(backend: CLIBackend, scope: str) -> int:
    """Clean an abandoned skills tree at install time.

    Uninstall alone is not enough: a user who upgrades and reinstalls never runs
    it, so the dead tree would survive forever. Same guards as the uninstall
    sweep — real confined directory, agent-notes' own skill names only.
    """
    legacy = legacy_skills_dir_for(backend, scope)
    if legacy is None or not legacy.exists():
        return 0
    if target_dir_for(backend, "skills", scope) is not None:
        return 0
    if not _is_sweepable_dir(legacy, backend, scope):
        return 0
    if not _fs.silent_file_ops:
        print(f"Removing abandoned {backend.label} skills from {legacy} ...")
    count = _remove_managed_skills(legacy, copy_mode=True)
    remove_dir_if_empty(legacy)
    return count


def uninstall_component_for_backend(
    backend: CLIBackend,
    component: str,
    scope: str,
    copy_mode: bool = False,
) -> int:
    """Uninstall one component for one backend. Returns count of files removed."""
    dst = target_dir_for(backend, component, scope)
    if dst is None and component == "skills":
        dst = legacy_skills_dir_for(backend, scope)
    if dst is None or not dst.exists():
        return 0

    if component == "config":
        filename = config_filename_for(backend)
        if filename:
            config_file = dst / filename
            removed = remove_symlink(config_file, copy_mode)
            return 1 if removed else 0
        return 0

    if not _is_sweepable_dir(dst, backend, scope):
        return 0

    if component == "skills":
        count = _remove_managed_skills(dst, copy_mode)
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
# Skill-filtering helper — implementation lives in memory/install.py;
# re-exported here so existing callers (installer.py, tests) keep working.
# ---------------------------------------------------------------------------

from ..memory.install import filter_skills_by_backend as _filter_skills_by_backend  # noqa: E402
