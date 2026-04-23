"""State dataclasses — pure data models for installation state."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class InstalledItem:
    sha: str
    target: str
    mode: str


@dataclass
class BackendState:
    """Installation manifest for one CLI within one scope."""
    role_models: dict[str, str] = field(default_factory=dict)   # role_name -> model_id
    installed: dict[str, dict[str, InstalledItem]] = field(default_factory=dict)
    # installed is a dict of component_type -> {filename/key -> InstalledItem}
    # e.g. installed["agents"]["lead.md"] = InstalledItem(...)


@dataclass
class ScopeState:
    """One install scope: either the single global install or one local-project install."""
    installed_at: str = ""
    updated_at: str = ""
    mode: str = "symlink"
    clis: dict[str, BackendState] = field(default_factory=dict)


@dataclass
class State:
    """Full agent-notes state."""
    source_path: str = ""
    source_commit: str = ""
    global_install: Optional[ScopeState] = None         # JSON key is "global"
    local_installs: dict[str, ScopeState] = field(default_factory=dict)  # JSON key is "local"