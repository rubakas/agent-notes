"""Role dataclass — pure data model for role descriptors."""

from __future__ import annotations
from dataclasses import dataclass


# Default display order for roles whose YAML declares no `order:` —
# large so unknown/future roles sort last (alphabetical tiebreak on name).
DEFAULT_ROLE_ORDER = 999


@dataclass(frozen=True)
class Role:
    name: str
    label: str
    description: str
    typical_class: str
    color: str = ""
    typical_effort: str = ""
    order: int = DEFAULT_ROLE_ORDER
