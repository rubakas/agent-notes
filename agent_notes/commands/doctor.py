"""Health check for agent-notes installation."""

from pathlib import Path

from ..registries.skill_registry import load_skill_registry

# Re-export for backward compatibility. New code should import from agent_notes.domain.
from ..domain.diagnostics import Issue, FixAction  # noqa: F401

# Re-export config constants that tests mock  
from ..config import (
    ROOT, DIST_CLAUDE_DIR, DIST_OPENCODE_DIR, DIST_GITHUB_DIR, DIST_RULES_DIR,
    DIST_SKILLS_DIR, BIN_HOME,
    CLAUDE_HOME, OPENCODE_HOME, GITHUB_HOME, AGENTS_HOME,
    Color, info, issue, ok, warn, fail
)

# Re-export all diagnostic functions from services
from ..services.diagnostics import (
    check_stale_files,
    check_broken_symlinks,
    check_shadowed_files,
    check_missing_files,
    check_content_drift,
    check_build_freshness,
    count_stale,
    print_summary,
    print_issues,
    do_fix,
    _check_role_models,
    _find_dist_source,
    _count_agents,
    _count_skills,
    _count_rules,
    _check_config,
    _cli_base_dir,
    _print_status
)

# Re-export filesystem utilities from services/fs for backward compatibility
from ..services.fs import (
    resolve_symlink, 
    symlink_target_exists, 
    files_differ
)

# Canonical group vocabulary for skill frontmatter.
# "process" and "domain" come from the base skills in data/skills/.
# "rails", "docker", and "kamal" come from the sub-skills that are generated
# during the release/packaging step and land in data/skills/ of the built
# package (e.g. rails-models → group: rails, rails-kamal → group: kamal,
# docker-compose → group: docker).  There is no single source-of-truth
# constant elsewhere in the codebase, so the full vocabulary is listed here.
_VALID_GROUPS = {"process", "domain", "rails", "docker", "kamal"}
_VALID_MEMORY_BACKENDS = {"obsidian", "wiki", "local", "none"}


def check_skill_frontmatter(scope: str, issues: list, fix_actions: list, profile_label: str = "") -> None:
    """Warn (non-fatal) about skill frontmatter violations.

    Checks every skill for:
    - non-empty name and description
    - group, if present, is in {"process", "domain"}
    - requires_memory tokens, if present, are each in {"obsidian", "wiki", "local", "none"}

    Violations are printed as advisories and do NOT affect issues/fix_actions or exit code.
    """
    registry = load_skill_registry()
    for skill in registry.all():
        if not skill.name:
            print(f"  [skill-frontmatter] {skill.path.name}: 'name' is empty")
        if not skill.description:
            print(f"  [skill-frontmatter] {skill.path.name}: 'description' is empty")
        if skill.group and skill.group not in _VALID_GROUPS:
            print(f"  [skill-frontmatter] {skill.name}: 'group' value '{skill.group}' is not in {sorted(_VALID_GROUPS)}")
        if skill.requires_memory:
            for token in skill.requires_memory.split(","):
                token = token.strip()
                if token and token not in _VALID_MEMORY_BACKENDS:
                    print(f"  [skill-frontmatter] {skill.name}: 'requires_memory' token '{token}' is not in {sorted(_VALID_MEMORY_BACKENDS)}")


def _check_session_hook(scope: str, issues: list) -> None:
    """Check that the Claude Code SessionStart hook is registered in settings.json."""
    from ..services.settings_writer import has_hook
    from ..services.installer import _session_hook_paths
    from ..domain.diagnostics import Issue

    try:
        from ..registries.cli_registry import load_registry
        registry = load_registry()
        claude_backend = registry.get("claude")
    except KeyError:
        return

    from ..services.state_store import load_state, get_profiles_for_project
    state = load_state()

    # Check all profiles for the current project (local scope) or default (global)
    backends_to_check = [claude_backend]
    if state and scope == "local":
        for _key, ss in get_profiles_for_project(state, Path.cwd()):
            bs = ss.clis.get("claude")
            if bs and bs.local_dir_override:
                backends_to_check.append(claude_backend.with_local_dir(bs.local_dir_override))

    for backend in backends_to_check:
        settings_path, _context_file, hook_command = _session_hook_paths(backend, scope)
        if not settings_path.exists():
            continue
        if not has_hook(settings_path, "SessionStart", hook_command):
            issues.append(Issue(
                "missing_hook",
                str(settings_path),
                "SessionStart hook not found — run: agent-notes install to re-add the hook",
            ))

    # Memory bridge check on the default backend only
    settings_path, _, _ = _session_hook_paths(claude_backend, scope)
    from ..constants import Hooks
    if state and state.memory.backend in ("obsidian", "wiki"):
        if settings_path.exists() and not has_hook(settings_path, "SessionStart", Hooks.MEMORY_BRIDGE):
            issues.append(Issue(
                "missing_hook",
                str(settings_path),
                "memory-bridge SessionStart hook not found — run: agent-notes install to re-add",
            ))


def check_version_drift(scope: str, issues: list, fix_actions: list) -> None:
    """Check if the installed package version matches the current running version."""
    from ..services.state_store import load_current_state, get_scope
    from ..config import get_version
    from ..domain.diagnostics import Issue, FixAction
    from pathlib import Path

    state = load_current_state()
    if state is None:
        return

    project_path = Path.cwd() if scope == "local" else None
    scope_state = get_scope(state, scope, project_path)
    if scope_state is None:
        return

    installed_version = scope_state.installed_version
    if not installed_version:
        return

    current_version = get_version()
    if installed_version != current_version:
        issues.append(Issue(
            "version_drift",
            "state.json",
            f"Installed with v{installed_version} but running v{current_version}. "
            "Run `agent-notes doctor --fix` or `agent-notes install` to update.",
        ))
        fix_actions.append(FixAction("_TRIGGER_INSTALL", "state.json", "reinstall to update"))


def diagnose(scope: str, fix: bool = False) -> bool:
    """Run all diagnostic checks and optionally apply fixes."""
    print_summary(scope)

    issues = []
    fix_actions = []

    from ..services.state_store import load_current_state, get_profiles_for_project
    from ..services.state_store import label_from_key

    # For local scope, run checks against each installed profile
    if scope == "local":
        state = load_current_state()
        profiles = []
        if state:
            profiles = get_profiles_for_project(state, Path.cwd().resolve())
        # Fall back to default profile if none recorded
        if not profiles:
            profiles = [("", None)]
        for key, _ss in profiles:
            label = label_from_key(key, Path.cwd())
            check_stale_files(scope, issues, fix_actions, profile_label=label)
            check_broken_symlinks(scope, issues, fix_actions, profile_label=label)
            check_shadowed_files(scope, issues, fix_actions, profile_label=label)
            check_missing_files(scope, issues, fix_actions, profile_label=label)
            check_content_drift(scope, issues, fix_actions, profile_label=label)
    else:
        check_stale_files(scope, issues, fix_actions)
        check_broken_symlinks(scope, issues, fix_actions)
        check_shadowed_files(scope, issues, fix_actions)
        check_missing_files(scope, issues, fix_actions)
        check_content_drift(scope, issues, fix_actions)

    # Build freshness check (scope-independent)
    check_build_freshness(issues, fix_actions)

    # Version drift check
    check_version_drift(scope, issues, fix_actions)

    # SessionStart hook check (Claude Code only)
    _check_session_hook(scope, issues)

    # Skill frontmatter advisory check (warn-only, non-fatal)
    check_skill_frontmatter(scope, issues, fix_actions)

    # Print role→model assignments
    state = load_current_state()
    if state is not None:
        _check_role_models(state)
    
    # Print issues and optionally fix
    if print_issues(issues):
        return True  # No issues
    
    if fix:
        result = do_fix(issues, fix_actions)
        # Services layer flagged that an install is needed — invoke it here
        # (commands layer), avoiding a services→commands dependency.
        if any(a.action == "_TRIGGER_INSTALL" for a in fix_actions):
            from ..commands.install import install
            install()
        return result
    else:
        return False  # Issues found but not fixed

# Alias for backward compatibility with CLI
def doctor(local: bool = False, fix: bool = False):
    """Main doctor function called by CLI."""
    scope = "local" if local else "global"
    return diagnose(scope, fix)