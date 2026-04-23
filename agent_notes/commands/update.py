"""Pull latest changes, rebuild, show diff, and reinstall."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional

from ..config import ROOT, Color, get_version, PKG_DIR
from .. import install_state, update_diff


def _run_git(args, cwd) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=cwd,
        capture_output=True, text=True, check=True,
    )


def _git_head(repo) -> str:
    try:
        return _run_git(["rev-parse", "HEAD"], repo).stdout.strip()
    except Exception:
        return ""


def _git_pull(repo) -> None:
    _run_git(["pull", "--ff-only"], repo)


def _show_commits(repo, before: str, after: str, limit: int = 5) -> None:
    if not before or not after or before == after:
        return
    try:
        out = _run_git(["log", "--oneline", f"{before}..{after}"], repo).stdout.strip()
    except Exception:
        return
    if not out:
        return
    lines = out.split("\n")
    print(f"{Color.GREEN}Updated{Color.NC} {len(lines)} commits.")
    for line in lines[:limit]:
        print(f"  {line}")
    if len(lines) > limit:
        print(f"  ... and {len(lines) - limit} more")
    print("")


def update(
    dry_run: bool = False,
    yes: bool = False,
    only: Optional[list[str]] = None,
    since: Optional[str] = None,
    skip_pull: bool = False,
) -> None:
    """Pull, rebuild, diff against state.json, prompt, reinstall.
    
    - dry_run: show the diff, do NOT reinstall
    - yes: don't prompt, just reinstall if there are changes
    - only: list of component types to include in the diff (agents, skills, rules, commands, config, settings)
    - since: if set, compare against this git sha rather than current state.json (advanced)
    - skip_pull: skip the git pull (useful when user already pulled)
    """
    from .. import update as parent_module
    
    repo = parent_module.ROOT
    print("Updating agent-notes...")
    print("")

    # Step 1: git pull
    if not skip_pull:
        git_dir = repo / ".git"
        if not git_dir.exists():
            print(f"{parent_module.Color.RED}Error:{parent_module.Color.NC} Not a git repository. Update requires a git-based install.")
            return
        before = _git_head(repo)
        try:
            _git_pull(repo)
        except subprocess.CalledProcessError:
            print(f"{Color.RED}Error:{Color.NC} Could not fast-forward. Resolve manually: cd {repo} && git status")
            return
        after = _git_head(repo)
        _show_commits(repo, before, after)
        if before == after and before:
            print(f"{Color.GREEN}Already up to date (no new commits).{Color.NC}")

    # Step 2: rebuild dist/
    print("Rebuilding...")
    try:
        from .. import update as parent_module
        parent_module.run_build()
    except Exception as e:
        print(f"{Color.RED}Build failed: {e}{Color.NC}")
        return

    # Step 3: determine which scope to update and compute "new" state
    old_state = install_state.load_current_state()
    
    # Determine scope: if CWD has a local install, update that; otherwise update global
    current_project = Path.cwd()
    local_exists = old_state and str(current_project.resolve()) in old_state.local_installs if old_state else False
    global_exists = old_state and old_state.global_install is not None if old_state else False
    
    # Default to global unless local exists and global doesn't, or if only local exists
    if local_exists and not global_exists:
        scope = "local"
        project_path = current_project
    elif local_exists and global_exists:
        # Both exist - default to global (could add --local flag in future)
        scope = "global"
        project_path = None
    else:
        # Default to global
        scope = "global"
        project_path = None
    
    # Get the existing scope's mode, or default
    if scope == "global" and old_state and old_state.global_install:
        mode = old_state.global_install.mode
    elif scope == "local" and old_state and str(current_project.resolve()) in old_state.local_installs:
        mode = old_state.local_installs[str(current_project.resolve())].mode
    else:
        mode = "symlink"  # default
    
    new_state = install_state.build_install_state(
        mode=mode,
        scope=scope,
        repo_root=parent_module.PKG_DIR.parent,
        project_path=project_path,
    )

    # If `since` is provided, we'd need to stash old state and rebuild from that commit.
    # Keep it minimal for now: `since` only influences the commit label in the diff output.
    if since:
        if old_state is not None:
            old_state.source_commit = since
        else:
            print(f"{Color.YELLOW}Warning: --since provided but no prior state.json; treating as initial install.{Color.NC}")

    # Step 4: diff
    diff = update_diff.diff_states(old_state, new_state)
    if only:
        diff = update_diff.filter_diff(diff, only=only)

    # Step 5: render report
    print("")
    print(update_diff.render_diff_report(diff, use_color=Color.NC != ""))
    print("")

    # Step 6: decide
    if not diff.has_changes():
        print(f"{Color.GREEN}Nothing to apply.{Color.NC}")
        return

    if dry_run:
        print(f"{Color.CYAN}Dry run — no changes applied.{Color.NC}")
        return

    if not yes:
        resp = input("Apply these changes? [Y/n] ").strip().lower()
        if resp not in ("", "y", "yes"):
            print("Aborted.")
            return

    # Step 7: reinstall (use existing install flow — it also writes new state.json)
    # Use the determined scope and mode from the analysis above
    import agent_notes.install as install_shim
    local = (scope == "local")
    copy = (mode == "copy")
    install_shim.install(local=local, copy=copy)