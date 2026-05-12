"""Vault lifecycle subcommands: vault, init, index."""

from . import _common
from ...config import Color


def do_vault() -> None:
    """Show current storage and memory path."""
    backend, path = _common._load_memory_config()
    if backend == "none":
        print("Memory storage: disabled")
        return
    if backend == "obsidian":
        print(f"Memory storage: obsidian")
        print(f"Vault path:     {path}")
    elif backend == "wiki":
        print(f"Memory storage: wiki")
        print(f"Wiki path:      {path}")
    else:
        print(f"Memory storage: local")
        print(f"Memory path:    {path}")
    initialized = path is not None and path.exists()
    print(f"Initialized:    {'yes' if initialized else 'no — run: agent-notes memory init'}")


def do_init() -> None:
    """Initialize the memory vault — create folder structure and Index.md."""
    backend, path = _common._load_memory_config()
    if backend == "none":
        print("Memory is disabled. Re-run `agent-notes install` and choose memory storage.")
        return
    if path is None:
        print("Memory path not configured.")
        return
    from ...services.memory_router import memory_init
    memory_init(backend, path)
    if backend == "wiki":
        from ...services.wiki_backend import WIKI_PAGE_TYPES
        print(f"{Color.GREEN}Wiki initialised at {path}{Color.NC}")
        print(f"  Folders: raw/, wiki/{{{', '.join(WIKI_PAGE_TYPES)}}}")
        print(f"  Index:   {path / 'wiki' / 'index.md'}")
    elif backend == "obsidian":
        from ...services.obsidian_backend import OBSIDIAN_CATEGORIES
        print(f"{Color.GREEN}Obsidian vault initialised at {path}{Color.NC}")
        print(f"  Folders: {', '.join(OBSIDIAN_CATEGORIES)}")
        print(f"  Index:   {path / 'Index.md'}")
        print(f"\nOpen the folder as a vault in Obsidian to start browsing.")
    else:
        print(f"{Color.GREEN}Memory directory initialised at {path}{Color.NC}")


def do_index() -> None:
    """Regenerate Index.md for the current backend."""
    backend, path = _common._load_memory_config()
    if backend == "none":
        print("Memory is disabled. Run `agent-notes memory vault` to check configuration.")
        return
    if path is None:
        print("Memory path not configured.")
        return
    from ...services.memory_router import memory_regenerate_index
    memory_regenerate_index(backend, path)
    if backend == "wiki":
        print(f"{Color.GREEN}index.md regenerated at {path / 'wiki' / 'index.md'}{Color.NC}")
    else:
        print(f"{Color.GREEN}Index.md regenerated at {path / 'Index.md'}{Color.NC}")
