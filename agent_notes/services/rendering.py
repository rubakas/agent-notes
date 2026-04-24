"""Frontmatter and agent file rendering."""

import yaml
import shutil
import importlib
import re
from pathlib import Path
from typing import Dict, Any, Optional


def expand_includes(text: str, shared_dir: Path) -> str:
    """Expand include directives in text by substituting shared content.
    
    Scans for lines matching `<!-- include: NAME -->` (where NAME is [a-z0-9_-]+)
    and replaces each entire line with the contents of `shared_dir/NAME.md`.
    
    Args:
        text: Input text that may contain include directives
        shared_dir: Path to directory containing shared .md files
    
    Returns:
        Text with include directives expanded to their content
    
    Raises:
        ValueError: If an include directive references a file that doesn't exist
    
    Notes:
        - If shared_dir doesn't exist, returns text unchanged (backward compatibility)
        - Include directives must be on their own line (may have surrounding whitespace)
        - Included files cannot contain other include directives (non-recursive)
        - Trailing newlines are stripped from included content to avoid double blanks
        - Include directives inside code fences are still processed (v1 simplicity)
    """
    if not shared_dir.exists():
        return text
    
    # Pattern matches <!-- include: NAME --> on its own line with optional whitespace
    # NAME must be [a-z0-9_-]+
    pattern = r'^\s*<!--\s*include:\s*([a-z0-9_-]+)\s*-->\s*$'
    
    def replace_include(match):
        include_name = match.group(1)
        include_file = shared_dir / f"{include_name}.md"
        
        if not include_file.exists():
            raise ValueError(f"Unknown include: {include_name} (file not found: {include_file})")
        
        content = include_file.read_text()
        # Strip trailing newline to avoid double blanks
        return content.rstrip('\n')
    
    return re.sub(pattern, replace_include, text, flags=re.MULTILINE)


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
        
        # Expand shared-content include directives (<!-- include: NAME -->)
        # No-op if shared/ directory is absent.
        prompt_content = expand_includes(prompt_content, AGENTS_DIR / "shared")
        
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
            
            # Resolve model. Resolution chain:
            #   1. State-driven: state.clis[backend].role_models[role] -> model_id
            #   2. Role-class fallback: role.typical_class matched against
            #      any model's class, with a compatible provider for this backend
            #   3. Legacy tier fallback: agent_config['tier'] -> tiers[tier][backend.name]
            model_str = None
            agent_role = agent_config.get('role')
            
            if (scope_state is not None and 
                agent_role is not None and 
                backend.name in scope_state.clis and
                agent_role in scope_state.clis[backend.name].role_models):
                
                # Step 1: state-driven resolution
                model_id = scope_state.clis[backend.name].role_models[agent_role]
                
                # Lazy load model registry
                if model_registry is None:
                    model_registry = load_model_registry()
                
                try:
                    model = model_registry.get(model_id)
                    resolved = model.resolve_for_providers(list(backend.accepted_providers))
                    if resolved is not None:
                        _provider, alias_str = resolved
                        model_str = alias_str
                except KeyError:
                    pass  # fall through to class/tier fallback
            
            # Step 2: role.typical_class fallback — the "works from shipped YAMLs
            # with zero state" path. Loads the role and picks any model whose
            # class matches role.typical_class and which has an alias for one
            # of this backend's accepted providers.
            if model_str is None and agent_role is not None:
                if model_registry is None:
                    model_registry = load_model_registry()
                try:
                    from ..registries.role_registry import load_role_registry
                    role_registry = load_role_registry()
                    role = role_registry.get(agent_role)
                except (KeyError, FileNotFoundError, ValueError):
                    role = None
                
                if role is not None:
                    # Prefer newer model IDs when multiple match the class.
                    # Registries are sorted ascending by id, so iterate reversed
                    # to pick e.g. claude-opus-4-7 over claude-opus-4-6.
                    for model in reversed(model_registry.all()):
                        if model.model_class != role.typical_class:
                            continue
                        resolved = model.resolve_for_providers(list(backend.accepted_providers))
                        if resolved is not None:
                            _provider, alias_str = resolved
                            model_str = alias_str
                            break
            
            # Step 3: legacy tier fallback (for pre-v1.1 agents.yaml files that
            # still declare `tier:` instead of `role:`).
            if model_str is None:
                if 'tier' not in agent_config:
                    raise ValueError(
                        f"Agent '{agent_name}' has role='{agent_role}' but no model could be "
                        f"resolved for backend '{backend.name}'. Tried: state.role_models, "
                        f"role.typical_class->model.class matching, and legacy 'tier' fallback. "
                        f"Check that data/roles/{agent_role}.yaml exists and that at least one "
                        f"model in data/models/*.yaml has class={role.typical_class if 'role' in locals() and role else '?'} "
                        f"with an alias for one of {list(backend.accepted_providers)}."
                    )
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