"""DEPRECATED shim. Import from agent_notes.commands.regenerate instead."""

from agent_notes.commands.regenerate import *  # noqa: F401,F403

# Re-export config constants that tests might patch
from agent_notes.config import (  # noqa: F401
    Color, DATA_DIR, PKG_DIR
)