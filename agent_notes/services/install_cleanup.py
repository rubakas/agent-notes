"""Cleanup after a reinstall: remove what the replaced install placed and the new one does not.

    stale = owned(old manifest + marker scan) - new placements - claimed by other installs

Computing the stale set writes nothing; removing it is a separate step so callers
can place first, build the new manifest, and only then remove (spec 007 FR-A07).
Anything doubtful is kept: removal re-checks ownership at the moment it deletes.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Iterator, Optional

from .. import config
from ..domain.state import InstalledItem, ScopeState, State
from . import fs as _fs
from .ui import printable
from .install_ownership import confined, home_is_valid, is_ours, path_key as _key
from .install_plan import _apply_overrides

COMPONENT_DIRS = ("agents", "skills", "rules", "commands")


@dataclass(frozen=True)
class Stale:
    """A path the replaced install owns and the new one drops."""

    path: Path
    recorded: Optional[InstalledItem] = None
    root: Optional[Path] = None   # the install root it was found under: removal re-checks it


@dataclass
class Claims:
    """What the OTHER installs in the snapshot still use, per CLI."""

    paths: dict[str, set[str]] = field(default_factory=dict)   # cli -> dirs and config files
    configs: set[str] = field(default_factory=set)             # every config file any CLI of another install writes
    homes: dict[str, set[str]] = field(default_factory=dict)   # cli -> home dirs
    mirror: set[str] = field(default_factory=set)              # ~/.agents/skills entries
    mirror_all: bool = False                                   # a global install that predates mirror records


def _effective(backend, backend_state, scope: str, project_path: Optional[Path]):
    """The backend with the install's overrides applied, or None when its home may not be
    trusted as a root (an override of "/", of HOME or of a directory above it)."""
    folder = {backend.name: backend_state.local_dir_override} if backend_state.local_dir_override else None
    effective = _apply_overrides(backend, folder, backend_state.global_home_override or None)
    return effective if home_is_valid(_home(effective, scope, project_path), project_path) else None


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
        try:
            if _same_install(scope, project_path, label, o_scope, o_path, o_label):
                continue
            _add_claims(claims, o_scope, o_path, o_state, registry)
        except (OSError, ValueError, TypeError, AttributeError):
            continue  # a malformed entry claims nothing
    return claims


def _add_claims(claims: Claims, o_scope: str, o_path: Optional[Path], o_state: ScopeState, registry) -> None:
    for cli, bs in o_state.clis.items():
        try:
            backend = _effective(registry.get(cli), bs, o_scope, o_path)
        except KeyError:
            continue
        if backend is None:
            continue
        claimed = claims.paths.setdefault(cli, set())
        claimed.update(_key(d) for d in _component_dirs(backend, o_scope, o_path))
        config_file = _config_file(backend, o_scope, o_path)
        if config_file is not None:
            claimed.add(_key(config_file))
            claims.configs.add(_key(config_file))
        claims.homes.setdefault(cli, set()).add(_key(_home(backend, o_scope, o_path)))
    if o_scope == "global":
        # The key is absent only in a manifest that predates mirror records: then everything is claimed
        if any("skills_mirror" in bs.installed for bs in o_state.clis.values()):
            claims.mirror |= {_key(Path(i.target)) for bs in o_state.clis.values()
                              for i in bs.installed.get("skills_mirror", {}).values()}
        else:
            claims.mirror_all = True


def _scan_links(directory: Path) -> Iterator[Path]:
    """Our symlinks directly inside a real directory: a symlinked directory is
    never walked, a user's file or foreign link is never listed."""
    try:
        if directory.is_symlink() or not directory.is_dir():
            return
        entries = sorted(directory.iterdir())
    except OSError:
        return
    for entry in entries:
        if entry.is_symlink() and is_ours(entry):
            yield entry


def _roots(backend, scope: str, project_path: Optional[Path]) -> list[Path]:
    """Where an install's files may be: its component dirs, the shared mirror and its config
    file. Not the CLI home itself (that holds the user's own files); an emptied home is
    removed by prunable_dirs."""
    roots = _component_dirs(backend, scope, project_path)
    if scope == "global":
        roots.append(_mirror_dir())
    config_file = _config_file(backend, scope, project_path)
    if config_file is not None:
        roots.append(config_file)
    return roots


def _root_for(path: Path, backend, scope: str, project_path: Optional[Path]) -> Optional[Path]:
    """The install root *path* is confined to (no symlink in between), if any: a corrupted or
    hand-edited state.json must never steer deletion elsewhere."""
    return next((root for root in _roots(backend, scope, project_path) if confined(path, root)), None)


def _owned(old: ScopeState, scope: str, project_path: Optional[Path], registry) -> dict[str, tuple[str, Stale]]:
    """key -> (cli, Stale): the old manifest's paths that are ours and inside the install's roots,
    plus our links found in the old install's component dirs and config files, so a manifest
    that is incomplete (or predates this cleanup) still gets cleaned."""
    owned: dict[str, tuple[str, Stale]] = {}
    for cli, bs in old.clis.items():
        try:
            backend = _effective(registry.get(cli), bs, scope, project_path)
        except KeyError:
            continue
        if backend is None:
            continue
        for component, items in bs.installed.items():
            if component == "context":
                continue  # removed with its session hook (dropped_hook_backends), not by path
            for item in items.values():
                try:
                    path = Path(item.target)
                    root = _root_for(path, backend, scope, project_path)
                    if root is not None and is_ours(path, item):
                        owned.setdefault(_key(path), (cli, Stale(path, item, root)))
                except (TypeError, ValueError, OSError, AttributeError):
                    continue  # a malformed record names nothing
        for directory in _component_dirs(backend, scope, project_path):
            for link in _scan_links(directory):
                owned.setdefault(_key(link), (cli, Stale(link, None, directory)))
        config_file = _config_file(backend, scope, project_path)
        if config_file is not None and config_file.is_symlink() and is_ours(config_file):
            owned.setdefault(_key(config_file), (cli, Stale(config_file, None, config_file)))
    if scope == "global" and old.clis:
        for link in _scan_links(_mirror_dir()):
            owned.setdefault(_key(link), ("", Stale(link, None, _mirror_dir())))
    return owned


def is_claimed(path: Path, cli: str, claims: Claims) -> bool:
    """True when another install still uses *path* (a CLI's dir or config file, or a mirror entry)."""
    if _key(path.parent) == _key(_mirror_dir()):
        return claims.mirror_all or _key(path) in claims.mirror
    claimed = claims.paths.get(cli, set())
    return _key(path.parent) in claimed or _key(path) in claimed or _key(path) in claims.configs


def stale_placements(old: Optional[ScopeState], scope: str, project_path: Optional[Path],
                     new_targets: Iterable[Path], claims: Claims, registry) -> list[Stale]:
    """The paths to remove. Reads the disk, writes nothing."""
    if old is None:
        return []
    kept = {_key(Path(t)) for t in new_targets}
    return [stale for key, (cli, stale) in sorted(_owned(old, scope, project_path, registry).items())
            if key not in kept and not is_claimed(stale.path, cli, claims)]


def planned_stale(snapshot: Optional[State], scope: str, project_path: Optional[Path], label: str,
                  new_targets: Iterable[Path], registry) -> list[Stale]:
    """What an install about to place *new_targets* would remove, for a preview."""
    from .state_store import get_scope
    old = get_scope(snapshot, scope, project_path, profile_label=label) if snapshot else None
    claims = claims_of_others(snapshot, scope, project_path, label, registry)
    return stale_placements(old, scope, project_path, new_targets, claims, registry)


def prunable_dirs(old: Optional[ScopeState], scope: str, project_path: Optional[Path], registry) -> list[Path]:
    """The directories cleanup may remove once they are empty: a CLI's component dirs and its
    own home (~/.codex/agents, ~/.codex), never a project folder and never HOME."""
    if old is None:
        return []
    dirs: list[Path] = []
    for cli, bs in old.clis.items():
        try:
            backend = _effective(registry.get(cli), bs, scope, project_path)
        except KeyError:
            continue
        if backend is not None:
            dirs += [*_component_dirs(backend, scope, project_path), _home(backend, scope, project_path)]
    return list(dict.fromkeys(dirs))


def prune_empty(directories: Iterable[Path]) -> None:
    """Remove the given directories that are empty, deepest first."""
    for directory in sorted(set(directories), key=lambda d: len(d.parts), reverse=True):
        _fs.remove_dir_if_empty(directory)


def remove_stale(stale: Iterable[Stale], prune: Iterable[Path] = ()) -> list[Path]:
    """Delete what is still ours and still inside its root at this moment: a link, or a copy
    that has not been edited. Then remove the *prune* directories that ended up empty."""
    removed: list[Path] = []
    for item in stale:
        path = item.path
        if item.root is None or not confined(path, item.root) or not is_ours(path, item.recorded):
            continue
        try:
            if path.is_symlink() or path.is_file():
                path.unlink()
            else:
                shutil.rmtree(path)
        except OSError as e:
            print(f"Could not remove {printable(path)}: {printable(e)}")
            continue
        _fs._removed(str(path))
        removed.append(path)
    if removed:
        prune_empty(prune)
    return removed


def deletion_guard(state: Optional[State], registry, cwd: Path) -> Callable[[Path], bool]:
    """A predicate for tools that delete on their own findings (doctor --fix): a path is
    deletable only if it is ours (a link into a real dist, or a copy still matching its
    manifest record) AND inside the roots of an install or of a registered CLI's default dirs."""
    records: dict[str, list[InstalledItem]] = {}
    roots: list[Path] = []
    if state is not None:
        for o_scope, o_path, _label, o_state in _installs(state):
            for cli, bs in o_state.clis.items():
                try:
                    backend = _effective(registry.get(cli), bs, o_scope, o_path)
                    if backend is None:
                        continue
                    roots += _roots(backend, o_scope, o_path)
                    for items in bs.installed.values():
                        for item in items.values():
                            records.setdefault(_key(Path(item.target)), []).append(item)
                except (KeyError, TypeError, ValueError, OSError, AttributeError):
                    continue
    for backend in registry.all():
        roots += _roots(backend, "global", None) + _roots(backend, "local", cwd)

    def deletable(path: Path) -> bool:
        return (any(is_ours(path, record) for record in records.get(_key(path), [None]))
                and any(confined(path, root) for root in roots))

    return deletable


def home_claimed(backend, scope: str, project_path: Optional[Path], claims: Claims) -> bool:
    """True when another install lists this CLI under the same home: the hook there is theirs too."""
    return _key(_home(backend, scope, project_path)) in claims.homes.get(backend.name, set())


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
            backend = _effective(registry.get(cli), bs, scope, project_path)
        except KeyError:
            continue
        if backend is None or not backend.supports("session_hook"):
            continue
        if home_claimed(backend, scope, project_path, claims):
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
