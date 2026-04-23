"""Shared helpers used by all registries."""
from __future__ import annotations
from pathlib import Path
from typing import Any
import yaml


def load_yaml_file(path: Path) -> dict[str, Any]:
    """Load a single YAML file, wrapping errors with the filename."""
    try:
        return yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in {path}: {e}")
    except Exception as e:
        raise ValueError(f"Failed to read {path}: {e}")


def require_fields(data: dict, required: list[str], source: Path) -> None:
    """Validate that required top-level fields are present; raise ValueError on miss."""
    for f in required:
        if f not in data:
            raise ValueError(f"Missing required field '{f}' in {source}")


def load_yaml_dir(dir_path: Path, required_fields: list[str] | None = None) -> list[tuple[Path, dict]]:
    """Load every *.yaml in dir_path (sorted). Returns list of (path, data) pairs.
    Raises ValueError if dir missing or any YAML invalid.
    """
    if not dir_path.exists():
        raise ValueError(f"Registry directory not found: {dir_path}")
    items = []
    for yaml_file in sorted(dir_path.glob("*.yaml")):
        data = load_yaml_file(yaml_file)
        if required_fields:
            require_fields(data, required_fields, yaml_file)
        items.append((yaml_file, data))
    return items