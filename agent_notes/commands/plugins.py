"""plugins command — list and manage agent-notes plugins."""

from __future__ import annotations

from ..registries.plugin_registry import default_plugin_registry
from ..services.user_config import config_path, load_user_config, save_user_config


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


def _set_enabled(name: str, value: bool) -> None:
    """Write enabled_plugins.<name> = value to user config. Errors on unknown plugin."""
    reg = default_plugin_registry()
    if name not in reg.names():
        known = ", ".join(reg.names()) if reg.names() else "(none)"
        print(f"Unknown plugin: {name!r}. Known: {known}")
        return
    path = config_path()
    cfg = load_user_config(path)
    cfg.setdefault("enabled_plugins", {})[name] = value
    save_user_config(cfg, path)
    verb = "enabled" if value else "disabled"
    print(f"Plugin {name!r} {verb}. Run 'agent-notes install' to apply.")


def enable_plugin(name: str) -> None:
    """Enable a plugin by name."""
    _set_enabled(name, True)


def disable_plugin(name: str) -> None:
    """Disable a plugin by name."""
    _set_enabled(name, False)


def info_plugin(name: str) -> None:
    """Print details for a plugin: description, default, and contributed surfaces."""
    reg = default_plugin_registry()
    if name not in reg.names():
        known = ", ".join(reg.names()) if reg.names() else "(none)"
        print(f"Unknown plugin: {name!r}. Known: {known}")
        return
    p = reg.get(name)
    print(f"{p.name} — {p.description}")
    print(f"  default:  {'on' if p.default else 'off'}")
    print(f"  skills:   {', '.join(p.skills) or '—'}")
    print(f"  includes: {', '.join(p.includes) or '—'}")
    print(f"  hooks:    {', '.join(h.event for h in p.hooks) or '—'}")
    print(f"  allow:    {', '.join(a.value for a in p.allow) or '—'}")
