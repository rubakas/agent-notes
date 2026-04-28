"""Agent registry for loading and managing agent configurations."""

from __future__ import annotations
from pathlib import Path
from typing import Optional
from functools import lru_cache

from ..config import AGENTS_YAML
from ..domain.agent import AgentSpec
from ._base import load_yaml_file


class AgentRegistry:
    """Registry of agent configurations from agents.yaml."""
    
    def __init__(self, agents: list[AgentSpec]):
        self._agents = agents
        self._by_name = {a.name: a for a in agents}
    
    def all(self) -> list[AgentSpec]:
        """Return all agents."""
        return self._agents.copy()
    
    def get(self, name: str) -> AgentSpec:
        """Get agent by name. Raises KeyError if unknown."""
        if name not in self._by_name:
            raise KeyError(f"Agent '{name}' not found in registry")
        return self._by_name[name]
    
    def names(self) -> list[str]:
        """Return sorted list of agent names."""
        return sorted(self._by_name.keys())
    
    def with_role(self, role: str) -> list[AgentSpec]:
        """Return agents with the specified role."""
        return [a for a in self._agents if a.role == role]


def load_agent_registry(yaml_path: Optional[Path] = None) -> AgentRegistry:
    """Load agents from agents.yaml. Single file, not a directory."""
    if yaml_path is None:
        yaml_path = AGENTS_YAML
    
    if not yaml_path.exists():
        raise ValueError(f"Agents file not found: {yaml_path}")
    
    data = load_yaml_file(yaml_path)
    
    # The YAML has an 'agents' top-level key
    agents_data = data.get("agents", {})
    if not agents_data:
        return AgentRegistry([])
    
    # Known top-level keys that are NOT per-backend config
    NON_BACKEND_KEYS = {"description", "role", "mode", "color", "effort", "claude_exclude"}
    
    agents = []
    for name, config in agents_data.items():
        # Extract required fields
        if "description" not in config:
            raise ValueError(f"Missing 'description' field for agent '{name}' in {yaml_path}")
        if "role" not in config:
            raise ValueError(f"Missing 'role' field for agent '{name}' in {yaml_path}")
        if "mode" not in config:
            raise ValueError(f"Missing 'mode' field for agent '{name}' in {yaml_path}")
        
        # Everything that is NOT in NON_BACKEND_KEYS is treated as per-backend config.
        # This is what makes the loader registry-driven: adding a new CLI named
        # "gemini" just means agents.yaml may have a 'gemini:' key and it flows
        # through automatically.
        backends: dict[str, dict] = {}
        for key, value in config.items():
            if key in NON_BACKEND_KEYS:
                continue
            if isinstance(value, dict):
                backends[key] = value
            else:
                # Non-dict top-level keys are unknown; ignore with no error to be
                # lenient with user-edited YAML (could log a warning later).
                pass

        # Backward compat: translate legacy top-level claude_exclude into backends
        # Note: This is the only hardcoded "claude" reference for backward compatibility
        if config.get("claude_exclude"):
            backends.setdefault("claude", {})["exclude"] = True

        agent = AgentSpec(
            name=name,
            description=config["description"],
            role=config["role"],
            mode=config["mode"],
            color=config.get("color"),
            effort=config.get("effort"),
            backends=backends,
        )
        agents.append(agent)
    
    # Sort by name for deterministic order
    agents.sort(key=lambda a: a.name)
    
    return AgentRegistry(agents)


@lru_cache(maxsize=1)
def default_agent_registry() -> AgentRegistry:
    """Return the default agent registry, cached."""
    return load_agent_registry()