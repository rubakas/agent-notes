"""Diff dataclasses — pure data models for state comparison."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ComponentDiff:
    """Diff for one component type (agents, skills, rules, commands, config) within one backend."""
    backend: str
    component: str                       # "agents" | "skills" | "rules" | "commands" | "config" | "settings"
    added: list[str] = field(default_factory=list)      # names/keys present in new, absent in old
    removed: list[str] = field(default_factory=list)    # present in old, absent in new
    modified: list[str] = field(default_factory=list)   # present in both, sha differs
    unchanged: list[str] = field(default_factory=list)  # present in both, sha identical

    def has_changes(self) -> bool:
        return bool(self.added or self.removed or self.modified)

    def change_count(self) -> int:
        return len(self.added) + len(self.removed) + len(self.modified)


@dataclass
class StateDiff:
    """Full diff between two State snapshots."""
    old_version: Optional[str]
    new_version: str
    old_commit: Optional[str]
    new_commit: str
    added_backends: list[str]            # present in new, absent in old
    removed_backends: list[str]          # present in old, absent in new
    components: list[ComponentDiff]      # one per (backend, component-type) that has at least one of {added, removed, modified, unchanged}

    def has_changes(self) -> bool:
        return (
            bool(self.added_backends) or
            bool(self.removed_backends) or
            any(c.has_changes() for c in self.components)
        )

    def total_changes(self) -> int:
        return sum(c.change_count() for c in self.components)