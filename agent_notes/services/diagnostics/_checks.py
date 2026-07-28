"""Diagnostic check functions for agent-notes installation."""

import os
from pathlib import Path
from typing import List, Optional

from ...domain.diagnostics import Issue, FixAction


def _load_scope_state(scope: str, profile_label: str = ""):
    """Load registry and scope state for a given scope.

    Returns (registry, scope_state) where scope_state may be None if no
    state file exists.
    """
    from ...registries.cli_registry import load_registry
    from ...services.state_store import load_current_state, get_scope

    registry = load_registry()
    state = load_current_state()
    if state is None:
        return registry, None
    project_path = Path.cwd() if scope == "local" else None
    scope_state = get_scope(state, scope, project_path, profile_label=profile_label)
    return registry, scope_state


def expected_paths_for_install(
    registry, scope: str
) -> list:
    """Return list of (source_file, target_file, backend_name, component) tuples
    that SHOULD be installed given the current dist/ tree and registry.

    Does NOT read state.json — this is "what would be installed if user ran install now".
    """
    from ... import installer
    from ...config import AGENTS_HOME, DIST_SKILLS_DIR

    expected: list = []

    for backend in registry.all():
        for component in installer.COMPONENT_TYPES:
            src = installer.dist_source_for(backend, component)
            dst = installer.target_dir_for(backend, component, scope)
            if src is None or dst is None:
                continue

            if component == "config":
                fn = installer.config_filename_for(backend)
                if not fn:
                    continue
                src_file = src / fn
                if src_file.exists():
                    expected.append((src_file, dst / fn, backend.name, component))
            elif component == "skills":
                # Each top-level dir in src is a skill
                for skill_dir in sorted(src.iterdir()):
                    if skill_dir.is_dir():
                        expected.append((skill_dir, dst / skill_dir.name, backend.name, component))
            else:
                # agents, rules, commands: flat *.md files
                for f in sorted(src.glob("*.md")):
                    expected.append((f, dst / f.name, backend.name, component))

    # Universal skills mirror (global only)
    if scope == "global" and DIST_SKILLS_DIR.exists():
        any_backend_has_skills = any(b.supports("skills") for b in registry.all())
        if any_backend_has_skills:
            for skill_dir in sorted(DIST_SKILLS_DIR.iterdir()):
                if skill_dir.is_dir():
                    expected.append((skill_dir, AGENTS_HOME / "skills" / skill_dir.name, "universal", "skills"))

    return expected


def check_missing(scope, registry, issues, fix_actions, scope_state=None):
    """Files that exist in dist/ but are not installed.

    If ``scope_state`` is provided, only flag missing files for backends the
    user actually installed — backends absent from state were opted-out of
    and legitimately have no files on disk. When ``scope_state`` is None,
    fall back to expecting every registry backend (legacy behavior).
    """
    installed_backends = None
    if scope_state is not None:
        installed_backends = set(scope_state.clis.keys())

    for src, dst, backend_name, component in expected_paths_for_install(registry, scope):
        # "universal" is shared (not per-CLI-backend); always expected.
        if (installed_backends is not None
                and backend_name not in ("universal",)
                and backend_name not in installed_backends):
            continue
        if not dst.exists() and not dst.is_symlink():
            issues.append(Issue("missing", str(dst), "Source exists but not installed"))
            fix_actions.append(FixAction("INSTALL", str(dst), f"install {component}"))


def check_broken(scope, registry, issues, fix_actions, scope_state=None):
    """Expected files that are broken symlinks."""
    from ...services.state_store import sha256_of

    paths_to_check: set = set()

    # Expected paths from current dist
    for src, dst, _, _ in expected_paths_for_install(registry, scope):
        paths_to_check.add((src, dst))

    # Plus state.json paths (may differ from expected if dist changed)
    if scope_state is not None:
        for backend_name, bs in scope_state.clis.items():
            for component_type, items in bs.installed.items():
                for _name, item in items.items():
                    paths_to_check.add((Path("?"), Path(item.target)))

    for _src, path in paths_to_check:
        if path.is_symlink():
            target = path.readlink()
            if not target.is_absolute():
                target = path.parent / target
            if not target.exists():
                issues.append(Issue("broken", str(path), "Symlink target does not exist"))
                # Try to recover the source — if it's in our dist, relink; else delete
                fix_actions.append(FixAction("RELINK", str(path), "reinstall"))


def check_drift(scope, registry, issues, fix_actions, scope_state=None):
    """Content drift: regular file (not symlink) whose content differs from source.

    Only meaningful when install mode was 'copy'. Limit to state.json paths if available.
    """
    from ...services.state_store import sha256_of

    if scope_state is None:
        return  # without state.json, we don't know if drift is expected (no manifest)

    if scope_state.mode != "copy":
        return  # symlinks can't drift

    for backend_name, bs in scope_state.clis.items():
        for component_type, items in bs.installed.items():
            for name, item in items.items():
                p = Path(item.target)
                if not p.exists() or p.is_symlink():
                    continue
                # File exists as regular file; compare sha
                try:
                    current_sha = sha256_of(p) if p.is_file() else None
                    # For directories (skills), we'd need deeper compare — skip for now
                    if current_sha and current_sha != item.sha:
                        issues.append(Issue("drift", str(p),
                            "Content differs from source. Local changes will be lost on update."))
                except OSError:
                    pass


def check_stale(scope, scope_state, registry, issues, fix_actions):
    """State-based check: files listed in state.json whose dist source is gone."""
    from ... import installer

    if scope_state is None:
        return

    # Build lookup of what currently exists in dist for each backend
    for backend_name, bs in scope_state.clis.items():
        try:
            backend = registry.get(backend_name)
        except KeyError:
            # Backend was removed entirely — everything is stale
            for component_type, items in bs.installed.items():
                for name, item in items.items():
                    issues.append(Issue("stale", str(item.target),
                        f"Backend '{backend_name}' no longer exists in agent-notes"))
                    fix_actions.append(FixAction("DELETE", str(item.target), "stale"))
            continue

        for component_type, items in bs.installed.items():
            src_dir = installer.dist_source_for(backend, component_type)
            if src_dir is None:
                continue
            for name, item in items.items():
                # Check if this specific item's source still exists
                if component_type == "config":
                    config_fn = installer.config_filename_for(backend)
                    if config_fn and (src_dir / config_fn).exists():
                        continue  # Still exists
                    issues.append(Issue("stale", str(item.target),
                        f"Config file no longer built for {backend_name}"))
                    fix_actions.append(FixAction("DELETE", str(item.target), "stale config"))
                elif component_type == "skills":
                    if (src_dir / name).is_dir():
                        continue  # Still exists
                    issues.append(Issue("stale", str(item.target),
                        f"Skill '{name}' no longer exists in agent-notes"))
                    fix_actions.append(FixAction("DELETE", str(item.target), "stale skill"))
                else:
                    # agents, rules, commands: files
                    if (src_dir / name).exists():
                        continue  # Still exists
                    issues.append(Issue("stale", str(item.target),
                        f"{component_type.title()} '{name}' no longer exists in agent-notes"))
                    fix_actions.append(FixAction("DELETE", str(item.target), f"stale {component_type}"))


def _find_dist_source(symlink: Path, scope: str) -> Optional[Path]:
    """Map an installed path back to its dist source for relinking.

    Iterates all registered backends; returns first dist source whose
    component and filename match the given symlink.
    """
    from ...registries.cli_registry import load_registry
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


def check_broken_symlinks(scope: str, issues: List[Issue], fix_actions: List[FixAction],
                          profile_label: str = ""):
    """Check for symlinks with non-existent targets."""
    registry, scope_state = _load_scope_state(scope, profile_label)
    check_broken(scope, registry, issues, fix_actions, scope_state)


def check_shadowed_files(scope: str, issues: List[Issue], fix_actions: List[FixAction],
                         profile_label: str = ""):
    """Check for regular files where symlinks are expected - TARGETED check only."""
    registry, scope_state = _load_scope_state(scope, profile_label)

    # Only check paths we know should exist
    for src, dst, backend_name, component in expected_paths_for_install(registry, scope):
        if dst.exists() and not dst.is_symlink():
            # This is a regular file where we expected a symlink (or copy in copy mode)
            # If we're in symlink mode, this is shadowed
            if scope_state is None or scope_state.mode == "symlink":
                issues.append(Issue("shadowed", str(dst),
                              "Regular file instead of symlink. Won't receive updates."))
                fix_actions.append(FixAction("RELINK", str(dst),
                                           f"replace copy with symlink to {src}"))


def check_missing_files(scope: str, issues: List[Issue], fix_actions: List[FixAction],
                        profile_label: str = ""):
    """Check for source files that aren't installed."""
    from ...registries.cli_registry import load_registry
    from ...services.state_store import load_current_state, get_scope

    registry = load_registry()
    # Pass scope state so opted-out backends aren't flagged as "missing".
    # Use a try/except here since local scope resolution can raise ValueError/KeyError.
    state = load_current_state()
    scope_state = None
    if state is not None:
        try:
            project_path = Path.cwd().resolve() if scope == "local" else None
            scope_state = get_scope(state, scope, project_path, profile_label=profile_label)
        except (ValueError, KeyError):
            scope_state = None
    check_missing(scope, registry, issues, fix_actions, scope_state=scope_state)


def check_content_drift(scope: str, issues: List[Issue], fix_actions: List[FixAction],
                        profile_label: str = ""):
    """Check for copied files that differ from source."""
    registry, scope_state = _load_scope_state(scope, profile_label)
    check_drift(scope, registry, issues, fix_actions, scope_state)


def check_stale_files(scope: str, issues: List[Issue], fix_actions: List[FixAction],
                      profile_label: str = ""):
    """Check for installed files without matching source."""
    registry, scope_state = _load_scope_state(scope, profile_label)
    check_stale(scope, scope_state, registry, issues, fix_actions)


def check_build_freshness(issues: List[Issue], fix_actions: List[FixAction]):
    """Check if source files are newer than generated files."""
    from ...config import AGENTS_YAML, AGENTS_DIR
    agents_yaml = AGENTS_YAML

    # Check agents.yaml vs generated agents
    if agents_yaml.exists():
        source_time = agents_yaml.stat().st_mtime
        from ...registries.cli_registry import load_registry
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
        from ...registries.cli_registry import load_registry
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

    # Check global source files
    from ...registries.cli_registry import load_registry
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
