"""DEPRECATED shim. Import from agent_notes.commands.wizard instead."""

from agent_notes.commands.wizard import *  # noqa: F401,F403

# Explicit re-exports of private names so test patching works
from agent_notes.commands.wizard import (  # noqa: F401
    _confirm_install, _count_rules, _get_skill_groups, 
    _select_cli, _select_mode, _select_models_per_role, _select_scope, _select_skills,
    install_skills_filtered, install_agents_filtered, install_config_filtered
)

# Re-export UI functions that tests patch
from agent_notes.services.ui import (  # noqa: F401
    _HAS_TTY, _safe_input, _can_interactive, _read_key,
    _checkbox_select, _radio_select, _checkbox_select_fallback, _radio_select_fallback
)

# Re-export filesystem functions that tests patch
from agent_notes.services.fs import (  # noqa: F401
    place_file, place_dir_contents, remove_symlink,
    remove_all_symlinks_in_dir, remove_dir_if_empty
)

# Re-export build function that tests patch
from agent_notes.commands.build import build  # noqa: F401

# Re-export install helpers that tests patch
from agent_notes.commands._install_helpers import count_agents, count_skills  # noqa: F401
from agent_notes.commands.wizard import _count_rules  # noqa: F401

# Re-export config constants that tests patch
from agent_notes.config import (  # noqa: F401
    AGENTS_DIR, SKILLS_DIR, RULES_DIR, DATA_DIR, ROOT,
    DIST_DIR, DIST_CLAUDE_DIR, DIST_OPENCODE_DIR, DIST_GITHUB_DIR,
    DIST_RULES_DIR, DIST_SKILLS_DIR, DIST_SCRIPTS_DIR,
    CLAUDE_HOME, OPENCODE_HOME, GITHUB_HOME, AGENTS_HOME,
    MEMORY_DIR, BACKUP_DIR, BIN_HOME, PKG_DIR,
    GLOBAL_CLAUDE_MD, GLOBAL_OPENCODE_MD, GLOBAL_COPILOT_MD,
    AGENTS_YAML, Color, get_version
)