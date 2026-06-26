"""Backend-agnostic dispatch for common memory operations."""
from __future__ import annotations

from pathlib import Path

from .memory_backend import get_backend


def memory_init(backend: str, path: Path) -> None:
    get_backend(backend).init(path)


def memory_regenerate_index(backend: str, path: Path) -> None:
    get_backend(backend).regenerate_index(path)
