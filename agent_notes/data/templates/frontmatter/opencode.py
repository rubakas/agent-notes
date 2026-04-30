"""OpenCode frontmatter generator template."""

from typing import Dict, Any


_COLOR_TO_HEX = {
    'red':    '#ef4444',
    'blue':   '#3b82f6',
    'green':  '#22c55e',
    'yellow': '#eab308',
    'purple': '#a855f7',
    'orange': '#f97316',
    'pink':   '#ec4899',
    'cyan':   '#06b6d4',
    'iris':   '#6366f1',
    'violet': '#8b5cf6',
    'ruby':   '#e11d48',
    'gold':   '#d97706',
    'gray':   '#6b7280',
    'jade':   '#10b981',
    'lime':   '#84cc16',
    'mint':   '#14b8a6',
}


def render(ctx: dict) -> str:
    """Render YAML frontmatter for an OpenCode agent.
    
    ctx keys:
      agent_name:  str
      agent_config: dict (from agents.yaml entry)
      model_str:   str (resolved model string)
      backend_name: str
      backend:     CLIBackend object or None
    """
    agent_config = ctx['agent_config']
    model_str = ctx['model_str']
    
    frontmatter = ['---']
    frontmatter.append(f'description: {agent_config["description"]}')
    frontmatter.append(f'mode: {agent_config["mode"]}')
    frontmatter.append(f'model: {model_str}')
    
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
    
    if 'color' in agent_config:
        color = _COLOR_TO_HEX.get(agent_config['color'], agent_config['color'])
        frontmatter.append(f"color: '{color}'")
    
    frontmatter.append('---')
    
    return '\n'.join(frontmatter)


def post_process(prompt: str, ctx: dict) -> str:
    """Strip OpenCode-irrelevant sections from prompt.

    Strips:
    - ## Memory* sections (OpenCode doesn't support agent memory)
    - ## Cost reporting section (cost-report is a Claude Code CLI tool, not available in OpenCode)
    """
    _STRIP_PREFIXES = ("## Memory", "## Cost reporting")
    return _strip_sections(prompt, _STRIP_PREFIXES)


def _strip_sections(content: str, strip_prefixes: tuple) -> str:
    """Strip ## sections whose heading starts with any of the given prefixes."""
    lines = content.split('\n')
    result_lines = []
    in_stripped_section = False

    for line in lines:
        if any(line.startswith(prefix) for prefix in strip_prefixes):
            in_stripped_section = True
            continue
        elif line.startswith('## ') and in_stripped_section:
            in_stripped_section = False
            result_lines.append(line)
        elif not in_stripped_section:
            result_lines.append(line)

    # Remove trailing empty lines
    while result_lines and result_lines[-1].strip() == '':
        result_lines.pop()

    return '\n'.join(result_lines)
