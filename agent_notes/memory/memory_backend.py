"""Abstract base class for memory backends."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from ..services.stability import is_visible, enabled_wip


class MemoryBackend(ABC):
    """Common interface that all memory backends must implement."""

    stability: str = "stable"

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


_REGISTRY: dict[str, MemoryBackend] = {
    "local": LocalBackend(),
    "obsidian": ObsidianBackend(),
}

_REMOVED_BACKENDS = {"wiki"}


def get_backend(name: str, override=None) -> MemoryBackend:
    """Return the backend instance for *name*, raising ValueError if unknown or
    a work-in-progress backend that is not force-enabled."""
    if name in _REMOVED_BACKENDS:
        raise ValueError(
            f"Memory backend {name!r} has been removed. "
            "Run `agent-notes config memory` to switch to a supported backend "
            "(local or obsidian)."
        )
    try:
        backend = _REGISTRY[name]
    except KeyError:
        raise ValueError(f"Unknown memory backend: {name!r}")
    ov = enabled_wip() if override is None else override
    if not is_visible(getattr(backend, "stability", "stable"), name, ov):
        raise ValueError(
            f"Memory backend {name!r} is work-in-progress; "
            f"set AGENT_NOTES_ENABLE_WIP={name} to enable it."
        )
    return backend


def available_backends(override=None) -> list[str]:
    """Names of memory backends visible to users (non-removed, non-wip)."""
    ov = enabled_wip() if override is None else override
    return [
        name for name, backend in _REGISTRY.items()
        if name not in _REMOVED_BACKENDS
        and is_visible(getattr(backend, "stability", "stable"), name, ov)
    ]
