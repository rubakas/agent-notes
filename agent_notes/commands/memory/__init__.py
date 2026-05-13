"""Manage agent memory stored in ~/.claude/agent-memory/."""

from typing import Optional

from . import _common
from ._common import _load_memory_config, get_directory_size, format_size, _WIKI_TYPE_MAP
from .vault import do_vault, do_init, do_index
from .notes import do_add, do_list, do_show, do_size
from .transfer import do_export, do_import
from .wiki import do_ingest, do_query, do_lint, do_scan_raw
from .migrate import do_migrate
from .reset import do_reset


def show_help() -> None:
    """Show memory command help."""
    help_text = """Usage: agent-notes memory [command] [args]

Manage agent memory.

Commands:
  init             Create folder structure and Index.md
  list             List all agent memories with sizes (default)
  vault            Show current backend and memory path
  index            Regenerate Index.md for the current backend
  add <title> <body>  Add a note (obsidian and wiki backends)
  migrate          Migrate old per-project layout to new shared flat layout
  size             Total disk usage
  show <name>      Show memory contents for one agent/category
  reset            Clear ALL memories (requires confirmation)
  reset <name>     Clear one agent's memory
  export           Back up memories to agent-notes/memory-backup/
  import           Restore from agent-notes/memory-backup/
  ingest <title> <body>  Ingest source material and fan-out to concepts/entities (wiki backend)
  query <keyword>  Search wiki pages by keyword (wiki backend)
  lint             Check wiki health: orphans, broken links, stale index (wiki backend)

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
    elif action == "ingest":
        if not name:
            do_scan_raw()
            exit(0)
        body = extra[0] if extra else ""
        concepts_csv = extra[1] if extra and len(extra) > 1 else ""
        entities_csv = extra[2] if extra and len(extra) > 2 else ""
        tags_csv = extra[3] if extra and len(extra) > 3 else ""
        concepts = [c.strip() for c in concepts_csv.split(",") if c.strip()] if concepts_csv else None
        entities = [e.strip() for e in entities_csv.split(",") if e.strip()] if entities_csv else None
        tags = [t.strip() for t in tags_csv.split(",") if t.strip()] if tags_csv else None
        do_ingest(name, body, concepts=concepts, entities=entities, tags=tags)
    elif action == "query":
        if not name:
            print("Error: query requires a keyword.")
            exit(1)
        do_query(name)
    elif action == "lint":
        do_lint()
    else:
        print(f"Unknown command: {action}")
        show_help()
        exit(1)
