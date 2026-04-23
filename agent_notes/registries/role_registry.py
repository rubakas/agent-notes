"""Role registry for loading and managing role descriptors."""

from __future__ import annotations
from pathlib import Path
from typing import Optional
from functools import lru_cache

from ..config import DATA_DIR
from ..domain.role import Role
from ._base import load_yaml_file


class RoleRegistry:
    def __init__(self, roles: list[Role]):
        self._by_name: dict[str, Role] = {r.name: r for r in roles}

    def all(self) -> list[Role]:
        return sorted(self._by_name.values(), key=lambda r: r.name)

    def get(self, name: str) -> Role:
        if name not in self._by_name:
            raise KeyError(f"Role '{name}' not found in registry")
        return self._by_name[name]

    def names(self) -> list[str]:
        return sorted(self._by_name.keys())


def load_role_registry(roles_dir: Optional[Path] = None) -> RoleRegistry:
    if roles_dir is None:
        roles_dir = DATA_DIR / "roles"
    
    if not roles_dir.is_dir():
        raise ValueError(f"Roles directory not found: {roles_dir}")
    
    roles: list[Role] = []
    for yaml_file in sorted(roles_dir.glob("*.yaml")):
        try:
            data = load_yaml_file(yaml_file)
        except ValueError as e:
            # Maintain backward compatibility for error messages
            if "Invalid YAML" in str(e):
                raise ValueError(f"Invalid YAML in {yaml_file.name}: {str(e).split(': ', 1)[1]}")
            raise
        
        # Validate required fields with backward-compatible error messages
        for field_name in ["name", "label", "description", "typical_class"]:
            if field_name not in data:
                raise ValueError(f"Missing field '{field_name}' in {yaml_file.name}")
        
        roles.append(Role(
            name=data["name"],
            label=data["label"],
            description=data["description"],
            typical_class=data["typical_class"],
            color=data.get("color", ""),
        ))
    
    return RoleRegistry(roles)


@lru_cache(maxsize=1)
def default_role_registry() -> RoleRegistry:
    return load_role_registry()