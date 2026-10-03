"""Fix actions for agent-notes diagnostics."""

from pathlib import Path
from typing import List

from ...domain.diagnostics import Issue, FixAction
from ..install_ownership import is_ours, lexical_target
from ..ui import printable


def do_fix(issues: List[Issue], fix_actions: List[FixAction]) -> bool:
    """Apply fixes with user confirmation and safety guards."""
    from ...services.state_store import load_current_state
    from ...config import Color

    non_build = [i for i in issues if i.type != "build_stale"]
    if non_build and all(i.type == "missing_group" for i in non_build):
        print(f"Not installed. Run '{Color.CYAN}agent-notes install{Color.NC}' to set up.")
        return True

    if not fix_actions:
        print(f"{Color.GREEN}No fixes needed.{Color.NC}")
        return True

    print("The following changes will be made:")
    print("")

    # Safety check: a DELETE runs only on what is ours (a link into a real dist, or a copy still
    # matching its manifest record) and sits inside an install's roots. Nothing else is deleted.
    from ...registries.cli_registry import load_registry
    from ..install_cleanup import deletion_guard
    from ..fs import _move_aside
    is_safe_delete = deletion_guard(load_current_state(), load_registry(), Path.cwd())

    for action in fix_actions:
        if action.action == "DELETE":
            file_path = Path(action.file)
            if not is_safe_delete(file_path):
                print(f"  {Color.RED}UNSAFE DELETE BLOCKED:{Color.NC} {printable(action.file)}")
                if file_path.is_symlink():
                    print(f"    Symlink target {printable(lexical_target(file_path))} is not in agent-notes dist/")
                    print(f"    This appears to be a third-party file. Skipping for safety.")
                else:
                    print(f"    Not a link into agent-notes dist/, and not an unedited copy it recorded.")
                    print(f"    This may be a user file. Skipping for safety.")
                continue

            print(f"  {Color.RED}DELETE{Color.NC}  {printable(action.file)} ({printable(action.details)})")
        elif action.action == "RELINK":
            print(f"  {Color.CYAN}RELINK{Color.NC}  {printable(action.file)} ({printable(action.details)})")
        elif action.action == "INSTALL":
            print(f"  {Color.GREEN}INSTALL{Color.NC} {printable(action.file)} ({printable(action.details)})")
        elif action.action == "BUILD":
            print(f"  {Color.CYAN}BUILD{Color.NC}   {printable(action.file)} ({printable(action.details)})")

    print("")
    response = input("Proceed? [y/N] ")

    if response.lower() != 'y':
        print("Aborted.")
        return False

    print("")
    print("Applying fixes...")

    needs_install = False
    needs_build = False

    for action in fix_actions:
        if action.action == "DELETE":
            file_path = Path(action.file)
            # Recheck safety (same logic as above)
            if not is_safe_delete(file_path):
                print(f"  {Color.RED}SKIPPED{Color.NC}   {printable(action.file)} (unsafe)")
                continue

            if file_path.exists() or file_path.is_symlink():
                if file_path.is_symlink():
                    file_path.unlink()
                elif file_path.is_dir():
                    import shutil
                    shutil.rmtree(file_path)
                else:
                    file_path.unlink()
                print(f"  {Color.RED}DELETED{Color.NC}  {printable(action.file)}")

        elif action.action == "RELINK":
            # Extract source from details
            if "symlink to " in action.details:
                source_file_str = action.details.split("symlink to ")[1]
                source_file = Path(source_file_str)

                if source_file.exists():
                    file_path = Path(action.file)
                    # What is there goes to a fresh backup, unless it is our own link
                    if file_path.is_symlink() and is_ours(file_path):
                        file_path.unlink()
                    elif file_path.exists() or file_path.is_symlink():
                        _move_aside(file_path)

                    file_path.parent.mkdir(parents=True, exist_ok=True)
                    file_path.symlink_to(source_file.resolve())
                    print(f"  {Color.CYAN}RELINKED{Color.NC} {printable(action.file)}")
                else:
                    print(f"  {Color.RED}FAILED{Color.NC}   {printable(action.file)} (source not found: {printable(source_file)})")

        elif action.action == "INSTALL":
            needs_install = True

        elif action.action == "BUILD":
            needs_build = True

    # Handle bulk operations
    if needs_install:
        print(f"  {Color.GREEN}RUNNING{Color.NC} regenerate to install missing components...")
        # Invocation is deferred to the caller (commands layer) — services must
        # not reach into the commands/top-level namespace. The caller checks
        # for _TRIGGER_INSTALL in fix_actions and regenerates the affected install.
        fix_actions.append(FixAction("_TRIGGER_INSTALL", "-", "run regenerate"))

    if needs_build:
        print(f"  {Color.CYAN}NOTICE{Color.NC}   Build stale issues detected.")
        print("           Run the build process to regenerate files from source.")

    return True
