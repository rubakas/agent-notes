"""Install command."""

import sys
from pathlib import Path

from ..config import Color, PKG_DIR
from ..domain.state import MemoryConfig
from ..services.install_ownership import replacing
from ..services.install_state_builder import build_install_state
from ..services.ui import printable
from ..services.state_store import (
    StateUnreadable, load_current_state, remove_install_state, label_from_key,
)
from ._install_helpers import (
    commit_install, describe_install, flags_recovery, has_terminal, override_problem,
    placement_errors, profile_label_problem, recommended_pins, render_quietly,
)

STALE_SHOWN = 10


def install(local: bool = False, copy: bool = False, reconfigure: bool = False,
            profile_label: str = "", folder: str = "", global_home: str = "",
            assume_yes: bool = False) -> None:
    """Build from source and install to targets, replacing and cleaning an existing install.

    reconfigure is accepted and does nothing: an install over an existing one always replaces it.
    """
    from ..services.state_store import get_scope

    if copy and not local:
        print("Error: --copy is only valid with --local installs.")
        print("Global installs always use symlinks.")
        sys.exit(2)

    scope = "local" if local else "global"
    project_path = Path.cwd().resolve() if local else None
    _validate_targets(global_home, folder, project_path or Path.cwd().resolve())
    problem = profile_label_problem(profile_label)
    if problem:
        print(f"Error: --profile {printable(profile_label)} is not a usable label: {problem}.")
        sys.exit(2)

    # Build folder overrides from --folder / --profile
    folder_overrides = None
    if folder:
        folder_overrides = {"claude": folder}
    elif profile_label and not folder:
        folder_overrides = {"claude": f".claude-{profile_label}"}

    # Default --global-home from profile label if not explicit
    global_home_flag = global_home
    if profile_label and not global_home:
        global_home = f"~/.claude-{profile_label}"

    # Read-only snapshot: nothing below changes state until the final write.
    snapshot = load_current_state()
    existing = get_scope(snapshot, scope, project_path, profile_label=profile_label) if snapshot else None
    what = describe_install(scope, project_path, profile_label)

    if existing and not assume_yes and not has_terminal():
        print(f"Refusing to replace {printable(what)} without a terminal; rerun with --yes.")
        sys.exit(2)

    # Render this run's install first: the plan and the placed links both read dist/.
    # Fresh: the recommended pins plus the flags, not the pins of the install being replaced.
    pins, efforts = recommended_pins()
    # Memory and plugin toggles are global and have no flag: this run renders the saved ones, or
    # the defaults on a fresh machine, so a first install and a reinstall render the same text.
    memory = snapshot.memory if snapshot is not None else MemoryConfig()
    print("Building from source...")
    try:
        from ..commands.build import build
        build(scope=scope, project_path=project_path, profile_label=profile_label,
              role_models=pins, role_efforts=efforts, fresh=True, memory=memory)
    except StateUnreadable:
        raise
    except Exception as e:
        print(f"{Color.RED}Build failed: {e}{Color.NC}")
        try:
            render_quietly(scope, project_path, profile_label)
        except Exception:
            pass  # the same failure: the message above already says what to fix
        sys.exit(1)

    # dist/ is shared by every install: until this one is placed, put back what the
    # saved install renders if the run stops here
    try:
        confirmed = not existing or assume_yes or _confirm_replace(
            snapshot, existing, what, scope, project_path, profile_label, copy,
            folder_overrides, global_home)
    except BaseException:
        render_quietly(scope, project_path, profile_label)
        raise
    if not confirmed:
        render_quietly(scope, project_path, profile_label)
        print("Nothing was changed.")
        return

    # Execute
    label_msg = f", profile={profile_label}" if profile_label else ""
    print(f"Installing ({'local' if local else 'global'}, {'copy' if copy else 'symlink'}{label_msg}) ...")
    print("")

    from ..services import installer
    recovery = flags_recovery(local, copy, profile_label, folder, global_home_flag)
    try:
        with replacing(existing), placement_errors(recovery):
            installer.install_all(scope, copy,
                                  folder_overrides=folder_overrides,
                                  global_home_override=global_home or None)
    except installer.HookInstallError as e:
        print(f"Error: {e}.\n{recovery}", file=sys.stderr)
        sys.exit(1)

    # Record state: the manifest of what was just placed, then cleanup, then the write
    st = build_install_state(
        mode="copy" if copy else "symlink",
        scope=scope,
        repo_root=PKG_DIR.parent,
        project_path=project_path,
        profile_label=profile_label,
        folder_overrides=folder_overrides,
        global_home_override=global_home or None,
        role_models=pins,
        role_efforts=efforts,
    )
    commit_install(st, snapshot, scope, project_path, profile_label, recovery)

    print("")
    print(f"{Color.GREEN}Done.{Color.NC} Restart Claude Code / OpenCode to pick up changes.")


def _validate_targets(global_home: str, folder: str, project: Path) -> None:
    """--global-home and --folder name a directory agent-notes will fill and later sweep: see
    override_problem for what it refuses."""
    for flag, kind, value in (("--global-home", "home", global_home), ("--folder", "folder", folder)):
        problem = override_problem(kind, value, project) if value else ""
        if problem:
            print(f"Error: {flag} {printable(value)} {problem}.")
            sys.exit(2)


def _confirm_replace(snapshot, existing, what, scope, project_path, profile_label, copy,
                     folder_overrides, global_home) -> bool:
    """Show what replacing the install places and removes, and ask."""
    from ..registries.cli_registry import load_registry
    from ..services import install_cleanup as cleanup
    from ..services.install_plan import plan_install, summarize_plan
    from ..services.ui import _safe_input

    registry = load_registry()
    with replacing(existing):
        plan = plan_install(scope=scope, registry=registry, copy_mode=copy,
                            folder_overrides=folder_overrides, global_home_override=global_home or None)
    placed = summarize_plan(plan).to_install
    stale = cleanup.planned_stale(snapshot, scope, project_path, profile_label,
                                  [a.dst for a in plan], registry)
    print()
    print(f"Replacing the {what} (installed {existing.installed_at}, {existing.mode}).")
    print("  Model pins reset to the recommended ones.")
    print(f"  {len(placed)} files will be placed.")
    print(f"  {len(stale)} stale files will be removed." if stale else "  Nothing stale to remove.")
    for item in stale[:STALE_SHOWN]:
        print(f"    {printable(item.path)}")
    if len(stale) > STALE_SHOWN:
        print(f"    ... {len(stale) - STALE_SHOWN} more")
    print()
    return _safe_input("Replace this install? [y/N]: ", "N").lower() in ("y", "yes")


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
                    except StateUnreadable:
                        raise
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
                    except StateUnreadable:
                        raise
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
        except StateUnreadable:
            raise
        except Exception as e:
            print(f"{Color.YELLOW}Warning: failed to clear state.json: {e}{Color.NC}")

    print(f"{Color.GREEN}Done.{Color.NC} agent-notes components removed.")