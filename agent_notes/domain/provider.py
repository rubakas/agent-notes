"""Provider dataclass — pure data model for provider effort descriptors."""

from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class Provider:
    name: str
    efforts: tuple[str, ...]
    default_effort: str
