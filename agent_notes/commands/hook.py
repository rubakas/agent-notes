"""Hook command - Claude Code PostToolUse integration."""

import fnmatch
import json
import sys
from pathlib import Path


def hook(subaction: str) -> None:
    """Handle hook subactions."""
    if subaction == "memory-bridge":
        _memory_bridge()


def _memory_bridge() -> None:
    """PostToolUse hook for the Read tool.

    Reads JSON from stdin (Claude Code PostToolUse format), checks if the
    file_path matches the Claude Code memory pattern, and if so prints the
    agent-notes memory index so both memory systems are visible in context.
    """
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return

    try:
        file_path = data["tool_input"]["file_path"]
    except (KeyError, TypeError):
        return

    if not fnmatch.fnmatch(file_path, "*/.claude/projects/*/memory/*"):
        return

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
