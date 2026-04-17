"""List installed components."""

import yaml
from pathlib import Path
from typing import Dict, Any, Optional

from .config import ROOT, SOURCE_DIR, Color, find_skill_dirs

def list_agents() -> None:
    """List all agents with tier and description."""
    print(f"{Color.CYAN}Agents:{Color.NC}")
    
    source_agents_dir = SOURCE_DIR / "agents"
    agents_yaml = SOURCE_DIR / "agents.yaml"
    
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
                tier = agents_metadata[name].get('tier', '')
                description = agents_metadata[name].get('description', '')
                print(f"  {name:<22} {Color.DIM}({tier:<8}){Color.NC} {description}")
            else:
                print(f"  {name}")
    
    print("")

def list_skills() -> None:
    """List all skills."""
    print(f"{Color.CYAN}Skills:{Color.NC}")
    
    skill_dirs = find_skill_dirs()
    for skill_path in sorted(skill_dirs):
        skill_name = skill_path.name
        print(f"  {skill_name}")
    
    print("")

def list_rules() -> None:
    """List all rules and global configs."""
    print(f"{Color.CYAN}Rules:{Color.NC}")
    
    source_rules_dir = SOURCE_DIR / "rules"
    if source_rules_dir.exists():
        for f in sorted(source_rules_dir.glob("*.md")):
            print(f"  {f.stem}")
    
    print("")
    
    print(f"{Color.CYAN}Global configs:{Color.NC}")
    print("  global.md")
    print("  global-copilot.md")
    print("")

def list_components(filter_type: str = "all") -> None:
    """List installed components."""
    if filter_type == "agents":
        list_agents()
    elif filter_type == "skills":
        list_skills()
    elif filter_type == "rules":
        list_rules()
    elif filter_type == "all":
        list_agents()
        list_skills()
        list_rules()
    else:
        print(f"Unknown filter: {filter_type}")
        print("Usage: agent-notes list [agents|skills|rules]")
        exit(1)