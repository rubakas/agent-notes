"""Load and merge user config for agent role/model overrides and prompt patches."""
from __future__ import annotations
from pathlib import Path
from typing import Optional
import yaml


def config_path() -> Path:
    xdg = Path.home() / ".config" / "agent-notes" / "config.yaml"
    legacy = Path.home() / ".agent-notes.yaml"
    if xdg.exists():
        return xdg
    if legacy.exists():
        return legacy
    return xdg  # canonical write location


def load_user_config(path: Optional[Path] = None) -> dict:
    """Return user config dict. Empty dict if file missing."""
    p = path or config_path()
    if not p.exists():
        return {}
    try:
        data = yaml.safe_load(p.read_text())
        return data or {}
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in {p}: {e}") from e


def resolve_agent_role(agent_name: str, default_role: str, config: dict) -> str:
    """Return effective role, applying user override if present."""
    return config.get("agent_roles", {}).get(agent_name, default_role)


def resolve_role_model(role: str, backend_name: str, config: dict) -> Optional[str]:
    """Return user-specified model ID for a role+backend, or None."""
    return config.get("role_models", {}).get(backend_name, {}).get(role)


def get_patch(agent_name: str, config: dict) -> Optional[str]:
    """Return patch text to append to agent prompt, or None."""
    return config.get("patches", {}).get(agent_name)


def merge_configs(base: dict, override: dict) -> dict:
    """Merge override on top of base. Nested dicts are merged; patches are concatenated."""
    result = dict(base)
    for key, value in override.items():
        if key == "patches" and key in result:
            # Concatenate patches from both configs
            merged_patches = dict(result[key])
            for agent, patch in value.items():
                if agent in merged_patches:
                    merged_patches[agent] = merged_patches[agent].rstrip() + "\n\n" + patch
                else:
                    merged_patches[agent] = patch
            result[key] = merged_patches
        elif isinstance(value, dict) and key in result and isinstance(result[key], dict):
            result[key] = {**result[key], **value}
        else:
            result[key] = value
    return result
