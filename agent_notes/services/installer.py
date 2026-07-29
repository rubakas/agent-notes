"""Generic install/uninstall engine driven by the CLI backend registry.

Thin coordinator: delegates to focused sub-modules and owns only the functions
that require top-level `load_state` / `load_registry` imports (install_all,
uninstall_all, _install_session_hook, _uninstall_session_hook) so that tests
can patch those names at this module's namespace.

Sub-modules:
  install_plan     — compute WHAT to install (paths, actions, pure — no I/O)
  install_executor — DO it (place files/symlinks for individual components)
"""

from __future__ import annotations

import shlex
from pathlib import Path
from typing import List, Optional

from ..domain.cli_backend import CLIBackend
from ..registries.cli_registry import CLIRegistry, load_registry
from .. import config
from . import fs as _fs
from .state_store import load_state, get_scope

# ---------------------------------------------------------------------------
# Re-export: planning layer (install_plan.py)
# ---------------------------------------------------------------------------
from .install_plan import (
    InstallAction,
    PlanSummary,
    summarize_plan,
    COMPONENT_TYPES,
    _apply_overrides,
    _agent_glob,
    dist_source_for,
    target_dir_for,
    config_filename_for,
    _plan_file,
    _plan_component,
    _hooks_filename,
    _session_hook_paths,
    _plan_session_hook,
    plan_install,
)

# ---------------------------------------------------------------------------
# Re-export: execution layer (install_executor.py)
# ---------------------------------------------------------------------------
from .install_executor import (
    install_component_for_backend,
    uninstall_component_for_backend,
    _install_universal_skills,
    _uninstall_universal_skills,
    _filter_skills_by_backend,
)


# ---------------------------------------------------------------------------
# Top-level orchestrators (kept here so tests can patch installer.load_state
# and installer.load_registry to intercept calls made inside these functions)
# ---------------------------------------------------------------------------

def install_all(scope: str, copy_mode: bool, registry: Optional[CLIRegistry] = None,
                folder_overrides: Optional[dict] = None,
                global_home_override: Optional[str] = None) -> None:
    """Top-level: install every (backend, component) combo."""
    if registry is None:
        registry = load_registry()

    for backend in registry.all():
        effective = _apply_overrides(backend, folder_overrides, global_home_override)
        for component in COMPONENT_TYPES:
            install_component_for_backend(effective, component, scope, copy_mode)

    # Universal skills mirror: keep existing behavior — also install skills
    # to ~/.agents/skills/ for any backend that supports skills, only for global scope.
    if scope == "global":
        _install_universal_skills(copy_mode, registry)

    # SessionStart hooks — installed for every backend with features.session_hook == true
    for _hook_backend in registry.with_feature("session_hook"):
        _hook_backend = _apply_overrides(_hook_backend, folder_overrides, global_home_override)
        _install_session_hook(_hook_backend, scope)


def uninstall_all(scope: str, registry: Optional[CLIRegistry] = None,
                  folder_overrides: Optional[dict] = None,
                  global_home_override: Optional[str] = None,
                  profile_label: str = "") -> None:
    """Top-level uninstall."""
    if registry is None:
        registry = load_registry()

    # Determine copy_mode from state so plain copy-installed files are removed too
    copy_mode = False
    state = load_state()
    if state is not None:
        scope_state = get_scope(
            state, scope,
            project_path=Path.cwd() if scope == "local" else None,
            profile_label=profile_label,
        )
        if scope_state is not None:
            copy_mode = (scope_state.mode == "copy")

    with _fs.silent_ops():
        # Track counts per (backend, component) for summary output
        summary: dict[str, int] = {}

        for backend in registry.all():
            effective = _apply_overrides(backend, folder_overrides, global_home_override)
            for component in COMPONENT_TYPES:
                count = uninstall_component_for_backend(effective, component, scope, copy_mode)
                if count:
                    dst = target_dir_for(effective, component, scope)
                    if dst is not None:
                        key = str(dst)
                        summary[key] = summary.get(key, 0) + count

        if scope == "global":
            count = _uninstall_universal_skills(copy_mode)
            if count:
                target = config.AGENTS_HOME / "skills"
                key = str(target)
                summary[key] = summary.get(key, 0) + count

    # Print summary lines for components that had files removed
    home = Path.home()
    for path_str, count in summary.items():
        display = path_str.replace(str(home), "~")
        print(f"  Cleaned: {display}/ ({count} files)")

    # Remove SessionStart hooks — for every backend with features.session_hook == true
    for _hook_backend in registry.with_feature("session_hook"):
        _hook_backend = _apply_overrides(_hook_backend, folder_overrides, global_home_override)
        _uninstall_session_hook(_hook_backend, scope)


# ---------------------------------------------------------------------------
# Session-hook install / uninstall (kept here: tests patch installer.load_state
# to control the state lookup these functions perform)
# ---------------------------------------------------------------------------

def _install_session_hook(backend, scope: str, memory_backend: str = "", memory_path: str = "") -> None:
    """Install the SessionStart hook and write the context file.

    Behaviour is driven by the backend's feature flags:
      stop_hook        — memory-bridge and Stop/cost-report hook (claude: true, codex: false)
      pretooluse_hooks — PreToolUse credential guard (claude: true, codex: false)
      allow_entries    — Bash permission allow-list entries (claude: true, codex: false)
    """
    from .settings_writer import install_hook, install_allow_entry, remove_allow_entry, remove_matching_allow_entries, remove_hook
    from ..constants import Hooks
    from .session_context import write_context
    from ..registries.skill_registry import default_skill_registry
    from .. import config
    from ..memory.install import install_memory_hooks, install_memory_allow_entries

    settings_path, context_file, hook_command = _session_hook_paths(backend, scope)

    # Gather installed agent names from dist directory using the backend's agent extension
    agents: list[str] = []
    agents_dist = config.DIST_DIR / backend.name / backend.layout.get("agents", "agents")
    if agents_dist.exists():
        agents = sorted(p.stem for p in agents_dist.glob(_agent_glob(backend)))

    current_state = load_state()
    if not memory_backend:
        memory_backend = current_state.memory.backend if current_state else "local"
        memory_path = current_state.memory.path if current_state else ""

    skills = _filter_skills_by_backend(default_skill_registry().all(), memory_backend)

    version = config.get_version()
    if not _fs.silent_file_ops:
        print(f"Installing {backend.label} SessionStart hook ...")
    write_context(context_file, agents, version, skills)
    install_hook(settings_path, "SessionStart", hook_command)

    # Memory-bridge hooks and Stop/cost-report — backends that support stop_hook
    if backend.supports("stop_hook"):
        install_memory_hooks(settings_path, memory_backend)
        # Stop hook: emit cost report at end of session
        install_hook(settings_path, "Stop", Hooks.COST_REPORT)

    # PreToolUse credential guard — backends that support pretooluse_hooks
    if backend.supports("pretooluse_hooks"):
        # Scoped to Read|Bash|Grep tools via the matcher field (defense-in-depth).
        install_hook(
            settings_path,
            "PreToolUse",
            Hooks.GUARD_CREDENTIALS,
            matcher=Hooks.GUARD_CREDENTIALS_MATCHER,
        )

    if backend.supports("allow_entries"):
        # Remove ALL agent-notes Bash permission entries (covers stale entries from
        # any previous install, not just the immediately preceding one)
        remove_matching_allow_entries(settings_path, "Bash(agent-notes")
        remove_allow_entry(settings_path, "Bash(cost-report)")
        install_allow_entry(settings_path, "Bash(agent-notes cost-report)")
        install_memory_allow_entries(settings_path, memory_backend, memory_path, current_state)


def _uninstall_session_hook(backend, scope: str, memory_backend: str = "", memory_path: str = "") -> None:
    """Remove the SessionStart hook and context file.

    Behaviour is driven by the backend's feature flags:
      stop_hook        — memory-bridge and Stop/cost-report hook (claude: true, codex: false)
      pretooluse_hooks — PreToolUse credential guard (claude: true, codex: false)
      allow_entries    — Bash permission allow-list entries (claude: true, codex: false)
    """
    from .settings_writer import remove_hook, remove_allow_entry, remove_matching_allow_entries
    from ..constants import Hooks
    from ..memory.install import uninstall_memory_hooks

    settings_path, context_file, hook_command = _session_hook_paths(backend, scope)

    print(f"Removing {backend.label} SessionStart hook ...")
    context_file.unlink(missing_ok=True)
    remove_hook(settings_path, "SessionStart", hook_command)

    if backend.supports("stop_hook"):
        uninstall_memory_hooks(settings_path)
        remove_hook(settings_path, "Stop", Hooks.COST_REPORT)

    if backend.supports("pretooluse_hooks"):
        remove_hook(settings_path, "PreToolUse", Hooks.GUARD_CREDENTIALS)

    if backend.supports("allow_entries"):
        # Remove ALL agent-notes Bash permission entries (covers old naming too)
        remove_matching_allow_entries(settings_path, "Bash(agent-notes")
        remove_allow_entry(settings_path, "Bash(cost-report)")
        # Read/Write/Edit entries for memory vault paths are intentionally kept —
        # the user may still want Claude to access their vault without agent-notes.


__all__ = [
    # Data types
    "InstallAction",
    # Constants
    "COMPONENT_TYPES",
    # Planning helpers (from install_plan)
    "_apply_overrides",
    "_agent_glob",
    "dist_source_for",
    "target_dir_for",
    "config_filename_for",
    "_plan_file",
    "_plan_component",
    "_hooks_filename",
    "_session_hook_paths",
    "_plan_session_hook",
    "plan_install",
    # Execution helpers (from install_executor)
    "install_component_for_backend",
    "uninstall_component_for_backend",
    "_install_universal_skills",
    "_uninstall_universal_skills",
    "_filter_skills_by_backend",
    # Orchestrators (defined here — use load_state/load_registry)
    "install_all",
    "uninstall_all",
    "_install_session_hook",
    "_uninstall_session_hook",
    # Dependencies re-exported so tests can patch installer.load_state etc.
    "load_state",
    "load_registry",
]
