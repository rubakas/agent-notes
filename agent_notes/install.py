"""DEPRECATED shim. Import from agent_notes.commands.install instead."""

# Re-export the main command functions
from agent_notes.commands.install import install  # noqa: F401
from agent_notes.commands.uninstall import uninstall  # noqa: F401
from agent_notes.commands.info import show_info  # noqa: F401

# Re-export helper functions that tests and other code might import
from agent_notes.commands._install_helpers import (  # noqa: F401
    install_scripts_global, install_skills_global, install_skills_local,
    install_agents_global, install_agents_local, install_rules_global, install_rules_local,
    uninstall_scripts_global, uninstall_skills_global, uninstall_skills_local,
    uninstall_agents_global, uninstall_agents_local, uninstall_rules_global, uninstall_rules_local,
    count_scripts, count_skills, count_agents, count_global, _verify_install,
    _files_identical, _handle_existing
)

# Re-export fs functions that were imported from services but tests expect from install module
from agent_notes.services.fs import (  # noqa: F401
    place_file, place_dir_contents, remove_symlink,
    remove_all_symlinks_in_dir, remove_dir_if_empty
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
    get_version, find_skill_dirs,
)

# Re-export services that tests patch
from agent_notes import install_state  # noqa: F401
from agent_notes.commands.build import build  # noqa: F401