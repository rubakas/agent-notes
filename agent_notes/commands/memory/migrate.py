"""Migration subcommand: migrate."""

import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from . import _common
from ...config import Color


def do_migrate() -> None:
    """Migrate vault from per-project layout to flat shared layout with new filenames."""
    backend, vault = _common._load_memory_config()
    if backend != "obsidian":
        print("migrate is only available for obsidian storage.")
        return
    if vault is None:
        print("Memory path not configured.")
        return

    from ...services.obsidian_backend import (
        OBSIDIAN_CATEGORIES, obsidian_regenerate_index,
    )
    from ...services._memory_utils import _parse_frontmatter

    _NEW_FILE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}_")
    _LEGACY_TS_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})-(\d{2})-(\d{2})-(\d{2})-(.+)$")
    _BARE_UUID_RE = re.compile(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
    )

    moved = 0
    renamed = 0
    skipped = 0
    errors: list[str] = []

    def _date_from_frontmatter(path: Path) -> Optional[str]:
        try:
            text = path.read_text()
            fm, _ = _parse_frontmatter(text)
            ca = fm.get("created_at", "")
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", ca):
                return ca[:10]
        except OSError:
            pass
        return None

    def _date_from_mtime(path: Path) -> str:
        ts = path.stat().st_mtime
        return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")

    def _safe_rename(src: Path, dst: Path) -> bool:
        if dst.exists():
            return False
        src.rename(dst)
        return True

    def _new_stem(old_stem: str, folder: Path, path: Path) -> Optional[str]:
        """Return new stem under new naming scheme, or None if already correct."""
        if _NEW_FILE_RE.match(old_stem):
            return None  # already in new format

        # Legacy timestamp: YYYY-MM-DD-HH-MM-SS-<slug>
        m = _LEGACY_TS_RE.match(old_stem)
        if m:
            date_part = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
            slug_part = m.group(7)
            base = f"{date_part}_{slug_part}"
            candidate = f"{base}.md"
            if not (folder / candidate).exists():
                return base
            # collision: append HHMMSS from the original timestamp
            hhmmss = f"{m.group(4)}{m.group(5)}{m.group(6)}"
            return f"{base}_{hhmmss}"

        # Bare session UUID: <uuid>.md → <date>_<uuid>.md
        if _BARE_UUID_RE.match(old_stem):
            date_part = _date_from_frontmatter(path) or _date_from_mtime(path)
            base = f"{date_part}_{old_stem}"
            candidate = f"{base}.md"
            if not (folder / candidate).exists():
                return base
            hhmmss = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).strftime("%H%M%S")
            return f"{base}_{hhmmss}"

        # Unrecognized pattern — skip
        return None

    # Step 1: move files from per-project subfolders into the shared root
    for item in list(vault.iterdir()):
        if not item.is_dir():
            continue
        if item.name in OBSIDIAN_CATEGORIES or item.name == "Index.md":
            continue
        # item is a per-project subfolder
        for cat in OBSIDIAN_CATEGORIES:
            src_cat = item / cat
            if not src_cat.exists():
                continue
            dst_cat = vault / cat
            dst_cat.mkdir(exist_ok=True)
            for note in src_cat.glob("*.md"):
                dst = dst_cat / note.name
                if dst.exists():
                    errors.append(f"collision: {note} -> {dst}")
                    continue
                try:
                    shutil.move(str(note), str(dst))
                    moved += 1
                except OSError as exc:
                    errors.append(f"move failed: {note}: {exc}")
            # Remove now-empty category subdir so parent rmdir can succeed
            try:
                src_cat.rmdir()
            except OSError:
                pass
        # Remove subfolder only if empty (preserves any uncategorized files the user may have there)
        try:
            item.rmdir()
        except OSError:
            errors.append(f"per-project subfolder not removed (non-empty): {item}")

    # Step 2: rename files in each category to the new naming scheme
    for cat in OBSIDIAN_CATEGORIES:
        cat_dir = vault / cat
        if not cat_dir.exists():
            continue
        for note in list(cat_dir.glob("*.md")):
            new_stem = _new_stem(note.stem, cat_dir, note)
            if new_stem is None:
                skipped += 1
                continue
            dst = cat_dir / f"{new_stem}.md"
            try:
                if not _safe_rename(note, dst):
                    errors.append(f"rename collision: {note.name} -> {dst.name}")
                    skipped += 1
                else:
                    renamed += 1
            except OSError as exc:
                errors.append(f"rename failed: {note}: {exc}")
                skipped += 1

    # Step 3: regenerate index
    obsidian_regenerate_index(vault)

    print(f"{moved} moved, {renamed} renamed, {skipped} skipped", end="")
    if errors:
        print(f", errors: {'; '.join(errors)}")
    else:
        print()
