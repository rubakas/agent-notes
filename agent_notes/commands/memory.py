"""Manage agent memory stored in ~/.claude/agent-memory/."""

import shutil
from pathlib import Path
from typing import Optional

from ..config import MEMORY_DIR, BACKUP_DIR, Color


def _load_memory_config():
    from ..services.state_store import load_state
    from ..config import memory_dir_for_backend
    state = load_state()
    if state is None:
        return "local", MEMORY_DIR
    backend = state.memory.backend
    path = memory_dir_for_backend(backend, state.memory.path)
    return backend, path


def do_vault() -> None:
    """Show current backend and memory path."""
    backend, path = _load_memory_config()
    if backend == "none":
        print("Memory backend: disabled (none)")
        return
    if backend == "obsidian":
        print(f"Memory backend: obsidian")
        print(f"Vault path:     {path}")
    else:
        print(f"Memory backend: local")
        print(f"Memory path:    {path}")
    initialized = path is not None and path.exists()
    print(f"Initialized:    {'yes' if initialized else 'no — run: agent-notes memory init'}")


def do_init() -> None:
    """Initialize the memory vault — create folder structure and Index.md."""
    backend, path = _load_memory_config()
    if backend == "none":
        print("Memory is disabled. Re-run `agent-notes install` and choose a memory backend.")
        return
    if path is None:
        print("Memory path not configured.")
        return
    if backend == "obsidian":
        from ..services.memory_backend import obsidian_init, OBSIDIAN_CATEGORIES
        obsidian_init(path)
        print(f"{Color.GREEN}Obsidian vault initialised at {path}{Color.NC}")
        print(f"  Folders: {', '.join(OBSIDIAN_CATEGORIES)}")
        print(f"  Index:   {path / 'Index.md'}")
        print(f"\nOpen the folder as a vault in Obsidian to start browsing.")
    else:
        from ..services.memory_backend import local_init
        local_init(path)
        print(f"{Color.GREEN}Memory directory initialised at {path}{Color.NC}")


def do_index() -> None:
    """Regenerate Index.md for the current backend."""
    backend, path = _load_memory_config()
    if backend == "none":
        print("Memory is disabled. Run `agent-notes memory vault` to check configuration.")
        return
    if path is None:
        print("Memory path not configured.")
        return
    if backend == "obsidian":
        from ..services.memory_backend import obsidian_regenerate_index
        obsidian_regenerate_index(path)
        print(f"{Color.GREEN}Index.md regenerated at {path / 'Index.md'}{Color.NC}")
    else:
        from ..services.memory_backend import local_regenerate_index
        local_regenerate_index(path)
        print(f"{Color.GREEN}Index.md regenerated at {path / 'Index.md'}{Color.NC}")


def do_add(title: str, body: str, note_type: str = "context", agent: str = "", project: str = "", tags: Optional[list] = None) -> None:
    """Add a note to memory (obsidian backend only for structured notes)."""
    backend, path = _load_memory_config()
    if backend == "none":
        print("Memory is disabled. Run `agent-notes memory vault` to check configuration.")
        return
    if path is None:
        print("Memory path not configured.")
        return
    if backend == "obsidian":
        from ..services.memory_backend import obsidian_init, obsidian_write_note
        obsidian_init(path)
        note_path = obsidian_write_note(
            path,
            title=title,
            body=body,
            note_type=note_type,
            agent=agent,
            project=project,
            tags=tags or [],
        )
        print(f"{Color.GREEN}Note saved: {note_path}{Color.NC}")
    else:
        print("The `add` subcommand is for the obsidian backend.")
        print("For local backend, write files directly to the agent subdirectory.")


def do_list() -> None:
    """List all agent memories with sizes."""
    backend, path = _load_memory_config()

    if backend == "none":
        print("Memory is disabled. Run `agent-notes memory backend` to enable it.")
        return

    if backend == "obsidian":
        if path is None or not path.exists():
            print(f"Obsidian vault not found at {path}")
            return
        from ..services.memory_backend import obsidian_list_notes
        notes = obsidian_list_notes(path)
        if not notes:
            print(f"No notes found in vault {path}")
            return
        print(f"Obsidian vault ({path}):")
        print("")
        current_cat = None
        for note in notes:
            if note["category"] != current_cat:
                current_cat = note["category"]
                print(f"  {Color.CYAN}{current_cat}{Color.NC}")
            print(f"    {note['file']}")
        return

    # local backend
    if path is None or not path.exists() or not any(path.iterdir()):
        print(f"No agent memories found in {path}")
        return

    print(f"Agent memories ({path}):")
    print("")
    print(f"  {'AGENT':<25} {'SIZE'}")
    print(f"  {'-' * 25} {'-' * 4}")

    for d in path.iterdir():
        if d.is_dir():
            name = d.name
            size = get_directory_size(d)
            size_str = format_size(size)
            print(f"  {name:<25} {size_str}")


def do_size() -> None:
    """Show total memory usage."""
    backend, path = _load_memory_config()

    if backend == "none":
        print("Memory is disabled.")
        return

    if path is None or not path.exists():
        print("No agent memories found.")
        return

    total_size = get_directory_size(path)
    size_str = format_size(total_size)
    print("Total memory usage:")
    print(f"  {size_str}")


def do_show(name: str) -> None:
    """Show memory contents for one agent (local) or category (obsidian)."""
    backend, path = _load_memory_config()

    if backend == "none":
        print("Memory is disabled.")
        return

    if backend == "obsidian":
        if path is None:
            print("Memory path not configured.")
            return
        cat_dir = path / name
        if not cat_dir.exists():
            print(f"Category '{name}' not found in vault {path}")
            return
        print(f"Notes in category '{name}':")
        print("")
        for f in sorted(cat_dir.glob("*.md")):
            print(f"{Color.CYAN}--- {f.name} ---{Color.NC}")
            try:
                print(f.read_text())
            except (UnicodeDecodeError, OSError):
                print("(binary file or read error)")
            print("")
        return

    # local backend
    if path is None:
        path = MEMORY_DIR
    agent_dir = path / name
    if not agent_dir.exists():
        print(f"No memory found for agent '{name}'")
        available = sorted(d.name for d in path.iterdir() if d.is_dir()) if path.exists() else []
        if available:
            print(f"Available: {' '.join(available)}")
        exit(1)

    print(f"Memory for agent '{name}' ({agent_dir}):")
    print("")

    for f in agent_dir.iterdir():
        if f.is_file():
            print(f"{Color.CYAN}--- {f.name} ---{Color.NC}")
            try:
                content = f.read_text()
                print(content)
            except (UnicodeDecodeError, OSError):
                print("(binary file or read error)")
            print("")


def do_reset(name: Optional[str] = None) -> None:
    """Clear agent memory (all or specific agent)."""
    backend, path = _load_memory_config()

    if backend == "none":
        print("Memory is disabled.")
        return

    if path is None:
        path = MEMORY_DIR

    if name:
        agent_dir = path / name
        if not agent_dir.exists():
            print(f"No memory found for agent '{name}'")
            exit(1)

        print(f"{Color.YELLOW}This will delete all memory for agent '{name}'.{Color.NC}")
        confirm = input("Continue? [y/N] ")
        if confirm.lower() == 'y':
            shutil.rmtree(agent_dir)
            print(f"{Color.GREEN}Memory for '{name}' cleared.{Color.NC}")
        else:
            print("Cancelled.")
    else:
        if not path.exists() or not any(path.iterdir()):
            print("No agent memories to clear.")
            return

        print(f"{Color.RED}This will delete ALL agent memories.{Color.NC}")
        print(f"Contents of {path}:")
        for d in path.iterdir():
            if d.is_dir():
                print(f"  {d.name}")
        print("")

        confirm = input("Type 'yes' to confirm: ")
        if confirm == "yes":
            for item in path.iterdir():
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()
            print(f"{Color.GREEN}All agent memories cleared.{Color.NC}")
        else:
            print("Cancelled.")


def do_export() -> None:
    """Copy memories to agent-notes/memory-backup/."""
    backend, path = _load_memory_config()

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
    backend, path = _load_memory_config()

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


def get_directory_size(path: Path) -> int:
    """Calculate total size of directory in bytes."""
    total = 0
    try:
        for item in path.rglob('*'):
            if item.is_file():
                total += item.stat().st_size
    except (OSError, PermissionError):
        pass
    return total


def format_size(size_bytes: int) -> str:
    """Format size in human-readable format."""
    if size_bytes == 0:
        return "0B"

    original_size = size_bytes
    for unit in ['B', 'K', 'M', 'G', 'T']:
        if original_size < 1024:
            if unit == 'B':
                return f"{original_size}B"
            else:
                return f"{original_size:.1f}{unit}"
        original_size /= 1024

    return f"{original_size:.1f}P"


def do_migrate() -> None:
    """Migrate vault from per-project layout to flat shared layout with new filenames."""
    import re
    import shutil
    from datetime import datetime, timezone

    backend, vault = _load_memory_config()
    if backend != "obsidian":
        print("migrate is only available for the obsidian backend.")
        return
    if vault is None:
        print("Memory path not configured.")
        return

    from ..services.memory_backend import (
        OBSIDIAN_CATEGORIES, obsidian_regenerate_index, _parse_frontmatter,
    )

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


def show_help() -> None:
    """Show memory command help."""
    help_text = """Usage: agent-notes memory [command] [args]

Manage agent memory.

Commands:
  init             Create folder structure and Index.md
  list             List all agent memories with sizes (default)
  vault            Show current backend and memory path
  index            Regenerate Index.md for the current backend
  add <title> <body>  Add a note (obsidian backend)
  migrate          Migrate old per-project layout to new shared flat layout
  size             Total disk usage
  show <name>      Show memory contents for one agent/category
  reset            Clear ALL memories (requires confirmation)
  reset <name>     Clear one agent's memory
  export           Back up memories to agent-notes/memory-backup/
  import           Restore from agent-notes/memory-backup/

Examples:
  agent-notes memory                    List all memories
  agent-notes memory vault              Show backend configuration
  agent-notes memory index              Regenerate Index.md
  agent-notes memory migrate            Migrate to new flat layout
  agent-notes memory show coder         View coder agent's memory
  agent-notes memory reset reviewer     Clear reviewer's memory
  agent-notes memory export             Back up before cleanup"""

    print(help_text)


def memory(action: str = "list", name: Optional[str] = None, extra: Optional[list] = None) -> None:
    """Manage agent memory."""
    if action == "list":
        do_list()
    elif action == "init":
        do_init()
    elif action == "vault":
        do_vault()
    elif action == "index":
        do_index()
    elif action == "add":
        # name is title, extra[0] is body
        if not name:
            print("Error: add requires a title.")
            exit(1)
        body = extra[0] if extra else ""
        note_type = extra[1] if extra and len(extra) > 1 else "context"
        agent = extra[2] if extra and len(extra) > 2 else ""
        project = extra[3] if extra and len(extra) > 3 else ""
        do_add(name, body, note_type=note_type, agent=agent, project=project)
    elif action == "size":
        do_size()
    elif action == "show":
        if not name:
            print("Error: show requires an agent name.")
            exit(1)
        do_show(name)
    elif action == "reset":
        do_reset(name)
    elif action == "export":
        do_export()
    elif action == "import":
        do_import()
    elif action == "migrate":
        do_migrate()
    else:
        print(f"Unknown command: {action}")
        show_help()
        exit(1)
