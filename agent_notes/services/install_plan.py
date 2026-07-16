"""Install plan: compute WHAT to install without writing any files.

This module owns:
  - The InstallAction data type
  - Path resolution helpers (dist_source_for, target_dir_for, config_filename_for)
  - Pure planning functions (_plan_file, _plan_component, _plan_session_hook, plan_install)
"""

from __future__ import annotations

import shlex
from pathlib import Path
from typing import List, NamedTuple, Optional

from ..domain.cli_backend import CLIBackend
from ..registries.cli_registry import CLIRegistry, load_registry
from .. import config


class InstallAction(NamedTuple):
    """Describes a single file placement that plan_install would perform."""

    action: str          # "install", "overwrite", "modify", or "skip"
    src: Path
    dst: Path
    backup_path: Optional[Path]  # set when action == "overwrite"


COMPONENT_TYPES = ("agents", "skills", "rules", "commands", "config")
# Note: "scripts" is handled separately, not per-backend.


class PlanSummary(NamedTuple):
    """Counts derived from a plan_install manifest (pure, no I/O)."""

    to_install: List[InstallAction]  # every action that writes: install/modify/overwrite
    overwrites: List[InstallAction]  # subset replacing an existing file (gets a backup)


def summarize_plan(manifest: List[InstallAction]) -> PlanSummary:
    """Split a manifest into actions that will write files and the overwrites among them."""
    return PlanSummary(
        to_install=[a for a in manifest if a.action != "skip"],
        overwrites=[a for a in manifest if a.action == "overwrite"],
    )


def _apply_overrides(
    backend: CLIBackend,
    folder_overrides: Optional[dict] = None,
    global_home_override: Optional[str] = None,
) -> CLIBackend:
    """Return a backend with folder/global_home overrides applied.

    global_home_override and folder_overrides are Claude-profile features.
    They are applied only to the claude backend so that codex/opencode/copilot
    global homes are never silently redirected.
    """
    effective = backend
    if folder_overrides and backend.name in folder_overrides:
        effective = effective.with_local_dir(folder_overrides[backend.name])
    if global_home_override and backend.name == "claude":
        effective = effective.with_global_home(Path(global_home_override).expanduser())
    return effective


def _agent_glob(backend: CLIBackend) -> str:
    """Return the glob pattern for agent files in the dist agents directory."""
    ext = backend.layout.get("agent_extension", "md")
    return f"*.{ext}"


def dist_source_for(backend: CLIBackend, component: str) -> Optional[Path]:
    """Return dist source path for a (backend, component) pair, or None if N/A.

    For "config" returns the directory containing the config file (the file
    itself is named per backend.layout["config"]).
    """
    if component == "agents":
        p = config.DIST_DIR / backend.name / "agents"
        return p if p.exists() else None
    if component == "config":
        # The config FILE lives directly under DIST_DIR / backend.name / <filename>
        # Caller resolves the filename via backend.layout["config"].
        p = config.DIST_DIR / backend.name
        return p if p.exists() else None
    if component == "rules":
        dist_rules_dir = config.DIST_RULES_DIR
        return dist_rules_dir if dist_rules_dir.exists() else None
    if component == "skills":
        dist_skills_dir = config.DIST_SKILLS_DIR
        return dist_skills_dir if dist_skills_dir.exists() else None
    if component == "commands":
        p = config.DIST_DIR / backend.name / "commands"
        return p if p.exists() else None
    return None


def target_dir_for(backend: CLIBackend, component: str, scope: str) -> Optional[Path]:
    """Return destination directory for a (backend, component, scope).

    scope: "global" or "local"
    Returns None if backend doesn't support this component.
    """
    # Special case for config: check layout instead of features
    if component == "config":
        if not backend.layout.get("config"):
            return None
    else:
        if not backend.supports(component):
            return None

    layout_value = backend.layout.get(component)
    if not layout_value:
        return None
    home = backend.global_home if scope == "global" else Path(backend.local_dir)
    if component == "config":
        if scope == "local":
            return Path(".")
        return home
    # All others are subdirectories
    return home / layout_value.rstrip("/")


def config_filename_for(backend: CLIBackend) -> Optional[str]:
    """Return e.g. 'CLAUDE.md', 'AGENTS.md', 'copilot-instructions.md'."""
    return backend.layout.get("config")


def _plan_file(src: Path, dst: Path, copy_mode: bool = False) -> InstallAction:
    """Return the InstallAction for a single src→dst placement."""
    from .fs import files_identical, _timestamped_backup_path

    if copy_mode and dst.is_symlink() and dst.resolve() == src.resolve():
        return InstallAction(action="skip", src=src, dst=dst, backup_path=None)
    if dst.exists() and not dst.is_symlink():
        if files_identical(src, dst):
            return InstallAction(action="skip", src=src, dst=dst, backup_path=None)
        backup_path = _timestamped_backup_path(dst)
        return InstallAction(action="overwrite", src=src, dst=dst, backup_path=backup_path)
    return InstallAction(action="install", src=src, dst=dst, backup_path=None)


def _plan_component(
    backend: CLIBackend,
    component: str,
    scope: str,
    copy_mode: bool = False,
) -> List[InstallAction]:
    """Return InstallActions for one (backend, component, scope) without writing."""
    src = dist_source_for(backend, component)
    if src is None:
        return []
    dst = target_dir_for(backend, component, scope)
    if dst is None:
        return []

    actions: List[InstallAction] = []

    if component == "config":
        filename = config_filename_for(backend)
        if not filename:
            return []
        src_file = src / filename
        if not src_file.exists():
            return []
        actions.append(_plan_file(src_file, dst / filename, copy_mode))
    elif component in ("agents", "rules", "commands"):
        glob = _agent_glob(backend) if component == "agents" else "*.md"
        for src_file in sorted(src.glob(glob)):
            if src_file.exists():
                actions.append(_plan_file(src_file, dst / src_file.name, copy_mode))
    elif component == "skills":
        if not src.exists():
            return []
        for skill_dir in sorted(d for d in src.iterdir() if d.is_dir()):
            actions.append(_plan_file(skill_dir, dst / skill_dir.name, copy_mode))

    return actions


def _hooks_filename(backend) -> str:
    """Return the hooks/settings filename for a given backend.

    Claude uses 'settings.json' (stored in layout["settings"]).
    Codex uses 'hooks.json' (stored in layout["hooks"]).
    Falls back to 'settings.json' for unknown backends.
    """
    return backend.layout.get("hooks") or backend.layout.get("settings") or "settings.json"


def _session_hook_paths(backend, scope: str):
    """Return (settings_path, context_file, hook_command) for the given scope."""
    home = backend.global_home if scope == "global" else Path(backend.local_dir)
    hooks_file = _hooks_filename(backend)
    settings_path = home / hooks_file
    context_file = home / "agent-notes-context.md"
    hook_command = f"cat {shlex.quote(str(context_file))} 2>/dev/null || true"
    return settings_path, context_file, hook_command


def _plan_session_hook(
    backend,
    scope: str,
) -> List[InstallAction]:
    """Return InstallActions for the settings.json SessionStart hook write.

    The hook is injected via merge (never a full overwrite), so:
      - If settings.json does not exist: action="install"
      - If settings.json exists but hook is absent: action="modify"
      - If settings.json exists and hook is already present: action="skip"
    """
    from .settings_writer import has_hook

    settings_path, _context_file, hook_command = _session_hook_paths(backend, scope)

    if not settings_path.exists():
        # Fresh write — settings.json will be created
        return [InstallAction(action="install", src=settings_path, dst=settings_path, backup_path=None)]

    if has_hook(settings_path, "SessionStart", hook_command):
        # Already installed — no-op
        return [InstallAction(action="skip", src=settings_path, dst=settings_path, backup_path=None)]

    # Merge inject — file exists but hook is absent; classified as modify
    return [InstallAction(action="modify", src=settings_path, dst=settings_path, backup_path=None)]


def plan_install(
    scope: str,
    registry: Optional[CLIRegistry] = None,
    selected_clis: Optional[set] = None,
    selected_skills: Optional[List[str]] = None,
    copy_mode: bool = False,
    folder_overrides: Optional[dict] = None,
    global_home_override: Optional[str] = None,
) -> List[InstallAction]:
    """Return a manifest of what install_all would do, without writing any files.

    Each entry is an InstallAction(action, src, dst, backup_path) where:
      action == "install"   — dst does not yet exist (fresh placement)
      action == "modify"    — dst exists and will be merge-updated (e.g. settings.json hook)
      action == "overwrite" — dst exists and differs; backup_path is the timestamped path
      action == "skip"      — dst exists and is byte-identical (or symlink unchanged); no write needed
    """
    if registry is None:
        registry = load_registry()

    actions: List[InstallAction] = []

    for backend in registry.all():
        if selected_clis is not None and backend.name not in selected_clis:
            continue
        effective = _apply_overrides(backend, folder_overrides, global_home_override)
        for component in COMPONENT_TYPES:
            if component == "skills" and selected_skills is not None:
                # Skills are filtered — plan them separately below
                continue
            actions.extend(_plan_component(effective, component, scope, copy_mode))

    # Skills: respect the selected_skills filter (mirrors wizard's install_skills_filtered)
    if scope == "global" or selected_skills is not None:
        dist_skills_dir = config.DIST_SKILLS_DIR
        if dist_skills_dir.exists():
            skill_dirs = {d.name: d for d in dist_skills_dir.iterdir() if d.is_dir()}
            names_to_plan = selected_skills if selected_skills is not None else list(skill_dirs.keys())

            # Per-backend skill targets
            for backend in registry.all():
                if selected_clis is not None and backend.name not in selected_clis:
                    continue
                if not backend.supports("skills"):
                    continue
                effective = _apply_overrides(backend, folder_overrides, global_home_override)
                dst_dir = target_dir_for(effective, "skills", scope)
                if dst_dir is None:
                    continue
                for name in sorted(names_to_plan):
                    skill_dir = skill_dirs.get(name)
                    if skill_dir:
                        actions.append(_plan_file(skill_dir, dst_dir / name, copy_mode))

            # Universal skills mirror (~/.agents/skills/)
            if scope == "global":
                target = config.AGENTS_HOME / "skills"
                for name in sorted(names_to_plan):
                    skill_dir = skill_dirs.get(name)
                    if skill_dir:
                        actions.append(_plan_file(skill_dir, target / name, copy_mode))

    # SessionStart hooks — planned for every backend with features.session_hook == true
    for _hook_backend in registry.with_feature("session_hook"):
        if selected_clis is not None and _hook_backend.name not in selected_clis:
            continue
        _hook_backend = _apply_overrides(_hook_backend, folder_overrides, global_home_override)
        actions.extend(_plan_session_hook(_hook_backend, scope))

    return actions
