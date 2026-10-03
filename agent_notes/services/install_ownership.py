"""Which paths agent-notes owns: the one predicate behind cleanup, uninstall and doctor.

A symlink is ours when its lexical target lies under an owned root. A copy is ours
only when it is byte-identical to what the install manifest recorded for it.
Anything doubtful is not ours, so callers keep it.
"""

from __future__ import annotations

import hashlib
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Iterator, Optional

from .. import config
from ..domain.state import InstalledItem


def lexical_target(link: Path) -> Path:
    """Where *link* points, without following it: works on dangling links and
    never walks a chain of links."""
    return Path(os.path.normpath(Path(link).parent / os.readlink(link)))


def _lexical_and_real(path: Path) -> tuple[Path, Path]:
    """*path* as written (absolute, normalised) and with its parent directory resolved."""
    absolute = os.path.abspath(path)
    return Path(absolute), Path(os.path.join(os.path.realpath(os.path.dirname(absolute)),
                                             os.path.basename(absolute)))


def under(path: Path, root: Path) -> bool:
    """True when *path* is *root* or inside it: BOTH as written AND with its parent directory
    resolved, so a symlinked directory below the root cannot lead out of it. The root may be
    spelled through a symlink (a symlinked HOME): its resolved form counts too."""
    try:
        lexical, real = _lexical_and_real(path)
        lexical_root, real_root = Path(os.path.abspath(root)), Path(os.path.realpath(root))
    except (OSError, ValueError, TypeError):
        return False
    if lexical == lexical_root:
        return True  # the root itself (a config file may be a symlink: it is not followed)
    return (lexical.is_relative_to(lexical_root) or lexical.is_relative_to(real_root)) \
        and real.is_relative_to(real_root)


def confined(path: Path, root: Path) -> bool:
    """under() but strictly below a directory root, and no symlink anywhere between *root* and *path*'s parent: a manifest path
    that crosses a link is not where the install put it. A raw ".." is refused too: the checks
    here collapse it lexically, but the OS resolves it through a symlinked directory."""
    if ".." in Path(path).parts or not under(path, root):
        return False
    if os.path.abspath(path) == os.path.abspath(root) and os.path.isdir(root):
        return False  # a directory root is never itself the thing to delete (a file root, the config file, is)
    try:
        lexical = Path(os.path.abspath(path))
        base = Path(os.path.abspath(root))
        if not lexical.is_relative_to(base):
            base = Path(os.path.realpath(root))
        parent = lexical.parent
        while parent != base and parent.is_relative_to(base):
            if parent.is_symlink():
                return False
            parent = parent.parent
    except (OSError, ValueError, TypeError):
        return False
    return True


def home_is_valid(path: Path, project_path: Optional[Path] = None) -> bool:
    """A CLI home that may be trusted as a root: never "/", never HOME or a directory above it,
    never the project folder itself. A state.json override that says otherwise is ignored.
    Judged by identity (samefile), so a respelling on a case-insensitive filesystem cannot
    pass; a path that does not exist yet falls back to the lexical comparison."""
    try:
        home = Path(os.path.realpath(Path.home()))
        forbidden = [home, *home.parents]
        if project_path is not None:
            forbidden.append(Path(os.path.realpath(project_path)))
        for candidate in (Path(os.path.abspath(path)), Path(os.path.realpath(path))):
            if candidate == Path(candidate.anchor) or home.is_relative_to(candidate):
                return False
            if project_path is not None and candidate == Path(os.path.realpath(project_path)):
                return False
            if any(_same_file(candidate, other) for other in forbidden):
                return False
    except (OSError, ValueError, TypeError):
        return False
    return True


def _same_file(a: Path, b: Path) -> bool:
    try:
        return os.path.samefile(a, b)
    except OSError:
        return False


def is_legacy_dist(target: Path) -> bool:
    """A target inside the dist of a real agent-notes package: site-packages/…/agent_notes/dist
    (any venv, any Python version), or the dist of the package that is running. A folder that
    merely looks like one (~/work/agent_notes/dist) is the user's."""
    parts = Path(target).parts
    for i, part in enumerate(parts):
        if part == "site-packages" and any(
                a == "agent_notes" and b == "dist" for a, b in zip(parts[i + 1:], parts[i + 2:])):
            return True
    return under(target, config.PKG_DIR / "dist")


def tree_sha(path: Path) -> str:
    """A file by its sha256 (a symlink by its target text); a directory by a sha256 over every
    entry in it: relative path, type, and for files the mode and content sha, for links the
    target text, so an added empty directory, link or changed mode is a change. Anything else
    (a FIFO, a socket, a device) is recorded by type and mode and never opened: reading a
    FIFO blocks forever."""
    path = Path(path)
    if path.is_symlink():
        return hashlib.sha256(f"l\0{os.readlink(path)}".encode()).hexdigest()
    if path.is_file():
        return hashlib.sha256(path.read_bytes()).hexdigest()
    if path.exists() and not path.is_dir():
        return hashlib.sha256(b"o\0").hexdigest()
    digest = hashlib.sha256()
    for entry in sorted(path.rglob("*")):
        rel = entry.relative_to(path).as_posix()
        if entry.is_symlink():
            line = f"{rel}\0l\0{os.readlink(entry)}"
        elif entry.is_dir():
            line = f"{rel}\0d\0{entry.stat().st_mode & 0o7777:o}"
        elif not entry.is_file():
            line = f"{rel}\0o\0{entry.stat().st_mode & 0o7777:o}"
        else:
            line = f"{rel}\0f\0{entry.stat().st_mode & 0o7777:o}\0{hashlib.sha256(entry.read_bytes()).hexdigest()}"
        digest.update(line.encode() + b"\n")
    return digest.hexdigest()


def is_ours(path: Path, recorded: Optional[InstalledItem] = None) -> bool:
    """*recorded* is the old manifest's InstalledItem for this target, if any. Anything that
    cannot be judged (an unreadable path, a malformed record) is not ours."""
    try:
        path = Path(path)
        if path.is_symlink():
            target = lexical_target(path)
            return under(target, config.DIST_DIR) or is_legacy_dist(target)
        if path.exists() and recorded is not None:
            return recorded.sha == tree_sha(path)
    except (OSError, ValueError, TypeError):
        return False
    return False


def path_key(path: Path) -> str:
    """A comparable form of *path*: absolute, normalised, the parent directory
    resolved (so a symlinked HOME matches) and the leaf left alone."""
    try:
        absolute = os.path.abspath(path)
        return os.path.join(os.path.realpath(os.path.dirname(absolute)), os.path.basename(absolute))
    except (OSError, ValueError, TypeError):
        return f"\0unusable:{path!r}"


# The install run in progress: what the replaced (or uninstalled) install recorded, and who
# else claims a path. Set once around a run so fs and the executors need no extra parameters.
_records: dict[str, list[InstalledItem]] = {}
_placed: Optional[dict[str, str]] = None   # copies this run wrote: path key -> tree sha then
_claimed: Optional[Callable[[Path, str], bool]] = None


@contextmanager
def replacing(scope_state, claimed: Optional[Callable[[Path, str], bool]] = None) -> Iterator[None]:
    """Judge ownership against *scope_state*'s manifest for the duration of the block.
    *claimed(path, cli)* says whether another install still uses a path."""
    global _records, _placed, _claimed
    previous = _records, _placed, _claimed
    _records, _placed = {}, {}
    for bs in (scope_state.clis.values() if scope_state else ()):
        for items in bs.installed.values():
            for item in items.values():
                # several CLIs can share a target (a project's AGENTS.md): any record may match
                try:
                    _records.setdefault(path_key(Path(item.target)), []).append(item)
                except (TypeError, ValueError):
                    continue  # a malformed record names nothing
    _claimed = claimed
    try:
        yield
    finally:
        _records, _placed, _claimed = previous


def note_placed(path: Path) -> None:
    """A copy this run just wrote is ours: a later CLI may share the target (AGENTS.md)."""
    if _placed is not None:
        try:
            _placed[path_key(Path(path))] = tree_sha(path)
        except OSError:
            pass


def owned(path: Path) -> bool:
    """is_ours against the manifest of the run in progress, and the copies it has written."""
    key = path_key(Path(path))
    if any(is_ours(path, item) for item in _records.get(key, [None])):
        return True
    placed = (_placed or {}).get(key)
    try:
        return placed is not None and not Path(path).is_symlink() and Path(path).exists() \
            and placed == tree_sha(path)
    except (OSError, ValueError, TypeError):
        return False


def claimed_by_others(path: Path, cli: str) -> bool:
    return _claimed is not None and _claimed(path, cli)
