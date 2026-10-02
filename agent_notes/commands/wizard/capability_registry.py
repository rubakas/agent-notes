"""Code-side registry: capability name -> its wizard view + install process.

Manifests/kinds are pure data (domain.Capability); behavior is registered here
in code. `view(step, total, version)` runs the interactive screen and returns
the collected value. `process` (optional) applies it at install time. Phase 1
uses `view` only; `process` is reserved for later phases.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from ...domain.capability import Capability


@dataclass(frozen=True)
class CapabilityBehaviour:
    view: Optional[Callable] = None        # legacy step view; removed in Task 9
    process: Optional[Callable] = None
    config_view: Optional[Callable] = None  # legacy; removed in Task 9
    row: Optional[Callable] = None          # (ReviewContext) -> list[Row] for the install review
    config_row: Optional[Callable] = None   # (ConfigContext) -> list[Row] for `agent-notes config`


class CapabilityRegistry:
    def __init__(self) -> None:
        self._entries: dict[str, tuple[Capability, CapabilityBehaviour]] = {}

    def register(self, capability: Capability, *, view=None, process=None, config_view=None,
                 row=None, config_row=None) -> None:
        if capability.name in self._entries:
            raise ValueError(f"Capability {capability.name!r} already registered")
        self._entries[capability.name] = (
            capability,
            CapabilityBehaviour(view, process, config_view, row, config_row),
        )

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
