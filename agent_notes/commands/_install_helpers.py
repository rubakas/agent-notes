"""Shared installation helpers for install/uninstall/info commands."""

import os
import shlex
import sys
from contextlib import contextmanager

from ..config import DIST_CLAUDE_DIR, DIST_OPENCODE_DIR, DIST_GITHUB_DIR, DIST_RULES_DIR, DIST_SKILLS_DIR
from ..services.ui import printable


def count_skills() -> int:
    """Count skill directories."""
    if not DIST_SKILLS_DIR.exists():
        return 0
    return len([d for d in DIST_SKILLS_DIR.iterdir() if d.is_dir()])


def count_agents(backend) -> int:
    """Count agents for backend from the canonical YAML source. Returns 0 if backend
    doesn't support agents."""
    if not backend.supports("agents"):
        return 0
    from ..registries.agent_registry import load_agent_registry
    registry = load_agent_registry()
    return sum(1 for a in registry.available() if not a.excluded_from(backend.name))


def count_global() -> int:
    """Count global config files."""
    count = 0

    # Check each potential global config file (maintaining backward compatibility)
    if (DIST_CLAUDE_DIR / "CLAUDE.md").exists():
        count += 1
    if (DIST_OPENCODE_DIR / "AGENTS.md").exists():
        count += 1
    if (DIST_GITHUB_DIR / "copilot-instructions.md").exists():
        count += 1

    # Count rules files
    if DIST_RULES_DIR.exists():
        count += len(list(DIST_RULES_DIR.glob("*.md")))

    return count


def _verify_install(scope_state, scope, project_path, registry) -> list[str]:
    """Check each file recorded in scope_state.installed exists. Return list of missing issues."""
    from pathlib import Path
    issues = []
    for cli_name, backend_state in scope_state.clis.items():
        try:
            backend = registry.get(cli_name)
        except KeyError:
            issues.append(f"CLI '{cli_name}' no longer in registry")
            continue
        # Print per-component counts
        for component_type, items in backend_state.installed.items():
            present = 0
            missing_names = []
            for name, item in items.items():
                if Path(item.target).exists():
                    present += 1
                else:
                    missing_names.append(name)
            total = len(items)
            if missing_names:
                comp_label = f"{backend.label} {component_type}"
                print(f"  ✗ {comp_label}: {len(missing_names)} missing ({', '.join(missing_names[:3])}{'...' if len(missing_names) > 3 else ''})")
                for m in missing_names:
                    issues.append(f"{comp_label}: {m} missing")
            else:
                if total > 0:
                    if component_type == "config":
                        comp_label = f"{backend.label} config"
                    else:
                        comp_label = f"{backend.label} {component_type}"
                    print(f"  ✓ {total} {comp_label} present")
    return issues

def profile_label_problem(label: str) -> str:
    """Why *label* cannot name a profile, or "" when it can: it becomes part of a folder name
    (.claude-<label>), so it must not hold a path separator, a NUL or a control character."""
    if "/" in label or "\\" in label or not label.isprintable():
        return "a label cannot hold '/', '\\', or a control character"
    return ""


def override_problem(kind: str, value: str, project) -> str:
    """Why *value* cannot be the local folder (kind "folder") or the global home (kind "home") of
    a CLI, or "" when it can. The one check behind --folder/--global-home, the wizard's Profile
    rows and the wizard's last look before it places anything. Spoken after the value:
    "<value> <problem>"."""
    from pathlib import Path
    from ..services.install_ownership import home_is_valid
    from ..services.install_plan import expanded_home, is_safe_local_dir

    if not value.isprintable():
        return "holds a control character"
    if kind == "folder":   # nothing expands ~ in a folder: it is taken as written, under the project
        path = Path(value) if Path(value).is_absolute() else Path(project) / value
    else:
        path = expanded_home(value)
        if path is None:
            return "has no home directory: the user after '~' does not exist"
    if not home_is_valid(path, project if kind == "folder" else None):
        return ("is not a CLI directory of its own: it is '/', your home folder, a folder above it, "
                "or the project itself")
    if kind == "folder" and not is_safe_local_dir(value):
        return "must be a folder inside the project: it is an absolute path, starts with '~' or climbs out with '..'"
    return ""


def describe_install(scope: str, project_path, profile_label: str = "") -> str:
    """'local install at /p (profile work)': how messages name the install being replaced."""
    where = "global install" if scope == "global" else f"local install at {project_path}"
    return where + (f" (profile {profile_label})" if profile_label else "")


def has_terminal() -> bool:
    """True when both stdin and stdout are a terminal: only then may anything prompt."""
    import sys
    return sys.stdin.isatty() and sys.stdout.isatty()


def commit_install(new_state, snapshot, scope: str, project_path, profile_label: str,
                   recovery: str) -> int:
    """The tail of every install, after the new files are placed and the new manifest is built:
    recompute the stale set from that manifest, remove it, then write state.json.

    A failed state write is an error with a recovery command, not a warning: the files are
    placed, so rerunning the same install converges. Returns how many stale paths were removed.
    """
    from ..registries.cli_registry import load_registry
    from ..services import install_cleanup as cleanup
    from ..services.state_store import StateUnreadable, get_scope, record_install_state

    registry = load_registry()
    old = get_scope(snapshot, scope, project_path, profile_label=profile_label) if snapshot else None
    new = get_scope(new_state, scope, project_path, profile_label=profile_label)
    claims = cleanup.claims_of_others(snapshot, scope, project_path, profile_label, registry)
    stale = cleanup.stale_placements(old, scope, project_path, cleanup.manifest_targets(new),
                                     claims, registry)
    try:
        removed = cleanup.remove_stale(stale)
        cleanup.remove_dropped_hooks(
            cleanup.dropped_hook_backends(old, new.clis, scope, project_path, claims, registry), scope)
        cleanup.prune_empty(cleanup.prunable_dirs(old, scope, project_path, registry))
    except OSError as e:
        print(f"Error: the install was placed but could not remove the old install's files "
              f"({e}).\n{recovery}", file=sys.stderr)
        sys.exit(1)
    try:
        record_install_state(new_state)
    except StateUnreadable:
        raise
    except Exception as e:
        print(f"Error: the install was placed but state.json could not be written ({e}).\n"
              f"{recovery}", file=sys.stderr)
        sys.exit(1)
    return len(removed)


def _shell_word(value: str) -> str:
    """*value* as one shell word. A leading ~/ stays bare so the shell still expands it."""
    if value.startswith("~/"):
        return "~/" + shlex.quote(value[2:]) if value[2:] else "~/"
    return shlex.quote(value)


def rerun_command(local: bool = False, copy: bool = False, profile_label: str = "",
                  folder: str = "", global_home: str = "") -> str:
    """The command that repeats an install, for recovery messages. Values are joined with '=' so
    one that starts with '-' is still a value to argparse."""
    parts = ["agent-notes install"]
    if local:
        parts.append("--local")
    if copy:
        parts.append("--copy")
    if profile_label:
        parts.append(f"--profile={_shell_word(profile_label)}")
    if folder:
        parts.append(f"--folder={_shell_word(folder)}")
    if global_home:
        parts.append(f"--global-home={_shell_word(global_home)}")
    return " ".join(parts + ["--yes"])


def recommended_pins() -> tuple[dict, dict]:
    """({cli: {role: model}}, {cli: {role: effort}}) of the recommended setup, for every CLI
    that has agents: what the review starts from, and what a flags install renders and records."""
    from ..registries.cli_registry import load_registry
    from .wizard.role_models import Catalog, recommended_choices

    catalog, models, efforts = Catalog(), {}, {}
    for backend in load_registry().available():
        if not backend.supports("agents"):
            continue
        cli_models, cli_efforts = recommended_choices(catalog, backend)
        if cli_models:
            models[backend.name], efforts[backend.name] = cli_models, cli_efforts
    return models, efforts


def render_quietly(scope: str, project_path, profile_label: str, **picks) -> None:
    """Render dist/ without output, as the wizard's _render does."""
    from ..services.fs import quiet_output, silent_ops
    from .build import build
    with silent_ops(), quiet_output():
        build(scope=scope, project_path=project_path, profile_label=profile_label, **picks)


def flags_recovery(local: bool = False, copy: bool = False, profile_label: str = "",
                   folder: str = "", global_home: str = "") -> str:
    """What to say after a failed flags install: the exact flags repeat it."""
    return f"Fix the cause, then rerun to converge: {rerun_command(local, copy, profile_label, folder, global_home)}"


def wizard_recovery(scope: str, copy: bool, profile_label: str = "", folder_overrides=None,
                    global_home: str = "") -> str:
    """What to say after a failed wizard install. Its choices (CLIs, skills, pins, memory) cannot be
    replayed as flags, so the review is the way back; the flags form is added only when it
    reproduces the same target (and then installs the recommended setup there)."""
    text = "Fix the cause, then rerun agent-notes install and pick the same choices."
    if copy and scope != "local":
        return text   # --copy is a local-only flag: no flags form reproduces this target
    folder = (folder_overrides or {}).get("claude", "")
    if folder == f".claude-{profile_label}" and profile_label:
        folder = ""
    if global_home == f"~/.claude-{profile_label}" and profile_label:
        global_home = ""
    command = rerun_command(scope == "local", copy, profile_label, folder, global_home)
    return f"{text}\nTo install the recommended setup on the same target instead: {command}"


@contextmanager
def placement_errors(recovery: str):
    """A file that cannot be placed (permissions, a read-only disk) is an error with a recovery
    hint and exit 1, not a traceback. Nothing after the failed placement runs: no cleanup,
    no state write."""
    try:
        yield
    except OSError as e:
        named = e.filename2 or e.filename
        path = os.path.abspath(named) if named else "?"
        print(f"Error: could not place {printable(path)}: {e.strerror or e}\n{recovery}", file=sys.stderr)
        sys.exit(1)
