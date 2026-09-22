"""Model registry for loading and managing model descriptors."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional
from functools import lru_cache

from ..config import DATA_DIR
from ..domain.model import Model
from ._base import load_yaml_file, require_fields


def _natural_key(model_id: str) -> tuple:
    """Sort key that orders version numbers numerically, not lexicographically.

    Without this, `claude-opus-4-10` sorts before `claude-opus-4-8` because "1" < "8".
    Each chunk is tagged (0, int) or (1, str) so numeric and text chunks never compare
    against each other and raise TypeError.

    Used only for human-facing id listings; automatic selection is driven by the
    catalog's frontier-first order, not by id sorting.
    """
    return tuple(
        (0, int(part)) if part.isdigit() else (1, part)
        for part in re.split(r"(\d+)", model_id)
        if part
    )


def _frontier_key(model: Model) -> tuple:
    """Global frontier-first order across every provider.

    seed.json ranks each provider independently, so concatenating provider
    blocks yields two separate descending runs. Sorting on the benchmark score
    itself merges them: rated models by capability descending, unrated last
    (keeping their relative catalog order, since the sort is stable).
    """
    return (model.coding_index is None, -(model.coding_index or 0.0))


class ModelRegistry:
    def __init__(self, models: list[Model]):
        ordered = sorted(models, key=_frontier_key)
        self._by_id: dict[str, Model] = {m.id: m for m in ordered}

    def all(self) -> list[Model]:
        """Every model, frontier first — see :func:`_frontier_key`.

        This is the single ordering every consumer inherits: automatic
        selection, the numbered `config role-model` list, and `list models`.
        """
        return list(self._by_id.values())

    def get(self, model_id: str) -> Model:
        if model_id not in self._by_id:
            raise KeyError(f"Model '{model_id}' not found in registry")
        return self._by_id[model_id]

    def ids(self) -> list[str]:
        return sorted(self._by_id.keys(), key=_natural_key)


def _load_from_yaml_dir(models_dir: Path) -> ModelRegistry:
    """Load all *.yaml files from models_dir into a ModelRegistry."""
    if not models_dir.is_dir():
        raise ValueError(f"Models directory not found: {models_dir}")

    models: list[Model] = []
    for yaml_file in sorted(models_dir.glob("*.yaml")):
        try:
            data = load_yaml_file(yaml_file)
        except ValueError as e:
            if "Invalid YAML" in str(e):
                raise ValueError(f"Invalid YAML in {yaml_file.name}: {str(e).split(': ', 1)[1]}")
            raise

        require_fields(
            data, ["id", "label", "family", "class", "aliases"], yaml_file,
            msg_template="Missing field '{field}' in {filename}",
        )

        models.append(Model(
            id=data["id"],
            label=data["label"],
            family=data["family"],
            model_class=data["class"],
            aliases=data["aliases"],
            capabilities=data.get("capabilities", {}) or {},
            deprecated=bool(data.get("deprecated", False)),
            rank=int(data.get("rank", 0)),
            coding_index=data.get("coding_index"),
            intelligence_index=data.get("intelligence_index"),
            price_in=data.get("price_in"),
            price_out=data.get("price_out"),
            context_length=data.get("context_length"),
            created_at=data.get("created_at"),
        ))

    return ModelRegistry(models)


def load_model_registry(models_dir: Optional[Path] = None) -> ModelRegistry:
    """Load models from the catalog (seed.json + rules.yaml) by default.

    When models_dir is explicitly provided the legacy YAML-glob path is used
    instead, which is useful for tests that build fixture registries on disk.
    """
    if models_dir is not None:
        return _load_from_yaml_dir(models_dir)

    from .catalog_loader import load_catalog
    return ModelRegistry(load_catalog())


@lru_cache(maxsize=1)
def default_model_registry() -> ModelRegistry:
    """Cached singleton."""
    return load_model_registry()