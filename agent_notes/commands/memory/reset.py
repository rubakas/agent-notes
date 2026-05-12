"""Destructive subcommand: reset."""

import shutil
from typing import Optional

from . import _common
from ...config import MEMORY_DIR, Color


def do_reset(name: Optional[str] = None) -> None:
    """Clear agent memory (all or specific agent)."""
    backend, path = _common._load_memory_config()

    if backend == "none":
        print("Memory is disabled.")
        return

    if backend == "wiki":
        if path is None or not path.exists():
            print("No wiki found to reset.")
            return
        target = f"wiki at {path}" if name is None else f"wiki page type '{name}' at {path}"
        print(f"{Color.RED}Warning: this will permanently delete the {target}.{Color.NC}")
        confirm = input("Type 'yes' to confirm: ")
        if confirm == "yes":
            from ...services.wiki_backend import WIKI_PAGE_TYPES
            wiki_dir = path / "wiki"
            if name is None:
                for page_type in WIKI_PAGE_TYPES:
                    type_dir = wiki_dir / page_type
                    if type_dir.exists():
                        shutil.rmtree(type_dir)
                        type_dir.mkdir()
                print(f"{Color.GREEN}Wiki at {path} cleared.{Color.NC}")
            else:
                if name not in WIKI_PAGE_TYPES:
                    print(f"Page type '{name}' not found. Available types: {', '.join(WIKI_PAGE_TYPES)}")
                    return
                type_dir = wiki_dir / name
                if not type_dir.exists():
                    print(f"No pages found for type '{name}'.")
                    return
                shutil.rmtree(type_dir)
                type_dir.mkdir()
                print(f"{Color.GREEN}Wiki pages for type '{name}' cleared.{Color.NC}")
        else:
            print("Cancelled.")
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
