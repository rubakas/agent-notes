"""Services — side-effecting operations called by commands."""
# Re-export commonly used symbols for convenience. Be conservative to avoid namespace pollution.
from . import fs, ui, state_store, install_state_builder, rendering, diff, diagnostics, validation

# Note: installer causes circular import with cli_backend -> registries -> config -> ui
# Import installer directly when needed: from agent_notes.services import installer

__all__ = ["fs", "ui", "state_store", "install_state_builder", "rendering", "diff", "diagnostics", "validation"]