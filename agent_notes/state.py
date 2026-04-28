"""Installation state management."""

# Re-export dataclasses from domain
from .domain.state import State, ScopeState, BackendState, InstalledItem  # noqa: F401

# Re-export I/O functions from services
from .services.state_store import (
    state_dir, state_file, 
    load_state as load, load_state,  # Export both names
    save_state as save, save_state,  # Export both names
    clear_state as clear,
    get_scope, set_scope, remove_scope, default_state, sha256_of, now_iso
)

# Backward compatibility aliases
__all__ = [
    'State', 'ScopeState', 'BackendState', 'InstalledItem',
    'state_dir', 'state_file', 'load', 'save', 'clear',
    'load_state', 'save_state',  # Original names too
    'get_scope', 'set_scope', 'remove_scope', 'default_state', 'sha256_of', 'now_iso'
]