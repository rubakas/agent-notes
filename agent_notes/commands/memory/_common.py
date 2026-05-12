"""Shared helpers for memory subcommands."""

from pathlib import Path
from typing import Optional

from ...config import MEMORY_DIR


_WIKI_TYPE_MAP = {
    "pattern": "concepts",
    "decision": "concepts",
    "mistake": "concepts",
    "context": "concepts",
    "concept": "concepts",
    "entity": "entities",
    "synthesis": "synthesis",
    "session": "sessions",
    "source": "sources",
}


def _load_memory_config():
    from ...services.state_store import load_state
    from ...config import memory_dir_for_backend
    state = load_state()
    if state is None:
        return "local", MEMORY_DIR
    backend = state.memory.backend
    path = memory_dir_for_backend(backend, state.memory.path)
    return backend, path


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
