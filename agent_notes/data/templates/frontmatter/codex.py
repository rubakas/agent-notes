"""Codex CLI agent file generator — emits whole-file TOML, not frontmatter+markdown."""

from .base import strip_sections

# Backward-compatible alias — tests import this private name directly.
_strip_sections = strip_sections


def render(ctx: dict) -> str:
    """Not used for Codex — emit_file supersedes render.
    Kept so the module is consistent with other frontmatter templates."""
    return ""


def emit_file(ctx: dict, body: str) -> tuple[str, str]:
    """Return (filename, full_file_content) for a Codex agent TOML file.

    The returned content is a complete TOML document — not a frontmatter snippet.
    rendering.py writes this verbatim in place of the normal frontmatter+body output.
    """
    agent_name = ctx['agent_name']
    agent_config = ctx['agent_config']
    model_str = ctx.get('model_str') or ''

    doc: dict = {
        "name": agent_name,
        "description": agent_config["description"],
        "developer_instructions": body,
    }

    if model_str:
        doc["model"] = model_str

    # ctx['resolved_effort'] is already validated against the openai provider's
    # effort vocabulary upstream (rendering.py's _resolve_effort) — emitted verbatim,
    # no cross-provider mapping. "medium" is the openai provider's own default_effort,
    # used here only when nothing resolved at all, to preserve prior behavior.
    doc["model_reasoning_effort"] = ctx.get("resolved_effort") or "medium"

    doc["sandbox_mode"] = _sandbox_mode(agent_config)

    import tomli_w  # lazy import — only needed when emitting Codex TOML files

    filename = f"{agent_name}.toml"
    content = tomli_w.dumps(doc)
    return filename, content


def post_process(prompt: str, ctx: dict) -> str:
    """Strip Codex-irrelevant sections from the agent prompt body.

    Strips:
    - ## Memory* sections (Codex has no agent memory)
    - ## Cost reporting section (Claude Code CLI tool, not available in Codex)
    """
    return strip_sections(prompt)


# --- helpers ---

def _sandbox_mode(agent_config: dict) -> str:
    """Derive Codex sandbox_mode from the agent's tool/permission config.

    Writer agents (those that can Write or Edit files) -> "workspace-write"
    All others -> "read-only"
    """
    claude_config = agent_config.get('claude', {}) or {}
    tools = claude_config.get('tools', '') or ''
    if isinstance(tools, str):
        if 'Write' in tools or 'Edit' in tools:
            return "workspace-write"
    elif isinstance(tools, list):
        if 'Write' in tools or 'Edit' in tools:
            return "workspace-write"

    opencode_config = agent_config.get('opencode', {}) or {}
    permission = opencode_config.get('permission', {}) or {}
    if permission.get('edit') == 'allow':
        return "workspace-write"

    return "read-only"


