"""Data portability subcommands: export, import."""

import shutil

from . import _common
from ...config import MEMORY_DIR, BACKUP_DIR, Color


def do_export() -> None:
    """Copy memories to agent-notes/memory-backup/."""
    backend, path = _common._load_memory_config()

    if backend == "none":
        print("Memory is disabled.")
        return

    if path is None:
        path = MEMORY_DIR

    if not path.exists() or not any(path.iterdir()):
        print("No agent memories to export.")
        return

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    for item in path.iterdir():
        if item.is_dir():
            dest = BACKUP_DIR / item.name
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(item, dest)
        elif item.is_file():
            shutil.copy2(item, BACKUP_DIR)

    print(f"{Color.GREEN}Exported to {BACKUP_DIR}{Color.NC}")
    print("Contents:")
    for item in BACKUP_DIR.iterdir():
        print(f"  {item.name}")
    print("")
    print(f"{Color.YELLOW}Note: memory-backup/ is in .gitignore — these are personal learnings.{Color.NC}")


def do_import() -> None:
    """Restore from agent-notes/memory-backup/."""
    backend, path = _common._load_memory_config()

    if backend == "none":
        print("Memory is disabled.")
        return

    if path is None:
        path = MEMORY_DIR

    if not BACKUP_DIR.exists() or not any(BACKUP_DIR.iterdir()):
        print(f"No backup found in {BACKUP_DIR}")
        exit(1)

    path.mkdir(parents=True, exist_ok=True)

    for item in BACKUP_DIR.iterdir():
        if item.is_dir():
            dest = path / item.name
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(item, dest)
        elif item.is_file():
            shutil.copy2(item, path)

    print(f"{Color.GREEN}Imported from {BACKUP_DIR} to {path}{Color.NC}")
    print("Restored agents:")
    for item in path.iterdir():
        if item.is_dir():
            print(f"  {item.name}")
