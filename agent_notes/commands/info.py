"""Info command - show installation status and component counts."""

from pathlib import Path

from .. import install_state


def show_info() -> None:
    """Show installation status and component counts."""
    from ..cli_backend import load_registry
    from agent_notes import install as _shim  # lazy shim import
    
    version = _shim.get_version()
    print(f"agent-notes {version}")
    print("")
    print("Components:")
    print(f"  Scripts:             {_shim.count_scripts()}")
    print(f"  Skills:              {_shim.count_skills()}")
    
    # Show agent counts per backend
    registry = load_registry()
    for backend in registry.all():
        if backend.supports("agents"):
            agent_count = _shim.count_agents(backend)
            print(f"  Agents ({backend.label}):  {agent_count}")
    
    print(f"  Global config:       {_shim.count_global()} files")
    print("")
    print("Install targets:")
    print("  Scripts:       ~/.local/bin/")
    
    # Show CLI install targets
    for backend in registry.all():
        print(f"  {backend.label}:  {backend.global_home}")
    
    print("  Universal:     ~/.agents/")
    print("")

    # Check install status
    global_ok = (_shim.CLAUDE_HOME / "agents").exists() and any((_shim.CLAUDE_HOME / "agents").iterdir())
    local_ok = Path(".claude/agents").exists() and any(Path(".claude/agents").iterdir())

    print("Status:")
    if global_ok:
        print(f"  Global:  {_shim.Color.GREEN}installed{_shim.Color.NC} (use doctor for details)")
    else:
        print(f"  Global:  {_shim.Color.YELLOW}not installed{_shim.Color.NC}")
    if local_ok:
        print(f"  Local:   {_shim.Color.GREEN}detected{_shim.Color.NC}")
    else:
        print(f"  Local:   {_shim.Color.CYAN}not detected{_shim.Color.NC}")
    
    # State info
    st = install_state.load_current_state()
    if st is not None:
        print("")
        print("Last install:")
        
        # Global install
        if st.global_install:
            gs = st.global_install
            print(f"  Global:   installed {gs.installed_at}, {gs.mode}")
            # Count backends and items
            if gs.clis:
                backend_summaries = []
                for backend_name, bs in sorted(gs.clis.items()):
                    counts = []
                    for component_type, items in bs.installed.items():
                        if items:
                            counts.append(f"{len(items)} {component_type}")
                    if counts:
                        backend_summaries.append(f"{backend_name} ({', '.join(counts)})")
                if backend_summaries:
                    print(f"            Backends: {', '.join(backend_summaries)}")
        else:
            print("  Global:   none")
        
        # Local installs
        if st.local_installs:
            for project_path, ls in sorted(st.local_installs.items()):
                print(f"  Local:    {project_path}  (installed {ls.installed_at}, {ls.mode})")
                if ls.clis:
                    backend_summaries = []
                    for backend_name, bs in sorted(ls.clis.items()):
                        counts = []
                        for component_type, items in bs.installed.items():
                            if items:
                                counts.append(f"{len(items)} {component_type}")
                        if counts:
                            backend_summaries.append(f"{backend_name} ({', '.join(counts)})")
                    if backend_summaries:
                        print(f"            Backends: {', '.join(backend_summaries)}")
        else:
            print("  Local:    none")