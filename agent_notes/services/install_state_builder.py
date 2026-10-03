"""Build install state during install/uninstall flows."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Iterable, Optional

from ..domain.state import State, ScopeState, BackendState, InstalledItem
from ..services.install_ownership import tree_sha
from ..services.state_store import load_state, now_iso, sha256_of, set_scope

CONTEXT_FILE = "agent-notes-context.md"


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
    role_efforts: Optional[dict[str, dict[str, str]]] = None,
    # ^^ {cli_name: {role_name: effort}}, optional — empty dict fine for now
    selected_clis: Optional[set[str]] = None,
    # ^^ If given, only these backends are recorded as installed. None = all
    # backends with shipped content (legacy behavior, used by the plain
    # `agent-notes install` non-wizard path).
    profile_label: str = "",
    folder_overrides: Optional[dict[str, str]] = None,
    global_home_override: Optional[str] = None,
    selected_skills: Optional[Iterable[str]] = None,
    # ^^ The skills this install placed. None = every skill in dist/ (the flags
    # path installs them all); an empty list = none.
) -> State:
    """Build a complete State snapshot.
    
    - Loads current state.json if present, so we can ADD the new scope without
      clobbering other installs. E.g. installing globally doesn't erase existing
      local installs.
    - Constructs a ScopeState for the requested (scope, project_path).
    - Scans dist/ for each backend; fills BackendState.installed with what this
      install placed: agents, the selected skills, rules, commands, config, the
      session-hook context file and, for a global install, the ~/.agents/skills mirror.
      A copy install records the sha of each file's or directory's whole tree.
    - BackendState.role_models comes from the `role_models` arg if provided,
      else empty dict (will be populated by wizard in Phase E).
    - BackendState.role_efforts comes from the `role_efforts` arg if provided,
      else empty dict.
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
    from ..registries.cli_registry import load_registry
    from ..config import PKG_DIR, DIST_DIR, DIST_SKILLS_DIR, DIST_RULES_DIR, AGENTS_HOME

    # Build scope-specific install
    try:
        registry = load_registry()
    except Exception:
        # Fallback to empty registry if CLI backend loading fails
        from ..registries.cli_registry import CLIRegistry
        registry = CLIRegistry([])
    
    from ..services.install_plan import expanded_home, is_safe_local_dir  # install_plan loads the registries

    timestamp = now_iso()

    wanted = None if selected_skills is None else set(selected_skills)
    placed_skills = sorted(
        d for d in (DIST_SKILLS_DIR.iterdir() if DIST_SKILLS_DIR.exists() else ())
        if d.is_dir() and (wanted is None or d.name in wanted)
    )
    
    # Build CLIs dict for this scope
    clis = {}
    
    for backend in registry.all():
        # Skip backends the user opted out of during wizard selection.
        if selected_clis is not None and backend.name not in selected_clis:
            continue

        # Apply profile overrides to backend paths
        effective_backend = backend
        local_dir_override = ""
        global_home_override_val = ""
        if folder_overrides and is_safe_local_dir(folder_overrides.get(backend.name, "")):
            local_dir_override = folder_overrides[backend.name]
            effective_backend = effective_backend.with_local_dir(local_dir_override)
        if global_home_override and backend.name == "claude" and expanded_home(global_home_override):
            global_home_override_val = global_home_override
            effective_backend = effective_backend.with_global_home(expanded_home(global_home_override))

        backend_state = BackendState(
            local_dir_override=local_dir_override,
            global_home_override=global_home_override_val,
        )
        backend_has_content = False

        # Set role_models from arg (empty dict for now)
        if role_models and backend.name in role_models:
            backend_state.role_models = role_models[backend.name].copy()

        # Set role_efforts from arg (empty dict for now)
        if role_efforts and backend.name in role_efforts:
            backend_state.role_efforts = role_efforts[backend.name].copy()

        # Check agents
        if effective_backend.supports("agents"):
            agents_dir = PKG_DIR / "dist" / effective_backend.name / "agents"
            if agents_dir.exists():
                for agent_file in agents_dir.glob(f"*.{effective_backend.layout.get('agent_extension', 'md')}"):
                    try:
                        sha = sha256_of(agent_file)
                        target = _get_target_path(agent_file, effective_backend, "agents", scope, project_path)
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
        if effective_backend.supports("skills"):
            # Skills are in dist/skills/, not dist/<backend>/skills/
            for skill_dir in placed_skills:
                try:
                    target = _get_target_path(skill_dir, effective_backend, "skills", scope, project_path)
                    backend_state.installed.setdefault("skills", {})[skill_dir.name] = InstalledItem(
                        sha=_skill_sha(skill_dir, mode), target=str(target), mode=mode
                    )
                    backend_has_content = True
                except Exception:
                    continue

        # Check rules
        if effective_backend.supports("rules"):
            # Rules come from dist/rules/
            rules_dir = DIST_RULES_DIR
            if rules_dir.exists():
                for rule_file in rules_dir.glob("*.md"):
                    try:
                        sha = sha256_of(rule_file)
                        target = _get_target_path(rule_file, effective_backend, "rules", scope, project_path)
                        if "rules" not in backend_state.installed:
                            backend_state.installed["rules"] = {}
                        backend_state.installed["rules"][rule_file.name] = InstalledItem(
                            sha=sha, target=str(target), mode=mode
                        )
                        backend_has_content = True
                    except Exception:
                        continue
        
        # Check config files
        config_file = PKG_DIR / "dist" / effective_backend.name / effective_backend.layout.get("config", "")
        if config_file.exists():
            try:
                sha = sha256_of(config_file)
                target = _get_target_path(config_file, effective_backend, "config", scope, project_path)
                if "config" not in backend_state.installed:
                    backend_state.installed["config"] = {}
                backend_state.installed["config"][config_file.name] = InstalledItem(
                    sha=sha, target=str(target), mode=mode
                )
                backend_has_content = True
            except Exception:
                pass
        
        # Check commands
        commands_dir = DIST_DIR / effective_backend.name / "commands"
        if effective_backend.supports("commands") and commands_dir.exists():
            for command_file in commands_dir.glob("*.md"):
                try:
                    target = _get_target_path(command_file, effective_backend, "commands", scope, project_path)
                    backend_state.installed.setdefault("commands", {})[command_file.name] = InstalledItem(
                        sha=sha256_of(command_file), target=str(target), mode=mode
                    )
                    backend_has_content = True
                except Exception:
                    continue

        # The context file the session hook writes: generated, never linked
        if effective_backend.supports("session_hook"):
            context_file = _get_target_path(Path(CONTEXT_FILE), effective_backend, "context", scope, project_path)
            if context_file.is_file():
                backend_state.installed["context"] = {CONTEXT_FILE: InstalledItem(
                    sha=sha256_of(context_file), target=str(context_file), mode="copy"
                )}
                backend_has_content = True

        # The cross-tool skills mirror every global install places
        if scope == "global":
            # present even when empty: "no skills mirrored" is an answer, not a missing record
            backend_state.installed.setdefault("skills_mirror", {})
            for skill_dir in placed_skills:
                backend_state.installed.setdefault("skills_mirror", {})[skill_dir.name] = InstalledItem(
                    sha=_skill_sha(skill_dir, mode), target=str(AGENTS_HOME / "skills" / skill_dir.name), mode=mode
                )

        if backend_has_content:
            clis[backend.name] = backend_state
    
    # Create the new scope state
    from ..config import get_version
    new_scope_state = ScopeState(
        installed_at=timestamp,
        updated_at=timestamp,
        mode=mode,
        installed_version=get_version(),
        clis=clis,
        profile_label=profile_label,
    )

    # Set the appropriate scope
    set_scope(state, scope, new_scope_state, project_path, profile_label=profile_label)
    
    return state


def _skill_sha(skill_dir: Path, mode: str) -> str:
    """A copied skill is hashed by its whole tree, so an edit anywhere in it shows.
    A linked one keeps the SKILL.md hash older manifests carry."""
    if mode == "copy":
        return tree_sha(skill_dir)
    skill_md = skill_dir / "SKILL.md"
    return sha256_of(skill_md) if skill_md.exists() else ""


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
        if scope == "local":
            root = project_path if project_path else Path.cwd()
            return root / source_path.name
        return base_dir / source_path.name
    elif component_type in ["agents", "rules", "skills", "commands"]:
        # These go into subdirectories according to backend layout
        if component_type in backend.layout:
            subdir = backend.layout[component_type].rstrip("/")
            return base_dir / subdir / source_path.name
        else:
            # Fallback
            return base_dir / component_type / source_path.name
    else:
        return base_dir / source_path.name