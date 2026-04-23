"""DEPRECATED shim. Import from agent_notes.commands.memory instead."""

from agent_notes.commands.memory import *  # noqa: F401,F403

# Re-export config constants that tests patch
from agent_notes.config import (  # noqa: F401
    ROOT, MEMORY_DIR, BACKUP_DIR, Color
)

# Re-export functions that tests patch
from agent_notes.commands.memory import (  # noqa: F401
    do_list, do_size, do_show, do_reset, do_export, do_import
)