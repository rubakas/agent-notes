"""Role dataclass — pure data model for role descriptors."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


# Default display order for roles whose YAML declares no `order:` —
# large so unknown/future roles sort last (alphabetical tiebreak on name).
DEFAULT_ROLE_ORDER = 999


@dataclass(frozen=True)
class Role:
    name: str
    label: str
    description: str
    budget: Optional[float] = None   # max USD per 1M input tokens; None = unbounded
    color: str = ""
    typical_effort: str = ""
    order: int = DEFAULT_ROLE_ORDER
