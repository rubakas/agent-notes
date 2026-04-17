"""Build agent configuration files from source."""

import yaml
import shutil
from pathlib import Path
from typing import Dict, Any

from .config import (
    SOURCE_AGENTS_YAML, SOURCE_AGENTS_DIR, SOURCE_GLOBAL_MD, 
    SOURCE_GLOBAL_COPILOT_MD, SOURCE_RULES_DIR,
    DIST_CLAUDE_DIR, DIST_OPENCODE_DIR, DIST_GITHUB_DIR, DIST_RULES_DIR, DIST_DIR,
    info, ROOT, find_skill_dirs
)


def strip_memory_section(content: str) -> str:
    """Strip ## Memory section from content for OpenCode format."""
    lines = content.split('\n')
    result_lines = []
    in_memory_section = False
    
    for line in lines:
        if line.startswith('## Memory'):
            in_memory_section = True
            continue
        elif line.startswith('## ') and in_memory_section:
            # New section after Memory, include this line and continue
            in_memory_section = False
            result_lines.append(line)
        elif not in_memory_section:
            result_lines.append(line)
    
    # Remove trailing empty lines
    while result_lines and result_lines[-1].strip() == '':
        result_lines.pop()
    
    return '\n'.join(result_lines)


def generate_claude_frontmatter(agent_name: str, agent_config: Dict[str, Any], tiers: Dict[str, Any]) -> str:
    """Generate Claude Code format frontmatter."""
    frontmatter = ['---']
    frontmatter.append(f'name: {agent_name}')
    frontmatter.append(f'description: {agent_config["description"]}')
    
    # Map tier to model name
    tier = agent_config['tier']
    model = tiers[tier]['claude']
    frontmatter.append(f'model: {model}')
    
    # Add Claude-specific settings
    claude_config = agent_config.get('claude', {})
    if 'tools' in claude_config:
        frontmatter.append(f'tools: {claude_config["tools"]}')
    if 'disallowedTools' in claude_config:
        frontmatter.append(f'disallowedTools: {claude_config["disallowedTools"]}')
    if 'memory' in claude_config:
        frontmatter.append(f'memory: {claude_config["memory"]}')
    
    # Add metadata
    frontmatter.append(f'color: {agent_config["color"]}')
    frontmatter.append(f'effort: {agent_config["effort"]}')
    frontmatter.append('---')
    
    return '\n'.join(frontmatter)


def generate_opencode_frontmatter(agent_name: str, agent_config: Dict[str, Any], tiers: Dict[str, Any]) -> str:
    """Generate OpenCode format frontmatter."""
    frontmatter = ['---']
    frontmatter.append(f'description: {agent_config["description"]}')
    frontmatter.append(f'mode: {agent_config["mode"]}')
    
    # Map tier to full model string
    tier = agent_config['tier']
    model = tiers[tier]['opencode']
    frontmatter.append(f'model: {model}')
    
    # Handle permissions
    opencode_config = agent_config.get('opencode', {})
    permission = opencode_config.get('permission', {})
    
    if permission:
        frontmatter.append('permission:')
        
        # Handle simple permissions
        if 'edit' in permission:
            frontmatter.append(f'  edit: {permission["edit"]}')
        
        # Handle bash permissions (can be string or dict)
        if 'bash' in permission:
            bash_perm = permission['bash']
            if isinstance(bash_perm, str):
                frontmatter.append(f'  bash: {bash_perm}')
            elif isinstance(bash_perm, dict):
                frontmatter.append('  bash:')
                for key, value in bash_perm.items():
                    # Properly quote keys with special characters
                    if '*' in key or ' ' in key:
                        frontmatter.append(f'    "{key}": {value}')
                    else:
                        frontmatter.append(f'    {key}: {value}')
    
    frontmatter.append('---')
    
    return '\n'.join(frontmatter)


def generate_agent_files(agents_config: Dict[str, Any], tiers: Dict[str, Any]) -> list[Path]:
    """Generate agent files for both Claude and OpenCode formats."""
    generated_files = []
    
    for agent_name, agent_config in agents_config.items():
        # Read the source prompt
        prompt_file = SOURCE_AGENTS_DIR / f'{agent_name}.md'
        if not prompt_file.exists():
            print(f"Warning: Missing source file {prompt_file}")
            continue
        
        prompt_content = prompt_file.read_text()
        
        # Generate Claude Code format
        claude_frontmatter = generate_claude_frontmatter(agent_name, agent_config, tiers)
        claude_content = f"{claude_frontmatter}\n\n{prompt_content}"
        
        claude_file = DIST_CLAUDE_DIR / 'agents' / f'{agent_name}.md'
        claude_file.parent.mkdir(parents=True, exist_ok=True)
        claude_file.write_text(claude_content)
        generated_files.append(claude_file)
        
        # Generate OpenCode format (strip Memory section)
        opencode_frontmatter = generate_opencode_frontmatter(agent_name, agent_config, tiers)
        opencode_prompt = strip_memory_section(prompt_content)
        opencode_content = f"{opencode_frontmatter}\n\n{opencode_prompt}"
        
        opencode_file = DIST_OPENCODE_DIR / 'agents' / f'{agent_name}.md'
        opencode_file.parent.mkdir(parents=True, exist_ok=True)
        opencode_file.write_text(opencode_content)
        generated_files.append(opencode_file)
    
    return generated_files


def copy_global_files() -> list[Path]:
    """Copy global files and rules to destination."""
    copied_files = []
    
    # Copy global.md to both CLAUDE.md and AGENTS.md
    global_content = SOURCE_GLOBAL_MD.read_text()
    
    claude_global = DIST_CLAUDE_DIR / 'CLAUDE.md'
    claude_global.parent.mkdir(parents=True, exist_ok=True)
    claude_global.write_text(global_content)
    copied_files.append(claude_global)
    
    agents_global = DIST_OPENCODE_DIR / 'AGENTS.md'
    agents_global.parent.mkdir(parents=True, exist_ok=True)
    agents_global.write_text(global_content)
    copied_files.append(agents_global)
    
    # Copy global-copilot.md to copilot-instructions.md
    copilot_content = SOURCE_GLOBAL_COPILOT_MD.read_text()
    copilot_global = DIST_GITHUB_DIR / 'copilot-instructions.md'
    copilot_global.parent.mkdir(parents=True, exist_ok=True)
    copilot_global.write_text(copilot_content)
    copied_files.append(copilot_global)
    
    # Copy all rules files
    if SOURCE_RULES_DIR.exists():
        DIST_RULES_DIR.mkdir(parents=True, exist_ok=True)
        
        for rule_file in SOURCE_RULES_DIR.glob('*.md'):
            dest_file = DIST_RULES_DIR / rule_file.name
            shutil.copy2(rule_file, dest_file)
            copied_files.append(dest_file)
    
    return copied_files


def copy_skills() -> list[Path]:
    """Copy skill directories to dist/skills/."""
    dist_skills = DIST_DIR / "skills"
    # Clean and recreate
    if dist_skills.exists():
        shutil.rmtree(dist_skills)
    dist_skills.mkdir(parents=True, exist_ok=True)
    
    copied = []
    for skill_dir in find_skill_dirs():
        dest = dist_skills / skill_dir.name
        shutil.copytree(skill_dir, dest)
        copied.append(dest)
    return copied


def count_lines(file_path: Path) -> int:
    """Count lines in a file."""
    try:
        return len(file_path.read_text().splitlines())
    except Exception:
        return 0


def build() -> None:
    """Build agent configuration files from source."""
    # Read configuration
    if not SOURCE_AGENTS_YAML.exists():
        print(f"Error: {SOURCE_AGENTS_YAML} not found")
        return
    
    config = yaml.safe_load(SOURCE_AGENTS_YAML.read_text())
    agents_config = config['agents']
    tiers = config['tiers']
    
    # Generate agent files
    print("Generating agent files...")
    agent_files = generate_agent_files(agents_config, tiers)
    
    # Copy global files
    print("Copying global files...")
    global_files = copy_global_files()
    
    # Copy skills
    print("Copying skills...")
    skill_files = copy_skills()
    
    # Report results
    all_files = agent_files + global_files + skill_files
    print(f"\nGenerated {len(all_files)} files:")
    
    total_lines = 0
    for file_path in sorted(all_files):
        rel_path = file_path.relative_to(ROOT)
        lines = count_lines(file_path)
        total_lines += lines
        print(f"  {rel_path} ({lines} lines)")
    
    print(f"\nTotal: {total_lines} lines across {len(all_files)} files")


if __name__ == '__main__':
    build()