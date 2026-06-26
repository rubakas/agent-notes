"""Role dataclass — pure data model for role descriptors."""

from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class Role:
    name: str
    label: str
    description: str
    typical_class: str
    color: str = ""