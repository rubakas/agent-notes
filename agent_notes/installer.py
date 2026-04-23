"""Registry-driven installer service."""

# Re-export everything from services
from .services.installer import *  # noqa: F403, F401

# Re-export constants that tests expect to mock
from .config import (
    DIST_DIR, DIST_RULES_DIR, DIST_SKILLS_DIR, DIST_SCRIPTS_DIR,
    AGENTS_HOME, BIN_HOME
)

# Re-export private functions that tests need to mock
from .services.installer import _install_universal_skills, _uninstall_universal_skills