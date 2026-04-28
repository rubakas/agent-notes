"""Skill domain type."""

from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class Skill:
    """Skill from data/skills/<name>/."""
    name: str              # directory name
    path: Path             # full path to skill dir
    description: str       # from SKILL.md frontmatter or first line
    group: Optional[str] = None   # from SKILL.md frontmatter (if present)