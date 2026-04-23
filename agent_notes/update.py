"""DEPRECATED shim. Import from agent_notes.commands.update instead."""

from agent_notes.commands.update import *  # noqa: F401,F403

# Re-export config constants that tests patch
from agent_notes.config import (  # noqa: F401
    ROOT, Color, get_version, PKG_DIR
)

# Re-export build function that tests patch
from agent_notes.commands.build import build as run_build  # noqa: F401