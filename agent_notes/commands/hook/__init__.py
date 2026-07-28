"""Hook command — Claude Code hook integrations.

Entry-point functions (_guard_credentials, _memory_bridge, _precompact_memory_bridge)
are defined here so that ``patch("agent_notes.commands.hook.<name>", ...)`` targets
in tests resolve to this module's namespace and intercept calls correctly.

Implementation logic is split across focused submodules:
  _guard.py    — credential detection helpers + evaluate_credential_access
  _session.py  — _session_discover
  _memory.py   — _load_memory_index (shared renderer)
"""

from __future__ import annotations

import json
import sys

# Re-export everything tests import from this package
from ._guard import (
    evaluate_credential_access,
    _is_credential_path,
    _bash_reads_credential,
    _keyword_in_segment,
    _deny_payload,
    _is_template_file,
    _is_path_shaped,
    _first_effective_command,
    _strip_token_punctuation,
    _command_contains_credential_path,
    _TEMPLATE_MARKERS,
    _HARD_SECRET_EXTS,
    _SOURCE_EXTS,
    _CREDENTIAL_BASENAME_PATTERNS,
    _SEG_SEPS,
    _TOKEN_SPLIT,
    _CREDENTIAL_SEGMENT_KEYWORDS,
    _SAFE_EXISTENCE_COMMANDS,
    _COMMAND_PREFIXES,
)
from ._session import _session_discover
from ._memory import _load_memory_index


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

def hook(subaction: str) -> None:
    """Handle hook subactions."""
    if subaction == "memory-bridge":
        _memory_bridge()
    elif subaction == "precompact-memory-bridge":
        _precompact_memory_bridge()
    elif subaction == "session-discover":
        _session_discover()
    elif subaction == "guard-credentials":
        _guard_credentials()


# ---------------------------------------------------------------------------
# Entry-point functions that call module-level names (kept here so that
# patch("agent_notes.commands.hook.<dep>", ...) intercepts their calls).
# ---------------------------------------------------------------------------

def _guard_credentials() -> None:
    """PreToolUse hook that denies attempts to read credential files.

    Reads the PreToolUse JSON payload from stdin, calls evaluate_credential_access,
    and prints a deny or allow response. Always exits 0 so Claude Code parses stdout.

    Fail-closed for recognized tool types: if stdin parsed and tool_name is a
    guarded tool (Read/Bash/Grep), any downstream error emits a static deny.
    Only a total stdin/JSON parse failure fails open (writes to stderr).
    """
    raw = ""
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw)
    except Exception as exc:
        # Total infrastructure failure — cannot parse stdin at all; fail open
        # with a stderr note so operators can diagnose.
        print(f"credential-guard: stdin parse error ({exc})", file=sys.stderr)
        return

    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {})

    _GUARDED_TOOLS = {"Read", "Bash", "Grep"}

    if tool_name in _GUARDED_TOOLS:
        try:
            decision = evaluate_credential_access(tool_name, tool_input)
            if decision is not None:
                print(json.dumps(decision))
        except Exception:
            # Evaluation error on a guarded tool — fail closed
            print(json.dumps(_deny_payload(
                "Credential guard: evaluation error — denying as a precaution; "
                "remove the guard hook from settings.json to override."
            )))
    else:
        # Non-guarded tool: pass through (hook matcher already scopes to Read|Bash|Grep,
        # but defensive check here in case Claude Code invokes us for other tools)
        try:
            decision = evaluate_credential_access(tool_name, tool_input)
            if decision is not None:
                print(json.dumps(decision))
        except Exception:
            pass  # Non-guarded tool errors fail open


def _memory_bridge() -> None:
    """SessionStart hook that prints the agent-notes memory index.

    Unconditionally loads and prints the memory index so it is visible in
    context at the start of every Claude Code session.
    """
    content = _load_memory_index()
    if content is None:
        return
    print("<!-- agent-notes memory index (auto-loaded) -->")
    print(content)


def _precompact_memory_bridge() -> None:
    """PreCompact hook that re-emits the memory index before context compaction.

    When Claude Code compacts a long conversation the SessionStart context
    injected by memory-bridge can be summarised away, losing the pointer to
    durable memory.  This hook fires immediately before compaction and returns
    the index via the `additionalContext` field in the hook JSON output schema
    (see docs/CLI_CAPABILITIES.md §Hooks → "JSON output schema").  Claude Code
    merges `additionalContext` into the compacted context, keeping the memory
    pointer alive.

    Contract: exit 0, emit a single JSON object to stdout:
        {"additionalContext": "<header>\\n<index content>"}
    If the memory index is unavailable (no backend configured, no index file)
    the hook exits silently with no output so compaction proceeds normally.
    """
    content = _load_memory_index()
    if content is None:
        return
    payload = {
        "additionalContext": "<!-- agent-notes memory index (auto-loaded) -->\n" + content,
    }
    print(json.dumps(payload))
