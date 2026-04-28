"""Scoped health checks for agent-notes — only touches files we own."""

from __future__ import annotations
from pathlib import Path
from typing import Optional

from .registries.cli_registry import CLIRegistry
from .domain.cli_backend import CLIBackend
from .services import installer
from .state import State, ScopeState, sha256_of
from .config import BIN_HOME, AGENTS_HOME, DIST_SCRIPTS_DIR, DIST_SKILLS_DIR


def expected_paths_for_install(
    registry: CLIRegistry, scope: str
) -> list[tuple[Path, Path, str, str]]:
    """Return list of (source_file, target_file, backend_name, component) tuples
    that SHOULD be installed given the current dist/ tree and registry.
    
    Does NOT read state.json — this is "what would be installed if user ran install now".
    """
    expected: list[tuple[Path, Path, str, str]] = []
    
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
    
    # Scripts (global only)
    if scope == "global" and DIST_SCRIPTS_DIR.exists():
        for script in sorted(DIST_SCRIPTS_DIR.iterdir()):
            if script.is_file():
                expected.append((script, BIN_HOME / script.name, "scripts", "scripts"))
    
    # Universal skills mirror (global only)
    if scope == "global" and DIST_SKILLS_DIR.exists():
        any_backend_has_skills = any(b.supports("skills") for b in registry.all())
        if any_backend_has_skills:
            for skill_dir in sorted(DIST_SKILLS_DIR.iterdir()):
                if skill_dir.is_dir():
                    expected.append((skill_dir, AGENTS_HOME / "skills" / skill_dir.name, "universal", "skills"))
    
    return expected


def check_missing(scope, registry, issues, fix_actions, scope_state: Optional[ScopeState] = None):
    """Files that exist in dist/ but are not installed.

    If ``scope_state`` is provided, only flag missing files for backends the
    user actually installed — backends absent from state were opted-out of
    and legitimately have no files on disk. When ``scope_state`` is None,
    fall back to expecting every registry backend (legacy behavior).
    """
    from .doctor import Issue, FixAction  # reuse existing classes
    installed_backends: Optional[set[str]] = None
    if scope_state is not None:
        installed_backends = set(scope_state.clis.keys())

    for src, dst, backend_name, component in expected_paths_for_install(registry, scope):
        # "scripts" / "universal" are shared (not per-CLI-backend); always expected.
        if (installed_backends is not None
                and backend_name not in ("scripts", "universal")
                and backend_name not in installed_backends):
            continue
        if not dst.exists() and not dst.is_symlink():
            issues.append(Issue("missing", str(dst), "Source exists but not installed"))
            fix_actions.append(FixAction("INSTALL", str(dst), f"install {component}"))


def check_broken(scope, registry, issues, fix_actions, scope_state: Optional[ScopeState] = None):
    """Expected files that are broken symlinks."""
    from .doctor import Issue, FixAction
    paths_to_check: set[tuple[Path, Path]] = set()
    
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


def check_drift(scope, registry, issues, fix_actions, scope_state: Optional[ScopeState] = None):
    """Content drift: regular file (not symlink) whose content differs from source.
    
    Only meaningful when install mode was 'copy'. Limit to state.json paths if available.
    """
    from .doctor import Issue, FixAction
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
    from .doctor import Issue, FixAction
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