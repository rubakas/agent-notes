"""Shared helpers for frontmatter generator templates."""

# Central registry of ## section headings stripped from prompt bodies by CLI
# backends that lack those features (## Memory for backends without agent memory,
# ## Cost reporting for backends other than Claude Code).
#
# This stays here rather than being contributed by each subsystem because the
# only consumers are the frontmatter templates in this package — moving the
# constants into agent_notes/memory/ or agent_notes/cost/ would create a
# cross-layer import from data/templates into services, which is worse coupling
# than the current inward reference.
STRIP_PREFIXES = ("## Memory", "## Cost reporting")

# Named-color → hex mapping used by backends that require hex color values.
COLOR_TO_HEX = {
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


def strip_sections(content: str, strip_prefixes: tuple = STRIP_PREFIXES) -> str:
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
