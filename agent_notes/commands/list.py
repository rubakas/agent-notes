"""List installed components."""

import yaml
from pathlib import Path
from typing import Dict, Any, Optional

from ..registries import default_skill_registry, default_rule_registry


def list_clis() -> None:
    """Print all registered CLIs."""
    from ..cli_backend import load_registry
    registry = load_registry()
    backends = sorted(registry.all(), key=lambda b: b.name)
    print(f"CLIs ({len(backends)}):")
    for b in backends:
        # Pad name to ~10 chars, label to ~20 chars
        print(f"  {b.name:<10} {b.label:<25} → {b.global_home}")


def list_models() -> None:
    """Print all available models with CLI compatibility."""
    from ..model_registry import load_model_registry
    from ..cli_backend import load_registry
    models = load_model_registry().all()
    registry = load_registry()
    print(f"Models ({len(models)}):")
    for m in sorted(models, key=lambda m: m.id):
        compat = [b.name for b in registry.all() if b.first_alias_for(m.aliases) is not None]
        label = f" {m.label}" if hasattr(m, 'label') and m.label else ""
        model_class = f" [{m.model_class}]" if hasattr(m, 'model_class') and m.model_class else ""
        if compat:
            compat_str = ", ".join(compat)
            print(f"  {m.id:<22}{label:<22}{model_class:<10} compatible: {compat_str}")
        else:
            print(f"  {m.id:<22}{label:<22}{model_class:<10} compatible: (none)")


def list_roles() -> None:
    """Print all roles."""
    from ..role_registry import load_role_registry
    roles = load_role_registry().all()
    print(f"Roles ({len(roles)}):")
    for r in sorted(roles, key=lambda r: r.name):
        typical = f" (typical: {r.typical_class})" if hasattr(r, 'typical_class') and r.typical_class else ""
        print(f"  {r.name:<15} {r.description}{typical}")


def list_agents() -> None:
    """List all agents with metadata from YAML."""
    # Import from parent shim to enable test patching
    from .. import list as parent_module
    
    print(f"{parent_module.Color.CYAN}Agents:{parent_module.Color.NC}")
    source_agents_dir = parent_module.DATA_DIR / "agents"
    agents_yaml = parent_module.DATA_DIR / "agents" / "agents.yaml"
    
    # Load agents metadata from YAML if available
    agents_metadata: Dict[str, Dict[str, Any]] = {}
    if agents_yaml.exists():
        try:
            with open(agents_yaml, 'r') as f:
                yaml_data = yaml.safe_load(f)
                if yaml_data and 'agents' in yaml_data:
                    agents_metadata = yaml_data['agents']
        except (yaml.YAMLError, FileNotFoundError):
            pass
    
    if source_agents_dir.exists():
        for f in sorted(source_agents_dir.glob("*.md")):
            name = f.stem
            
            if name in agents_metadata:
                role = agents_metadata[name].get('role', agents_metadata[name].get('tier', ''))  # role or fallback to tier
                description = agents_metadata[name].get('description', '')
                print(f"  {name:<22} {parent_module.Color.DIM}({role:<8}){parent_module.Color.NC} {description}")
            else:
                print(f"  {name}")
    
    print("")

def list_skills() -> None:
    """List all skills."""
    from .. import list as parent_module
    
    print(f"{parent_module.Color.CYAN}Skills:{parent_module.Color.NC}")
    
    # For backward compatibility with tests, call find_skill_dirs through shim
    skill_dirs = parent_module.find_skill_dirs()
    if skill_dirs:
        for skill_path in sorted(skill_dirs):
            print(f"  {skill_path.name}")
    else:
        # If no skills found via find_skill_dirs, try the registry
        try:
            registry = default_skill_registry()
            skills = registry.all()
            if skills:
                for skill in sorted(skills, key=lambda s: s.name):
                    print(f"  {skill.name}")
        except Exception:
            pass  # Ignore registry errors
    
    print("")


# Compatibility function for tests that patch agent_notes.list.find_skill_dirs
def find_skill_dirs():
    """DEPRECATED compatibility shim."""
    from ..config import find_skill_dirs as config_find_skill_dirs
    return config_find_skill_dirs()

def list_rules() -> None:
    """List all rules and global configs."""
    from .. import list as parent_module
    
    print(f"{parent_module.Color.CYAN}Rules:{parent_module.Color.NC}")
    
    # Try registry first, but fall back to filesystem if needed for testing
    try:
        registry = parent_module.default_rule_registry()
        rules = registry.all()
        
        # If we get an empty registry but there are files in parent_module.DATA_DIR/rules, use fallback
        if not rules:
            source_rules_dir = parent_module.DATA_DIR / "rules"
            if source_rules_dir.exists() and list(source_rules_dir.glob("*.md")):
                # Use fallback
                for f in sorted(source_rules_dir.glob("*.md")):
                    print(f"  {f.stem}")
            # else: truly no rules
        else:
            for rule in sorted(rules, key=lambda r: r.name):
                print(f"  {rule.name}")
    except Exception:
        # Fallback to old behavior if registry fails
        source_rules_dir = parent_module.DATA_DIR / "rules"
        if source_rules_dir.exists():
            for f in sorted(source_rules_dir.glob("*.md")):
                print(f"  {f.stem}")
    
    print("")
    
    print(f"{parent_module.Color.CYAN}Global configs:{parent_module.Color.NC}")
    from ..cli_backend import load_registry
    registry = load_registry()
    for backend in registry.all():
        if backend.global_template:
            print(f"  {backend.global_template}")
    print("")

def list_all() -> None:
    """Show grouped summary of everything."""
    # Import from shim to enable test patching
    from .. import list as list_shim
    
    list_shim.list_clis()
    print()
    list_shim.list_models()
    print()
    list_shim.list_roles()
    print()
    list_shim.list_agents()
    list_shim.list_skills()
    list_shim.list_rules()


def list_components(filter_type: str = "all") -> None:
    """List installed components."""
    # Import from shim to enable test patching
    from .. import list as list_shim
    
    dispatch = {
        "agents": list_shim.list_agents,
        "skills": list_shim.list_skills,
        "rules": list_shim.list_rules,
        "clis": list_shim.list_clis,
        "models": list_shim.list_models,
        "roles": list_shim.list_roles,
        "all": list_shim.list_all,
    }
    
    if filter_type in dispatch:
        dispatch[filter_type]()
    else:
        print(f"Unknown filter: {filter_type}")
        print("Usage: agent-notes list [agents|skills|rules|clis|models|roles|all]")
        exit(1)