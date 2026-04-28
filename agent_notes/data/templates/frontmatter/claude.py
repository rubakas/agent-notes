"""Claude Code frontmatter generator template."""

from typing import Dict, Any


def render(ctx: dict) -> str:
    """Render YAML frontmatter for a Claude Code agent.
    
    ctx keys:
      agent_name:  str
      agent_config: dict (from agents.yaml entry)
      model_str:   str (resolved model string)
      backend_name: str
      backend:     CLIBackend object or None
    """
    agent_name = ctx['agent_name']
    agent_config = ctx['agent_config']
    model_str = ctx['model_str']
    
    frontmatter = ['---']
    frontmatter.append(f'name: {agent_name}')
    frontmatter.append(f'description: {agent_config["description"]}')
    frontmatter.append(f'model: {model_str}')
    
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


def post_process(prompt: str, ctx: dict) -> str:
    """Optional: transform the prompt body. Return as-is by default."""
    return prompt
