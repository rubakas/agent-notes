"""DEPRECATED shim. Import from agent_notes.registries and agent_notes.domain."""
from agent_notes.domain.cli_backend import CLIBackend  # noqa: F401
from agent_notes.registries.cli_registry import CLIRegistry, load_registry, default_registry  # noqa: F401
__all__ = ["CLIBackend", "CLIRegistry", "load_registry", "default_registry"]