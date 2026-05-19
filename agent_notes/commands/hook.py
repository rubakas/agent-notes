"""Hook command - Claude Code hook integrations."""

from pathlib import Path


def hook(subaction: str) -> None:
    """Handle hook subactions."""
    if subaction == "memory-bridge":
        _memory_bridge()


def _memory_bridge() -> None:
    """SessionStart hook that prints the agent-notes memory index.

    Unconditionally loads and prints the memory index so it is visible in
    context at the start of every Claude Code session.
    """
    try:
        from .memory._common import _load_memory_config
        from ..constants import Obsidian, Wiki

        backend, path = _load_memory_config()

        if backend == "none" or backend is None:
            return

        if backend == "obsidian":
            index_file = Path(path) / Obsidian.INDEX
        elif backend == "wiki":
            index_file = Path(path) / Wiki.DIR / Wiki.INDEX
        else:
            # local and any unknown backends: use Index.md at root
            index_file = Path(path) / "Index.md"

        if not index_file.exists():
            return

        content = index_file.read_text(encoding="utf-8")
        print("<!-- agent-notes memory index (auto-loaded) -->")
        print(content)
    except Exception:
        return
