"""Install command."""

from pathlib import Path

from ..config import Color, PKG_DIR
from .. import install_state
from ._install_helpers import _verify_install


def install(local: bool = False, copy: bool = False, reconfigure: bool = False) -> None:
    """Build from source and install to targets."""
    from ..state import get_scope, state_file
    from pathlib import Path
    
    scope = "local" if local else "global"
    project_path = Path.cwd().resolve() if local else None

    state = install_state.load_current_state()
    existing = get_scope(state, scope, project_path) if state else None

    if existing and not reconfigure:
        # Print existing-install summary
        print(f"Found existing {scope} installation at {state_file()}")
        print(f"  Installed: {existing.installed_at}")
        cli_labels = []
        from ..cli_backend import load_registry
        registry = load_registry()
        for cli_name in existing.clis.keys():
            try:
                cli_labels.append(registry.get(cli_name).label)
            except KeyError:
                cli_labels.append(cli_name)
        print(f"  CLIs:      {', '.join(cli_labels)}")
        print(f"  Mode:      {existing.mode}")
        print()
        print("Verifying ...")
        # Run verification. Use doctor_checks or a new helper.
        issues = _verify_install(existing, scope, project_path, registry)
        if not issues:
            print()
            print("Installation is healthy.")
            print()
            print("Tip: To reinstall with different choices, run:")
            print("       agent-notes uninstall")
            print("       agent-notes install")
            print()
            print("     Or to re-run the wizard and overwrite in place:")
            print("       agent-notes install --reconfigure")
        else:
            print()
            print(f"Installation has {len(issues)} issue(s).")
            print()
            print("Tip: Run `agent-notes doctor --fix` to repair, or `agent-notes install --reconfigure` to rewizard.")
        return

    if existing and reconfigure:
        print(f"Clearing existing {scope} state (--reconfigure) ...")
        install_state.remove_install_state(scope, project_path)
        # Fall through to normal install flow
    
    # Validate args
    if copy and not local:
        print("Error: --copy is only valid with --local installs.")
        print("Global installs always use symlinks.")
        return

    # Build first
    print("Building from source...")
    try:
        from agent_notes import install as _shim  # lazy shim import
        _shim.build()
    except Exception as e:
        print(f"{Color.RED}Build failed: {e}{Color.NC}")
        return

    # Execute
    print(f"Installing ({'local' if local else 'global'}, {'copy' if copy else 'symlink'}) ...")
    print("")

    from .. import installer
    scope = "local" if local else "global"
    copy_mode = copy
    installer.install_all(scope, copy_mode)

    print("")
    print(f"{Color.GREEN}Done.{Color.NC} Restart Claude Code / OpenCode to pick up changes.")
    
    # Record state
    try:
        project_path = Path.cwd() if local else None
        st = install_state.build_install_state(
            mode="copy" if copy else "symlink",
            scope="local" if local else "global",
            repo_root=PKG_DIR.parent,  # repo root (parent of agent_notes pkg)
            project_path=project_path,
        )
        install_state.record_install_state(st)
    except Exception as e:
        print(f"{Color.YELLOW}Warning: failed to write state.json: {e}{Color.NC}")