"""Frontmatter and agent file rendering."""

import yaml
import shutil
import importlib
from pathlib import Path
from typing import Dict, Any, Optional


def _load_frontmatter_template(template_name):
    """Load a frontmatter template plugin by name.
    
    Args:
        template_name: Name of the template (e.g., 'claude', 'opencode', None)
    
    Returns:
        The template module, or None if template_name is None
    
    Raises:
        ValueError: if template_name is not a simple identifier (defensive: prevents
            directory traversal or loading arbitrary modules) or if no such template
            file exists under agent_notes/data/templates/frontmatter/.
    """
    if template_name is None:
        return None
    if not isinstance(template_name, str) or not template_name.isidentifier():
        raise ValueError(
            f"Invalid frontmatter template name: {template_name!r}. "
            f"Must be a simple Python identifier (e.g. 'claude', 'opencode')."
        )
    try:
        return importlib.import_module(f"agent_notes.data.templates.frontmatter.{template_name}")
    except ModuleNotFoundError as e:
        raise ValueError(
            f"Frontmatter template '{template_name}' not found. "
            f"Expected agent_notes/data/templates/frontmatter/{template_name}.py to exist. "
            f"Original error: {e}"
        ) from e


def generate_agent_files(agents_config: Dict[str, Any], tiers: Dict[str, Any], 
                         state=None, scope='global', project_path=None) -> list[Path]:
    """Generate agent files for all CLI backends.
    
    Args:
        agents_config: Dict of agent configurations from agents.yaml
        tiers: Dict mapping tiers to model names per backend (legacy fallback)
        state: Optional State object for role-based model resolution
        scope: 'global' or 'local' (only used if state is provided)
        project_path: Path for local scope (only used if state is provided and scope='local')
    
    If state is None, behaves exactly as before (uses tiers dict).
    If state is provided, tries state-driven resolution first, falls back to tiers on miss.
    """
    from ..cli_backend import load_registry
    from ..model_registry import load_model_registry
    from .. import state as state_module
    from ..config import AGENTS_DIR, DIST_DIR
    
    generated_files = []
    registry = load_registry()
    model_registry = None  # Lazy load only if needed
    scope_state = None
    
    # Get scope state if state is provided
    if state is not None:
        scope_state = state_module.get_scope(state, scope, project_path)
    
    for agent_name, agent_config in agents_config.items():
        # Read the source prompt
        prompt_file = AGENTS_DIR / f'{agent_name}.md'
        if not prompt_file.exists():
            print(f"Warning: Missing source file {prompt_file}")
            continue
        
        prompt_content = prompt_file.read_text()
        
        # Generate for each backend that supports agents
        for backend in registry.all():
            if not backend.supports("agents"):
                continue
                
            # Skip if agent is excluded for this backend
            # Check both new backend-specific exclusion and legacy exclude_flag
            excluded = False
            
            # New backend-specific exclusion: check if backend.name key exists and has exclude: true
            if backend.name in agent_config and isinstance(agent_config[backend.name], dict):
                backend_cfg = agent_config[backend.name]
                if backend_cfg.get("exclude"):
                    excluded = True
            
            # Legacy exclusion: check if exclude_flag is set (for backward compat)
            exclude_flag = backend.exclude_flag
            if not excluded and exclude_flag and agent_config.get(exclude_flag):
                excluded = True
            
            if excluded:
                continue
            
            # Get frontmatter generator
            frontmatter_type = backend.features.get("frontmatter")
            if frontmatter_type is None:
                continue  # Skip backends without frontmatter (like copilot)
            
            # Load template dynamically
            template = _load_frontmatter_template(frontmatter_type)
            if template is None:
                continue
            
            # Resolve model: try state-driven first, fall back to tiers
            model_str = None
            agent_role = agent_config.get('role')
            
            if (scope_state is not None and 
                agent_role is not None and 
                backend.name in scope_state.clis and
                agent_role in scope_state.clis[backend.name].role_models):
                
                # State-driven resolution path
                model_id = scope_state.clis[backend.name].role_models[agent_role]
                
                # Lazy load model registry
                if model_registry is None:
                    model_registry = load_model_registry()
                
                try:
                    model = model_registry.get(model_id)
                    # Resolve for this backend's accepted providers
                    resolved = model.resolve_for_providers(list(backend.accepted_providers))
                    if resolved is not None:
                        provider, alias_str = resolved
                        model_str = alias_str
                except KeyError:
                    # Model not found in registry, fall back to tiers
                    pass
            
            # Fall back to tiers if state-driven resolution failed or not applicable
            if model_str is None:
                if 'tier' not in agent_config:
                    raise ValueError(f"Agent '{agent_name}' has no 'role' field and no fallback 'tier' field. Cannot determine model.")
                tier = agent_config['tier']
                if backend.name not in tiers[tier]:
                    raise ValueError(f"tier '{tier}' missing model for CLI '{backend.name}' in agents.yaml")
                model_str = tiers[tier][backend.name]
            
            # Build context for template
            ctx = {
                'agent_name': agent_name,
                'agent_config': agent_config,
                'model_str': model_str,
                'backend_name': backend.name,
                'backend': backend,
            }
            
            # Generate frontmatter using template
            frontmatter = template.render(ctx)
            
            # Apply post-processing transformation (e.g., strip memory section)
            content = template.post_process(prompt_content, ctx)
            
            # Combine and write
            full_content = f"{frontmatter}\n\n{content}"
            
            # Write to backend's agents directory
            from .. import installer
            agents_dir = installer.dist_source_for(backend, "agents")
            if agents_dir is None:
                agents_dir = DIST_DIR / backend.name / "agents"
            
            agent_file = agents_dir / f'{agent_name}.md'
            agent_file.parent.mkdir(parents=True, exist_ok=True)
            agent_file.write_text(full_content)
            generated_files.append(agent_file)
    
    return generated_files


def render_globals() -> list[Path]:
    """Copy global files to destinations."""
    from ..config import (
        GLOBAL_CLAUDE_MD, GLOBAL_OPENCODE_MD, GLOBAL_COPILOT_MD,
        DIST_CLAUDE_DIR, DIST_OPENCODE_DIR, DIST_GITHUB_DIR
    )
    
    copied_files = []
    
    # Copy global-claude.md to CLAUDE.md
    claude_global_content = GLOBAL_CLAUDE_MD.read_text()
    claude_global = DIST_CLAUDE_DIR / 'CLAUDE.md'
    claude_global.parent.mkdir(parents=True, exist_ok=True)
    claude_global.write_text(claude_global_content)
    copied_files.append(claude_global)
    
    # Copy global-opencode.md to AGENTS.md
    opencode_global_content = GLOBAL_OPENCODE_MD.read_text()
    agents_global = DIST_OPENCODE_DIR / 'AGENTS.md'
    agents_global.parent.mkdir(parents=True, exist_ok=True)
    agents_global.write_text(opencode_global_content)
    copied_files.append(agents_global)
    
    # Copy global-copilot.md to copilot-instructions.md
    copilot_content = GLOBAL_COPILOT_MD.read_text()
    copilot_global = DIST_GITHUB_DIR / 'copilot-instructions.md'
    copilot_global.parent.mkdir(parents=True, exist_ok=True)
    copilot_global.write_text(copilot_content)
    copied_files.append(copilot_global)
    
    return copied_files


def load_agents_config() -> tuple[Dict[str, Any], Dict[str, Any]]:
    """Load agents configuration from agents.yaml."""
    from ..config import AGENTS_YAML
    
    if not AGENTS_YAML.exists():
        raise FileNotFoundError(f"Configuration file not found: {AGENTS_YAML}")
    
    config = yaml.safe_load(AGENTS_YAML.read_text())
    return config.get('agents', {}), config.get('tiers', {})