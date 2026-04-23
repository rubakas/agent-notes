"""Uninstall command."""

from pathlib import Path

from ..config import Color
from .. import install_state


def uninstall(local: bool = False) -> None:
    """Remove installed components."""
    print(f"Uninstalling ({'local' if local else 'global'}) ...")
    print("")

    from .. import installer
    scope = "local" if local else "global"
    installer.uninstall_all(scope)

    print("")
    print(f"{Color.GREEN}Done.{Color.NC}")
    
    # Remove state for this scope only
    try:
        project_path = Path.cwd() if local else None
        install_state.remove_install_state("local" if local else "global", project_path)
    except Exception as e:
        print(f"{Color.YELLOW}Warning: failed to update state.json: {e}{Color.NC}")