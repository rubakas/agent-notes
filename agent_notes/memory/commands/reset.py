"""Destructive subcommand: reset."""

import sys
import shutil
from typing import Optional

from . import _common
from ...config import MEMORY_DIR, Color


def do_reset(name: Optional[str] = None) -> None:
    """Clear agent memory (all or specific agent)."""
    backend, path = _common._load_memory_config()

    if path is None:
        path = MEMORY_DIR

    if name:
        agent_dir = path / name
        if not agent_dir.exists():
            print(f"No memory found for agent '{name}'")
            sys.exit(1)

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
