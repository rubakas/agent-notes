"""OpenCode frontmatter generator template."""

from .base import COLOR_TO_HEX, strip_sections


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
        color = COLOR_TO_HEX.get(agent_config['color'], agent_config['color'])
        frontmatter.append(f"color: '{color}'")
    
    frontmatter.append('---')
    
    return '\n'.join(frontmatter)


def post_process(prompt: str, ctx: dict) -> str:
    """Strip OpenCode-irrelevant sections from prompt.

    Strips:
    - ## Memory* sections (OpenCode doesn't support agent memory)
    - ## Cost reporting section (cost-report is a Claude Code CLI tool, not available in OpenCode)
    """
    return strip_sections(prompt)
