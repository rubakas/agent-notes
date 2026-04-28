"""CLI backend dataclass — pure data model for CLI backend descriptors."""

from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class CLIBackend:
    """Represents a single CLI backend loaded from YAML descriptor."""
    
    name: str                      # "claude"
    label: str                     # "Claude Code"
    global_home: Path              # expanded ~/.claude (Path object)
    local_dir: str                 # ".claude"
    layout: dict[str, str]         # {"agents": "agents/", ...}
    features: dict[str, object]    # {"agents": True, "frontmatter": "claude", ...}
    global_template: Optional[str] # "global-claude.md" or None
    exclude_flag: Optional[str] = None    # "claude_exclude" or None
    strip_memory_section: bool = False
    settings_template: Optional[str] = None
    accepted_providers: tuple[str, ...] = ()   # new

    def supports(self, feature: str) -> bool:
        """Return True if the backend has that feature enabled."""
        val = self.features.get(feature)
        return bool(val)

    def local_path(self) -> Path:
        """Return Path(self.local_dir) relative to cwd — caller decides absolute."""
        return Path(self.local_dir)

    def first_alias_for(self, model_aliases: dict[str, str]) -> Optional[tuple[str, str]]:
        """Given a model's aliases dict, return (provider, alias) for the first
        of self.accepted_providers that has an alias. None if no compat."""
        for provider in self.accepted_providers:
            if provider in model_aliases:
                return (provider, model_aliases[provider])
        return None