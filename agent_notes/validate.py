"""DEPRECATED shim. Import from agent_notes.commands.validate instead."""

from agent_notes.commands.validate import *  # noqa: F401,F403

# Re-export validation helpers for backward compatibility
from agent_notes.services.validation import (  # noqa: F401
    has_field, get_field, line_count, has_frontmatter, check_unclosed_code_blocks
)

# Re-export config constants that tests patch
from agent_notes.config import (  # noqa: F401
    ROOT, DIST_DIR, DATA_DIR, DIST_CLAUDE_DIR, DIST_OPENCODE_DIR, DIST_GITHUB_DIR, 
    DIST_RULES_DIR, get_version, find_skill_dirs, Color
)