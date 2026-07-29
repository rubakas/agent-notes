"""plugins command — list and manage agent-notes plugins."""

from __future__ import annotations

from ..registries.plugin_registry import default_plugin_registry
from ..services.user_config import config_path, load_user_config


def list_plugins() -> None:
    """List all available plugins with their enabled/disabled status."""
    registry = default_plugin_registry()
    cfg_path = config_path()
    config = load_user_config(cfg_path)
    plugins = registry.all()
    if not plugins:
        return
    chosen = config.get("enabled_plugins") or {}
    for p in sorted(plugins, key=lambda p: p.name):
        enabled = chosen.get(p.name, p.default)
        status = "on" if enabled else "off"
        print(f"  {p.name:<20} [{status}]  {p.description}")
