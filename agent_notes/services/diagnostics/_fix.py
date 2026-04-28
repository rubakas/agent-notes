"""Fix actions for agent-notes diagnostics."""

from pathlib import Path
from typing import List

from ...domain.diagnostics import Issue, FixAction


def do_fix(issues: List[Issue], fix_actions: List[FixAction]) -> bool:
    """Apply fixes with user confirmation and safety guards."""
    from ... import install_state
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

    # Safety check: verify DELETE actions are safe
    state = install_state.load_current_state()
    safe_delete_paths = set()
    if state is not None:
        # All paths in state.json are safe to delete
        # Check global install
        if state.global_install:
            for backend_name, bs in state.global_install.clis.items():
                for component_type, items in bs.installed.items():
                    for name, item in items.items():
                        safe_delete_paths.add(str(Path(item.target)))

        # Check local installs
        for project_path, scope_state in state.local_installs.items():
            for backend_name, bs in scope_state.clis.items():
                for component_type, items in bs.installed.items():
                    for name, item in items.items():
                        safe_delete_paths.add(str(Path(item.target)))

    for action in fix_actions:
        if action.action == "DELETE":
            file_path = Path(action.file)
            # Safety check: only allow DELETE if path is in state.json or is a symlink to our dist/
            if str(file_path) not in safe_delete_paths:
                if file_path.is_symlink():
                    target = file_path.readlink()
                    if not target.is_absolute():
                        target = file_path.parent / target
                    # Check if symlink target is within our dist/ directory
                    try:
                        from ...config import DIST_DIR
                        target_resolved = target.resolve()
                        dist_resolved = DIST_DIR.resolve()
                        if not str(target_resolved).startswith(str(dist_resolved)):
                            print(f"  {Color.RED}UNSAFE DELETE BLOCKED:{Color.NC} {action.file}")
                            print(f"    Symlink target {target} is not in agent-notes dist/")
                            print(f"    This appears to be a third-party file. Skipping for safety.")
                            continue
                    except (OSError, ValueError):
                        print(f"  {Color.RED}UNSAFE DELETE BLOCKED:{Color.NC} {action.file}")
                        print(f"    Cannot verify symlink target safety. Skipping.")
                        continue
                else:
                    print(f"  {Color.RED}UNSAFE DELETE BLOCKED:{Color.NC} {action.file}")
                    print(f"    File not in state.json and not a symlink to our dist/")
                    print(f"    This may be a user file. Skipping for safety.")
                    continue

            print(f"  {Color.RED}DELETE{Color.NC}  {action.file} ({action.details})")
        elif action.action == "RELINK":
            print(f"  {Color.CYAN}RELINK{Color.NC}  {action.file} ({action.details})")
        elif action.action == "INSTALL":
            print(f"  {Color.GREEN}INSTALL{Color.NC} {action.file} ({action.details})")
        elif action.action == "BUILD":
            print(f"  {Color.CYAN}BUILD{Color.NC}   {action.file} ({action.details})")

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
            if str(file_path) not in safe_delete_paths:
                if file_path.is_symlink():
                    target = file_path.readlink()
                    if not target.is_absolute():
                        target = file_path.parent / target
                    try:
                        from ...config import DIST_DIR
                        target_resolved = target.resolve()
                        dist_resolved = DIST_DIR.resolve()
                        if not str(target_resolved).startswith(str(dist_resolved)):
                            print(f"  {Color.RED}SKIPPED{Color.NC}   {action.file} (unsafe)")
                            continue
                    except (OSError, ValueError):
                        print(f"  {Color.RED}SKIPPED{Color.NC}   {action.file} (unsafe)")
                        continue
                else:
                    print(f"  {Color.RED}SKIPPED{Color.NC}   {action.file} (unsafe)")
                    continue

            if file_path.exists() or file_path.is_symlink():
                if file_path.is_symlink():
                    file_path.unlink()
                elif file_path.is_dir():
                    import shutil
                    shutil.rmtree(file_path)
                else:
                    file_path.unlink()
                print(f"  {Color.RED}DELETED{Color.NC}  {action.file}")

        elif action.action == "RELINK":
            # Extract source from details
            if "symlink to " in action.details:
                source_file_str = action.details.split("symlink to ")[1]
                source_file = Path(source_file_str)

                if source_file.exists():
                    file_path = Path(action.file)
                    # Backup original
                    if file_path.exists() and not file_path.is_symlink():
                        backup_path = Path(str(file_path) + ".bak")
                        file_path.rename(backup_path)

                    if file_path.exists():
                        file_path.unlink()

                    file_path.parent.mkdir(parents=True, exist_ok=True)
                    file_path.symlink_to(source_file.resolve())
                    print(f"  {Color.CYAN}RELINKED{Color.NC} {action.file}")
                else:
                    print(f"  {Color.RED}FAILED{Color.NC}   {action.file} (source not found: {source_file})")

        elif action.action == "INSTALL":
            needs_install = True

        elif action.action == "BUILD":
            needs_build = True

    # Handle bulk operations
    if needs_install:
        print(f"  {Color.GREEN}RUNNING{Color.NC} install to install missing components...")
        # Invocation is deferred to the caller (commands layer) — services must
        # not reach into the commands/top-level namespace. The caller checks
        # for action.action == "INSTALL" in fix_actions and dispatches install().
        # We flag it here by attaching a marker on the actions list.
        fix_actions.append(FixAction("_TRIGGER_INSTALL", "-", "run install"))

    if needs_build:
        print(f"  {Color.CYAN}NOTICE{Color.NC}   Build stale issues detected.")
        print("           Run the build process to regenerate files from source.")

    return True
