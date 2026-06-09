"""Info command - show installation status and component counts."""

from pathlib import Path

from ..services.state_store import load_current_state as _load_current_state
from ..config import get_version, CLAUDE_HOME, Color
from ._install_helpers import count_skills, count_agents, count_global


def show_info() -> None:
    """Show installation status and component counts."""
    from ..registries.cli_registry import load_registry

    version = get_version()
    print(f"agent-notes {version}")
    print("")
    print("Components:")
    print(f"  Skills:              {count_skills()}")

    # Show agent counts per backend
    registry = load_registry()
    for backend in registry.all():
        if backend.supports("agents"):
            agent_count = count_agents(backend)
            print(f"  Agents ({backend.label}):  {agent_count}")

    print(f"  Global config:       {count_global()} files")
    print("")
    print("Install targets:")
    # Show CLI install targets
    for backend in registry.all():
        print(f"  {backend.label}:  {backend.global_home}")

    print("  Universal:     ~/.agents/")
    print("")

    # Check install status
    global_ok = (CLAUDE_HOME / "agents").exists() and any((CLAUDE_HOME / "agents").iterdir())
    local_ok = Path(".claude/agents").exists() and any(Path(".claude/agents").iterdir())

    print("Status:")
    if global_ok:
        print(f"  Global:  {Color.GREEN}installed{Color.NC} (use doctor for details)")
    else:
        print(f"  Global:  {Color.YELLOW}not installed{Color.NC}")
    if local_ok:
        print(f"  Local:   {Color.GREEN}detected{Color.NC}")
    else:
        print(f"  Local:   {Color.CYAN}not detected{Color.NC}")
    
    # State info
    st = _load_current_state()
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
                    print(f"            Storage: {', '.join(backend_summaries)}")
        else:
            print("  Global:   none")

        # Named global profiles
        if st.global_installs:
            for label, gs in sorted(st.global_installs.items()):
                print(f"  Global [{label}]: installed {gs.installed_at}, {gs.mode}")
                if gs.clis:
                    backend_summaries = []
                    for backend_name, bs in sorted(gs.clis.items()):
                        parts = []
                        for component_type, items in bs.installed.items():
                            if items:
                                parts.append(f"{len(items)} {component_type}")
                        if parts:
                            extra = ""
                            if bs.global_home_override:
                                extra = f", home={bs.global_home_override}"
                            backend_summaries.append(f"{backend_name} ({', '.join(parts)}{extra})")
                    if backend_summaries:
                        print(f"            Storage: {', '.join(backend_summaries)}")

        # Local installs
        if st.local_installs:
            for project_path, ls in sorted(st.local_installs.items()):
                profile_hint = f" [{ls.profile_label}]" if ls.profile_label else ""
                print(f"  Local{profile_hint}:  {project_path}  (installed {ls.installed_at}, {ls.mode})")
                if ls.clis:
                    backend_summaries = []
                    for backend_name, bs in sorted(ls.clis.items()):
                        counts = []
                        for component_type, items in bs.installed.items():
                            if items:
                                counts.append(f"{len(items)} {component_type}")
                        if counts:
                            extra = ""
                            if bs.local_dir_override:
                                extra = f", folder={bs.local_dir_override}"
                            backend_summaries.append(f"{backend_name} ({', '.join(counts)}{extra})")
                    if backend_summaries:
                        print(f"            Storage: {', '.join(backend_summaries)}")
        else:
            print("  Local:    none")