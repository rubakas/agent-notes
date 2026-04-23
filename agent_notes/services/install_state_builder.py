"""Build install state during install/uninstall flows."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional

from ..domain.state import State, ScopeState, BackendState, InstalledItem
from ..services.state_store import load_state, now_iso, sha256_of, set_scope


def git_head_short(repo_root: Path) -> str:
    """Return short git HEAD sha, or '' on error."""
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return ""


def build_install_state(
    mode: str,
    scope: str,                  # "global" or "local"
    repo_root: Path,
    project_path: Optional[Path] = None,  # required when scope == "local"
    role_models: Optional[dict[str, dict[str, str]]] = None,
    # ^^ {cli_name: {role_name: model_id}}, optional — empty dict fine for now
    selected_clis: Optional[set[str]] = None,
    # ^^ If given, only these backends are recorded as installed. None = all
    # backends with shipped content (legacy behavior, used by the plain
    # `agent-notes install` non-wizard path).
) -> State:
    """Build a complete State snapshot.
    
    - Loads current state.json if present, so we can ADD the new scope without
      clobbering other installs. E.g. installing globally doesn't erase existing
      local installs.
    - Constructs a ScopeState for the requested (scope, project_path).
    - Scans dist/ for each backend; fills BackendState.installed.
    - BackendState.role_models comes from the `role_models` arg if provided,
      else empty dict (will be populated by wizard in Phase E).
    - Returns the updated full State. Caller must call save().
    """
    # Load existing state or create fresh one
    current_state = load_state()
    if current_state is None:
        state = State()
    else:
        state = current_state
    
    # Update top-level metadata
    state.source_path = str(repo_root.resolve())
    state.source_commit = git_head_short(repo_root)
    
    # Import here to avoid circular import
    from ..cli_backend import load_registry
    from ..config import PKG_DIR, DIST_SKILLS_DIR, DIST_RULES_DIR
    
    # Build scope-specific install
    try:
        registry = load_registry()
    except Exception:
        # Fallback to empty registry if CLI backend loading fails
        from ..cli_backend import CLIRegistry
        registry = CLIRegistry([])
    
    timestamp = now_iso()
    
    # Build CLIs dict for this scope
    clis = {}
    
    for backend in registry.all():
        # Skip backends the user opted out of during wizard selection.
        if selected_clis is not None and backend.name not in selected_clis:
            continue
        backend_state = BackendState()
        backend_has_content = False
        
        # Set role_models from arg (empty dict for now)
        if role_models and backend.name in role_models:
            backend_state.role_models = role_models[backend.name].copy()
        
        # Check agents
        if backend.supports("agents"):
            agents_dir = PKG_DIR / "dist" / backend.name / "agents"
            if agents_dir.exists():
                for agent_file in agents_dir.glob("*.md"):
                    try:
                        sha = sha256_of(agent_file)
                        target = _get_target_path(agent_file, backend, "agents", scope, project_path)
                        if "agents" not in backend_state.installed:
                            backend_state.installed["agents"] = {}
                        backend_state.installed["agents"][agent_file.name] = InstalledItem(
                            sha=sha, target=str(target), mode=mode
                        )
                        backend_has_content = True
                    except Exception:
                        # Skip files we can't process
                        continue
        
        # Check skills
        if backend.supports("skills"):
            # Skills are in dist/skills/, not dist/<backend>/skills/
            skills_dir = DIST_SKILLS_DIR
            if skills_dir.exists():
                for skill_dir in skills_dir.iterdir():
                    if skill_dir.is_dir():
                        try:
                            # Use SKILL.md as the file to hash for consistency
                            skill_md = skill_dir / "SKILL.md"
                            if skill_md.exists():
                                sha = sha256_of(skill_md)
                            else:
                                # If no SKILL.md, use empty string sha
                                sha = ""
                            target = _get_target_path(skill_dir, backend, "skills", scope, project_path)
                            if "skills" not in backend_state.installed:
                                backend_state.installed["skills"] = {}
                            backend_state.installed["skills"][skill_dir.name] = InstalledItem(
                                sha=sha, target=str(target), mode=mode
                            )
                            backend_has_content = True
                        except Exception:
                            continue
        
        # Check rules
        if backend.supports("rules"):
            # Rules come from dist/rules/
            rules_dir = DIST_RULES_DIR
            if rules_dir.exists():
                for rule_file in rules_dir.glob("*.md"):
                    try:
                        sha = sha256_of(rule_file)
                        target = _get_target_path(rule_file, backend, "rules", scope, project_path)
                        if "rules" not in backend_state.installed:
                            backend_state.installed["rules"] = {}
                        backend_state.installed["rules"][rule_file.name] = InstalledItem(
                            sha=sha, target=str(target), mode=mode
                        )
                        backend_has_content = True
                    except Exception:
                        continue
        
        # Check config files
        config_file = PKG_DIR / "dist" / backend.name / backend.layout.get("config", "")
        if config_file.exists():
            try:
                sha = sha256_of(config_file)
                target = _get_target_path(config_file, backend, "config", scope, project_path)
                if "config" not in backend_state.installed:
                    backend_state.installed["config"] = {}
                backend_state.installed["config"][config_file.name] = InstalledItem(
                    sha=sha, target=str(target), mode=mode
                )
                backend_has_content = True
            except Exception:
                pass
        
        # Check commands (future enhancement)
        # Check settings (future enhancement)
        
        if backend_has_content:
            clis[backend.name] = backend_state
    
    # Create the new scope state
    new_scope_state = ScopeState(
        installed_at=timestamp,
        updated_at=timestamp,
        mode=mode,
        clis=clis,
    )
    
    # Set the appropriate scope
    set_scope(state, scope, new_scope_state, project_path)
    
    return state


def _get_target_path(source_path: Path, backend, component_type: str, scope: str, project_path: Optional[Path] = None) -> Path:
    """Get the target installation path for a source file/directory."""
    if scope == "global":
        base_dir = backend.global_home
    else:
        # Local scope - relative to the provided project path or current working directory
        if project_path:
            base_dir = project_path / backend.local_dir
        else:
            base_dir = Path.cwd() / backend.local_dir
    
    if component_type == "config":
        # Config files go to the root of the backend directory
        return base_dir / source_path.name
    elif component_type in ["agents", "rules", "skills"]:
        # These go into subdirectories according to backend layout
        if component_type in backend.layout:
            subdir = backend.layout[component_type].rstrip("/")
            return base_dir / subdir / source_path.name
        else:
            # Fallback
            return base_dir / component_type / source_path.name
    else:
        return base_dir / source_path.name