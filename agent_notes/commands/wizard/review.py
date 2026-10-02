"""The install review screen: every setting on one screen, pre-filled with
the recommendation (spec 005 FR-001 – FR-013)."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from ...constants import DEFAULT_VAULT_DIR, DEFAULT_VAULT_NAME, Obsidian
from ...domain.capability import KIND_BACKEND, KIND_PROVIDER, KIND_TOGGLE
from ...domain.state import MemoryConfig
from ...services.tui.screen import DIM, YELLOW, elide_middle, tilde
from ...services.tui.widgets import PickItem, ReviewForm, Row, complete_path, cycle_text
from .role_models import Catalog, edit_models, recommended_choices, role_line, roles_for


@dataclass
class InstallChoices:
    """Everything the review collects; the orchestrator hands it to build,
    plan and _execute_install."""

    clis: set = field(default_factory=set)
    role_models: dict = field(default_factory=dict)    # cli -> role -> model id
    role_efforts: dict = field(default_factory=dict)   # cli -> role -> effort
    scope: str = "global"
    copy_mode: bool = False
    skills: list = field(default_factory=list)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    plugins: dict = field(default_factory=dict)        # toggle capability -> on
    profile_label: str = ""
    local_folder: str = ""   # "" = derived from the label
    global_home: str = ""    # "" = derived from the label

    @property
    def folder_overrides(self) -> Optional[dict]:
        if not self.profile_label:
            return None
        return {"claude": self.local_folder or f".claude-{self.profile_label}"}

    @property
    def global_home_override(self) -> str:
        if not self.profile_label:
            return ""
        return self.global_home or f"~/.claude-{self.profile_label}"


@dataclass
class ReviewContext:
    choices: InstallChoices
    ui: Any
    catalog: Catalog
    cli_registry: Any


def add_cli(choices: InstallChoices, catalog: Catalog, backend) -> None:
    choices.clis.add(backend.name)
    if backend.supports("agents"):
        models, efforts = recommended_choices(catalog, backend)
        if models:
            choices.role_models[backend.name] = models
            choices.role_efforts[backend.name] = efforts


def remove_cli(choices: InstallChoices, name: str) -> None:
    choices.clis.discard(name)
    choices.role_models.pop(name, None)
    choices.role_efforts.pop(name, None)


def initial_choices(catalog: Catalog, cli_registry, capabilities=None) -> InstallChoices:
    """The recommended setup (spec 005 FR-003)."""
    from ._common import _get_skill_groups
    from .capabilities import default_capability_registry
    registry = capabilities if capabilities is not None else default_capability_registry()
    choices = InstallChoices()
    available = {backend.name for backend in cli_registry.available()}
    for name in sorted({"claude"} & available):
        add_cli(choices, catalog, cli_registry.get(name))
    choices.skills = [skill for skills in _get_skill_groups().values() for skill in skills]
    choices.plugins = {cap.name: cap.default for cap in registry.by_kind(KIND_TOGGLE)}
    return choices


# ── CLIs and Models ──────────────────────────────────────────────────────────

def backends_rows(ctx: ReviewContext) -> list[Row]:
    choices = ctx.choices

    def cli_lines() -> list[str]:
        labels = [ctx.cli_registry.get(name).label for name in sorted(choices.clis)]
        return [", ".join(labels) if labels else ctx.ui.style("none — select at least one", YELLOW)]

    def edit_clis() -> None:
        items = [(b.label, b.name) for b in sorted(ctx.cli_registry.available(), key=lambda b: b.name)]
        picked = ctx.ui.checklist("CLIs", items, set(choices.clis))
        if picked is None:
            return
        for name in sorted(set(choices.clis) - picked):
            remove_cli(choices, name)
        for name in sorted(picked - set(choices.clis)):
            add_cli(choices, ctx.catalog, ctx.cli_registry.get(name))

    rows = [Row("clis", "CLIs", cli_lines, edit=edit_clis)]
    agent_clis = [ctx.cli_registry.get(name) for name in sorted(choices.clis)
                  if ctx.cli_registry.get(name).supports("agents")]
    for index, backend in enumerate(agent_clis):
        rows.append(models_row(ctx, backend, label="Models" if index == 0 else "",
                               show_cli=len(agent_clis) > 1))
    return rows


def models_row(ctx: ReviewContext, backend, *, label: str, show_cli: bool) -> Row:
    key = f"models:{backend.name}"
    models = ctx.choices.role_models.get(backend.name)
    if not models:
        return Row(key, label, lambda: [
            f"{backend.label}: no compatible models — uses legacy tier resolution"],
            focusable=False)
    efforts = ctx.choices.role_efforts.setdefault(backend.name, {})

    def lines() -> list[str]:
        out = [backend.label] if show_cli else []
        out += [role_line(role, models, efforts) for role in roles_for(backend)
                if role.name in models]
        return out

    return Row(key, label, lines,
               edit=lambda: edit_models(ctx.ui, ctx.catalog, backend, models, efforts))


# ── Scope, install mode, skills ──────────────────────────────────────────────

def _target_path(ctx: ReviewContext) -> str:
    choices = ctx.choices
    names = sorted(choices.clis)
    if not names:
        return ""
    backend = ctx.cli_registry.get(names[0])
    if choices.scope == "global":
        home = choices.global_home_override if backend.name == "claude" else ""
        path = Path(home).expanduser() if home else backend.global_home
    else:
        folders = choices.folder_overrides or {}
        path = Path.cwd() / folders.get(backend.name, backend.local_dir)
    more = f"  +{len(names) - 1} more" if len(names) > 1 else ""
    return elide_middle(tilde(path), 44) + more


def scope_row(ctx: ReviewContext) -> Row:
    choices = ctx.choices
    return Row("scope", "Scope",
               lambda: [f"{cycle_text(choices.scope)}   {ctx.ui.style(_target_path(ctx), DIM)}"],
               options=[("global", "global"), ("local", "local")],
               get=lambda: choices.scope, set=lambda value: setattr(choices, "scope", value))


_MODE_NOTES = {False: "updates when agent-notes updates", True: "standalone files you can edit"}


def mode_row(ctx: ReviewContext) -> Row:
    choices = ctx.choices
    return Row("mode", "Install as",
               lambda: [f"{cycle_text('copy' if choices.copy_mode else 'symlink')}  "
                        f"{ctx.ui.style(_MODE_NOTES[choices.copy_mode], DIM)}"],
               options=[("symlink", False), ("copy", True)],
               get=lambda: choices.copy_mode, set=lambda value: setattr(choices, "copy_mode", value))


def _skill_descriptions() -> dict:
    try:
        from ...registries import default_skill_registry
        return {skill.name: skill.description for skill in default_skill_registry().all()}
    except Exception:
        return {}


def _first_sentence(text: str) -> str:
    return " ".join((text or "").split()).split(". ")[0].rstrip(".")


def skills_row(ctx: ReviewContext) -> Row:
    from ._common import _get_skill_groups
    choices = ctx.choices
    groups = _get_skill_groups()
    process = list(groups.get("process", []))
    domain = [skill for name, skills in groups.items() if name != "process" for skill in skills]

    def lines() -> list[str]:
        chosen = sum(1 for skill in domain if skill in choices.skills)
        return [f"process {len(process)} · domain {chosen} of {len(domain)}"]

    def edit() -> None:
        descriptions = _skill_descriptions()
        items = [(f"{skill} — {_first_sentence(descriptions[skill])}" if descriptions.get(skill)
                  else skill, skill) for skill in domain]
        picked = ctx.ui.checklist("Skills", items, {s for s in domain if s in choices.skills},
                                  fixed=[f"process ({len(process)}) — always included"])
        if picked is not None:
            choices.skills = process + [skill for skill in domain if skill in picked]

    return Row("skills", "Skills", lines, edit=edit if domain else None)


# ── Memory and toggles (shared with config) ──────────────────────────────────

MEMORY_OPTIONS = [("built-in", "local"), ("Obsidian", "obsidian")]


def memory_label(memory: MemoryConfig) -> str:
    """The one name each memory backend has everywhere (spec 005 FR-028)."""
    if memory.backend == "obsidian":
        where = f" · {tilde(memory.path)}" if memory.path else ""
        return f"Obsidian · {memory.strategy}{where}"
    return "built-in"


def _default_vault() -> str:
    from . import _detect_obsidian_vaults
    candidates = _detect_obsidian_vaults()
    return str(candidates[0]) if candidates else str(Path.home() / DEFAULT_VAULT_DIR / DEFAULT_VAULT_NAME)


def memory_row(ui, memory: MemoryConfig) -> Row:
    def set_backend(value: str) -> None:
        memory.backend = value
        if value == "obsidian":
            if not memory.path:
                memory.path = str(Path(_default_vault()).expanduser() / Obsidian.SUBFOLDER)
        else:
            memory.path, memory.strategy = "", "single-brain"

    def lines() -> list[str]:
        if memory.backend != "obsidian":
            return [cycle_text("built-in")]
        return [f"{cycle_text('Obsidian')}   {memory.strategy} · "
                f"{ui.style(tilde(Path(memory.path).parent), DIM)}"]

    def edit() -> None:
        if memory.backend == "obsidian":
            edit_obsidian(ui, memory)

    def line_edit() -> None:
        value = ui.pick("Memory", [PickItem(value, label) for label, value in MEMORY_OPTIONS],
                        current=memory.backend)
        if value:
            set_backend(value)
        edit()

    return Row("memory", "Memory", lines, options=MEMORY_OPTIONS,
               get=lambda: memory.backend, set=set_backend, edit=edit, line_edit=line_edit)


def edit_obsidian(ui, memory: MemoryConfig) -> None:
    """Strategy (←→) and vault path (⏎) for Obsidian memory."""
    from . import _detect_obsidian_vaults, _validate_vault_path

    def vault() -> str:
        return str(Path(memory.path).parent) if memory.path else _default_vault()

    def edit_vault() -> None:
        current = vault()
        notes = [f"detected: {tilde(path)}" for path in _detect_obsidian_vaults()[:3]]
        notes.append(f"notes go in <vault>/{Obsidian.SUBFOLDER}")
        chosen = ui.text("Memory · Obsidian vault", "Vault", current, notes=notes,
                         complete=complete_path,
                         validate=lambda text: _validate_vault_path(text or current)[1])
        if chosen is not None:
            memory.path = str(Path(chosen.strip() or current).expanduser() / Obsidian.SUBFOLDER)

    def rows() -> list[Row]:
        return [
            Row("strategy", "Strategy", lambda: [cycle_text(memory.strategy)],
                options=[("single-brain", "single-brain"), ("per-project", "per-project")],
                get=lambda: memory.strategy,
                set=lambda value: setattr(memory, "strategy", value)),
            Row("vault", "Vault", lambda: [tilde(vault())], edit=edit_vault),
        ]

    ui.form(ReviewForm("Memory · Obsidian", rows, hints="↑↓ move   ←→ change   ⏎ edit   esc done",
                       escape_closes=True, style=ui.style))


def toggle_row(ui, name: str, label: str, plugins: dict) -> Row:
    return Row(f"toggle:{name}", label, lambda: [cycle_text("on" if plugins.get(name) else "off")],
               options=[("off", False), ("on", True)],
               get=lambda: bool(plugins.get(name)),
               set=lambda value: plugins.__setitem__(name, value))


# ── Profile ──────────────────────────────────────────────────────────────────

def profile_row(ctx: ReviewContext) -> Row:
    choices = ctx.choices

    def lines() -> list[str]:
        if not choices.profile_label:
            return ["default"]
        return [f"{choices.profile_label} · {choices.folder_overrides['claude']} · "
                f"{choices.global_home_override}"]

    return Row("profile", "Profile", lines, edit=lambda: edit_profile(ctx))


def edit_profile(ctx: ReviewContext) -> None:
    """Label, local folder and global home; folder and home follow the label
    until edited (spec 005 FR-013)."""
    choices, ui = ctx.choices, ctx.ui

    def set_label(value: str) -> None:
        choices.profile_label = value.strip()
        if not choices.profile_label:
            choices.local_folder = choices.global_home = ""

    def field_row(key, label, shown, current, store) -> Row:
        def edit() -> None:
            value = ui.text(f"Profile · {label}", label, current())
            if value is not None:
                store(value)
        return Row(key, label, lambda: [shown() or ui.style("—", DIM)], edit=edit)

    def rows() -> list[Row]:
        out = [field_row("label", "Label", lambda: choices.profile_label,
                         lambda: choices.profile_label, set_label)]
        if choices.profile_label:
            out.append(field_row("folder", "Local folder",
                                 lambda: choices.folder_overrides["claude"],
                                 lambda: choices.folder_overrides["claude"],
                                 lambda v: setattr(choices, "local_folder", v.strip())))
            out.append(field_row("home", "Global home", lambda: choices.global_home_override,
                                 lambda: choices.global_home_override,
                                 lambda v: setattr(choices, "global_home", v.strip())))
        return out

    ui.form(ReviewForm("Profile", rows, hints="↑↓ move   ⏎ edit   esc done",
                       escape_closes=True, style=ui.style))


# ── The whole screen ─────────────────────────────────────────────────────────

def install_rows(ctx: ReviewContext, capabilities=None) -> Callable[[], list[Row]]:
    """Rows in spec order (FR-002): backend capabilities (CLIs, Models), the
    fixed scope / install-as / skills rows, provider capabilities (Memory),
    toggle capabilities, then Profile. Recomputed on every render."""
    from .capabilities import default_capability_registry
    registry = capabilities if capabilities is not None else default_capability_registry()

    def rows() -> list[Row]:
        out: list[Row] = []
        for cap in registry.by_kind(KIND_BACKEND):
            out += registry.get(cap.name).row(ctx)
        out += [scope_row(ctx), mode_row(ctx), skills_row(ctx)]
        for kind in (KIND_PROVIDER, KIND_TOGGLE):
            for cap in registry.by_kind(kind):
                out += registry.get(cap.name).row(ctx)
        out.append(profile_row(ctx))
        return out

    return rows
