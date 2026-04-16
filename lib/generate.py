#!/usr/bin/env python3
"""
Generates CLI-specific agent configuration files from source/ directory.

Reads source/agents.yaml + source/agents/*.md and generates:
1. dist/agents/<name>.md (Claude Code format)
2. dist/agents-opencode/<name>.md (OpenCode format)
3. Global files: dist/global/CLAUDE.md, dist/global/AGENTS.md, dist/global/copilot-instructions.md
4. Rules: dist/global/rules/*.md
"""

import sys
import os
import shutil
import glob
from pathlib import Path
import re


def parse_agent_config(agent_content):
    """Parse individual agent configuration from YAML text."""
    agent_config = {}
    
    # Extract basic fields
    desc_match = re.search(r'^\s*description:\s*"([^"]*)"', agent_content, re.MULTILINE)
    if desc_match:
        agent_config['description'] = desc_match.group(1)
    
    tier_match = re.search(r'^\s*tier:\s*(\w+)', agent_content, re.MULTILINE)
    if tier_match:
        agent_config['tier'] = tier_match.group(1)
    
    mode_match = re.search(r'^\s*mode:\s*(\w+)', agent_content, re.MULTILINE)
    if mode_match:
        agent_config['mode'] = mode_match.group(1)
    
    color_match = re.search(r'^\s*color:\s*(\w+)', agent_content, re.MULTILINE)
    if color_match:
        agent_config['color'] = color_match.group(1)
    
    effort_match = re.search(r'^\s*effort:\s*(\w+)', agent_content, re.MULTILINE)
    if effort_match:
        agent_config['effort'] = effort_match.group(1)
    
    # Extract claude section
    claude_match = re.search(r'^\s*claude:\s*$\n(.*?)(?=^\s*(?:opencode:|$))', agent_content, re.MULTILINE | re.DOTALL)
    if claude_match:
        claude_content = claude_match.group(1)
        claude_config = {}
        
        tools_match = re.search(r'^\s*tools:\s*"([^"]*)"', claude_content, re.MULTILINE)
        if tools_match:
            claude_config['tools'] = tools_match.group(1)
        
        disallowed_match = re.search(r'^\s*disallowedTools:\s*"([^"]*)"', claude_content, re.MULTILINE)
        if disallowed_match:
            claude_config['disallowedTools'] = disallowed_match.group(1)
        
        memory_match = re.search(r'^\s*memory:\s*(\w+)', claude_content, re.MULTILINE)
        if memory_match:
            claude_config['memory'] = memory_match.group(1)
        
        if claude_config:
            agent_config['claude'] = claude_config
    
    # Extract opencode section with permissions
    opencode_match = re.search(r'^\s*opencode:\s*$\n(.*)', agent_content, re.MULTILINE | re.DOTALL)
    if opencode_match:
        opencode_content = opencode_match.group(1)
        opencode_config = {}
        
        # Extract permission section
        perm_match = re.search(r'^\s*permission:\s*$\n(.*)', opencode_content, re.MULTILINE | re.DOTALL)
        if perm_match:
            perm_content = perm_match.group(1)
            permission = {}
            
            # Extract edit permission
            edit_match = re.search(r'^\s*edit:\s*(\w+)', perm_content, re.MULTILINE)
            if edit_match:
                permission['edit'] = edit_match.group(1)
            
            # Extract bash permissions
            bash_match = re.search(r'^\s*bash:\s*(\w+)$', perm_content, re.MULTILINE)
            if bash_match:
                # Simple bash permission
                permission['bash'] = bash_match.group(1)
            else:
                # Complex bash permissions
                bash_complex_match = re.search(r'^\s*bash:\s*$\n(.*)', perm_content, re.MULTILINE | re.DOTALL)
                if bash_complex_match:
                    bash_content = bash_complex_match.group(1)
                    bash_rules = {}
                    
                    # Extract individual bash rules
                    for line in bash_content.split('\n'):
                        line = line.strip()
                        if not line:
                            continue
                        
                        # Handle quoted keys like "git diff*": allow
                        quote_match = re.match(r'^"([^"]*)"\s*:\s*(\w+)', line)
                        if quote_match:
                            bash_rules[quote_match.group(1)] = quote_match.group(2)
                        else:
                            # Handle unquoted keys like "*": deny
                            unquote_match = re.match(r'^([^:]+)\s*:\s*(\w+)', line)
                            if unquote_match:
                                key = unquote_match.group(1).strip().strip('"')
                                bash_rules[key] = unquote_match.group(2)
                    
                    if bash_rules:
                        permission['bash'] = bash_rules
            
            if permission:
                opencode_config['permission'] = permission
        
        if opencode_config:
            agent_config['opencode'] = opencode_config
    
    return agent_config


def read_yaml(file_path):
    """Read and parse agents.yaml file using regex patterns."""
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Split into main sections
    sections = re.split(r'^([a-z]+):\s*$', content, flags=re.MULTILINE)
    
    agents = {}
    tiers = {}
    
    # Find agents and tiers sections
    for i in range(1, len(sections), 2):
        section_name = sections[i]
        section_content = sections[i + 1] if i + 1 < len(sections) else ""
        
        if section_name == 'agents':
            # Parse agents
            agent_parts = re.split(r'^  ([a-z-]+):\s*$', section_content, flags=re.MULTILINE)
            
            # Skip the first empty part and process pairs
            for j in range(1, len(agent_parts), 2):
                if j + 1 < len(agent_parts):
                    agent_name = agent_parts[j]
                    agent_content = agent_parts[j + 1]
                    agents[agent_name] = parse_agent_config(agent_content)
        
        elif section_name == 'tiers':
            # Parse tiers
            tier_parts = re.split(r'^  ([a-z]+):\s*$', section_content, flags=re.MULTILINE)
            
            # Skip the first empty part and process pairs
            for j in range(1, len(tier_parts), 2):
                if j + 1 < len(tier_parts):
                    tier_name = tier_parts[j]
                    tier_content = tier_parts[j + 1]
                    
                    tier_config = {}
                    claude_match = re.search(r'^\s*claude:\s*(\w+)', tier_content, re.MULTILINE)
                    if claude_match:
                        tier_config['claude'] = claude_match.group(1)
                    
                    opencode_match = re.search(r'^\s*opencode:\s*"([^"]*)"', tier_content, re.MULTILINE)
                    if opencode_match:
                        tier_config['opencode'] = opencode_match.group(1)
                    
                    tiers[tier_name] = tier_config
    
    return {'agents': agents, 'tiers': tiers}


def read_text(file_path):
    """Read text file content."""
    with open(file_path, 'r') as f:
        return f.read()


def write_text(file_path, content):
    """Write content to text file."""
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, 'w') as f:
        f.write(content)


def strip_memory_section(content):
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


def generate_claude_frontmatter(agent_name, agent_config, tiers):
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


def generate_opencode_frontmatter(agent_name, agent_config, tiers):
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


def generate_agent_files(agents_config, tiers, source_dir, agent_notes_dir):
    """Generate agent files for both Claude and OpenCode formats."""
    generated_files = []
    
    for agent_name, agent_config in agents_config.items():
        # Read the source prompt
        prompt_file = os.path.join(source_dir, 'agents', f'{agent_name}.md')
        if not os.path.exists(prompt_file):
            print(f"Warning: Missing source file {prompt_file}")
            continue
        
        prompt_content = read_text(prompt_file)
        
        # Generate Claude Code format
        claude_frontmatter = generate_claude_frontmatter(agent_name, agent_config, tiers)
        claude_content = f"{claude_frontmatter}\n\n{prompt_content}"
        
        claude_file = os.path.join(agent_notes_dir, 'dist', 'agents', f'{agent_name}.md')
        write_text(claude_file, claude_content)
        generated_files.append(claude_file)
        
        # Generate OpenCode format (strip Memory section)
        opencode_frontmatter = generate_opencode_frontmatter(agent_name, agent_config, tiers)
        opencode_prompt = strip_memory_section(prompt_content)
        opencode_content = f"{opencode_frontmatter}\n\n{opencode_prompt}"
        
        opencode_file = os.path.join(agent_notes_dir, 'dist', 'agents-opencode', f'{agent_name}.md')
        write_text(opencode_file, opencode_content)
        generated_files.append(opencode_file)
    
    return generated_files


def copy_global_files(source_dir, agent_notes_dir):
    """Copy global files and rules to destination."""
    copied_files = []
    
    # Copy global.md to both CLAUDE.md and AGENTS.md
    global_content = read_text(os.path.join(source_dir, 'global.md'))
    
    claude_global = os.path.join(agent_notes_dir, 'dist', 'global', 'CLAUDE.md')
    write_text(claude_global, global_content)
    copied_files.append(claude_global)
    
    agents_global = os.path.join(agent_notes_dir, 'dist', 'global', 'AGENTS.md')
    write_text(agents_global, global_content)
    copied_files.append(agents_global)
    
    # Copy global-copilot.md to copilot-instructions.md
    copilot_content = read_text(os.path.join(source_dir, 'global-copilot.md'))
    copilot_global = os.path.join(agent_notes_dir, 'dist', 'global', 'copilot-instructions.md')
    write_text(copilot_global, copilot_content)
    copied_files.append(copilot_global)
    
    # Copy all rules files
    rules_src_dir = os.path.join(source_dir, 'rules')
    rules_dest_dir = os.path.join(agent_notes_dir, 'dist', 'global', 'rules')
    
    if os.path.exists(rules_src_dir):
        os.makedirs(rules_dest_dir, exist_ok=True)
        
        for rule_file in glob.glob(os.path.join(rules_src_dir, '*.md')):
            filename = os.path.basename(rule_file)
            dest_file = os.path.join(rules_dest_dir, filename)
            shutil.copy2(rule_file, dest_file)
            copied_files.append(dest_file)
    
    return copied_files


def count_lines(file_path):
    """Count lines in a file."""
    try:
        with open(file_path, 'r') as f:
            return len(f.readlines())
    except:
        return 0


def main():
    if len(sys.argv) != 2:
        print("Usage: python3 generate.py <agent-notes-dir>")
        sys.exit(1)
    
    agent_notes_dir = sys.argv[1]
    source_dir = os.path.join(agent_notes_dir, 'source')
    
    # Read configuration
    config_file = os.path.join(source_dir, 'agents.yaml')
    if not os.path.exists(config_file):
        print(f"Error: {config_file} not found")
        sys.exit(1)
    
    config = read_yaml(config_file)
    agents_config = config['agents']
    tiers = config['tiers']
    
    # Generate agent files
    print("Generating agent files...")
    agent_files = generate_agent_files(agents_config, tiers, source_dir, agent_notes_dir)
    
    # Copy global files
    print("Copying global files...")
    global_files = copy_global_files(source_dir, agent_notes_dir)
    
    # Report results
    all_files = agent_files + global_files
    print(f"\nGenerated {len(all_files)} files:")
    
    total_lines = 0
    for file_path in sorted(all_files):
        rel_path = os.path.relpath(file_path, agent_notes_dir)
        lines = count_lines(file_path)
        total_lines += lines
        print(f"  {rel_path} ({lines} lines)")
    
    print(f"\nTotal: {total_lines} lines across {len(all_files)} files")


if __name__ == '__main__':
    main()