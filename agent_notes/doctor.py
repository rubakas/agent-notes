"""DEPRECATED shim. Import from agent_notes.commands.doctor instead."""

from agent_notes.commands.doctor import *  # noqa: F401,F403

# Explicit re-exports of private names so test patching works
from agent_notes.commands.doctor import (  # noqa: F401
    _check_role_models, _find_dist_source, _count_agents, _count_skills,
    _count_scripts, _count_rules, _check_config, _cli_base_dir, _print_status
)

# Re-export config constants that tests patch
from agent_notes.config import (  # noqa: F401
    ROOT, PKG_DIR, DATA_DIR, DIST_DIR,
    AGENTS_DIR, SKILLS_DIR, RULES_DIR, SCRIPTS_DIR, MODELS_DIR, ROLES_DIR,
    AGENTS_YAML,
    GLOBAL_CLAUDE_MD, GLOBAL_OPENCODE_MD, GLOBAL_COPILOT_MD,
    DIST_CLAUDE_DIR, DIST_OPENCODE_DIR, DIST_GITHUB_DIR,
    DIST_RULES_DIR, DIST_SKILLS_DIR, DIST_SCRIPTS_DIR,
    BIN_HOME, CLAUDE_HOME, OPENCODE_HOME, GITHUB_HOME, AGENTS_HOME,
    MEMORY_DIR, BACKUP_DIR,
    Color, ok, warn, fail, error, info, issue, linked, removed, skipped,
    get_version, find_skill_dirs
)