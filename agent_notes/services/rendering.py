"""Frontmatter and agent file rendering."""

import yaml
import importlib
import re
from pathlib import Path
from typing import Dict, Any, Optional


def expand_includes(text: str, shared_dir: Path, skip: Optional[set] = None) -> str:
    """Expand include directives in text by substituting shared content.

    Scans for lines matching `<!-- include: NAME -->` (where NAME is [a-z0-9_-]+)
    and replaces each entire line with the contents of `shared_dir/NAME.md`.

    Args:
        text: Input text that may contain include directives
        shared_dir: Path to directory containing shared .md files
        skip: Optional set of include NAMEs to suppress (replaced with empty string)

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

    _skip = skip or set()

    # Pattern matches <!-- include: NAME --> on its own line with optional whitespace
    # NAME must be [a-z0-9_-]+
    pattern = r'^\s*<!--\s*include:\s*([a-z0-9_-]+)\s*-->\s*$'

    def replace_include(match):
        include_name = match.group(1)
        if include_name in _skip:
            return ""
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


def _resolve_model_str(
    agent_name: str,
    agent_config: Dict[str, Any],
    backend,
    scope_state,
    model_registry,
    user_config: Dict[str, Any],
):
    """Resolve the model string for a given agent+backend combination.

    Returns (model_str, model_registry) where model_registry may have been
    lazily loaded inside and is returned so the caller can cache it.

    Delegates all resolution logic to ModelResolver; this function is kept
    as a thin shim so existing callers (tests, generate_agent_files) continue
    to work unchanged.
    """
    from ..services.model_resolver import ModelResolver

    resolver = ModelResolver(
        scope_state=scope_state,
        user_config=user_config,
        model_registry=model_registry,
    )
    model_str = resolver.resolve(agent_name, agent_config, backend)
    return model_str, resolver._model_registry


def _effective_role(agent_name: str, agent_config: Dict[str, Any], user_config: Dict[str, Any]) -> Optional[str]:
    """Return the effective role for agent_name (user override > declared).

    Mirrors ModelResolver._effective_role so role_efforts pins line up with
    the same role key that role_models pins use.
    """
    default_role = agent_config.get("role")
    return user_config.get("agent_roles", {}).get(agent_name, default_role)


def _resolve_provider_for_model_str(model_str: Optional[str], backend, model_registry) -> Optional[str]:
    """Reverse-lookup: given the already-resolved model_str for this backend, find
    which provider (from backend.accepted_providers) produced it, by scanning the
    model registry. Returns None if model_str isn't traceable to a registry model
    (e.g. legacy tier fallback, which isn't provider-registry-aware).

    Models are scanned in registry order and the scan returns on the first
    model that either matches model_str exactly by alias (state-pinned models
    render exact alias strings on every backend) or — on use_model_class
    backends, where the UNPINNED fallback still renders model_class — matches
    by class with family equal to backend.preferred_family. A class alone can
    be ambiguous across families (e.g. claude-sonnet-* vs gpt-* both class
    'sonnet'), so a class match on a non-preferred family is only remembered
    as the fallback, returned when the scan finishes with no exact-alias or
    preferred-family class match."""
    if not model_str or model_registry is None:
        return None

    class_match_provider = None
    for model in model_registry.all():
        resolved = model.resolve_for_providers(list(backend.accepted_providers))
        if resolved is None:
            continue
        provider, alias = resolved
        if alias == model_str:
            return provider
        if backend.use_model_class and model.model_class == model_str:
            if model.family == backend.preferred_family:
                return provider
            if class_match_provider is None:
                class_match_provider = provider
    return class_match_provider


def _resolve_effort(
    agent_name: str,
    agent_config: Dict[str, Any],
    backend,
    scope_state,
    user_config: Dict[str, Any],
    model_str: Optional[str],
    model_registry,
) -> Optional[str]:
    """Resolve the effective effort for an agent+backend, validated against the
    resolved model's provider effort vocabulary.

    Precedence (USER DECISION: pin wins):
      1. State-driven pin — scope_state.clis[backend].role_efforts[role]
      2. Agent's own 'effort' (agents.yaml)
      3. Role's 'typical_effort'
      4. None

    The raw value from that chain is then validated against the provider's
    effort list (resolved via the agent's model on this backend): if the
    provider has a registry entry and the raw value isn't in its vocabulary,
    the provider's own default_effort is used instead (NO cross-provider
    mapping/translation). If the provider has no registry entry at all,
    falls back to the model's other alias-providers (preferring the canonical
    one whose alias value equals the model's own id); resolves to None only
    if no alias-provider is in the registry either (nothing is emitted).
    """
    from ..registries.role_registry import default_role_registry

    agent_role = _effective_role(agent_name, agent_config, user_config)

    raw_effort = None
    if scope_state is not None and agent_role is not None and backend.name in scope_state.clis:
        pin = scope_state.clis[backend.name].role_efforts.get(agent_role)
        if pin:
            raw_effort = pin

    if raw_effort is None:
        raw_effort = agent_config.get("effort")

    if raw_effort is None and agent_role is not None:
        try:
            role = default_role_registry().get(agent_role)
            raw_effort = role.typical_effort or None
        except (KeyError, FileNotFoundError, ValueError):
            raw_effort = None

    if not raw_effort:
        return None

    provider_name = _resolve_provider_for_model_str(model_str, backend, model_registry)
    if provider_name is None:
        return None

    from ..registries.provider_registry import default_provider_registry

    try:
        pr = default_provider_registry()
    except (FileNotFoundError, ValueError):
        return None

    try:
        provider = pr.get(provider_name)
    except KeyError:
        # Routing provider has no effort registry entry; walk the model's
        # aliases to find a provider that does (e.g. github-copilot -> anthropic).
        provider = None
        if model_registry is not None:
            for model in model_registry.all():
                if model_str in model.aliases.values():
                    # Prefer the alias whose value equals model.id (canonical/
                    # family provider); fall back to insertion order.
                    candidates = sorted(
                        model.aliases.items(), key=lambda kv: kv[1] != model.id
                    )
                    for alias_provider, _ in candidates:
                        try:
                            provider = pr.get(alias_provider)
                            break
                        except KeyError:
                            continue
                    break
        if provider is None:
            return None

    if raw_effort in provider.efforts:
        return raw_effort
    return provider.default_effort


def _overlay_selection_pins(scope_state, role_models, role_efforts):
    """Return a copy of scope_state with explicit role_models/role_efforts pins
    layered on top (both shaped {cli_name: {role_name: value}}).

    Used by the wizard: its selections exist only in memory until state.json is
    written AFTER install, so the pre-install render must receive them
    explicitly. Explicit pins win over anything persisted; persisted pins for
    roles/CLIs not mentioned are preserved. scope_state may be None."""
    from copy import deepcopy
    from ..domain.state import ScopeState, BackendState

    merged = deepcopy(scope_state) if scope_state is not None else ScopeState()
    for pins, attr in ((role_models, "role_models"), (role_efforts, "role_efforts")):
        for cli_name, role_pins in (pins or {}).items():
            backend_state = merged.clis.setdefault(cli_name, BackendState())
            getattr(backend_state, attr).update(role_pins)
    return merged


def generate_agent_files(agents_config: Dict[str, Any],
                         state=None, scope='global', project_path=None,
                         role_models: Optional[Dict[str, Dict[str, str]]] = None,
                         role_efforts: Optional[Dict[str, Dict[str, str]]] = None,
                         profile_label: str = "") -> list[Path]:
    """Generate agent files for all CLI backends.

    Args:
        agents_config: Dict of agent configurations from agents.yaml
        state: Optional State object for role-based model resolution
        scope: 'global' or 'local' (only used if state is provided)
        project_path: Path for local scope (only used if state is provided and scope='local')
        role_models: Optional explicit {cli: {role: model_id}} pins that override
            the persisted state (wizard selections not yet written to state.json)
        role_efforts: Optional explicit {cli: {role: effort}} pins, same semantics
        profile_label: Named profile whose pins drive the render ("" = default profile)
    """
    from ..registries.cli_registry import load_registry
    from ..services.state_store import load_state as _load_state_fn, get_scope as _get_scope
    from ..config import AGENTS_DIR, DIST_DIR

    generated_files = []

    from ..services.user_config import load_user_config, get_patch, merge_configs

    user_config = load_user_config()
    # Merge project-level config if provided
    if project_path is not None:
        project_config_file = Path(project_path) / ".claude" / "agent-notes.yaml"
        if project_config_file.exists():
            project_config = load_user_config(project_config_file)
            user_config = merge_configs(user_config, project_config)

    registry = load_registry()
    model_registry = None  # Lazy load only if needed
    scope_state = None

    # Get scope state if state is provided
    if state is not None:
        scope_state = _get_scope(state, scope, project_path, profile_label=profile_label)

    # Explicit selection pins (wizard) override whatever state.json holds
    if role_models or role_efforts:
        scope_state = _overlay_selection_pins(scope_state, role_models, role_efforts)

    _st = _load_state_fn()

    for agent_name, agent_config in agents_config.items():
        # Read the source prompt
        prompt_file = AGENTS_DIR / f'{agent_name}.md'
        if not prompt_file.exists():
            print(f"Warning: Missing source file {prompt_file}")
            continue

        prompt_content = prompt_file.read_text()

        # Expand shared-content include directives (<!-- include: NAME -->)
        # No-op if shared/ directory is absent.
        _agent_include_skip = set() if user_config.get("cost_report_enabled", False) else {"cost_reporting"}
        prompt_content = expand_includes(prompt_content, AGENTS_DIR / "shared", skip=_agent_include_skip)

        # Substitute {{MEMORY_PATH}} with the configured vault/memory path.
        prompt_content = prompt_content.replace("{{MEMORY_PATH}}", _memory_path(_st))
        prompt_content = prompt_content.replace("{{MEMORY_READING_GUIDE}}", _memory_reading_guide(_st))

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
            #   3. Unresolvable: raises ValueError
            model_str, model_registry = _resolve_model_str(
                agent_name, agent_config, backend, scope_state, model_registry, user_config
            )
            
            # Build context for template
            ctx = {
                'agent_name': agent_name,
                'agent_config': agent_config,
                'model_str': model_str,
                'resolved_effort': _resolve_effort(
                    agent_name, agent_config, backend, scope_state, user_config, model_str, model_registry
                ),
                'backend_name': backend.name,
                'backend': backend,
            }
            
            # Apply post-processing transformation (e.g., strip memory section)
            body = template.post_process(prompt_content, ctx)

            # Apply user patch if present
            patch = get_patch(agent_name, user_config)
            if patch:
                body = body.rstrip() + "\n\n" + patch.strip()

            # Write to backend's agents directory
            from ..services import installer
            agents_dir = installer.dist_source_for(backend, "agents")
            if agents_dir is None:
                agents_dir = DIST_DIR / backend.name / "agents"
            agents_dir.mkdir(parents=True, exist_ok=True)

            if hasattr(template, 'emit_file'):
                # Whole-file emitters (e.g. Codex TOML): filename and content
                # are determined entirely by the template.
                filename, full_content = template.emit_file(ctx, body)
                agent_file = agents_dir / filename
            else:
                # Standard frontmatter+markdown path (claude, opencode, …)
                frontmatter = template.render(ctx)
                full_content = f"{frontmatter}\n\n{body}"
                agent_file = agents_dir / f'{agent_name}.md'

            # dist/ is a derived, regenerable artifact — overwrite in place.
            # Backups belong to user-facing install targets (fs.handle_existing
            # via installer.place_file), never to the build output itself.
            agent_file.write_text(full_content)
            generated_files.append(agent_file)
    
    return generated_files


def _resolve_memory_path(st) -> Optional[str]:
    """Return the resolved memory directory path as a string, or None if memory is disabled/absent."""
    from ..config import memory_dir_for_backend

    if st is None:
        return None

    backend = st.memory.backend
    custom_path = st.memory.path

    if backend == "none":
        return None

    resolved = memory_dir_for_backend(backend, custom_path)
    if resolved is None:
        return None

    return str(resolved)


def _memory_path(st) -> str:
    """Return the vault/memory path string for {{MEMORY_PATH}} substitution in agent prompts."""
    resolved = _resolve_memory_path(st)
    if resolved is None:
        return "disabled"
    return resolved


def _memory_reading_guide(st) -> str:
    """Return backend-appropriate reading instructions for {{MEMORY_READING_GUIDE}} substitution."""
    from ..constants import Wiki, Obsidian

    if st is None:
        return "Memory is not configured. Proceed without reading any shared state."

    backend = st.memory.backend

    resolved = _resolve_memory_path(st)
    if resolved is None:
        return "Memory is disabled. Proceed without reading any shared state."

    path = resolved

    if backend == "wiki":
        _sessions, _concepts, _entities = Wiki.PAGE_TYPES[4], Wiki.PAGE_TYPES[1], Wiki.PAGE_TYPES[2]
        return (
            f"You are part of a team that shares state via a knowledge wiki at `{path}`.\n\n"
            "### Read before working\n\n"
            "If the task references an in-flight initiative, prior decision, or session progress, read the relevant wiki files BEFORE you start:\n\n"
            f"1. `{path}/{Wiki.DIR}/{Wiki.INDEX}` — directory of all wiki pages\n"
            f"2. `{path}/{Wiki.DIR}/{_sessions}/` — session logs for ongoing work\n"
            f"3. `{path}/{Wiki.DIR}/{_concepts}/` — decisions, patterns, domain knowledge\n"
            f"4. `{path}/{Wiki.DIR}/{_entities}/` — key entities and components\n\n"
            f"If `{path}` is \"disabled\", skip this — proceed without wiki context."
        )

    if backend == "obsidian":
        _sessions_cat, _decisions_cat, _patterns_cat, _mistakes_cat = (
            Obsidian.CATEGORIES[4], Obsidian.CATEGORIES[1], Obsidian.CATEGORIES[0], Obsidian.CATEGORIES[2]
        )
        return (
            f"You are part of a team that shares state via an Obsidian vault at `{path}`.\n\n"
            "### Read before working\n\n"
            "If the task you've been given references an in-flight initiative, prior decision, recent pattern, or session progress, read the relevant vault files BEFORE you start:\n\n"
            f"1. `{path}/{Obsidian.INDEX}` — what's been written and where\n"
            f"2. `{path}/{_sessions_cat}/<recent>.md` — current session log if the task is part of an ongoing thread\n"
            f"3. `{path}/{_decisions_cat}/` or `{_patterns_cat}/` or `{_mistakes_cat}/` — relevant cross-session knowledge\n\n"
            f"If `{path}` is \"disabled\" (memory backend not configured), skip this — proceed without vault context."
        )

    # local backend
    return (
        f"You are part of a team that shares state via a local memory store at `{path}`.\n\n"
        "### Read before working\n\n"
        "If the task references an in-flight initiative, prior decision, or session progress, read the relevant memory files BEFORE you start:\n\n"
        f"1. `{path}/MEMORY.md` — index of saved memories\n"
        f"2. `{path}/` — individual memory files by topic\n\n"
        f"If `{path}` is \"disabled\", skip this — proceed without memory context."
    )


def _memory_instructions(st) -> str:
    """Return memory instructions text based on the configured backend."""
    if st is None:
        return (
            "Save memories using the `agent-notes memory add` CLI.\n\n"
            "Use: `agent-notes memory add \"<title>\" \"<body>\" [type] [agent]`\n"
            "Types: `pattern`, `decision`, `mistake`, `context`. Agent: `lead`."
        )

    backend = st.memory.backend

    resolved = _resolve_memory_path(st)
    if resolved is None:
        return "Memory is disabled for this installation."

    if backend == "wiki":
        return (
            f"Save memories using the `agent-notes memory add` CLI — it writes to the wiki at `{resolved}` automatically. "
            "Do not write memory files directly.\n\n"
            "Use: `agent-notes memory add \"<title>\" \"<body>\" [type] [agent]`\n"
            "Types: `sources`, `concepts`, `entities`, `synthesis`, `sessions`. Agent: `lead`."
        )
    label = "the configured Obsidian vault at" if backend == "obsidian" else "writes to"
    return (
        f"Save memories using the `agent-notes memory add` CLI — it {label} `{resolved}` automatically. "
        "Do not write memory files directly.\n\n"
        "Use: `agent-notes memory add \"<title>\" \"<body>\" [type] [agent]`\n"
        "Types: `pattern`, `decision`, `mistake`, `context`. Agent: `lead`."
    )


def render_globals() -> list[Path]:
    """Copy global files to destinations."""
    from ..config import (
        GLOBAL_CLAUDE_MD, GLOBAL_OPENCODE_MD, GLOBAL_COPILOT_MD,
        DIST_CLAUDE_DIR, DIST_OPENCODE_DIR, DIST_GITHUB_DIR
    )
    from ..services.state_store import load_state as _load_state_fn2

    copied_files = []

    # Build claude.md with includes expanded and memory instructions substituted
    st = _load_state_fn2()
    from ..config import AGENTS_DIR
    from ..services.user_config import load_user_config as _load_user_config
    _ucfg = _load_user_config()
    _include_skip = set() if _ucfg.get("cost_report_enabled", False) else {"cost_reporting"}
    claude_global_content = GLOBAL_CLAUDE_MD.read_text()
    claude_global_content = expand_includes(claude_global_content, AGENTS_DIR / "shared", skip=_include_skip)
    claude_global_content = claude_global_content.replace(
        "{{MEMORY_INSTRUCTIONS}}", _memory_instructions(st)
    )
    claude_global = DIST_CLAUDE_DIR / 'CLAUDE.md'
    claude_global.parent.mkdir(parents=True, exist_ok=True)
    claude_global.write_text(claude_global_content)
    copied_files.append(claude_global)

    # Copy global-opencode.md to AGENTS.md
    opencode_global_content = expand_includes(GLOBAL_OPENCODE_MD.read_text(), AGENTS_DIR / "shared", skip=_include_skip)
    agents_global = DIST_OPENCODE_DIR / 'AGENTS.md'
    agents_global.parent.mkdir(parents=True, exist_ok=True)
    agents_global.write_text(opencode_global_content)
    copied_files.append(agents_global)

    # Copy global-copilot.md to copilot-instructions.md
    copilot_content = expand_includes(GLOBAL_COPILOT_MD.read_text(), AGENTS_DIR / "shared", skip=_include_skip)
    copilot_global = DIST_GITHUB_DIR / 'copilot-instructions.md'
    copilot_global.parent.mkdir(parents=True, exist_ok=True)
    copilot_global.write_text(copilot_content)
    copied_files.append(copilot_global)

    # Render global templates for any additional registry-driven backends that
    # have a global_template and a config layout entry (e.g. codex -> AGENTS.md).
    # Claude, opencode, and copilot are handled explicitly above; skip them here.
    _handled = {"claude", "opencode", "copilot"}
    from ..registries.cli_registry import load_registry as _load_cli_registry
    from ..config import global_template_path, global_output_path, DATA_DIR as _DATA_DIR
    for _backend in _load_cli_registry().all():
        if _backend.name in _handled:
            continue
        _tmpl_path = global_template_path(_backend)
        _out_path = global_output_path(_backend)
        if _tmpl_path is None or _out_path is None:
            continue
        if not _tmpl_path.exists():
            continue
        _content = expand_includes(_tmpl_path.read_text(), AGENTS_DIR / "shared", skip=_include_skip)
        # Substitute {{MEMORY_INSTRUCTIONS}} to empty string for memory-less backends
        # (e.g. codex has features.memory=false) so no literal placeholder leaks.
        _content = _content.replace("{{MEMORY_INSTRUCTIONS}}", "")
        _out_path.parent.mkdir(parents=True, exist_ok=True)
        _out_path.write_text(_content)
        copied_files.append(_out_path)

    return copied_files


def load_agents_config() -> Dict[str, Any]:
    """Load agents configuration from agents.yaml."""
    from ..config import AGENTS_YAML

    if not AGENTS_YAML.exists():
        raise FileNotFoundError(f"Configuration file not found: {AGENTS_YAML}")

    config = yaml.safe_load(AGENTS_YAML.read_text())
    return config.get('agents', {})