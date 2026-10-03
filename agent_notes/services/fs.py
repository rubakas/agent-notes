"""Filesystem primitives."""

import io
import os
import shutil
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from . import install_ownership as _ownership
from .ui import Color as _Color, printable as _printable

# Set to True to suppress per-file LINKED/COPIED/SKIP output (e.g. during wizard)
silent_file_ops = False


@contextmanager
def silent_ops():
    """Context manager that suppresses per-file output for the duration of the block.

    Saves and restores the previous value of silent_file_ops so nesting is safe.
    """
    global silent_file_ops
    previous = silent_file_ops
    silent_file_ops = True
    try:
        yield
    finally:
        silent_file_ops = previous


@contextmanager
def quiet_output():
    """Discard everything printed to stdout and stderr in the block — keeps
    build, restore and regenerate output off a full-screen view (FR-024)."""
    sink = io.StringIO()
    with redirect_stdout(sink), redirect_stderr(sink):
        yield


def _info(msg: str) -> None:
    if not silent_file_ops:
        print(f"  {_Color.GREEN}✓{_Color.NC} {_printable(msg)}")


def _skipped(path: str, reason: str = "not a symlink — remove manually") -> None:
    if not silent_file_ops:
        print(f"  {_Color.YELLOW}SKIP{_Color.NC}     {_printable(path)} ({reason})")


def _linked(path: str) -> None:
    if not silent_file_ops:
        print(f"  {_Color.GREEN}LINKED{_Color.NC}  {_printable(path)}")


def _backed_up(path: str) -> None:
    if not silent_file_ops:
        print(f"  {_Color.CYAN}BACKUP{_Color.NC}   {_printable(path)}")


def _removed(path: str) -> None:
    if not silent_file_ops:
        print(f"  {_Color.GREEN}REMOVED{_Color.NC}  {_printable(path)}")


def files_identical(a: Path, b: Path) -> bool:
    """Check if two files or directories have identical content."""
    try:
        if a.is_dir() and b.is_dir():
            # Compare directory contents recursively
            a_files = {f.relative_to(a): f.read_bytes() for f in a.rglob("*") if f.is_file()}
            b_files = {f.relative_to(b): f.read_bytes() for f in b.rglob("*") if f.is_file()}
            return a_files == b_files
        elif a.is_file() and b.is_file():
            return a.read_bytes() == b.read_bytes()
        return False
    except OSError:
        return False


def _timestamped_backup_path(dst: Path) -> Path:
    """Return a timestamped backup path for dst, e.g. CLAUDE.md.bak.20260430T022500123456Z."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return Path(str(dst) + f".bak.{ts}")


def _move_aside(dst: Path) -> Path:
    """Move *dst* to a fresh timestamped backup name and return it. A directory is copied
    with its symlinks kept as symlinks; the name is claimed exclusively, so an existing
    backup is never overwritten (a numeric suffix is added on a collision)."""
    base = _timestamped_backup_path(dst)
    for attempt in range(1000):
        candidate = base if attempt == 0 else Path(f"{base}.{attempt}")
        try:
            if dst.is_dir() and not dst.is_symlink():
                shutil.copytree(dst, candidate, symlinks=True)
                shutil.rmtree(dst)
            else:
                os.close(os.open(candidate, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600))
                os.replace(dst, candidate)
            return candidate
        except FileExistsError:
            continue
    raise FileExistsError(f"no free backup name for {dst}")


def backup_copy(path: Path) -> Path:
    """Copy *path* (a file) next to itself under a fresh backup name, never overwriting one."""
    base = _timestamped_backup_path(path)
    for attempt in range(1000):
        candidate = base if attempt == 0 else Path(f"{base}.{attempt}")
        try:
            os.close(os.open(candidate, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600))
        except FileExistsError:
            continue
        shutil.copy2(path, candidate)
        return candidate
    raise FileExistsError(f"no free backup name for {path}")


def _owned_copy(dst: Path) -> bool:
    """A real file or directory the replaced install placed and nobody has edited since."""
    return not dst.is_symlink() and _ownership.owned(dst)


def handle_existing(src: Path, dst: Path, copy_mode: bool = True) -> bool:
    """Handle an existing non-symlink destination file.

    Our own unedited copy (the old manifest's record still matches it) is replaced with
    no backup; anything else that differs is backed up under a timestamped name.
    Returns True if install should proceed, False to skip (identical content, which a
    link install does not skip when the copy is ours: the mode would stay "copy").
    """
    owned = _owned_copy(dst)
    if files_identical(src, dst) and (copy_mode or not owned):
        _skipped(str(dst), "exists, identical content")
        return False

    if owned:
        if dst.is_dir():
            shutil.rmtree(dst)
        else:
            dst.unlink()
        return True

    _backed_up(str(_move_aside(dst)))
    return True


def _clear_symlink(src: Path, dst: Path) -> None:
    """Make room for src at a symlink dst: ours (or already pointing at src) is
    unlinked, anyone else's is renamed to a backup so it can be restored."""
    if _ownership.owned(dst) or _ownership.lexical_target(dst) == Path(os.path.normpath(src)):
        dst.unlink()
        return
    _backed_up(str(_move_aside(dst)))


def place_file(src: Path, dst: Path, copy_mode: bool = False) -> None:
    """Place file as symlink or copy, handling existing files."""
    dst.parent.mkdir(parents=True, exist_ok=True)

    if dst.exists() and not dst.is_symlink():
        if not handle_existing(src, dst, copy_mode):
            return
    if dst.is_symlink():
        _clear_symlink(src, dst)

    if copy_mode:
        if src.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dst)
        _ownership.note_placed(dst)
        _info(f"COPIED  {dst}")
    else:
        dst.symlink_to(src)
        _linked(str(dst))


def place_dir_contents(src_dir: Path, dst_dir: Path, pattern: str, copy_mode: bool = False) -> None:
    """Place all files matching pattern from src_dir to dst_dir."""
    dst_dir.mkdir(parents=True, exist_ok=True)
    for src_file in src_dir.glob(pattern):
        if src_file.exists():
            dst_file = dst_dir / src_file.name
            place_file(src_file, dst_file, copy_mode)


def remove_symlink(target: Path, copy_mode: bool = False) -> bool:
    """Remove symlink if it exists. In copy_mode, also removes plain files (managed installs).
    Returns True if something was removed, False otherwise."""
    if target.is_symlink():
        target.unlink()
        _removed(str(target))
        return True
    elif copy_mode and target.exists():
        target.unlink()
        _removed(str(target))
        return True
    elif target.exists():
        _skipped(str(target))
    return False


def remove_dir_if_empty(dir_path: Path) -> None:
    """Remove directory if it exists and is empty."""
    try:
        if dir_path.exists() and not any(dir_path.iterdir()):
            dir_path.rmdir()
    except OSError:
        pass


def resolve_symlink(path: Path) -> Optional[Path]:
    """Get symlink target if path is a symlink."""
    if path.is_symlink():
        try:
            return path.readlink()
        except OSError:
            return None
    return None


def symlink_target_exists(path: Path) -> bool:
    """Check if symlink target exists."""
    if not path.is_symlink():
        return False
    try:
        target = path.readlink()
        # Handle relative targets
        if not target.is_absolute():
            target = path.parent / target
        return target.exists()
    except OSError:
        return False


def files_differ(file1: Path, file2: Path) -> bool:
    """Compare file contents."""
    return not files_identical(file1, file2)