"""Install flow: recommended values → review screen → quiet build → confirm →
install (spec 005 FR-001, FR-005, FR-024, FR-026)."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from ...config import Color, get_version
from ...services.tui.screen import tilde
from ...services.tui.session import open_session
from ...services.tui.widgets import CANCEL, DONE, ReviewForm
from ..build import build
from .._install_helpers import count_agents, count_skills
from ._common import _count_rules
from .execute import _execute_install
from .review import InstallChoices, ReviewContext, initial_choices, install_rows
from .role_models import Catalog

log = logging.getLogger(__name__)

HINTS = "↑↓ move   ⏎ edit   ←→ change   i install   q quit"


def interactive_install(session_factory=open_session) -> None:
    """Run the install review."""
    try:
        _interactive_install(session_factory)
    except (KeyboardInterrupt, EOFError):  # Ctrl-C, or the terminal closed
        print(f"\n\n  {Color.YELLOW}Cancelled.{Color.NC}")


def _interactive_install(session_factory=open_session) -> None:
    from ...registries.cli_registry import load_registry
    cli_registry = load_registry()
    catalog = Catalog()
    choices = initial_choices(catalog, cli_registry)
    session = session_factory()
    if session is None:
        # stdin or stdout is not a terminal: nothing may prompt (FR-026).
        print("No terminal attached — installing the recommended setup.")
        error = _render(choices, with_selections=True)
        if error:
            print(f"{Color.RED}Build failed — {error}{Color.NC}")
            restore_error = _render(choices, with_selections=False)
            if restore_error:
                print(f"{Color.YELLOW}Restore failed — run agent-notes regenerate: "
                      f"{restore_error}{Color.NC}")
            return
        _install(choices)
        return
    with session as ui:
        confirmed = _review(ui, choices, catalog, cli_registry)
    if confirmed:
        _install(choices)
    else:
        print("Installation cancelled.")


def _counts(cli_registry) -> str:
    agents = sum(count_agents(b) for b in cli_registry.all() if b.supports("agents"))
    return f"{agents} agents · {count_skills()} skills · {_count_rules()} rules"


def _review(ui, choices: InstallChoices, catalog: Catalog, cli_registry) -> bool:
    ctx = ReviewContext(choices, ui, catalog, cli_registry)
    form = ReviewForm(f"AgentNotes {get_version()} · install", install_rows(ctx),
                      context=_counts(cli_registry), hints=HINTS,
                      default_command="i", default_label="install", style=ui.style)

    def install_command() -> Optional[str]:
        if not choices.clis:
            form.message = "select at least one CLI"
            return None
        ui.progress(form, "Building…")
        error, confirmed = None, False
        try:
            error = _render(choices, with_selections=True)
            if not error:
                question, lines = _plan_summary(choices, cli_registry)
                confirmed = ui.confirm(form, question, lines)
        finally:
            # Anything but a yes — a failed build, a no, Ctrl-C, line mode's
            # exit on Ctrl-D — must not leave this run's picks in dist/.
            restore_error = None if confirmed else _render(choices, with_selections=False)
        if confirmed:
            return DONE
        # The instruction leads: a long error is what the width cuts.
        if error and restore_error:
            form.message = (f"Build and restore failed — run agent-notes regenerate: "
                            f"{error}; {restore_error}")
        elif error:
            form.message = f"Build failed — {error}"
        elif restore_error:
            form.message = f"Restore failed — run agent-notes regenerate: {restore_error}"
        return None

    form.commands.update({"i": install_command, "q": lambda: CANCEL})
    return ui.form(form) == DONE


def _render(choices: InstallChoices, *, with_selections: bool) -> Optional[str]:
    """Render dist/ quietly. Returns the error, if any.

    *with_selections*: this run's picks, before confirming — the file count
    must come from what this install will write. Without: back to the
    persisted state pins, after anything but a yes — existing symlink installs
    would otherwise keep serving the rejected (or half-written) picks."""
    from ...services.fs import quiet_output, silent_ops
    picks = (dict(role_models=choices.role_models, role_efforts=choices.role_efforts)
             if with_selections else {})
    try:
        with silent_ops(), quiet_output():
            build(**picks, scope=choices.scope,
                  project_path=Path.cwd() if choices.scope == "local" else None,
                  profile_label=choices.profile_label)
    except Exception as e:
        return str(e) or type(e).__name__
    return None


def _plan_summary(choices: InstallChoices, cli_registry) -> tuple[str, list[str]]:
    """The confirmation question and up to five backup lines."""
    from ...services.installer import plan_install, summarize_plan
    try:
        # skills pass as-is: an empty selection must plan zero skills (None
        # would mean "all skills", which the install will not write).
        manifest = plan_install(scope=choices.scope, registry=cli_registry,
                                selected_clis=set(choices.clis), selected_skills=choices.skills,
                                copy_mode=choices.copy_mode,
                                folder_overrides=choices.folder_overrides,
                                global_home_override=choices.global_home_override or None)
        summary = summarize_plan(manifest)
    except Exception:
        log.debug("plan_install failed during pre-flight", exc_info=True)
        return "Install?", []
    backups = summary.overwrites
    lines = [f"backup  {tilde(a.dst)}  →  {tilde(a.backup_path)}" for a in backups[:5]]
    if len(backups) > 5:
        lines.append(f"… {len(backups) - 5} more")
    return f"Install {len(summary.to_install)} files ({len(backups)} backed up)?", lines


def _install(choices: InstallChoices) -> None:
    _execute_install(
        clis=choices.clis,
        scope=choices.scope,
        copy_mode=choices.copy_mode,
        selected_skills=choices.skills,
        role_models=choices.role_models,
        role_efforts=choices.role_efforts,
        memory_backend=choices.memory.backend,
        memory_path=choices.memory.path,
        memory_strategy=choices.memory.strategy,
        profile_label=choices.profile_label,
        folder_overrides=choices.folder_overrides,
        global_home_override=choices.global_home_override,
        enabled_plugins=dict(choices.plugins),
    )
