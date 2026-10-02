"""`agent-notes config` on the review screen (spec 005 FR-014 – FR-020)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ..services.tui.screen import tilde


@dataclass(frozen=True)
class InstallRef:
    """Where an install lives: enough to find its state and regenerate it."""

    scope: str                      # "global" | "local"
    project_path: Optional[Path]    # local only
    profile_label: str = ""

    @property
    def missing(self) -> bool:
        return self.scope == "local" and not self.project_path.is_dir()

    def label(self) -> str:
        where = "global" if self.scope == "global" else f"local · {tilde(self.project_path)}"
        if self.profile_label:
            where += f" · {self.profile_label}"
        return where + (" (missing)" if self.missing else "")

    def get(self, state):
        from ..services.state_store import get_scope
        return get_scope(state, self.scope, self.project_path, self.profile_label)


def _split_local_key(key: str) -> tuple[Path, str]:
    """A local key is 'path' or 'path#profile' (state_store._local_key). A '#'
    that belongs to an existing folder's name stays part of the path."""
    path, sep, label = key.rpartition("#")
    if not sep or Path(key).is_dir():
        return Path(key), ""
    return Path(path), label


def list_installs(state) -> list[InstallRef]:
    refs = []
    if state.global_install is not None:
        refs.append(InstallRef("global", None))
    refs += [InstallRef("global", None, label) for label in sorted(state.global_installs)]
    for key in sorted(state.local_installs):
        path, label = _split_local_key(key)
        refs.append(InstallRef("local", path, label))
    return refs


def default_install(refs: list[InstallRef], cwd: Path) -> Optional[InstallRef]:
    """The current folder's install, else the global one, else the only one.
    None means ask (spec 005 FR-014). A missing folder is never chosen."""
    cwd = Path(cwd).resolve()
    here = [r for r in refs if r.scope == "local" and r.project_path.resolve() == cwd]
    for candidates in ([r for r in here if not r.profile_label], here,
                       [r for r in refs if r.scope == "global" and not r.profile_label]):
        if candidates:
            return candidates[0]
    if len(refs) == 1 and not refs[0].missing:
        return refs[0]
    return None
