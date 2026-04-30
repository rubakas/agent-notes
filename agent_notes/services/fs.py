"""Filesystem primitives."""

import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


# Local color/print helpers to avoid circular import
class _Color:
    RED = "\033[0;31m"
    GREEN = "\033[0;32m"
    YELLOW = "\033[0;33m"
    BLUE = "\033[0;34m"
    MAGENTA = "\033[0;35m"
    CYAN = "\033[0;36m"
    WHITE = "\033[0;37m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    NC = "\033[0m"  # No color

    @staticmethod
    def disable():
        """Disable colors (for non-TTY output)."""
        for attr in ("RED", "GREEN", "YELLOW", "BLUE", "MAGENTA", "CYAN", "WHITE", "BOLD", "DIM", "NC"):
            setattr(_Color, attr, "")


# Disable colors if not a TTY
if not sys.stdout.isatty():
    _Color.disable()

# Set to True to suppress per-file LINKED/COPIED/SKIP output (e.g. during wizard)
silent_file_ops = False


def _info(msg: str) -> None:
    if not silent_file_ops:
        print(f"  {_Color.GREEN}✓{_Color.NC} {msg}")


def _skipped(path: str, reason: str = "not a symlink — remove manually") -> None:
    if not silent_file_ops:
        print(f"  {_Color.YELLOW}SKIP{_Color.NC}     {path} ({reason})")


def _linked(path: str) -> None:
    if not silent_file_ops:
        print(f"  {_Color.GREEN}LINKED{_Color.NC}  {path}")


def _removed(path: str) -> None:
    print(f"  {_Color.GREEN}REMOVED{_Color.NC}  {path}")


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


def handle_existing(src: Path, dst: Path) -> bool:
    """Handle an existing non-symlink destination file.

    Backs up the destination with a timestamped name and proceeds with install.
    Returns True if install should proceed, False to skip (identical content).
    """
    if files_identical(src, dst):
        _skipped(str(dst), "exists, identical content")
        return False

    backup_path = _timestamped_backup_path(dst)
    if dst.is_dir():
        shutil.copytree(dst, backup_path)
        shutil.rmtree(dst)
    else:
        dst.rename(backup_path)
    print(f"  {_Color.CYAN}BACKUP{_Color.NC}   {backup_path}")
    return True


def place_file(src: Path, dst: Path, copy_mode: bool = False) -> None:
    """Place file as symlink or copy, handling existing files."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    
    if copy_mode:
        if dst.exists() and not dst.is_symlink():
            if not handle_existing(src, dst):
                return
        if dst.is_symlink():
            dst.unlink()
        if src.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dst)
        _info(f"COPIED  {dst}")
    else:
        if dst.exists() and not dst.is_symlink():
            if not handle_existing(src, dst):
                return
        if dst.is_symlink():
            dst.unlink()
        dst.symlink_to(src)
        _linked(str(dst))


def place_dir_contents(src_dir: Path, dst_dir: Path, pattern: str, copy_mode: bool = False) -> None:
    """Place all files matching pattern from src_dir to dst_dir."""
    dst_dir.mkdir(parents=True, exist_ok=True)
    for src_file in src_dir.glob(pattern):
        if src_file.exists():
            dst_file = dst_dir / src_file.name
            place_file(src_file, dst_file, copy_mode)


def remove_symlink(target: Path, copy_mode: bool = False) -> None:
    """Remove symlink if it exists. In copy_mode, also removes plain files (managed installs)."""
    if target.is_symlink():
        target.unlink()
        _removed(str(target))
    elif copy_mode and target.exists():
        target.unlink()
        _removed(str(target))
    elif target.exists():
        _skipped(str(target))


def remove_all_symlinks_in_dir(dir_path: Path, copy_mode: bool = False) -> None:
    """Remove all symlinks in a directory. In copy_mode, also removes plain files (managed installs)."""
    if not dir_path.exists():
        return
    for item in dir_path.iterdir():
        if item.is_symlink():
            item.unlink()
            _removed(str(item))
        elif copy_mode and item.exists():
            if item.is_dir():
                import shutil
                shutil.rmtree(item)
            else:
                item.unlink()
            _removed(str(item))
        elif item.exists():
            _skipped(str(item))


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
    try:
        return file1.read_bytes() != file2.read_bytes()
    except (OSError, FileNotFoundError):
        return True