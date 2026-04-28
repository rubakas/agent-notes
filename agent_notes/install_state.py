"""Build and read State objects during install/uninstall flows."""

# Re-export everything from services
from .services.install_state_builder import build_install_state, git_head_short, _get_target_path
from .services.state_store import record_install_state, load_current_state, remove_install_state, clear_state

# Backward compatibility
__all__ = [
    'build_install_state', 'git_head_short', 'record_install_state', 
    'load_current_state', 'remove_install_state', 'clear_state'
]