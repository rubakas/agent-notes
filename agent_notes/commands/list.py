"""List installed components."""

import yaml
from pathlib import Path
from typing import Dict, Any, Optional

from ..registries import default_skill_registry, default_rule_registry
from ..config import Color, DATA_DIR, find_skill_dirs


def list_clis() -> None:
    """Print all registered CLIs."""
    from ..registries.cli_registry import load_registry
    registry = load_registry()
    backends = sorted(registry.all(), key=lambda b: b.name)
    print(f"CLIs ({len(backends)}):")
    for b in backends:
        # Pad name to ~10 chars, label to ~20 chars
        print(f"  {b.name:<10} {b.label:<25} → {b.global_home}")


def list_models() -> None:
    """Print the catalog grouped by provider, each provider in its own rank order.

    `rank` is per-provider data, so mixing providers into one list would make the
    numbers read as a single sequence they are not. Providers print in name order
    (anthropic, then openai). Columns come from the shared `model_columns`
    helper, so this table matches the wizard's and `config role-model`'s.
    """
    from ..registries.model_registry import load_model_registry
    from .config import model_columns, MODEL_COLUMNS_HEADER

    models = load_model_registry().all()
    by_provider: Dict[str, list] = {}
    for m in models:
        provider = next(iter(m.aliases), "(no provider)")
        by_provider.setdefault(provider, []).append(m)

    print(f"Models ({len(models)}):")
    for provider in sorted(by_provider):
        provider_models = sorted(by_provider[provider], key=lambda m: m.rank)
        print(f"\n  {provider} ({len(provider_models)}):")
        print(f"    {'rank':>4}  {MODEL_COLUMNS_HEADER}")
        for m in provider_models:
            print(f"    {m.rank:>4}  {model_columns(m)}")


def list_roles() -> None:
    """Print all roles."""
    from ..registries.role_registry import load_role_registry
    roles = load_role_registry().all()
    print(f"Roles ({len(roles)}):")
    for r in sorted(roles, key=lambda r: r.name):
        budget = "unbounded" if r.budget is None else f"${r.budget:g}/M in"
        print(f"  {r.name:<15} {r.description} (budget: {budget})")


def list_agents() -> None:
    """List all agents with metadata from YAML."""
    print(f"{Color.CYAN}Agents:{Color.NC}")
    source_agents_dir = DATA_DIR / "agents"
    agents_yaml = DATA_DIR / "agents" / "agents.yaml"

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
                print(f"  {name:<22} {Color.DIM}({role:<8}){Color.NC} {description}")
            else:
                print(f"  {name}")

    print("")

def list_skills() -> None:
    """List all skills."""
    print(f"{Color.CYAN}Skills:{Color.NC}")

    skill_dirs = find_skill_dirs()
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


def list_rules() -> None:
    """List all rules and global configs."""
    print(f"{Color.CYAN}Rules:{Color.NC}")

    # Try registry first, but fall back to filesystem if needed for testing
    try:
        registry = default_rule_registry()
        rules = registry.all()

        # If we get an empty registry but there are files in DATA_DIR/rules, use fallback
        if not rules:
            source_rules_dir = DATA_DIR / "rules"
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
        source_rules_dir = DATA_DIR / "rules"
        if source_rules_dir.exists():
            for f in sorted(source_rules_dir.glob("*.md")):
                print(f"  {f.stem}")

    print("")

    print(f"{Color.CYAN}Global configs:{Color.NC}")
    from ..registries.cli_registry import load_registry
    registry = load_registry()
    for backend in registry.all():
        if backend.global_template:
            print(f"  {backend.global_template}")
    print("")

def list_all() -> None:
    """Show grouped summary of everything."""
    list_clis()
    print()
    list_models()
    print()
    list_roles()
    print()
    list_agents()
    list_skills()
    list_rules()


def list_components(filter_type: str = "all") -> None:
    """List installed components."""
    dispatch = {
        "agents": list_agents,
        "skills": list_skills,
        "rules": list_rules,
        "clis": list_clis,
        "models": list_models,
        "roles": list_roles,
        "all": list_all,
    }

    if filter_type in dispatch:
        dispatch[filter_type]()
    else:
        print(f"Unknown filter: {filter_type}")
        print("Usage: agent-notes list [agents|skills|rules|clis|models|roles|all]")
        exit(1)
