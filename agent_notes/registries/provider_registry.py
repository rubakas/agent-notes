"""Provider registry for loading and managing provider effort descriptors."""

from __future__ import annotations
from pathlib import Path
from typing import Optional
from functools import lru_cache

from ..config import DATA_DIR
from ..domain.provider import Provider
from ._base import load_yaml_file, require_fields


class ProviderRegistry:
    def __init__(self, providers: list[Provider]):
        self._by_name: dict[str, Provider] = {p.name: p for p in providers}

    def all(self) -> list[Provider]:
        return sorted(self._by_name.values(), key=lambda p: p.name)

    def get(self, name: str) -> Provider:
        if name not in self._by_name:
            raise KeyError(f"Provider '{name}' not found in registry")
        return self._by_name[name]

    def names(self) -> list[str]:
        return sorted(self._by_name.keys())


def load_provider_registry(providers_dir: Optional[Path] = None) -> ProviderRegistry:
    if providers_dir is None:
        providers_dir = DATA_DIR / "providers"

    if not providers_dir.is_dir():
        raise ValueError(f"Providers directory not found: {providers_dir}")

    providers: list[Provider] = []
    for yaml_file in sorted(providers_dir.glob("*.yaml")):
        try:
            data = load_yaml_file(yaml_file)
        except ValueError as e:
            # Maintain backward compatibility for error messages
            if "Invalid YAML" in str(e):
                raise ValueError(f"Invalid YAML in {yaml_file.name}: {str(e).split(': ', 1)[1]}")
            raise

        require_fields(
            data, ["name", "efforts", "default_effort"], yaml_file,
            msg_template="Missing field '{field}' in {filename}",
        )

        providers.append(Provider(
            name=data["name"],
            efforts=tuple(data["efforts"]),
            default_effort=data["default_effort"],
        ))

    return ProviderRegistry(providers)


@lru_cache(maxsize=1)
def default_provider_registry() -> ProviderRegistry:
    return load_provider_registry()
