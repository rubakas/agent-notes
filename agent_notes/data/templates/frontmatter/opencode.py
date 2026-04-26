"""OpenCode frontmatter generator template."""

from typing import Dict, Any


# OpenCode requires `color` to be a 6-digit hex string (^#[0-9a-fA-F]{6}$)
# or one of a small set of theme names. agents.yaml uses Claude's named colors
# (which is the documented Claude Code standard), so we translate them here
# when emitting OpenCode frontmatter. Hex values are Tailwind-style mid-tones.
_CLAUDE_COLOR_TO_HEX = {
    'red':    '#ef4444',
    'blue':   '#3b82f6',
    'green':  '#22c55e',
    'yellow': '#eab308',
    'purple': '#a855f7',
    'orange': '#f97316',
    'pink':   '#ec4899',
    'cyan':   '#06b6d4',
}


def _to_opencode_color(value: str) -> str:
    """Translate a color value to an OpenCode-acceptable form.
    
    Already-hex values pass through unchanged. Known Claude color names
    are mapped to their hex equivalents. Unknown values fall back to the
    raw string so OpenCode-native theme names (primary/secondary/etc.)
    still work if anyone uses them.
    """
    if value.startswith('#'):
        return value
    return _CLAUDE_COLOR_TO_HEX.get(value, value)


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
    
    # Emit color if defined. OpenCode requires hex format; translate from
    # Claude's named colors (the source-of-truth format in agents.yaml).
    if 'color' in agent_config:
        frontmatter.append(f'color: {_to_opencode_color(agent_config["color"])}')
    
    frontmatter.append('---')
    
    return '\n'.join(frontmatter)


def post_process(prompt: str, ctx: dict) -> str:
    """Strip ## Memory section from prompt for OpenCode (doesn't support agent memory)."""
    return _strip_memory_section(prompt)


def _strip_memory_section(content: str) -> str:
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
