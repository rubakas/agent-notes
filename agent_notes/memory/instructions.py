"""Memory-instruction text generators for agent prompt substitution.

These functions produce the strings that replace {{MEMORY_PATH}},
{{MEMORY_READING_GUIDE}}, and {{MEMORY_INSTRUCTIONS}} in rendered
agent files and global config templates.
"""

from typing import Optional


def _resolve_memory_path(st) -> Optional[str]:
    """Return the resolved memory directory path as a string, or None if memory is disabled/absent."""
    from ..config import memory_dir_for_backend

    if st is None:
        return None

    backend = st.memory.backend
    custom_path = st.memory.path

    resolved = memory_dir_for_backend(backend, custom_path)
    if resolved is None:
        return None

    return str(resolved)


def _memory_path(st) -> str:
    """Return the vault/memory path string for {{MEMORY_PATH}} substitution in agent prompts."""
    # For the local provider, agent-notes steps aside — there is no agent-notes
    # store to point at; the AI CLI handles memory natively.
    if st is not None and st.memory.backend != "obsidian":
        return "your AI CLI's native memory"
    resolved = _resolve_memory_path(st)
    if resolved is None:
        return "disabled"
    return resolved


def _memory_reading_guide(st) -> str:
    """Return backend-appropriate reading instructions for {{MEMORY_READING_GUIDE}} substitution."""
    from ..constants import Obsidian

    if st is None:
        return "Memory is not configured. Proceed without reading any shared state."

    backend = st.memory.backend

    resolved = _resolve_memory_path(st)
    if resolved is None:
        return "Memory is disabled. Proceed without reading any shared state."

    path = resolved

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

    # local provider — agent-notes steps aside; the AI CLI handles memory natively
    return (
        "Memory for this installation is handled locally by your AI CLI in its default way. "
        "There is no shared agent-notes memory store to read — use your CLI's native memory."
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

    if backend != "obsidian":
        # local provider — agent-notes does not manage local memory; the AI CLI
        # handles it natively. `agent-notes memory add` is for the Obsidian provider.
        return (
            "Memory for this installation is handled locally by your AI CLI in its default way. "
            "agent-notes does not manage local memory — use your CLI's native memory mechanism."
        )

    return (
        "## Memory protocol (HARD RULE)\n\n"
        "The session memory note is the durable cross-session record of work done. It MUST be "
        "updated on every state change, not just at the end. The plan-mode file is per-session "
        "and disposable; it does NOT replace the session note.\n\n"
        "### When to write\n\n"
        "1. **First non-trivial turn of a session** — create or open the session note:\n"
        "   `agent-notes memory add \"<session description>\" \"<scope summary>\" session lead`\n"
        "   Filename is `<session-id>.md` per the obsidian-memory SKILL. Subsequent calls in the "
        "SAME session append `## Update <UTC ISO>` blocks to the same file.\n\n"
        "2. **At every phase / dispatched-agent completion** — before reporting that phase done:\n"
        "   `agent-notes memory add \"<session description>\" \"Phase N — <what shipped, files touched, test delta, deferrals>\" session lead`\n\n"
        "3. **When a decision, pattern, mistake, or context worth preserving across sessions surfaces** — write a SEPARATE note:\n"
        "   `agent-notes memory add \"<title>\" \"<body>\" decision|pattern|mistake|context <agent>`\n"
        "   These land in `Decisions/`, `Patterns/`, etc. — independent of the session note.\n\n"
        "**Auto-linking**: when a non-session note (Decision / Pattern / Mistake / Context) is written "
        "while a session is active, the CLI automatically appends a wikilink to that session note's "
        "`## Linked notes` section. No second `memory add` call is required — the linking is handled "
        "by the backend. Obsidian backend only — no-op on local.\n\n"
        "**Plan-mirror rule**: after every ExitPlanMode, mirror the plan content as a Decision note "
        "in Obsidian. See `obsidian-memory` SKILL \"Plan-mirror rule\" section. Obsidian backend only "
        "— no-op on local.\n\n"
        "### Persist agent discoveries\n\n"
        "After receiving output from any agent, scan for a `## Discoveries` section. For each discovery:\n\n"
        "1. Review for quality — is this non-obvious, durable, and worth cross-session retrieval?\n"
        "2. Skip if ephemeral, derivable from git log, or already in memory\n"
        "3. Persist worthy ones: `agent-notes memory add \"<title>\" \"<body>\" <type> <agent-name>`\n\n"
        f"Save memories using the `agent-notes memory add` CLI — it writes to the configured "
        f"Obsidian vault at `{resolved}` automatically. Do not write memory files directly.\n\n"
        "Use: `agent-notes memory add \"<title>\" \"<body>\" [type] [agent]`\n"
        "Types: `pattern`, `decision`, `mistake`, `context`. Agent: `lead`."
    )
