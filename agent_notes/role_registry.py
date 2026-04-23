"""DEPRECATED shim. Import from agent_notes.registries and agent_notes.domain."""
from agent_notes.domain.role import Role  # noqa: F401
from agent_notes.registries.role_registry import RoleRegistry, load_role_registry, default_role_registry  # noqa: F401

# Backward compatibility aliases
default_registry = default_role_registry  # noqa: F401

__all__ = ["Role", "RoleRegistry", "load_role_registry", "default_role_registry", "default_registry"]