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
from . import install_ownership as _ownership
from .fs import (
    place_file, place_dir_contents,
    remove_symlink, remove_dir_if_empty,
)
from .. import config
from .ui import printable
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
            print(f"Installing {backend.label} config to {printable(dst)} ...")
        place_file(src_file, dst / filename, copy_mode)
    elif component in ("agents", "rules", "commands"):
        # Directory of agent/rule/command files — flat copy
        # Only print if there are files to install
        glob = _agent_glob(backend) if component == "agents" else "*.md"
        files = list(src.glob(glob))
        if not files:
            return
        if not _fs.silent_file_ops:
            print(f"Installing {backend.label} {component} to {printable(dst)} ...")
        place_dir_contents(src, dst, glob, copy_mode)
    elif component == "skills":
        # Each top-level subdir of src is a skill — install each as a directory
        # Only print if there are skills to install
        skill_dirs = [d for d in src.iterdir() if d.is_dir()]
        if not skill_dirs:
            return
        if not _fs.silent_file_ops:
            print(f"Installing {backend.label} skills to {printable(dst)} ...")
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
            f"Refusing to clean {printable(dst)}: not a real directory "
            f"(symlink or file). Remove it manually if it is no longer needed."
        )
        return False
    try:
        resolved = dst.resolve()
        root_resolved = root.resolve()
    except (OSError, ValueError):
        print(f"Refusing to clean {printable(dst)}: path could not be resolved.")
        return False
    if root_resolved != resolved and root_resolved not in resolved.parents:
        print(
            f"Refusing to clean {printable(dst)}: it resolves to {printable(resolved)}, "
            f"outside {printable(root_resolved)}."
        )
        return False
    return True


def _managed_skill_names() -> set:
    """Names of the skill directories agent-notes ships."""
    dist_skills_dir = config.DIST_SKILLS_DIR
    if not dist_skills_dir.exists():
        return set()
    return {d.name for d in dist_skills_dir.iterdir() if d.is_dir()}


def _is_legacy_skill_ours(item: Path, shipped: Path) -> bool:
    """A skill in the abandoned codex tree is ours when it is a link into our dist, or a
    directory that is still byte-identical to the skill agent-notes ships (or to its manifest
    record). The name alone proves nothing: a user's own copy or link keeps it."""
    try:
        if item.is_symlink():
            return _ownership.is_ours(item)
        return _ownership.owned(item) or (item.is_dir() and shipped.is_dir()
                                         and _ownership.tree_sha(item) == _ownership.tree_sha(shipped))
    except (OSError, ValueError):
        return False


def _remove_managed_skills(dst: Path, copy_mode: bool = True) -> int:
    """Remove the skills in *dst* that are ours; report anything left behind."""
    managed = _managed_skill_names()
    foreign = []
    count = 0
    for item in sorted(dst.iterdir()):
        if item.name not in managed or not _is_legacy_skill_ours(item, config.DIST_SKILLS_DIR / item.name):
            foreign.append(item.name)
            continue
        if item.is_symlink():
            item.unlink()
        else:
            shutil.rmtree(item)
        _fs._removed(str(item))
        count += 1
    if foreign:
        print(
            f"  Left in place under {printable(dst)}: {printable(', '.join(foreign))} "
            f"(not installed by agent-notes)"
        )
    return count


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
        print(f"Removing abandoned {backend.label} skills from {printable(legacy)} ...")
    count = _remove_managed_skills(legacy)
    remove_dir_if_empty(legacy)
    return count


def _remove_owned(dst: Path, cli: str) -> int:
    """Remove the entries of *dst* that are ours and that no other install uses; say what stays.

    A link into our dist, or a copy still byte-identical to what the manifest recorded
    (SKILL.md alone is not proof of a skill directory). Never a user's file, never a
    foreign link."""
    removed, kept = 0, []
    for item in sorted(dst.iterdir()):
        if not _ownership.confined(item, dst) or not _ownership.owned(item) \
                or _ownership.claimed_by_others(item, cli):
            kept.append(item.name)
            continue
        if item.is_symlink() or item.is_file():
            item.unlink()
        else:
            shutil.rmtree(item)
        _fs._removed(str(item))
        removed += 1
    if kept:
        print(f"  Left in place under {printable(dst)}: {printable(', '.join(kept))} (not installed by agent-notes)")
    return removed


def uninstall_component_for_backend(
    backend: CLIBackend,
    component: str,
    scope: str,
    copy_mode: bool = False,
) -> int:
    """Uninstall one component for one backend. Returns count of files removed.

    copy_mode only matters for the abandoned codex skills tree (a dead layout whose copies
    are recognised by name); everything else is judged by ownership."""
    dst = target_dir_for(backend, component, scope)
    if dst is None and component == "skills":
        dst = legacy_skills_dir_for(backend, scope)
        legacy = True
    else:
        legacy = False
    if dst is None or not dst.exists():
        return 0

    if component == "config":
        config_file = dst / config_filename_for(backend) if config_filename_for(backend) else None
        if config_file is None or not _ownership.owned(config_file) \
                or _ownership.claimed_by_others(config_file, backend.name):
            return 0
        return 1 if remove_symlink(config_file, copy_mode=True) else 0

    if not _is_sweepable_dir(dst, backend, scope):
        return 0

    count = _remove_managed_skills(dst, copy_mode) if legacy else _remove_owned(dst, backend.name)
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
    """Remove our entries from the shared ~/.agents/skills mirror. Returns the count removed."""
    target = config.AGENTS_HOME / "skills"
    if not target.is_dir() or target.is_symlink():
        return 0
    count = _remove_owned(target, "")
    remove_dir_if_empty(target)
    return count


# ---------------------------------------------------------------------------
# Skill-filtering helper — implementation lives in memory/install.py;
# re-exported here so existing callers (installer.py, tests) keep working.
# ---------------------------------------------------------------------------

from ..memory.install import filter_skills_by_backend as _filter_skills_by_backend  # noqa: E402
