"""User-facing commands. Each module is a thin orchestrator.

Commands may import from: services/, registries/, domain/, config.
Commands MUST NOT import other commands (use services to share logic).

Exception: install/uninstall/info share helpers via _install_helpers.py since
they are sibling members of one logical command group.
"""
from .install import install
from .uninstall import uninstall
from .info import show_info
from .build import build
from .doctor import doctor
from .validate import validate
from .update import update
from .regenerate import regenerate
from .set_role import set_role
from .wizard import interactive_install
from . import list as list_cmd
from . import memory as memory_cmd

__all__ = [
    "install", "uninstall", "show_info",
    "build", "doctor", "validate", "update",
    "regenerate", "set_role", "interactive_install",
    "list_cmd", "memory_cmd",
]