"""Model registry for loading and managing model descriptors."""

from __future__ import annotations

from pathlib import Path
from typing import Optional
from functools import lru_cache

from ..config import DATA_DIR
from ..domain.model import Model
from ._base import load_yaml_file


class ModelRegistry:
    def __init__(self, models: list[Model]):
        self._by_id: dict[str, Model] = {m.id: m for m in models}

    def all(self) -> list[Model]:
        return sorted(self._by_id.values(), key=lambda m: m.id)

    def get(self, model_id: str) -> Model:
        if model_id not in self._by_id:
            raise KeyError(f"Model '{model_id}' not found in registry")
        return self._by_id[model_id]

    def ids(self) -> list[str]:
        return sorted(self._by_id.keys())

    def by_class(self, class_name: str) -> list[Model]:
        """All models with model_class == class_name, sorted by id."""
        return sorted(
            [m for m in self._by_id.values() if m.model_class == class_name],
            key=lambda m: m.id,
        )

    def compatible_with_providers(self, providers: list[str]) -> list[Model]:
        """Return models that have at least one alias matching providers list.
        Useful for CLI filtering: pass cli.accepted_providers."""
        result = []
        for m in self._by_id.values():
            if any(p in m.aliases for p in providers):
                result.append(m)
        return sorted(result, key=lambda m: m.id)


def load_model_registry(models_dir: Optional[Path] = None) -> ModelRegistry:
    """Load all *.yaml files from models_dir (default: data/models/)."""
    if models_dir is None:
        models_dir = DATA_DIR / "models"
    
    if not models_dir.is_dir():
        raise ValueError(f"Models directory not found: {models_dir}")
    
    models: list[Model] = []
    for yaml_file in sorted(models_dir.glob("*.yaml")):
        try:
            data = load_yaml_file(yaml_file)
        except ValueError as e:
            # Maintain backward compatibility for error messages  
            if "Invalid YAML" in str(e):
                raise ValueError(f"Invalid YAML in {yaml_file.name}: {str(e).split(': ', 1)[1]}")
            raise
        
        # Validate required fields with backward-compatible error messages
        for field_name in ["id", "label", "family", "class", "aliases"]:
            if field_name not in data:
                raise ValueError(f"Missing field '{field_name}' in {yaml_file.name}")
        
        models.append(Model(
            id=data["id"],
            label=data["label"],
            family=data["family"],
            model_class=data["class"],
            aliases=data["aliases"],
            pricing=data.get("pricing", {}) or {},
            capabilities=data.get("capabilities", {}) or {},
        ))
    
    return ModelRegistry(models)


@lru_cache(maxsize=1)
def default_model_registry() -> ModelRegistry:
    """Cached singleton."""
    return load_model_registry()