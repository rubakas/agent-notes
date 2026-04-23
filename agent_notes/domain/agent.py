"""Agent domain type for agent metadata."""

from __future__ import annotations
from dataclasses import dataclass
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
    claude_exclude: bool = False
    claude: Optional[Dict[str, Any]] = None
    opencode: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        # Ensure claude and opencode are dicts if provided
        if self.claude is not None and not isinstance(self.claude, dict):
            object.__setattr__(self, 'claude', {})
        if self.opencode is not None and not isinstance(self.opencode, dict):
            object.__setattr__(self, 'opencode', {})