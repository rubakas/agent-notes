"""Agent domain type for agent metadata."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Dict, Any


@dataclass(frozen=True)
class AgentSpec:
    """Agent configuration from agents.yaml."""
    name: str
    description: str
    role: str
    mode: str  # primary, subagent
    color: Optional[str] = None
    effort: Optional[str] = None  # low, medium, high
    backends: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    # backends is keyed by CLI backend name (e.g. "claude", "opencode", "copilot", ...).
    # Each value is the per-backend override dict as declared in agents.yaml.
    # Example: {"claude": {"exclude": True}, "opencode": {"mode": "subagent"}}
    
    def backend_config(self, backend_name: str) -> Dict[str, Any]:
        """Return per-backend config for backend_name, or {} if none declared."""
        return self.backends.get(backend_name, {}) or {}

    def excluded_from(self, backend_name: str) -> bool:
        """Return True if the agent is excluded from this backend's build.

        A backend is excluded when its config has exclude: true. For backward
        compat, also treat the legacy top-level 'claude_exclude' key as meaning
        excluded-from-claude — the loader maps this into backends["claude"]["exclude"].
        """
        cfg = self.backend_config(backend_name)
        return bool(cfg.get("exclude", False))