"""Install command."""

from pathlib import Path

from ..config import Color, PKG_DIR
from ..services.install_state_builder import build_install_state
from ..services.state_store import load_current_state, record_install_state, remove_install_state, label_from_key
from ._install_helpers import _verify_install


def install(local: bool = False, copy: bool = False, reconfigure: bool = False,
            profile_label: str = "", folder: str = "", global_home: str = "") -> None:
    """Build from source and install to targets."""
    from ..services.state_store import get_scope, state_file
    from pathlib import Path

    scope = "local" if local else "global"
    project_path = Path.cwd().resolve() if local else None

    # Build folder overrides from --folder / --profile
    folder_overrides = None
    if folder:
        folder_overrides = {"claude": folder}
    elif profile_label and not folder:
        folder_overrides = {"claude": f".claude-{profile_label}"}

    # Default --global-home from profile label if not explicit
    if profile_label and not global_home:
        global_home = f"~/.claude-{profile_label}"

    state = load_current_state()
    existing = get_scope(state, scope, project_path, profile_label=profile_label) if state else None

    profile_hint = f" (profile: {profile_label})" if profile_label else ""

    if existing and not reconfigure:
        # Print existing-install summary
        print(f"Found existing {scope} installation{profile_hint} at {state_file()}")
        print(f"  Installed: {existing.installed_at}")
        cli_labels = []
        from ..registries.cli_registry import load_registry
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
        print(f"Clearing existing {scope} state{profile_hint} (--reconfigure) ...")
        remove_install_state(scope, project_path, profile_label=profile_label)
        # Fall through to normal install flow

    # Validate args
    if copy and not local:
        print("Error: --copy is only valid with --local installs.")
        print("Global installs always use symlinks.")
        return

    # Build first
    print("Building from source...")
    try:
        from ..commands.build import build
        build()
    except Exception as e:
        print(f"{Color.RED}Build failed: {e}{Color.NC}")
        return

    # Execute
    label_msg = f", profile={profile_label}" if profile_label else ""
    print(f"Installing ({'local' if local else 'global'}, {'copy' if copy else 'symlink'}{label_msg}) ...")
    print("")

    from ..services import installer
    scope = "local" if local else "global"
    copy_mode = copy
    installer.install_all(scope, copy_mode,
                          folder_overrides=folder_overrides,
                          global_home_override=global_home or None)

    print("")
    print(f"{Color.GREEN}Done.{Color.NC} Restart Claude Code / OpenCode to pick up changes.")

    # Record state
    try:
        project_path = Path.cwd() if local else None
        st = build_install_state(
            mode="copy" if copy else "symlink",
            scope="local" if local else "global",
            repo_root=PKG_DIR.parent,
            project_path=project_path,
            profile_label=profile_label,
            folder_overrides=folder_overrides,
            global_home_override=global_home or None,
        )
        record_install_state(st)
    except Exception as e:
        print(f"{Color.YELLOW}Warning: failed to write state.json: {e}{Color.NC}")


def _resolve_overrides_from_state(scope: str, project_path, profile_label: str = ""):
    """Read folder/global_home overrides from state.json for the target scope."""
    from ..services.state_store import load_state, get_scope

    folder_overrides = None
    global_home_override = None

    state = load_state()
    if state is None:
        return folder_overrides, global_home_override

    ss = get_scope(state, scope, project_path, profile_label=profile_label)
    if ss is None:
        return folder_overrides, global_home_override

    for cli_name, bs in ss.clis.items():
        if bs.local_dir_override:
            folder_overrides = folder_overrides or {}
            folder_overrides[cli_name] = bs.local_dir_override
        if bs.global_home_override:
            global_home_override = bs.global_home_override

    return folder_overrides, global_home_override


def uninstall(local: bool = False, global_: bool = False,
              profile_label: str = "", all_profiles: bool = False) -> None:
    """Remove installed components managed by agent-notes."""
    from ..services import installer
    from ..services.state_store import load_state, get_profiles_for_project

    # Determine which scopes to uninstall
    if local and not global_:
        scopes = [("local", Path.cwd().resolve())]
    elif global_ and not local:
        scopes = [("global", None)]
    else:
        scopes = [("global", None), ("local", Path.cwd().resolve())]

    if all_profiles:
        state = load_state()
        if state is None:
            print("Nothing to uninstall — no agent-notes state found.")
            return
        for scope, project_path in scopes:
            if scope == "local":
                profiles = get_profiles_for_project(state, project_path) if state else []
                if not profiles:
                    print(f"  No profiles found for {project_path}")
                    continue
                for key, _ss in profiles:
                    label = label_from_key(key, project_path)
                    folder_overrides, global_home_override = _resolve_overrides_from_state(
                        scope, project_path, label)
                    label_hint = f" profile={label}" if label else ""
                    print(f"Uninstalling agent-notes ({scope}{label_hint}) ...")
                    installer.uninstall_all(scope,
                                            folder_overrides=folder_overrides,
                                            global_home_override=global_home_override,
                                            profile_label=label)
                    try:
                        remove_install_state(scope, project_path, profile_label=label)
                    except Exception as e:
                        print(f"{Color.YELLOW}Warning: failed to clear state.json: {e}{Color.NC}")
            else:
                # Global: uninstall default + all labeled profiles
                global_labels = [""] if (state and state.global_install) else []
                if state:
                    global_labels += list(state.global_installs.keys())
                for label in global_labels:
                    folder_overrides, global_home_override = _resolve_overrides_from_state(
                        scope, None, label)
                    label_hint = f" profile={label}" if label else ""
                    print(f"Uninstalling agent-notes ({scope}{label_hint}) ...")
                    installer.uninstall_all(scope,
                                            folder_overrides=folder_overrides,
                                            global_home_override=global_home_override,
                                            profile_label=label)
                    try:
                        remove_install_state(scope, None, profile_label=label)
                    except Exception as e:
                        print(f"{Color.YELLOW}Warning: failed to clear state.json: {e}{Color.NC}")
        print(f"{Color.GREEN}Done.{Color.NC} agent-notes components removed.")
        return

    for scope, project_path in scopes:
        # Always resolve overrides from state so we clean the right directories
        folder_overrides, global_home_override = _resolve_overrides_from_state(
            scope, project_path, profile_label)

        label_hint = f" profile={profile_label}" if profile_label else ""
        print(f"Uninstalling agent-notes ({scope}{label_hint}) ...")
        installer.uninstall_all(scope,
                                folder_overrides=folder_overrides,
                                global_home_override=global_home_override,
                                profile_label=profile_label)

        # Remove state entry for this scope
        try:
            remove_install_state(scope, project_path, profile_label=profile_label)
        except Exception as e:
            print(f"{Color.YELLOW}Warning: failed to clear state.json: {e}{Color.NC}")

    print(f"{Color.GREEN}Done.{Color.NC} agent-notes components removed.")