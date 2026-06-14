"""Codex CLI agent file generator — emits whole-file TOML, not frontmatter+markdown."""

import tomli_w


_EFFORT_MAP = {
    "minimal": "minimal",
    "low":     "low",
    "medium":  "medium",
    "high":    "high",
    "xhigh":   "xhigh",
}

_STRIP_PREFIXES = ("## Memory", "## Cost reporting")


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

    effort_key = agent_config.get("effort", "medium")
    doc["model_reasoning_effort"] = _EFFORT_MAP.get(effort_key, "medium")

    doc["sandbox_mode"] = _sandbox_mode(agent_config)

    filename = f"{agent_name}.toml"
    content = tomli_w.dumps(doc)
    return filename, content


def post_process(prompt: str, ctx: dict) -> str:
    """Strip Codex-irrelevant sections from the agent prompt body.

    Strips:
    - ## Memory* sections (Codex has no agent memory)
    - ## Cost reporting section (Claude Code CLI tool, not available in Codex)
    """
    return _strip_sections(prompt, _STRIP_PREFIXES)


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

    while result_lines and result_lines[-1].strip() == '':
        result_lines.pop()

    return '\n'.join(result_lines)
