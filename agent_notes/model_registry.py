"""DEPRECATED shim. Import from agent_notes.registries and agent_notes.domain."""
from agent_notes.domain.model import Model  # noqa: F401
from agent_notes.registries.model_registry import ModelRegistry, load_model_registry, default_model_registry  # noqa: F401

# Backward compatibility aliases
default_registry = default_model_registry  # noqa: F401

__all__ = ["Model", "ModelRegistry", "load_model_registry", "default_model_registry", "default_registry"]