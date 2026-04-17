"""Manage agent memory stored in ~/.claude/agent-memory/."""

import shutil
from pathlib import Path
from typing import Optional

from .config import ROOT, MEMORY_DIR, BACKUP_DIR, Color

def do_list() -> None:
    """List all agent memories with sizes."""
    if not MEMORY_DIR.exists() or not any(MEMORY_DIR.iterdir()):
        print(f"No agent memories found in {MEMORY_DIR}")
        return
    
    print(f"Agent memories ({MEMORY_DIR}):")
    print("")
    print(f"  {'AGENT':<25} {'SIZE'}")
    print(f"  {'-' * 25} {'-' * 4}")
    
    for d in MEMORY_DIR.iterdir():
        if d.is_dir():
            name = d.name
            # Calculate directory size
            size = get_directory_size(d)
            size_str = format_size(size)
            print(f"  {name:<25} {size_str}")

def do_size() -> None:
    """Show total memory usage."""
    if not MEMORY_DIR.exists():
        print("No agent memories found.")
        return
    
    total_size = get_directory_size(MEMORY_DIR)
    size_str = format_size(total_size)
    print("Total memory usage:")
    print(f"  {size_str}")

def do_show(name: str) -> None:
    """Show memory contents for one agent."""
    agent_dir = MEMORY_DIR / name
    if not agent_dir.exists():
        print(f"No memory found for agent '{name}'")
        available = sorted(d.name for d in MEMORY_DIR.iterdir() if d.is_dir()) if MEMORY_DIR.exists() else []
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
    if name:
        agent_dir = MEMORY_DIR / name
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
        if not MEMORY_DIR.exists() or not any(MEMORY_DIR.iterdir()):
            print("No agent memories to clear.")
            return
        
        print(f"{Color.RED}This will delete ALL agent memories.{Color.NC}")
        print(f"Contents of {MEMORY_DIR}:")
        for d in MEMORY_DIR.iterdir():
            if d.is_dir():
                print(f"  {d.name}")
        print("")
        
        confirm = input("Type 'yes' to confirm: ")
        if confirm == "yes":
            for item in MEMORY_DIR.iterdir():
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()
            print(f"{Color.GREEN}All agent memories cleared.{Color.NC}")
        else:
            print("Cancelled.")

def do_export() -> None:
    """Copy memories to agent-notes/memory-backup/."""
    if not MEMORY_DIR.exists() or not any(MEMORY_DIR.iterdir()):
        print("No agent memories to export.")
        return
    
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    
    for item in MEMORY_DIR.iterdir():
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
    if not BACKUP_DIR.exists() or not any(BACKUP_DIR.iterdir()):
        print(f"No backup found in {BACKUP_DIR}")
        exit(1)
    
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    
    for item in BACKUP_DIR.iterdir():
        if item.is_dir():
            dest = MEMORY_DIR / item.name
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(item, dest)
        elif item.is_file():
            shutil.copy2(item, MEMORY_DIR)
    
    print(f"{Color.GREEN}Imported from {BACKUP_DIR} to {MEMORY_DIR}{Color.NC}")
    print("Restored agents:")
    for item in MEMORY_DIR.iterdir():
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
    help_text = """Usage: agent-notes memory [command] [agent-name]

Manage agent memory stored in ~/.claude/agent-memory/.

Commands:
  list             List all agent memories with sizes (default)
  size             Total disk usage
  show <name>      Show memory contents for one agent
  reset            Clear ALL memories (requires confirmation)
  reset <name>     Clear one agent's memory
  export           Back up memories to agent-notes/memory-backup/
  import           Restore from agent-notes/memory-backup/

Examples:
  agent-notes memory                    List all memories
  agent-notes memory show coder         View coder agent's memory
  agent-notes memory reset reviewer     Clear reviewer's memory
  agent-notes memory export             Back up before cleanup"""
    
    print(help_text)

def memory(action: str = "list", name: Optional[str] = None) -> None:
    """Manage agent memory."""
    if action == "list":
        do_list()
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