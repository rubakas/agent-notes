"""`agent-notes config` on the review screen (spec 005 FR-014 – FR-020)."""
from __future__ import annotations

import copy
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

from ..domain.capability import KIND_BACKEND, KIND_PROVIDER, KIND_TOGGLE
from ..services.tui.screen import DIM, YELLOW, tilde
from ..services.tui.keys import TAB
from ..services.tui.widgets import CANCEL, DONE, PickItem, ReviewForm, Row
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


CONFIG_HINTS = "↑↓ move  ⏎ edit  ←→ change  u use ★  tab next install  s save  q quit"
SUBCOMMANDS = ("show", "role-model", "role-effort", "role-agent", "provider", "providers",
               "memory", "cost-report")


def _changes_text(count: int) -> str:
    return f"{count} change{'' if count == 1 else 's'}"


def describe_changes(original, working, ref: InstallRef, plugins_before: dict,
                     plugins_after: dict) -> list[str]:
    """One line per staged edit: `<cli> <role>: <old> → <new>` (FR-017)."""
    from .wizard.review import memory_label
    lines = []
    old_scope, new_scope = ref.get(original), ref.get(working)
    if old_scope is not None and new_scope is not None:
        for cli in sorted(new_scope.clis):
            old, new = old_scope.clis.get(cli), new_scope.clis[cli]
            if old is None:
                continue
            for field, suffix in (("role_models", ""), ("role_efforts", " effort")):
                before, after = getattr(old, field), getattr(new, field)
                for role in sorted(set(before) | set(after)):
                    if before.get(role) != after.get(role):
                        lines.append(f"{cli} {role}{suffix}: {before.get(role) or '—'} → "
                                     f"{after.get(role) or '—'}")
    if original.memory != working.memory:
        lines.append(f"memory: {memory_label(original.memory)} → {memory_label(working.memory)}")
    for name in sorted(set(plugins_before) | set(plugins_after)):
        before, after = bool(plugins_before.get(name)), bool(plugins_after.get(name))
        if before != after:
            lines.append(f"{name}: {'on' if before else 'off'} → {'on' if after else 'off'}")
    return lines


def apply_changes(working, ref: InstallRef, plugins_before: dict, plugins_after: dict) -> None:
    """One state write and one regenerate — of the edited install, not
    whatever regenerate would auto-detect (spec 005 Correction 3)."""
    from ..services.state_store import record_install_state
    from .plugins import disable_plugin, enable_plugin
    from .regenerate import regenerate
    from .wizard.orchestrator import _quiet  # one output-silencing helper, not two
    with _quiet():
        record_install_state(working)
        for name in sorted(plugins_after):
            if bool(plugins_after[name]) != bool(plugins_before.get(name)):
                (enable_plugin if plugins_after[name] else disable_plugin)(name)
        regenerate(scope=ref.scope, project_path=ref.project_path, profile_label=ref.profile_label)


def interactive_config(session_factory=None, cwd: Optional[Path] = None) -> None:
    """`agent-notes config` with no action (spec 005 FR-014)."""
    from ..services.state_store import load_state
    from ..services.tui.session import open_session
    state = load_state()
    refs = list_installs(state) if state is not None else []
    if not refs:
        print("No installation found — run agent-notes install")
        sys.exit(1)
    session = (session_factory or open_session)()
    if session is None:
        from .config import show
        show(state)
        print("\nChange settings with: agent-notes config " + " | ".join(SUBCOMMANDS))
        return
    with session as ui:
        message = _config_review(ui, state, refs, Path(cwd) if cwd else Path.cwd())
    if message:
        print(message)


def _config_review(ui, state, refs: list[InstallRef], cwd: Path) -> str:
    from ..config import get_version
    from ..registries.cli_registry import load_registry
    ref = default_install(refs, cwd)
    if ref is None:
        ref = ui.pick("Which install?", [PickItem(r, r.label(), dim=r.missing) for r in refs])
        if ref is None:
            return ""
    working = copy.deepcopy(state)
    plugins_before = enabled_toggles()
    ctx = ConfigContext(ui, working, ref, Catalog(), load_registry(), dict(plugins_before))

    def changes() -> list[str]:
        return describe_changes(state, working, ctx.ref, plugins_before, ctx.plugins)

    form = ReviewForm(f"AgentNotes {get_version()} · config", config_rows(ctx),
                      context=ref.label(), hints=CONFIG_HINTS, default_command="s",
                      default_label="save", style=ui.style,
                      status=lambda: _changes_text(len(changes())) if changes() else "")

    def save():
        if ctx.ref.missing:
            form.message = "this install's folder no longer exists"
            return None
        diff = changes()
        if not diff:
            form.message = "no changes to save"
            return None
        if not ui.confirm(form, f"Apply {_changes_text(len(diff))}?", diff):
            return None
        ui.progress(form, "Saving…")
        try:
            apply_changes(working, ctx.ref, plugins_before, ctx.plugins)
        except (Exception, SystemExit) as e:
            form.message = f"Save failed: {e}"
            return None
        form.value = f"Saved {_changes_text(len(diff))}. Restart your AI CLI to pick up changes."
        return DONE

    def quit_():
        count = len(changes())
        if count and not ui.confirm(form, f"Discard {_changes_text(count)}?"):
            return None
        return CANCEL

    def next_install():
        if len(refs) < 2:
            return None
        if changes():
            form.message = "save or discard changes before switching"
            return None
        ctx.ref = refs[(refs.index(ctx.ref) + 1) % len(refs)]
        form.context = ctx.ref.label()
        return None

    def use_recommended():
        moved = upgrade_flagged(ctx)
        form.message = (f"{moved} pin{'' if moved == 1 else 's'} moved to ★" if moved
                        else "nothing flagged")
        return None

    form.commands.update({"s": save, "q": quit_, TAB: next_install, "u": use_recommended})
    return form.value if ui.form(form) == DONE else ""


def render_show(state, width: int = 100, style=None) -> list[str]:
    """`config show`: the config screen without cursor or footer — shared
    settings once, then each install (spec 005 FR-020)."""
    from types import SimpleNamespace
    from ..registries.cli_registry import load_registry
    from ..services.tui.screen import BOLD, Style
    style = style or Style(False)
    refs = list_installs(state)
    if not refs:
        return ["(no installation found)"]
    ui = SimpleNamespace(style=style)
    catalog, clis, plugins = Catalog(), load_registry(), enabled_toggles()

    def static(ref, part) -> list[str]:
        ctx = ConfigContext(ui, state, ref, catalog, clis, plugins)
        return ReviewForm("", config_rows(ctx, part=part), style=style).render(
            width, 10_000, chrome=False)

    lines = static(refs[0], "global")
    for ref in refs:
        lines += ["", style(ref.label(), BOLD)] + static(ref, "install")
    return lines
