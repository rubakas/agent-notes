"""Diagnostic check functions for agent-notes installation."""

import os
from pathlib import Path
from typing import List, Optional

from ...domain.diagnostics import Issue, FixAction


def check_stale_files(scope: str, issues: List[Issue], fix_actions: List[FixAction]):
    """Check for installed files without matching source - DELEGATED to doctor_checks."""
    # This function is kept for backwards compatibility but delegates to the new module
    from ...cli_backend import load_registry
    from ... import install_state, doctor_checks
    from ...state import get_scope

    registry = load_registry()
    state = install_state.load_current_state()
    if state is None:
        scope_state = None
    else:
        project_path = Path.cwd() if scope == "local" else None
        scope_state = get_scope(state, scope, project_path)
    doctor_checks.check_stale(scope, scope_state, registry, issues, fix_actions)


def _find_dist_source(symlink: Path, scope: str) -> Optional[Path]:
    """Map an installed path back to its dist source for relinking.

    Iterates all registered backends; returns first dist source whose
    component and filename match the given symlink.
    """
    from ...cli_backend import load_registry
    from ... import installer
    registry = load_registry()

    symlink = symlink.resolve() if symlink.exists() else Path(os.path.abspath(symlink))
    name = symlink.name
    parent_name = symlink.parent.name  # e.g. "agents", "skills", "rules"

    # Try each backend's dist source for this component
    for backend in registry.all():
        src_dir = installer.dist_source_for(backend, parent_name)
        if src_dir is None:
            continue
        candidate = src_dir / name
        if candidate.exists():
            return candidate

    # Config files (global only): check each backend's config_filename
    if scope == "global":
        for backend in registry.all():
            config_fn = installer.config_filename_for(backend)
            if config_fn == name:
                src = installer.dist_source_for(backend, "config")
                if src is not None:
                    candidate = src / config_fn
                    if candidate.exists():
                        return candidate

    # Scripts
    def _get_bin_home():
        from ...config import BIN_HOME
        return BIN_HOME

    def _get_dist_scripts_dir():
        from ...config import DIST_SCRIPTS_DIR
        return DIST_SCRIPTS_DIR

    bin_home = _get_bin_home()
    dist_scripts_dir = _get_dist_scripts_dir()

    if bin_home and str(symlink).startswith(str(bin_home)):
        if dist_scripts_dir:
            source = dist_scripts_dir / name
            if source.exists():
                return source

    # Universal skills
    def _get_dist_skills_dir():
        from ...config import DIST_SKILLS_DIR
        return DIST_SKILLS_DIR

    if parent_name == "skills":
        dist_skills_dir = _get_dist_skills_dir()
        if dist_skills_dir:
            source = dist_skills_dir / name
            if source.exists():
                return source

    return None


def check_broken_symlinks(scope: str, issues: List[Issue], fix_actions: List[FixAction]):
    """Check for symlinks with non-existent targets - DELEGATED to doctor_checks."""
    # This function is kept for backwards compatibility but delegates to the new module
    from ...cli_backend import load_registry
    from ... import install_state, doctor_checks
    from ...state import get_scope

    registry = load_registry()
    state = install_state.load_current_state()
    if state is None:
        scope_state = None
    else:
        project_path = Path.cwd() if scope == "local" else None
        scope_state = get_scope(state, scope, project_path)
    doctor_checks.check_broken(scope, registry, issues, fix_actions, scope_state)


def check_shadowed_files(scope: str, issues: List[Issue], fix_actions: List[FixAction]):
    """Check for regular files where symlinks are expected - TARGETED check only."""
    from ...cli_backend import load_registry
    from ... import install_state, doctor_checks
    from ...state import get_scope

    # Get expected paths and check each one individually
    registry = load_registry()
    state = install_state.load_current_state()
    if state is None:
        scope_state = None
    else:
        project_path = Path.cwd() if scope == "local" else None
        scope_state = get_scope(state, scope, project_path)

    # Only check paths we know should exist
    for src, dst, backend_name, component in doctor_checks.expected_paths_for_install(registry, scope):
        if dst.exists() and not dst.is_symlink():
            # This is a regular file where we expected a symlink (or copy in copy mode)
            # If we're in symlink mode, this is shadowed
            if scope_state is None or scope_state.mode == "symlink":
                issues.append(Issue("shadowed", str(dst),
                              "Regular file instead of symlink. Won't receive updates."))
                fix_actions.append(FixAction("RELINK", str(dst),
                                           f"replace copy with symlink to {src}"))


def check_missing_files(scope: str, issues: List[Issue], fix_actions: List[FixAction]):
    """Check for source files that aren't installed - DELEGATED to doctor_checks."""
    # This function is kept for backwards compatibility but delegates to the new module
    from ...cli_backend import load_registry
    from ... import doctor_checks, install_state
    from ...state import get_scope

    registry = load_registry()
    # Pass scope state so opted-out backends aren't flagged as "missing".
    state = install_state.load_current_state()
    scope_state = None
    if state is not None:
        try:
            project_path = Path.cwd().resolve() if scope == "local" else None
            scope_state = get_scope(state, scope, project_path)
        except (ValueError, KeyError):
            scope_state = None
    # Call via kwargs only when we actually have scope_state — tests that
    # replace doctor_checks.check_missing with a narrower signature still work.
    if scope_state is not None:
        doctor_checks.check_missing(scope, registry, issues, fix_actions, scope_state=scope_state)
    else:
        doctor_checks.check_missing(scope, registry, issues, fix_actions)


def check_content_drift(scope: str, issues: List[Issue], fix_actions: List[FixAction]):
    """Check for copied files that differ from source - DELEGATED to doctor_checks."""
    # This function is kept for backwards compatibility but delegates to the new module
    from ...cli_backend import load_registry
    from ... import install_state, doctor_checks
    from ...state import get_scope

    registry = load_registry()
    state = install_state.load_current_state()
    if state is None:
        scope_state = None
    else:
        project_path = Path.cwd() if scope == "local" else None
        scope_state = get_scope(state, scope, project_path)
    doctor_checks.check_drift(scope, registry, issues, fix_actions, scope_state)


def check_build_freshness(issues: List[Issue], fix_actions: List[FixAction]):
    """Check if source files are newer than generated files."""
    from ...config import AGENTS_YAML, AGENTS_DIR, SCRIPTS_DIR, DIST_SCRIPTS_DIR
    agents_yaml = AGENTS_YAML

    # Check agents.yaml vs generated agents
    if agents_yaml.exists():
        source_time = agents_yaml.stat().st_mtime
        from ...cli_backend import load_registry
        from ...config import dist_dir_for

        registry = load_registry()
        for backend in registry.with_feature("agents"):
            agents_dir = dist_dir_for(backend) / backend.layout.get("agents", "agents")
            if agents_dir.exists():
                for f in agents_dir.glob("*.md"):
                    gen_time = f.stat().st_mtime
                    if source_time > gen_time:
                        issues.append(Issue("build_stale", str(f), "agents.yaml is newer than generated files"))
                        fix_actions.append(FixAction("BUILD", f"agents-{backend.name}/", "regenerate from source"))
                        break

    # Check individual source agents
    source_agents_dir = AGENTS_DIR
    if source_agents_dir.exists():
        from ...cli_backend import load_registry
        from ...config import dist_dir_for

        registry = load_registry()
        for src_file in source_agents_dir.glob("*.md"):
            source_time = src_file.stat().st_mtime

            # Check corresponding generated files across all backends with agents
            for backend in registry.with_feature("agents"):
                gen_file = dist_dir_for(backend) / backend.layout.get("agents", "agents") / src_file.name
                if gen_file.exists():
                    gen_time = gen_file.stat().st_mtime
                    if source_time > gen_time:
                        issues.append(Issue("build_stale", str(gen_file),
                                          f"{src_file} is newer than generated file"))
                        fix_actions.append(FixAction("BUILD", str(gen_file), "regenerate from source"))

    # Check scripts source vs dist
    if SCRIPTS_DIR.exists() and DIST_SCRIPTS_DIR.exists():
        for src_file in SCRIPTS_DIR.iterdir():
            if src_file.is_file():
                dist_file = DIST_SCRIPTS_DIR / src_file.name
                if dist_file.exists() and src_file.stat().st_mtime > dist_file.stat().st_mtime:
                    issues.append(Issue("build_stale", str(dist_file),
                                      f"{src_file} is newer than generated file"))
                    fix_actions.append(FixAction("BUILD", str(dist_file), "regenerate from source"))

    # Check global source files
    from ...cli_backend import load_registry
    from ...config import global_template_path, global_output_path

    registry = load_registry()
    for backend in registry.all():
        src = global_template_path(backend)
        gen = global_output_path(backend)

        if src and gen and src.exists() and gen.exists():
            src_time = src.stat().st_mtime
            gen_time = gen.stat().st_mtime

            if src_time > gen_time:
                issues.append(Issue("build_stale", str(gen), f"{src} is newer than generated file"))
                fix_actions.append(FixAction("BUILD", str(gen), "regenerate from source"))

    # Check plugin agents are up-to-date with dist agents
    from ...config import ROOT, DIST_DIR
    plugin_agents_dir = ROOT / ".claude-plugin" / "agents"
    dist_claude_agents = DIST_DIR / "claude" / "agents"
    if plugin_agents_dir.exists() and dist_claude_agents.exists():
        for dist_file in dist_claude_agents.glob("*.md"):
            plugin_file = plugin_agents_dir / dist_file.name
            if plugin_file.exists() and dist_file.stat().st_mtime > plugin_file.stat().st_mtime:
                issues.append(Issue("build_stale", str(plugin_file),
                                    "dist agent is newer than plugin agent — run scripts/build-plugin.sh"))
                fix_actions.append(FixAction("BUILD", ".claude-plugin/agents/", "run scripts/build-plugin.sh"))
                break  # one warning is enough

    # Check user config freshness against dist agents
    from ...services.user_config import config_path
    user_cfg = config_path()
    if user_cfg.exists() and dist_claude_agents.exists():
        cfg_time = user_cfg.stat().st_mtime
        for dist_file in dist_claude_agents.glob("*.md"):
            if cfg_time > dist_file.stat().st_mtime:
                issues.append(Issue("build_stale", str(user_cfg),
                                    "user config is newer than dist agents — run: agent-notes build"))
                fix_actions.append(FixAction("BUILD", "dist/", "regenerate from source"))
                break
