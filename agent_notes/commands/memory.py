"""Manage agent memory stored in ~/.claude/agent-memory/."""

import shutil
from pathlib import Path
from typing import Optional

def do_list() -> None:
    """List all agent memories with sizes."""
    from .. import memory as parent_module
    
    if not parent_module.MEMORY_DIR.exists() or not any(parent_module.MEMORY_DIR.iterdir()):
        print(f"No agent memories found in {parent_module.MEMORY_DIR}")
        return
    
    print(f"Agent memories ({parent_module.MEMORY_DIR}):")
    print("")
    print(f"  {'AGENT':<25} {'SIZE'}")
    print(f"  {'-' * 25} {'-' * 4}")
    
    for d in parent_module.MEMORY_DIR.iterdir():
        if d.is_dir():
            name = d.name
            # Calculate directory size
            size = get_directory_size(d)
            size_str = format_size(size)
            print(f"  {name:<25} {size_str}")

def do_size() -> None:
    """Show total memory usage."""
    from .. import memory as parent_module
    
    if not parent_module.MEMORY_DIR.exists():
        print("No agent memories found.")
        return
    
    total_size = get_directory_size(parent_module.MEMORY_DIR)
    size_str = format_size(total_size)
    print("Total memory usage:")
    print(f"  {size_str}")

def do_show(name: str) -> None:
    """Show memory contents for one agent."""
    import agent_notes.memory as _shim
    
    agent_dir = _shim.MEMORY_DIR / name
    if not agent_dir.exists():
        print(f"No memory found for agent '{name}'")
        available = sorted(d.name for d in _shim.MEMORY_DIR.iterdir() if d.is_dir()) if _shim.MEMORY_DIR.exists() else []
        if available:
            print(f"Available: {' '.join(available)}")
        exit(1)
    
    print(f"Memory for agent '{name}' ({agent_dir}):")
    print("")
    
    for f in agent_dir.iterdir():
        if f.is_file():
            print(f"{_shim.Color.CYAN}--- {f.name} ---{_shim.Color.NC}")
            try:
                content = f.read_text()
                print(content)
            except (UnicodeDecodeError, OSError):
                print("(binary file or read error)")
            print("")

def do_reset(name: Optional[str] = None) -> None:
    """Clear agent memory (all or specific agent)."""
    import agent_notes.memory as _shim
    
    if name:
        agent_dir = _shim.MEMORY_DIR / name
        if not agent_dir.exists():
            print(f"No memory found for agent '{name}'")
            exit(1)
        
        print(f"{_shim.Color.YELLOW}This will delete all memory for agent '{name}'.{_shim.Color.NC}")
        confirm = input("Continue? [y/N] ")
        if confirm.lower() == 'y':
            shutil.rmtree(agent_dir)
            print(f"{_shim.Color.GREEN}Memory for '{name}' cleared.{_shim.Color.NC}")
        else:
            print("Cancelled.")
    else:
        if not _shim.MEMORY_DIR.exists() or not any(_shim.MEMORY_DIR.iterdir()):
            print("No agent memories to clear.")
            return
        
        print(f"{_shim.Color.RED}This will delete ALL agent memories.{_shim.Color.NC}")
        print(f"Contents of {_shim.MEMORY_DIR}:")
        for d in _shim.MEMORY_DIR.iterdir():
            if d.is_dir():
                print(f"  {d.name}")
        print("")
        
        confirm = input("Type 'yes' to confirm: ")
        if confirm == "yes":
            for item in _shim.MEMORY_DIR.iterdir():
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()
            print(f"{_shim.Color.GREEN}All agent memories cleared.{_shim.Color.NC}")
        else:
            print("Cancelled.")

def do_export() -> None:
    """Copy memories to agent-notes/memory-backup/."""
    import agent_notes.memory as _shim
    
    if not _shim.MEMORY_DIR.exists() or not any(_shim.MEMORY_DIR.iterdir()):
        print("No agent memories to export.")
        return
    
    _shim.BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    
    for item in _shim.MEMORY_DIR.iterdir():
        if item.is_dir():
            dest = _shim.BACKUP_DIR / item.name
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(item, dest)
        elif item.is_file():
            shutil.copy2(item, _shim.BACKUP_DIR)
    
    print(f"{_shim.Color.GREEN}Exported to {_shim.BACKUP_DIR}{_shim.Color.NC}")
    print("Contents:")
    for item in _shim.BACKUP_DIR.iterdir():
        print(f"  {item.name}")
    print("")
    print(f"{_shim.Color.YELLOW}Note: memory-backup/ is in .gitignore — these are personal learnings.{_shim.Color.NC}")

def do_import() -> None:
    """Restore from agent-notes/memory-backup/."""
    import agent_notes.memory as _shim
    
    if not _shim.BACKUP_DIR.exists() or not any(_shim.BACKUP_DIR.iterdir()):
        print(f"No backup found in {_shim.BACKUP_DIR}")
        exit(1)
    
    _shim.MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    
    for item in _shim.BACKUP_DIR.iterdir():
        if item.is_dir():
            dest = _shim.MEMORY_DIR / item.name
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(item, dest)
        elif item.is_file():
            shutil.copy2(item, _shim.MEMORY_DIR)
    
    print(f"{_shim.Color.GREEN}Imported from {_shim.BACKUP_DIR} to {_shim.MEMORY_DIR}{_shim.Color.NC}")
    print("Restored agents:")
    for item in _shim.MEMORY_DIR.iterdir():
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
    import agent_notes.memory as _shim
    
    if action == "list":
        _shim.do_list()
    elif action == "size":
        _shim.do_size()
    elif action == "show":
        if not name:
            print("Error: show requires an agent name.")
            exit(1)
        _shim.do_show(name)
    elif action == "reset":
        _shim.do_reset(name)
    elif action == "export":
        _shim.do_export()
    elif action == "import":
        _shim.do_import()
    else:
        print(f"Unknown command: {action}")
        show_help()
        exit(1)