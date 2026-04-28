"""Set role to model mapping in state.json."""

import sys
from pathlib import Path
from typing import Optional, List

from ..config import Color


def set_role(role_name: str, model_id: str, cli: Optional[str] = None, scope: Optional[str] = None, local: bool = False) -> None:
    """Update role→model assignment in state.json and regenerate affected files.
    
    Args:
        role_name: Role to update (orchestrator, reasoner, worker, scout)
        model_id: New model ID (must be in model registry)
        cli: Target CLI name (auto-detect if only one CLI has this role in scope) 
        scope: 'global' or 'local' (auto: global if exists, else local)
        local: Shortcut for scope='local'
    """
    from .. import state as state_mod
    from ..state import get_scope, set_scope
    from ..registries.role_registry import load_role_registry
    from ..registries.model_registry import load_model_registry
    from ..registries.cli_registry import load_registry
    from .. import install_state
    
    # Load state.json
    current_state = state_mod.load()
    if current_state is None:
        print("No installation found. Run `agent-notes install` first.")
        sys.exit(1)
    
    # Determine scope
    if local:
        scope = 'local'
    elif scope is None:
        # Auto-detect: prefer global if exists
        if current_state.global_install is not None:
            scope = 'global'
        elif current_state.local_installs:
            scope = 'local'
        else:
            print("No installation found.")
            sys.exit(1)
    
    project_path = Path.cwd() if scope == 'local' else None
    scope_state = get_scope(current_state, scope, project_path)
    
    if scope_state is None:
        print(f"No {scope} installation found.")
        sys.exit(1)
    
    # Validate role exists
    role_registry = load_role_registry()
    try:
        role = role_registry.get(role_name)
    except KeyError:
        print(f"Unknown role: {role_name}")
        print(f"Available roles: {', '.join(role_registry.names())}")
        sys.exit(1)
    
    # Validate model exists and get it
    model_registry = load_model_registry()
    try:
        model = model_registry.get(model_id)
    except KeyError:
        print(f"Unknown model: {model_id}")
        print(f"Available models: {', '.join(model_registry.ids())}")
        sys.exit(1)
    
    # Determine target CLI(s)
    registry = load_registry()
    
    if cli == "all":
        # Apply to all CLIs where model is compatible
        target_clis = []
        for cli_name in scope_state.clis.keys():
            backend = registry.get(cli_name)
            if backend.first_alias_for(model.aliases) is not None:
                target_clis.append(cli_name)
            else:
                print(f"Warning: Skipping {backend.label} - model {model_id} not compatible")
        
        if not target_clis:
            print(f"Model {model_id} is not compatible with any installed CLI")
            sys.exit(1)
    
    elif cli is None:
        # Auto-detect: error if ambiguous
        candidates = [name for name in scope_state.clis.keys() 
                     if role_name in scope_state.clis[name].role_models]
        if len(candidates) == 0:
            # No CLI has this role yet, check all CLIs
            all_candidates = list(scope_state.clis.keys())
            if len(all_candidates) == 1:
                target_clis = all_candidates
            else:
                print(f"Multiple CLIs found: {', '.join(all_candidates)}")
                print("Specify --cli <name> or --cli all")
                sys.exit(1)
        elif len(candidates) == 1:
            target_clis = candidates
        else:
            print(f"Multiple CLIs found with role '{role_name}': {', '.join(candidates)}")
            print("Specify --cli <name> or --cli all")
            sys.exit(1)
    else:
        # Explicit CLI specified
        if cli not in scope_state.clis:
            print(f"CLI '{cli}' not found in {scope} installation")
            print(f"Installed CLIs: {', '.join(scope_state.clis.keys())}")
            sys.exit(1)
        
        backend = registry.get(cli)
        if backend.first_alias_for(model.aliases) is None:
            print(f"Model {model_id} is not compatible with {backend.label}")
            print(f"Compatible providers: {', '.join(backend.accepted_providers)}")
            print(f"Model providers: {', '.join(model.aliases.keys())}")
            sys.exit(1)
        
        target_clis = [cli]
    
    # Update state.json
    for cli_name in target_clis:
        backend_state = scope_state.clis[cli_name]
        backend_state.role_models[role_name] = model_id
        backend = registry.get(cli_name)
        print(f"Updated {backend.label}: {role_name} → {model_id}")
    
    # Write back
    install_state.record_install_state(current_state)
    print(f"Wrote {state_mod.state_file()}")
    
    # Trigger regenerate
    from ..regenerate import regenerate
    
    for cli_name in target_clis:
        backend = registry.get(cli_name) 
        print(f"\nRegenerating {backend.label}...")
        regenerate(scope=scope, cli=cli_name, project_path=project_path)
    
    print(f"\n{Color.GREEN}Done.{Color.NC} Restart your AI CLI to pick up changes.")
    print(f"Tip: Run `agent-notes regenerate` if you hand-edit state.json in the future.")