"""Regenerate agent files from current state.json."""

import contextlib
import sys
from pathlib import Path
from typing import Optional

from ..config import Color


def regenerate_instruction(scope: str, project_path: Optional[Path], profile_label: str = "") -> str:
    """The shell command that re-renders one install (what to run after a
    regenerate failed): plain `agent-notes regenerate` only fits a global,
    profile-less one."""
    import shlex
    command = "agent-notes regenerate"
    if scope == "local":
        command += " --local"
    if profile_label:
        command += f" --profile {shlex.quote(profile_label)}"
    if scope == "local":
        command = f"cd {shlex.quote(str(project_path))} && {command}"
    return command


def regenerate(scope: Optional[str] = None, cli: Optional[str] = None, local: bool = False,
               project_path: Optional[Path] = None, profile_label: str = "") -> None:
    """Rebuild agent/skill/config files from current state.json.

    Args:
        scope: 'global' or 'local' (auto-detect if omitted)
        cli: Target CLI (regenerate all if omitted)
        local: Shortcut for scope='local'
        project_path: Explicit project path for local scope
        profile_label: Named profile to regenerate
    """
    from ..services.state_store import load_state, get_scope, record_install_state
    from ..services.install_state_builder import build_install_state
    from .build import build
    from ..services import installer
    from ..registries.cli_registry import load_registry
    from ..config import PKG_DIR

    # Load state
    current_state = load_state()
    if current_state is None:
        print("No state.json found. Nothing to regenerate.")
        sys.exit(1)

    # Determine scope
    if local:
        scope = 'local'
    elif scope is None:
        if profile_label:
            if profile_label in current_state.global_installs:
                scope = 'global'
            else:
                scope = 'local'
        elif current_state.global_install:
            scope = 'global'
        elif current_state.local_installs:
            scope = 'local'
        else:
            print("No installation found in state")
            sys.exit(1)

    # Local targets (rules, CLAUDE.md, skills) resolve against the working
    # directory. An explicit project is placed from inside that project, so
    # regenerating it from another folder never writes into that folder.
    placement_dir = contextlib.nullcontext()
    if scope == 'local':
        if project_path is None:
            project_path = Path.cwd()
        else:
            project_path = Path(project_path).resolve()
            placement_dir = contextlib.chdir(project_path)

    scope_state = get_scope(current_state, scope, project_path, profile_label=profile_label)
    if scope_state is None:
        hint = f" (profile={profile_label})" if profile_label else ""
        print(f"No {scope} installation found{hint}")
        sys.exit(1)
    
    # Determine target CLIs
    if cli:
        if cli not in scope_state.clis:
            print(f"CLI '{cli}' not in {scope} installation")
            print(f"Installed: {', '.join(scope_state.clis.keys())}")
            sys.exit(1)
        target_clis = [cli]
    else:
        target_clis = list(scope_state.clis.keys())
    
    registry = load_registry()

    print(f"Regenerating {scope} installation...")

    total_files = 0
    copy_mode = scope_state.mode == "copy"

    with placement_dir:
        # The package ships no dist/ (a reinstall leaves it empty), and the
        # placed links point into it: render it first, exactly as install does.
        build(scope=scope, project_path=project_path, profile_label=profile_label)

        for cli_name in target_clis:
            backend = registry.get(cli_name)
            # Apply profile overrides from state
            bs = scope_state.clis.get(cli_name)
            if bs:
                if bs.local_dir_override:
                    backend = backend.with_local_dir(bs.local_dir_override)
                if bs.global_home_override:
                    backend = backend.with_global_home(Path(bs.global_home_override).expanduser())
            print(f"\n{backend.label}:")

            for component in installer.COMPONENT_TYPES:
                # A CLI without this component (codex has no commands) has no target.
                if installer.target_dir_for(backend, component, scope) is None:
                    continue
                if installer.dist_source_for(backend, component) is None:
                    # A string code: config's quiet_output hides prints but keeps the reason.
                    sys.exit(f"Error: nothing was rendered for {backend.label} {component}; "
                             f"its links would dangle.")
                planned = installer._plan_component(backend, component, scope, copy_mode)
                installer.install_component_for_backend(backend, component, scope, copy_mode)
                placed = [action for action in planned if action.dst.exists()]
                if not placed:
                    continue
                total_files += len(placed)
                if component == "agents":
                    print(f"  ✓ {len(placed)} agents regenerated")
                else:
                    print(f"  ✓ {component} regenerated for {backend.label}")

    # Update installed manifest to reflect current state
    try:
        # Get current role_models/role_efforts and overrides from state to preserve them
        existing_role_models = {}
        existing_role_efforts = {}
        folder_overrides = {}
        global_home_override = None
        for cli_name, backend_state in scope_state.clis.items():
            existing_role_models[cli_name] = backend_state.role_models
            existing_role_efforts[cli_name] = backend_state.role_efforts
            if backend_state.local_dir_override:
                folder_overrides[cli_name] = backend_state.local_dir_override
            if backend_state.global_home_override:
                global_home_override = backend_state.global_home_override

        # Build new state with current files but preserve role_models/role_efforts
        new_state = build_install_state(
            mode=scope_state.mode,
            scope=scope,
            repo_root=PKG_DIR.parent,
            project_path=project_path,
            role_models=existing_role_models,
            role_efforts=existing_role_efforts,
            profile_label=profile_label,
            selected_clis=set(scope_state.clis),
            folder_overrides=folder_overrides or None,
            global_home_override=global_home_override,
        )

        # Merge back into current_state preserving other scopes
        from ..services.state_store import _local_key
        if scope == 'global':
            if profile_label:
                current_state.global_installs[profile_label] = new_state.global_installs.get(profile_label, new_state.global_install)
            else:
                current_state.global_install = new_state.global_install
        else:
            if project_path:
                key = _local_key(project_path, profile_label)
                current_state.local_installs[key] = new_state.local_installs.get(key, new_state.local_installs.get(str(project_path.resolve())))

        record_install_state(current_state)
    except Exception as e:
        print(f"{Color.YELLOW}Warning: failed to update install state: {e}{Color.NC}")
    
    print(f"\n{Color.GREEN}Regenerated {total_files} files.{Color.NC}")