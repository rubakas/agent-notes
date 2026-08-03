"""Memory-bridge helpers — shared renderer for SessionStart and PreCompact hooks."""

from __future__ import annotations

from pathlib import Path
from typing import Optional


def _load_memory_index() -> Optional[str]:
    """Load the agent-notes memory index content, or return None if unavailable.

    Shared renderer used by both the SessionStart memory-bridge hook and the
    PreCompact memory-bridge hook so both emit from one source of truth.
    """
    try:
        from ...memory.commands._common import _load_memory_config
        from ...constants import Obsidian

        backend, path = _load_memory_config()

        if backend is None:
            return None

        if backend == "obsidian":
            index_file = Path(path) / Obsidian.INDEX
        else:
            # local and any unknown backends: use Index.md at root
            index_file = Path(path) / "Index.md"

        if not index_file.exists():
            return None

        return index_file.read_text(encoding="utf-8")
    except Exception:
        return None
