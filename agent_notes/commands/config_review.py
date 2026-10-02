"""`agent-notes config` on the review screen (spec 005 FR-014 – FR-020)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

from ..domain.capability import KIND_BACKEND, KIND_PROVIDER, KIND_TOGGLE
from ..services.tui.screen import DIM, YELLOW, tilde
from ..services.tui.widgets import PickItem, Row
from .wizard.role_models import (
    Catalog, default_effort, edit_models, initial_model, role_line, roles_for, starred_model,
)


@dataclass(frozen=True)
class InstallRef:
    """Where an install lives: enough to find its state and regenerate it."""

    scope: str                      # "global" | "local"
    project_path: Optional[Path]    # local only
    profile_label: str = ""

    @property
    def missing(self) -> bool:
        return self.scope == "local" and not self.project_path.is_dir()

    def label(self) -> str:
        where = "global" if self.scope == "global" else f"local · {tilde(self.project_path)}"
        if self.profile_label:
            where += f" · {self.profile_label}"
        return where + (" (missing)" if self.missing else "")

    def get(self, state):
        from ..services.state_store import get_scope
        return get_scope(state, self.scope, self.project_path, self.profile_label)


def _split_local_key(key: str) -> tuple[Path, str]:
    """A local key is 'path' or 'path#profile' (state_store._local_key). A '#'
    that belongs to an existing folder's name stays part of the path."""
    path, sep, label = key.rpartition("#")
    if not sep or Path(key).is_dir():
        return Path(key), ""
    return Path(path), label


def list_installs(state) -> list[InstallRef]:
    refs = []
    if state.global_install is not None:
        refs.append(InstallRef("global", None))
    refs += [InstallRef("global", None, label) for label in sorted(state.global_installs)]
    for key in sorted(state.local_installs):
        path, label = _split_local_key(key)
        refs.append(InstallRef("local", path, label))
    return refs


def default_install(refs: list[InstallRef], cwd: Path) -> Optional[InstallRef]:
    """The current folder's install, else the global one, else the only one.
    None means ask (spec 005 FR-014). A missing folder is never chosen."""
    cwd = Path(cwd).resolve()
    here = [r for r in refs if r.scope == "local" and r.project_path.resolve() == cwd]
    for candidates in ([r for r in here if not r.profile_label], here,
                       [r for r in refs if r.scope == "global" and not r.profile_label]):
        if candidates:
            return candidates[0]
    if len(refs) == 1 and not refs[0].missing:
        return refs[0]
    return None


@dataclass
class ConfigContext:
    ui: Any
    state: Any                 # a working copy of state.json; saved only on `s`
    ref: InstallRef
    catalog: Catalog
    cli_registry: Any
    plugins: dict              # toggle capability -> on (staged)

    def scope_state(self):
        return self.ref.get(self.state)


def pin_flag(catalog, backend, role, model_id: str) -> str:
    """'★' when the pin is the recommendation; '★ <id>' when it differs;
    '⚠ deprecated  ★ <id>' or '⚠ unknown model  ★ <id>' when it should move."""
    star = starred_model(catalog, backend, role)
    recommended = f"★ {star.id}" if star is not None else ""
    model = catalog.get(model_id)
    if model is None:
        return f"⚠ unknown model  {recommended}".rstrip()
    if model.deprecated:
        return f"⚠ deprecated  {recommended}".rstrip()
    if star is not None and star.id == model_id:
        return "★"
    return recommended


def is_flagged(catalog, model_id: str) -> bool:
    model = catalog.get(model_id)
    return model is None or model.deprecated


def _agent_backends(ctx) -> list:
    backends = []
    for name in sorted(ctx.scope_state().clis):
        try:
            backend = ctx.cli_registry.get(name)
        except KeyError:
            continue
        if backend.supports("agents"):
            backends.append(backend)
    return backends


def config_models_rows(ctx: ConfigContext) -> list[Row]:
    style = ctx.ui.style
    backends = _agent_backends(ctx)
    rows = []
    for index, backend in enumerate(backends):
        state = ctx.scope_state().clis[backend.name]
        models, efforts = state.role_models, state.role_efforts

        def lines(backend=backend, models=models, efforts=efforts) -> list[str]:
            out = [backend.label] if len(backends) > 1 else []
            for role in roles_for(backend):
                if role.name in models:
                    flag = pin_flag(ctx.catalog, backend, role, models[role.name])
                    color = YELLOW if flag.startswith("⚠") else DIM
                    out.append(f"{role_line(role, models, efforts)}   {style(flag, color)}")
            return out or [style("no pins — the recommendation applies at build time", DIM)]

        rows.append(Row(f"models:{backend.name}", "Models" if index == 0 else "", lines,
                        edit=(lambda b=backend, m=models, e=efforts:
                              edit_models(ctx.ui, ctx.catalog, b, m, e)) if models else None))
    return rows


def upgrade_flagged(ctx: ConfigContext) -> int:
    """Move every ⚠ pin to its ★ model and default effort (the `u` key)."""
    moved = 0
    for backend in _agent_backends(ctx):
        state = ctx.scope_state().clis[backend.name]
        for role in roles_for(backend):
            model_id = state.role_models.get(role.name)
            if model_id is None or not is_flagged(ctx.catalog, model_id):
                continue
            target = (starred_model(ctx.catalog, backend, role)
                      or initial_model(ctx.catalog, backend, role))
            if target is None:
                continue
            state.role_models[role.name] = target.id
            effort = default_effort(backend, target, role)
            if effort:
                state.role_efforts[role.name] = effort
            else:
                state.role_efforts.pop(role.name, None)
            moved += 1
    return moved


def _provider_names() -> list[str]:
    from ..registries.provider_registry import default_provider_registry
    from ..services import credentials
    return sorted(set(default_provider_registry().names()) | set(credentials.list_providers()))


def api_keys_row(ctx: ConfigContext) -> Row:
    """Status only — a key value is never rendered, printed or logged (FR-018).
    Keys are written when entered: they live in the credentials file, outside
    state.json (spec 005 Correction 2)."""
    from ..services import credentials

    def lines() -> list[str]:
        return [" · ".join(f"{name} {'✓' if credentials.is_configured(name) else '—'}"
                           for name in _provider_names())]

    def edit() -> None:
        items = [PickItem(name, f"{name:<14} {'key stored' if credentials.is_configured(name) else 'no key'}")
                 for name in _provider_names()]
        name = ctx.ui.pick("API keys", items)
        if not name:
            return
        key = ctx.ui.text(f"API key · {name}", "Key", "", secret=True,
                          notes=["input hidden · empty keeps the current key"])
        if not key or not key.strip():
            return
        credentials.set_value(name, "api_key", key.strip())
        base = ctx.ui.text(f"API key · {name}", "base_url", "", notes=["optional · empty to skip"])
        if base and base.strip():
            credentials.set_value(name, "base_url", base.strip())

    return Row("api-keys", "API keys", lines, edit=edit)


def reinstall_row(ctx: ConfigContext) -> Row:
    def lines() -> list[str]:
        scope_state = ctx.scope_state()
        labels = []
        for name in sorted(scope_state.clis):
            try:
                labels.append(ctx.cli_registry.get(name).label)
            except KeyError:
                labels.append(name)
        return [f"{', '.join(labels)} · {scope_state.mode} · change with: install --reconfigure"]

    return Row("reinstall", "Install", lines, focusable=False)


def config_rows(ctx: ConfigContext, *, part: str = "all", capabilities=None) -> Callable[[], list[Row]]:
    """Config-mode rows. *part*: "install" (Models and the read-only line),
    "global" (Memory, toggles, API keys), or "all"."""
    from .wizard.capabilities import default_capability_registry
    registry = capabilities if capabilities is not None else default_capability_registry()

    def from_kind(kind) -> list[Row]:
        out = []
        for cap in registry.by_kind(kind):
            behaviour = registry.get(cap.name)
            if behaviour.config_row is not None:
                out += behaviour.config_row(ctx)
        return out

    def rows() -> list[Row]:
        out: list[Row] = []
        if part in ("all", "install"):
            out += from_kind(KIND_BACKEND)
        if part in ("all", "global"):
            out += from_kind(KIND_PROVIDER) + from_kind(KIND_TOGGLE)
            out.append(api_keys_row(ctx))
        if part in ("all", "install"):
            out.append(reinstall_row(ctx))
        return out

    return rows


def enabled_toggles(capabilities=None) -> dict[str, bool]:
    """Each toggle capability's saved on/off, from the plugin config."""
    from ..registries.plugin_registry import default_plugin_registry
    from ..services.user_config import load_user_config
    from .wizard.capabilities import default_capability_registry
    registry = capabilities if capabilities is not None else default_capability_registry()
    on = {plugin.name for plugin in default_plugin_registry().enabled(load_user_config())}
    return {cap.name: cap.name in on for cap in registry.by_kind(KIND_TOGGLE)}
