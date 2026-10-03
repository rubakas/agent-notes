"""Cleanup after a reinstall: remove what the replaced install placed and the new one does not.

    stale = owned(old manifest + marker scan) - new placements - claimed by other installs

Computing the stale set writes nothing; removing it is a separate step so callers
can place first, build the new manifest, and only then remove (spec 007 FR-A07).
Anything doubtful is kept: removal re-checks ownership at the moment it deletes.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Iterator, Optional

from .. import config
from ..domain.state import InstalledItem, ScopeState, State
from . import fs as _fs
from .install_ownership import is_ours
from .install_plan import _apply_overrides

COMPONENT_DIRS = ("agents", "skills", "rules", "commands")


@dataclass(frozen=True)
class Stale:
    """A path the replaced install owns and the new one drops."""

    path: Path
    recorded: Optional[InstalledItem] = None


@dataclass
class Claims:
    """What the OTHER installs in the snapshot still use, per CLI."""

    paths: dict[str, set[str]] = field(default_factory=dict)   # cli -> dirs and config files
    homes: dict[str, set[str]] = field(default_factory=dict)   # cli -> home dirs
    mirror: set[str] = field(default_factory=set)              # ~/.agents/skills entries
    mirror_all: bool = False                                   # a global install that predates mirror records


def _key(path: Path) -> str:
    """A comparable form of *path*: absolute, normalised, the parent directory
    resolved (so a symlinked HOME matches) and the leaf left alone."""
    absolute = os.path.abspath(path)
    return os.path.join(os.path.realpath(os.path.dirname(absolute)), os.path.basename(absolute))


def _effective(backend, backend_state):
    folder = {backend.name: backend_state.local_dir_override} if backend_state.local_dir_override else None
    return _apply_overrides(backend, folder, backend_state.global_home_override or None)


def _home(backend, scope: str, project_path: Optional[Path]) -> Path:
    return backend.global_home if scope == "global" else Path(project_path) / backend.local_dir


def _component_dirs(backend, scope: str, project_path: Optional[Path]) -> list[Path]:
    home = _home(backend, scope, project_path)
    return [home / backend.layout[c].rstrip("/") for c in COMPONENT_DIRS
            if backend.supports(c) and backend.layout.get(c)]


def _config_file(backend, scope: str, project_path: Optional[Path]) -> Optional[Path]:
    name = backend.layout.get("config")
    if not name:
        return None
    return (_home(backend, scope, project_path) if scope == "global" else Path(project_path)) / name


def _mirror_dir() -> Path:
    return config.AGENTS_HOME / "skills"


def manifest_targets(scope_state: Optional[ScopeState]) -> set[Path]:
    """Every path a manifest lists."""
    if scope_state is None:
        return set()
    return {Path(item.target) for bs in scope_state.clis.values()
            for items in bs.installed.values() for item in items.values()}


def _installs(state: State) -> Iterator[tuple[str, Optional[Path], str, ScopeState]]:
    if state.global_install is not None:
        yield "global", None, "", state.global_install
    for label, scope_state in state.global_installs.items():
        yield "global", None, label, scope_state
    for key, scope_state in state.local_installs.items():
        label = scope_state.profile_label
        path = key[:-len(label) - 1] if label and key.endswith("#" + label) else key
        yield "local", Path(path), label, scope_state


def _same_install(scope, project_path, label, other_scope, other_path, other_label) -> bool:
    if (scope, label) != (other_scope, other_label):
        return False
    return scope == "global" or Path(project_path).resolve() == Path(other_path).resolve()


def claims_of_others(snapshot: Optional[State], scope: str, project_path: Optional[Path],
                     label: str, registry) -> Claims:
    """The dirs, config files, homes and mirror entries every other install lists."""
    claims = Claims()
    if snapshot is None:
        return claims
    for o_scope, o_path, o_label, o_state in _installs(snapshot):
        if _same_install(scope, project_path, label, o_scope, o_path, o_label):
            continue
        for cli, bs in o_state.clis.items():
            try:
                backend = _effective(registry.get(cli), bs)
            except KeyError:
                continue
            claimed = claims.paths.setdefault(cli, set())
            claimed.update(_key(d) for d in _component_dirs(backend, o_scope, o_path))
            config_file = _config_file(backend, o_scope, o_path)
            if config_file is not None:
                claimed.add(_key(config_file))
            claims.homes.setdefault(cli, set()).add(_key(_home(backend, o_scope, o_path)))
        if o_scope == "global":
            entries = {_key(Path(i.target)) for bs in o_state.clis.values()
                       for i in bs.installed.get("skills_mirror", {}).values()}
            if entries:
                claims.mirror |= entries
            else:
                claims.mirror_all = True
    return claims


def _scan_links(directory: Path) -> Iterator[Path]:
    """Our symlinks directly inside a real directory: a symlinked directory is
    never walked, a user's file or foreign link is never listed."""
    if directory.is_symlink() or not directory.is_dir():
        return
    for entry in sorted(directory.iterdir()):
        if entry.is_symlink() and is_ours(entry):
            yield entry


def _owned(old: ScopeState, scope: str, project_path: Optional[Path], registry) -> dict[str, tuple[str, Stale]]:
    """key -> (cli, Stale): the old manifest's paths that are ours, plus our
    links found in the old install's component dirs and config files, so a
    manifest that is incomplete (or predates this cleanup) still gets cleaned."""
    owned: dict[str, tuple[str, Stale]] = {}
    for cli, bs in old.clis.items():
        for component, items in bs.installed.items():
            if component == "context":
                continue  # removed with its session hook (dropped_hook_backends), not by path
            for item in items.values():
                path = Path(item.target)
                if is_ours(path, item):
                    owned.setdefault(_key(path), (cli, Stale(path, item)))
        try:
            backend = _effective(registry.get(cli), bs)
        except KeyError:
            continue
        found = [link for d in _component_dirs(backend, scope, project_path) for link in _scan_links(d)]
        config_file = _config_file(backend, scope, project_path)
        if config_file is not None and config_file.is_symlink() and is_ours(config_file):
            found.append(config_file)
        for link in found:
            owned.setdefault(_key(link), (cli, Stale(link)))
    if scope == "global" and old.clis:
        for link in _scan_links(_mirror_dir()):
            owned.setdefault(_key(link), ("", Stale(link)))
    return owned


def _claimed(path: Path, cli: str, claims: Claims) -> bool:
    if _key(path.parent) == _key(_mirror_dir()):
        return claims.mirror_all or _key(path) in claims.mirror
    claimed = claims.paths.get(cli, set())
    return _key(path.parent) in claimed or _key(path) in claimed


def stale_placements(old: Optional[ScopeState], scope: str, project_path: Optional[Path],
                     new_targets: Iterable[Path], claims: Claims, registry) -> list[Stale]:
    """The paths to remove. Reads the disk, writes nothing."""
    if old is None:
        return []
    kept = {_key(Path(t)) for t in new_targets}
    return [stale for key, (cli, stale) in sorted(_owned(old, scope, project_path, registry).items())
            if key not in kept and not _claimed(stale.path, cli, claims)]


def remove_stale(stale: Iterable[Stale]) -> list[Path]:
    """Delete what is still ours at this moment: a link, or a copy that has not been edited."""
    removed: list[Path] = []
    for item in stale:
        path = item.path
        if not is_ours(path, item.recorded):
            continue
        try:
            if path.is_symlink() or path.is_file():
                path.unlink()
            else:
                shutil.rmtree(path)
        except OSError as e:
            print(f"Could not remove {path}: {e}")
            continue
        _fs._removed(str(path))
        removed.append(path)
    for parent in sorted({p.parent for p in removed}):
        _fs.remove_dir_if_empty(parent)
    return removed


def dropped_hook_backends(old: Optional[ScopeState], new_clis: Iterable[str], scope: str,
                          project_path: Optional[Path], claims: Claims, registry) -> list:
    """The CLIs the new install no longer covers whose session hook (and context
    file) is ours to remove: not when another install still uses the same home."""
    if old is None:
        return []
    kept = set(new_clis)
    dropped = []
    for cli, bs in old.clis.items():
        if cli in kept:
            continue
        try:
            backend = _effective(registry.get(cli), bs)
        except KeyError:
            continue
        if not backend.supports("session_hook"):
            continue
        if _key(_home(backend, scope, project_path)) in claims.homes.get(cli, set()):
            continue
        if scope == "local":
            backend = backend.with_local_dir(str(_home(backend, scope, project_path)))
        dropped.append(backend)
    return dropped


def remove_dropped_hooks(backends: Iterable, scope: str) -> None:
    from . import installer
    for backend in backends:
        if _fs.silent_file_ops:
            with _fs.quiet_output():
                installer._uninstall_session_hook(backend, scope)
        else:
            installer._uninstall_session_hook(backend, scope)
