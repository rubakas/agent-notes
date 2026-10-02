"""Code-side registry: capability name -> its review row(s) + install process.

Manifests/kinds are pure data (domain.Capability); behavior is registered here
in code. `row(ctx)` returns the capability's rows on the install review;
`config_row(ctx)`, when given, its rows on `agent-notes config`. `process` is
reserved for applying a value at install time.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from ...domain.capability import Capability


@dataclass(frozen=True)
class CapabilityBehaviour:
    row: Callable
    config_row: Optional[Callable] = None
    process: Optional[Callable] = None


class CapabilityRegistry:
    def __init__(self) -> None:
        self._entries: dict[str, tuple[Capability, CapabilityBehaviour]] = {}

    def register(self, capability: Capability, *, row, config_row=None, process=None) -> None:
        if capability.name in self._entries:
            raise ValueError(f"Capability {capability.name!r} already registered")
        if row is None:
            raise ValueError(f"Capability {capability.name!r} has no review row")
        self._entries[capability.name] = (capability, CapabilityBehaviour(row, config_row, process))

    def get(self, name: str) -> CapabilityBehaviour:
        try:
            return self._entries[name][1]
        except KeyError:
            raise ValueError(f"No behaviour registered for capability {name!r}") from None

    def capability(self, name: str) -> Capability:
        try:
            return self._entries[name][0]
        except KeyError:
            raise ValueError(f"No capability {name!r} registered") from None

    def by_kind(self, kind: str) -> list[Capability]:
        return sorted(
            (cap for cap, _ in self._entries.values() if cap.kind == kind),
            key=lambda c: c.order,
        )

    def names(self) -> list[str]:
        return list(self._entries)
