"""Registry of agent-notes plugins from data/plugins/*/plugin.yaml."""
from __future__ import annotations
from pathlib import Path
from typing import Optional
from functools import lru_cache

from ..config import PLUGINS_DIR
from ..domain.plugin import Plugin, PluginHook, PluginAllow
from ..services.stability import normalize_stability, is_visible, enabled_wip
from ._base import load_yaml_file, require_fields


class PluginRegistry:
    def __init__(self, plugins: list[Plugin]):
        self._plugins = plugins
        self._by_name = {p.name: p for p in plugins}

    def all(self) -> list[Plugin]:
        return list(self._plugins)

    def available(self, override=None) -> list[Plugin]:
        ov = enabled_wip() if override is None else override
        return [p for p in self.all() if is_visible(p.stability, p.name, ov)]

    def get(self, name: str) -> Plugin:
        if name not in self._by_name:
            raise KeyError(f"Plugin '{name}' not found in registry")
        return self._by_name[name]

    def names(self) -> list[str]:
        return sorted(self._by_name)

    def enabled(self, config: dict) -> list[Plugin]:
        ov = enabled_wip()
        chosen = config.get("enabled_plugins") or {}
        return [
            p for p in self._plugins
            if chosen.get(p.name, p.default) and is_visible(p.stability, p.name, ov)
        ]

    def owned_includes(self) -> set:
        """Return the set of include names declared by any plugin (enabled or not)."""
        out = set()
        for p in self._plugins:
            out.update(p.includes)
        return out

    def active_includes(self, config: dict) -> set:
        """Return the set of include names declared by currently enabled plugins."""
        out = set()
        for p in self.enabled(config):
            out.update(p.includes)
        return out


def _parse_bool_default(value, source: Path) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip().lower() in ("on", "off"):
        return value.strip().lower() == "on"
    raise ValueError(f"'default' must be on/off in {source}, got {value!r}")


def _plugin_from(path: Path, data: dict) -> Plugin:
    require_fields(data, ["name", "description", "default"], path)
    name = data["name"]
    if name != path.parent.name:
        raise ValueError(f"Plugin name '{name}' != directory '{path.parent.name}' in {path}")
    hooks = tuple(
        PluginHook(event=h["event"], command=h["command"],
                   matcher=h.get("matcher"), requires=h.get("requires"))
        for h in (data.get("hooks") or [])
    )
    allow = tuple(
        PluginAllow(value=a["value"], requires=a.get("requires"))
        for a in (data.get("allow") or [])
    )
    return Plugin(
        name=name,
        description=data["description"],
        default=_parse_bool_default(data["default"], path),
        path=path.parent,
        skills=tuple(data.get("skills") or ()),
        agents=tuple(data.get("agents") or ()),
        rules=tuple(data.get("rules") or ()),
        includes=tuple(data.get("includes") or ()),
        hooks=hooks,
        allow=allow,
        stability=normalize_stability(data.get("stability"), path),
    )


def load_plugin_registry(plugins_dir: Optional[Path] = None) -> PluginRegistry:
    root = plugins_dir if plugins_dir is not None else PLUGINS_DIR
    if not root.exists():
        return PluginRegistry([])
    plugins = []
    for d in sorted(root.iterdir()):
        manifest = d / "plugin.yaml"
        if d.is_dir() and manifest.exists():
            plugins.append(_plugin_from(manifest, load_yaml_file(manifest)))
    return PluginRegistry(plugins)


@lru_cache(maxsize=1)
def default_plugin_registry() -> PluginRegistry:
    return load_plugin_registry()
