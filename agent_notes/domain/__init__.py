"""Domain model layer — pure data classes, no I/O, no agent_notes deps."""
from .cli_backend import CLIBackend
from .model import Model
from .role import Role
from .agent import AgentSpec
from .skill import Skill
from .rule import Rule
from .state import State, ScopeState, BackendState, InstalledItem
from .diagnostics import Issue, FixAction, ValidationError, ValidationWarning
from .diff import ComponentDiff, StateDiff

__all__ = [
    "CLIBackend", "Model", "Role", "AgentSpec", "Skill", "Rule",
    "State", "ScopeState", "BackendState", "InstalledItem",
    "Issue", "FixAction", "ValidationError", "ValidationWarning",
    "ComponentDiff", "StateDiff",
]