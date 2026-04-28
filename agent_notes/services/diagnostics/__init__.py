"""Diagnostic checks and fixes for agent-notes installation."""

from ._checks import (
    check_stale_files,
    check_broken_symlinks,
    check_shadowed_files,
    check_missing_files,
    check_content_drift,
    check_build_freshness,
    _find_dist_source,
)
from ._display import (
    count_stale,
    _print_status,
    print_summary,
    print_issues,
    _cli_base_dir,
    _count_agents,
    _count_skills,
    _count_scripts,
    _count_rules,
    _check_config,
    _check_role_models,
)
from ._fix import do_fix

__all__ = [
    "check_stale_files",
    "check_broken_symlinks",
    "check_shadowed_files",
    "check_missing_files",
    "check_content_drift",
    "check_build_freshness",
    "_find_dist_source",
    "count_stale",
    "_print_status",
    "print_summary",
    "print_issues",
    "_cli_base_dir",
    "_count_agents",
    "_count_skills",
    "_count_scripts",
    "_count_rules",
    "_check_config",
    "_check_role_models",
    "do_fix",
]
