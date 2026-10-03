"""Which paths agent-notes owns: the one predicate behind cleanup, uninstall and doctor.

A symlink is ours when its lexical target lies under an owned root. A copy is ours
only when it is byte-identical to what the install manifest recorded for it.
Anything doubtful is not ours, so callers keep it.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Optional

from .. import config
from ..domain.state import InstalledItem


def lexical_target(link: Path) -> Path:
    """Where *link* points, without following it: works on dangling links and
    never walks a chain of links."""
    return Path(os.path.normpath(Path(link).parent / os.readlink(link)))


def _forms(path: Path, *, resolve_leaf: bool) -> list[Path]:
    """*path* as written and as the filesystem names it, so a root reached through
    a symlinked directory (a symlinked HOME, macOS /tmp) still matches."""
    absolute = os.path.abspath(path)
    real = os.path.realpath(absolute) if resolve_leaf else os.path.join(
        os.path.realpath(os.path.dirname(absolute)), os.path.basename(absolute))
    return [Path(absolute), Path(real)]


def under(path: Path, root: Path) -> bool:
    """True when *path* is *root* or inside it, compared by path parts."""
    roots = _forms(root, resolve_leaf=True)
    return any(candidate.is_relative_to(r)
               for candidate in _forms(path, resolve_leaf=False) for r in roots)


def is_legacy_dist(target: Path) -> bool:
    """A target inside the dist of ANY agent-notes package: an old venv, another
    Python version, an editable checkout. Matches the consecutive pair
    agent_notes/dist, so a sibling like agent_notes/dist-old does not count."""
    parts = Path(target).parts
    return any(a == "agent_notes" and b == "dist" for a, b in zip(parts, parts[1:]))


def tree_sha(path: Path) -> str:
    """A file by its sha256; a directory by a sha256 over the sorted
    (relative path, file sha) pairs of every file in it."""
    path = Path(path)
    if path.is_file():
        return hashlib.sha256(path.read_bytes()).hexdigest()
    digest = hashlib.sha256()
    for file in sorted(p for p in path.rglob("*") if p.is_file()):
        digest.update(f"{file.relative_to(path).as_posix()}\0{tree_sha(file)}\n".encode())
    return digest.hexdigest()


def is_ours(path: Path, recorded: Optional[InstalledItem] = None) -> bool:
    """*recorded* is the old manifest's InstalledItem for this target, if any."""
    path = Path(path)
    if path.is_symlink():
        target = lexical_target(path)
        return under(target, config.DIST_DIR) or is_legacy_dist(target)
    if path.exists() and recorded is not None:
        return recorded.sha == tree_sha(path)
    return False
