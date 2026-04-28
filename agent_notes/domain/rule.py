"""Rule domain type."""

from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Rule:
    """Rule from data/rules/*.md."""
    name: str     # filename stem
    path: Path    # full path
    title: str    # first # heading in the file, or name