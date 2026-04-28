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
    elif backend == "obsidian":
        print(f"Memory backend: obsidian")
        print(f"Vault path:     {path}")
    else:
        print(f"Memory backend: local")
        print(f"Memory path:    {path}")


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


def show_help() -> None:
    """Show memory command help."""
    help_text = """Usage: agent-notes memory [command] [args]

Manage agent memory.

Commands:
  list             List all agent memories with sizes (default)
  vault            Show current backend and memory path
  index            Regenerate Index.md for the current backend
  add <title> <body>  Add a note (obsidian backend)
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
  agent-notes memory show coder         View coder agent's memory
  agent-notes memory reset reviewer     Clear reviewer's memory
  agent-notes memory export             Back up before cleanup"""

    print(help_text)


def memory(action: str = "list", name: Optional[str] = None, extra: Optional[list] = None) -> None:
    """Manage agent memory."""
    if action == "list":
        do_list()
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
    else:
        print(f"Unknown command: {action}")
        show_help()
        exit(1)
