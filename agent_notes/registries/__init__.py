"""Registries — load YAML/Markdown descriptors into typed in-memory indexes."""
from .cli_registry import CLIRegistry, load_registry, default_registry
from .model_registry import ModelRegistry, load_model_registry, default_model_registry
from .role_registry import RoleRegistry, load_role_registry, default_role_registry
from .agent_registry import AgentRegistry, load_agent_registry, default_agent_registry
from .skill_registry import SkillRegistry, load_skill_registry, default_skill_registry
from .rule_registry import RuleRegistry, load_rule_registry, default_rule_registry

__all__ = [
    "CLIRegistry", "load_registry", "default_registry",
    "ModelRegistry", "load_model_registry", "default_model_registry",
    "RoleRegistry", "load_role_registry", "default_role_registry",
    "AgentRegistry", "load_agent_registry", "default_agent_registry",
    "SkillRegistry", "load_skill_registry", "default_skill_registry",
    "RuleRegistry", "load_rule_registry", "default_rule_registry",
]