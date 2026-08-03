"""Capability: a configurable unit the install wizard composes.

Kinds:
- backend  — multi-select AI-provider (claude/codex/...); generates dist/<name>/
- provider — single-select slot (memory: local/obsidian); exactly one active
- toggle   — on/off subsystem (cost-report); can be disabled
- core     — always installed, never shown (credential guard)

Pure data. Behavior (wizard view + install process) lives in the code-side
capability registry, keyed by capability name.
"""
from __future__ import annotations

from dataclasses import dataclass

KIND_BACKEND = "backend"
KIND_PROVIDER = "provider"
KIND_TOGGLE = "toggle"
KIND_CORE = "core"
CAPABILITY_KINDS = frozenset({KIND_BACKEND, KIND_PROVIDER, KIND_TOGGLE, KIND_CORE})


@dataclass(frozen=True)
class Capability:
    name: str
    kind: str
    default: bool = False   # toggle default-on / backend default-selected
    order: int = 0          # tie-break within a wizard phase

    def __post_init__(self):
        if self.kind not in CAPABILITY_KINDS:
            raise ValueError(
                f"Invalid capability kind {self.kind!r} for {self.name!r}; "
                f"expected one of {sorted(CAPABILITY_KINDS)}"
            )
