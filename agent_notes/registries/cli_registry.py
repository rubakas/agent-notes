"""CLI backend registry for loading and managing CLI descriptors."""

from __future__ import annotations

from pathlib import Path
from typing import Optional
from functools import lru_cache

from ..config import DATA_DIR
from ..domain.cli_backend import CLIBackend
from ._base import load_yaml_dir, require_fields


class CLIRegistry:
    """Registry of all loaded CLI backends."""
    
    def __init__(self, backends: list[CLIBackend]):
        self._backends = backends
        self._by_name = {b.name: b for b in backends}
    
    def all(self) -> list[CLIBackend]:
        """Return all backends."""
        return self._backends.copy()
    
    def get(self, name: str) -> CLIBackend:
        """Get backend by name. Raises KeyError if unknown."""
        return self._by_name[name]
    
    def names(self) -> list[str]:
        """Return sorted list of backend names."""
        return sorted(self._by_name.keys())
    
    def with_feature(self, feature: str) -> list[CLIBackend]:
        """Return backends where self.supports(feature) is True."""
        return [b for b in self._backends if b.supports(feature)]


def load_registry(cli_dir: Optional[Path] = None) -> CLIRegistry:
    """Load all *.yaml files from cli_dir (default: agent_notes/data/cli/)
    and return a CLIRegistry. Raises ValueError if directory missing or any YAML invalid.
    """
    if cli_dir is None:
        cli_dir = DATA_DIR / "cli"
    
    if not cli_dir.exists():
        raise ValueError(f"CLI directory not found: {cli_dir}")
    
    required_fields = ["name", "label", "global_home", "layout", "features"]
    try:
        items = load_yaml_dir(cli_dir, required_fields)
    except ValueError as e:
        # Maintain backward compatibility for error messages
        if "Registry directory not found" in str(e):
            raise ValueError(f"CLI directory not found: {cli_dir}")
        raise
    
    backends = []
    for yaml_file, data in items:
        # Expand global_home path
        global_home = Path(data["global_home"]).expanduser()
        
        backend = CLIBackend(
            name=data["name"],
            label=data["label"],
            global_home=global_home,
            local_dir=data["local_dir"],
            layout=data["layout"],
            features=data["features"],
            global_template=data.get("global_template"),
            exclude_flag=data.get("exclude_flag"),
            strip_memory_section=data.get("strip_memory_section", False),
            settings_template=data.get("settings_template"),
            accepted_providers=tuple(data.get("accepted_providers", []))
        )
        backends.append(backend)
    
    if not backends:
        raise ValueError(f"No CLI backends found in {cli_dir}")
    
    # Sort by name for deterministic order
    backends.sort(key=lambda b: b.name)
    
    return CLIRegistry(backends)


@lru_cache(maxsize=1)
def default_registry() -> CLIRegistry:
    """Return the default CLI registry, cached."""
    return load_registry()