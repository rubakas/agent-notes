"""Backend-agnostic dispatch for common memory operations."""
from __future__ import annotations

from pathlib import Path


def memory_init(backend: str, path: Path) -> None:
    if backend == "wiki":
        from .wiki_backend import wiki_init
        wiki_init(path)
    elif backend == "obsidian":
        from .obsidian_backend import obsidian_init
        obsidian_init(path)
    elif backend == "local":
        from .local_backend import local_init
        local_init(path)
    else:
        raise ValueError(f"Unknown memory backend: {backend!r}")


def memory_regenerate_index(backend: str, path: Path) -> None:
    if backend == "wiki":
        from .wiki_backend import wiki_regenerate_index
        wiki_regenerate_index(path)
    elif backend == "obsidian":
        from .obsidian_backend import obsidian_regenerate_index
        obsidian_regenerate_index(path)
    elif backend == "local":
        from .local_backend import local_regenerate_index
        local_regenerate_index(path)
    else:
        raise ValueError(f"Unknown memory backend: {backend!r}")
