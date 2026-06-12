"""Note CRUD subcommands: add, list, show, size."""

from pathlib import Path
from typing import Optional

from . import _common
from ...config import MEMORY_DIR, Color


def do_add(title: str, body: str, note_type: str = "context", agent: str = "", project: str = "", tags: Optional[list] = None, description: str = "") -> None:
    """Add a note to memory (obsidian or wiki storage)."""
    backend, path = _common._load_memory_config()
    if backend == "none":
        print("Memory is disabled. Run `agent-notes memory vault` to check configuration.")
        return
    if path is None:
        print("Memory path not configured.")
        return
    if backend == "wiki":
        from ...services.wiki_backend import wiki_write_page
        page_type = _common._WIKI_TYPE_MAP.get(note_type, "concepts")
        extra_tags = [note_type] if note_type not in ("concept", "entity", "synthesis", "session", "source", "concepts", "entities", "sessions", "sources") else []
        page_path = wiki_write_page(
            path,
            title=title,
            body=body,
            page_type=page_type,
            agent=agent,
            project=project,
            tags=(tags or []) + extra_tags,
        )
        print(f"{Color.GREEN}Wiki page saved: {page_path}{Color.NC}")
    elif backend == "obsidian":
        from ...services.obsidian_backend import obsidian_init, obsidian_write_note
        obsidian_init(path)
        note_path = obsidian_write_note(
            path,
            title=title,
            body=body,
            note_type=note_type,
            agent=agent,
            project=project,
            description=description,
            tags=tags or [],
        )
        print(f"{Color.GREEN}Note saved: {note_path}{Color.NC}")
    else:
        import sys
        print("The `add` subcommand is for obsidian or wiki storage.", file=sys.stderr)
        print("For local storage, write files directly to the agent subdirectory.", file=sys.stderr)
        sys.exit(1)


def do_list() -> None:
    """List all agent memories with sizes."""
    backend, path = _common._load_memory_config()

    if backend == "none":
        print("Memory is disabled. Run `agent-notes config` and select memory storage to enable it.")
        return

    if backend == "wiki":
        if path is None or not path.exists():
            print(f"Wiki not found at {path}")
            return
        from ...services.wiki_backend import wiki_list_pages
        pages = wiki_list_pages(path)
        if not pages:
            print(f"No pages found in wiki {path}")
            return
        print(f"Wiki ({path}):")
        print("")
        current_type = None
        for page in pages:
            if page["type"] != current_type:
                current_type = page["type"]
                print(f"  {Color.CYAN}{current_type}{Color.NC}")
            tags_str = f"  [{', '.join(page['tags'])}]" if page["tags"] else ""
            print(f"    {page['file']}{tags_str}")
        return

    if backend == "obsidian":
        if path is None or not path.exists():
            print(f"Obsidian vault not found at {path}")
            return
        from ...services.obsidian_backend import obsidian_list_notes
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
            size = _common.get_directory_size(d)
            size_str = _common.format_size(size)
            print(f"  {name:<25} {size_str}")


def do_size() -> None:
    """Show total memory usage."""
    backend, path = _common._load_memory_config()

    if backend == "none":
        print("Memory is disabled.")
        return

    if path is None or not path.exists():
        print("No agent memories found.")
        return

    total_size = _common.get_directory_size(path)
    size_str = _common.format_size(total_size)
    print("Total memory usage:")
    print(f"  {size_str}")


def do_show(name: str) -> None:
    """Show memory contents for one agent (local) or category (obsidian)."""
    backend, path = _common._load_memory_config()

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

    elif backend == "wiki":
        if path is None:
            print("Memory path not configured.")
            return
        from ...services.wiki_backend import WIKI_PAGE_TYPES
        wiki_dir = path / "wiki"
        if name not in WIKI_PAGE_TYPES:
            print(f"Page type '{name}' not found. Available types: {', '.join(WIKI_PAGE_TYPES)}")
            return
        type_dir = wiki_dir / name
        if not type_dir.exists():
            print(f"No pages found for type '{name}' in wiki {path}")
            return
        print(f"Wiki pages in '{name}':")
        print("")
        for f in sorted(type_dir.glob("*.md")):
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
