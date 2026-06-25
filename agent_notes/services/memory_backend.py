"""Abstract base class for memory backends."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class MemoryBackend(ABC):
    """Common interface that all memory backends must implement."""

    @abstractmethod
    def init(self, path: Path) -> None:
        """Initialise the storage layout at *path* (idempotent)."""

    @abstractmethod
    def regenerate_index(self, path: Path) -> None:
        """Rebuild the index document inside *path*."""


class LocalBackend(MemoryBackend):
    def init(self, path: Path) -> None:
        from .local_backend import local_init
        local_init(path)

    def regenerate_index(self, path: Path) -> None:
        from .local_backend import local_regenerate_index
        local_regenerate_index(path)


class ObsidianBackend(MemoryBackend):
    def init(self, path: Path) -> None:
        from .obsidian_backend import obsidian_init
        obsidian_init(path)

    def regenerate_index(self, path: Path) -> None:
        from .obsidian_backend import obsidian_regenerate_index
        obsidian_regenerate_index(path)


class WikiBackend(MemoryBackend):
    def init(self, path: Path) -> None:
        from .wiki_backend import wiki_init
        wiki_init(path)

    def regenerate_index(self, path: Path) -> None:
        from .wiki_backend import wiki_regenerate_index
        wiki_regenerate_index(path)


_REGISTRY: dict[str, MemoryBackend] = {
    "local": LocalBackend(),
    "obsidian": ObsidianBackend(),
    "wiki": WikiBackend(),
}


def get_backend(name: str) -> MemoryBackend:
    """Return the backend instance for *name*, raising ValueError if unknown."""
    try:
        return _REGISTRY[name]
    except KeyError:
        raise ValueError(f"Unknown memory backend: {name!r}")
