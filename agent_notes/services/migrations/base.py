"""Base class for memory migrations."""
from __future__ import annotations
from abc import ABC, abstractmethod
from pathlib import Path


class Migration(ABC):
    """A single one-time vault migration."""
    name: str
    version: str
    description: str

    @abstractmethod
    def run(self, vault: Path) -> str:
        """Execute the migration. Returns a summary string."""
        ...
