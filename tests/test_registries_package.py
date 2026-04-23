"""Tests for the registries package."""

def test_registries_reexports():
    from agent_notes.registries import (
        CLIRegistry, ModelRegistry, RoleRegistry,
        AgentRegistry, SkillRegistry, RuleRegistry,
        load_registry, default_registry,
        load_model_registry, default_model_registry,
        load_role_registry, default_role_registry,
        load_agent_registry, default_agent_registry,
        load_skill_registry, default_skill_registry,
        load_rule_registry, default_rule_registry,
    )
    # sanity: instantiable names
    for name in [CLIRegistry, ModelRegistry, RoleRegistry,
                 AgentRegistry, SkillRegistry, RuleRegistry]:
        assert isinstance(name, type)


def test_backward_compat_shims():
    from agent_notes.cli_backend import CLIRegistry as A
    from agent_notes.registries import CLIRegistry as B
    assert A is B
    from agent_notes.model_registry import load_model_registry as L1
    from agent_notes.registries import load_model_registry as L2
    assert L1 is L2


def test_new_registries_load():
    from agent_notes.registries import (
        default_agent_registry, default_skill_registry, default_rule_registry
    )
    agents = default_agent_registry()
    skills = default_skill_registry()
    rules = default_rule_registry()
    # Just check they return instances with all() callable
    assert callable(agents.all)
    assert callable(skills.all)
    assert callable(rules.all)
    # And produce lists (possibly empty, possibly not)
    assert isinstance(agents.all(), list)
    assert isinstance(skills.all(), list)
    assert isinstance(rules.all(), list)


def test_registries_import_only_domain_and_config():
    """Registries depend only on domain + config + stdlib + yaml. Lock the layering."""
    import ast
    from pathlib import Path
    reg_dir = Path(__file__).parent.parent / "agent_notes" / "registries"
    allowed_prefixes = ("agent_notes.domain", "agent_notes.config", "agent_notes.registries")
    for py_file in reg_dir.rglob("*.py"):
        if py_file.name == "__init__.py":
            continue  # __init__.py imports from registries submodules
        tree = ast.parse(py_file.read_text())
        for node in ast.walk(tree):
            mods = []
            if isinstance(node, ast.ImportFrom) and node.module:
                mods.append(node.module)
            elif isinstance(node, ast.Import):
                mods.extend(a.name for a in node.names)
            for m in mods:
                if m.startswith("agent_notes") and not any(m.startswith(prefix) for prefix in allowed_prefixes):
                    raise AssertionError(f"{py_file.name} imports {m} — registries may not depend on services/commands")