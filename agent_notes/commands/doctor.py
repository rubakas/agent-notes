"""Health check for agent-notes installation."""

# Re-export for backward compatibility. New code should import from agent_notes.domain.
from ..domain.diagnostics import Issue, FixAction  # noqa: F401

# Re-export config constants that tests mock  
from ..config import (
    ROOT, DIST_CLAUDE_DIR, DIST_OPENCODE_DIR, DIST_GITHUB_DIR, DIST_RULES_DIR, 
    DIST_SKILLS_DIR, DIST_SCRIPTS_DIR, SCRIPTS_DIR, BIN_HOME,
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
    _count_scripts,
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

    settings_path, _context_file, hook_command = _session_hook_paths(claude_backend, scope)
    if not has_hook(settings_path, "SessionStart", hook_command):
        issues.append(Issue(
            "missing_hook",
            str(settings_path),
            "SessionStart hook not found — run: agent-notes install to re-add the hook",
        ))


def diagnose(scope: str, fix: bool = False) -> bool:
    """Run all diagnostic checks and optionally apply fixes."""
    from .. import install_state
    
    print_summary(scope)
    
    issues = []
    fix_actions = []
    
    # Run checks
    check_stale_files(scope, issues, fix_actions)
    check_broken_symlinks(scope, issues, fix_actions) 
    check_shadowed_files(scope, issues, fix_actions)
    check_missing_files(scope, issues, fix_actions)
    check_content_drift(scope, issues, fix_actions)
    
    # Build freshness check (scope-independent)
    check_build_freshness(issues, fix_actions)

    # SessionStart hook check (Claude Code only)
    _check_session_hook(scope, issues)

    # Print role→model assignments
    state = install_state.load_current_state()
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