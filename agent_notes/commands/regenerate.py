"""Regenerate agent files from current state.json."""

import sys
from pathlib import Path
from typing import Optional

from ..config import Color


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
    from ..config import DATA_DIR
    from .build import generate_agent_files
    from ..registries.cli_registry import load_registry
    from ..config import PKG_DIR
    import yaml

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

    if project_path is None and scope == 'local':
        project_path = Path.cwd()

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
    
    # Load agent config
    agents_yaml = DATA_DIR / "agents" / "agents.yaml"
    if not agents_yaml.exists():
        print(f"Error: {agents_yaml} not found")
        sys.exit(1)
        
    with open(agents_yaml) as f:
        agents_data = yaml.safe_load(f)
    
    agents_config = agents_data.get('agents', {})
    
    # Regenerate per CLI
    registry = load_registry()
    
    print(f"Regenerating {scope} installation...")
    
    total_files = 0
    
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

        # Generate agents
        if backend.supports("agents"):
            files = generate_agent_files(
                agents_config,
                {},  # empty tiers - state-driven only
                state=current_state,
                scope=scope,
                project_path=project_path
            )
            # Count files for this CLI
            try:
                cli_files = [f for f in files if backend.name in str(f)]
                if cli_files:
                    print(f"  ✓ {len(cli_files)} agents regenerated")
                    total_files += len(cli_files)
            except (TypeError, AttributeError):
                # Handle case where files is mocked or has unexpected structure
                print(f"  ✓ agents regenerated")
        
        # Regenerate other components as needed
        from ..services import installer
        
        # Regenerate rules for backends that support them
        if backend.supports("rules"):
            installer.install_component_for_backend(backend, "rules", scope, scope_state.mode == "copy")
            print(f"  ✓ rules regenerated for {backend.label}")
        
        # Regenerate global config files
        if backend.layout.get("config"):
            installer.install_component_for_backend(backend, "config", scope, scope_state.mode == "copy")
            print(f"  ✓ config regenerated for {backend.label}")
        
        # Regenerate skills (static files, just ensure they're synced)
        if backend.supports("skills"):
            installer.install_component_for_backend(backend, "skills", scope, scope_state.mode == "copy")
            print(f"  ✓ skills regenerated for {backend.label}")
    
    # Update installed manifest to reflect current state
    try:
        # Get current role_models and overrides from state to preserve them
        existing_role_models = {}
        folder_overrides = {}
        global_home_override = None
        for cli_name, backend_state in scope_state.clis.items():
            existing_role_models[cli_name] = backend_state.role_models
            if backend_state.local_dir_override:
                folder_overrides[cli_name] = backend_state.local_dir_override
            if backend_state.global_home_override:
                global_home_override = backend_state.global_home_override

        # Build new state with current files but preserve role_models
        new_state = build_install_state(
            mode=scope_state.mode,
            scope=scope,
            repo_root=PKG_DIR.parent,
            project_path=project_path,
            role_models=existing_role_models,
            profile_label=profile_label,
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