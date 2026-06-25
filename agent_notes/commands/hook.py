"""Hook command - Claude Code hook integrations."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Optional


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


def _session_discover() -> None:
    """Discover all agent-notes profiles for the current project and emit combined context."""
    try:
        from ..services.state_store import load_state, get_profiles_for_project
        from ..registries.cli_registry import load_registry

        state = load_state()
        if state is None:
            return

        registry = load_registry()
        default_local_dirs = {b.name: b.local_dir for b in registry.all()}

        for key, scope_state in get_profiles_for_project(state, Path.cwd()):
            for cli_name, backend_state in scope_state.clis.items():
                local_dir = backend_state.local_dir_override or default_local_dirs.get(cli_name, ".claude")
                context_file = Path(local_dir) / "agent-notes-context.md"
                if context_file.exists():
                    label = scope_state.profile_label or "default"
                    print(f"<!-- agent-notes profile: {label} -->")
                    print(context_file.read_text(encoding="utf-8"))
    except Exception:
        return


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


# ---------------------------------------------------------------------------
# Credential patterns (from safety.md "Credentials — ABSOLUTE PROHIBITION")
# ---------------------------------------------------------------------------

# Non-secret template suffixes — .env.example / .env.sample / .env.template /
# .env.dist are not real secret files. Allow them explicitly.
_ENV_TEMPLATE_SUFFIXES = frozenset({
    ".example", ".sample", ".template", ".dist",
})

# Filename-level patterns: matched against the basename of the path.
# Order: most specific first; the .env allowlist check runs BEFORE these.
_CREDENTIAL_BASENAME_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^service-account.*\.json$", re.IGNORECASE),
    re.compile(r"^credentials\.", re.IGNORECASE),
    re.compile(r"^secrets\.", re.IGNORECASE),
    re.compile(r"^.*-secrets\.", re.IGNORECASE),
    re.compile(r"^.*\.env$", re.IGNORECASE),            # bare *.env
    re.compile(r"^\.env(\.|$)", re.IGNORECASE),         # .env, .env.production, etc.
    re.compile(r"^.*\.key$", re.IGNORECASE),
    re.compile(r"^.*\.pem$", re.IGNORECASE),
    re.compile(r"^.*\.p12$", re.IGNORECASE),
    re.compile(r"^.*\.pfx$", re.IGNORECASE),
    re.compile(r"^.*\.jks$", re.IGNORECASE),
    re.compile(r"^.*\.keystore$", re.IGNORECASE),
    re.compile(r"^.*\.truststore$", re.IGNORECASE),
]

# Word-boundary separators for keyword matching within a path segment.
# A keyword only matches when surrounded by start/end of segment or one of these.
_SEG_SEPS = re.compile(r"[-_.\s]")

# Path-segment keywords: match only as DELIMITED words within a segment.
# E.g. "token" matches "auth-token.json" and "my_token" but NOT "tokenizer.py"
# or "PasswordResetToken.tsx". Boundaries are start/end of segment or [-_.\s].
_CREDENTIAL_SEGMENT_KEYWORDS = (
    "secret",
    "credential",
    "token",
    "apikey",
    "auth-key",
    "private-key",
)

# Existence/metadata commands that are ALWAYS allowed even if they reference a
# credential path — these never surface file contents.
_SAFE_EXISTENCE_COMMANDS = frozenset({"test", "[", "ls", "stat", "find", "file"})

# Prefix tokens that do not change the effective command — stripped before
# identifying the first real command.
_COMMAND_PREFIXES = frozenset({
    "sudo", "time", "nohup", "env", "xargs", "exec", "command",
    "nice", "doas",
})


def _is_env_template(basename: str) -> bool:
    """Return True if the basename is a non-secret .env template file.

    .env.example / .env.sample / .env.template / .env.dist are scaffolding
    files checked into repos — they contain placeholder values, not real secrets.
    """
    lower = basename.lower()
    if not lower.startswith(".env"):
        return False
    suffix = lower[4:]  # everything after ".env"
    return suffix in _ENV_TEMPLATE_SUFFIXES


def _keyword_in_segment(keyword: str, segment: str) -> bool:
    """Return True if keyword appears as a delimited word within segment.

    Boundaries are start/end of segment or a separator character (-, _, ., space).
    Case-insensitive. Multi-word keywords like "auth-key" are matched as a unit.
    """
    seg_lower = segment.lower()
    kw_lower = keyword.lower()
    kw_len = len(kw_lower)
    seg_len = len(seg_lower)

    start = 0
    while True:
        idx = seg_lower.find(kw_lower, start)
        if idx == -1:
            break
        # Check left boundary
        left_ok = (idx == 0) or bool(_SEG_SEPS.match(seg_lower[idx - 1]))
        # Check right boundary
        right_idx = idx + kw_len
        right_ok = (right_idx == seg_len) or bool(_SEG_SEPS.match(seg_lower[right_idx]))
        if left_ok and right_ok:
            return True
        start = idx + 1
    return False


def _is_credential_path(path_str: str) -> bool:
    """Return True if path_str refers to a credential file.

    Checks (in order):
    1. Explicit allow: non-secret .env template files (.env.example etc.)
    2. Basename against known credential file patterns.
    3. Every path segment for credential-related DELIMITED keywords.

    This function ONLY inspects the path string — it never reads file contents.
    """
    if not path_str:
        return False

    # Normalise separators for segment splitting
    normalised = path_str.replace("\\", "/")
    segments = [s for s in normalised.split("/") if s]
    if not segments:
        return False

    basename = segments[-1]

    # 1. Allow non-secret .env templates before any deny pattern fires
    if _is_env_template(basename):
        return False

    # 2. Basename pattern match
    for pattern in _CREDENTIAL_BASENAME_PATTERNS:
        if pattern.match(basename):
            return True

    # 3. Delimited keyword match in any segment
    for seg in segments:
        for keyword in _CREDENTIAL_SEGMENT_KEYWORDS:
            if _keyword_in_segment(keyword, seg):
                return True

    return False


def _first_effective_command(tokens: list[str]) -> str:
    """Return the basename of the first non-prefix, non-env-var token."""
    i = 0
    while i < len(tokens):
        t = tokens[i]
        # Skip VAR=value env-var assignments
        if "=" in t and not t.startswith("-"):
            i += 1
            continue
        # Strip absolute path prefix (/usr/bin/cat → cat)
        cmd = t.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
        if cmd in _COMMAND_PREFIXES:
            i += 1
            continue
        # Handle `su -c` (next token is the command string, not a prefix)
        if cmd == "su":
            break
        return cmd
    return ""


def _strip_token_punctuation(token: str) -> str:
    """Strip surrounding shell metacharacters that shlex may leave on a token.

    Handles: leading < > ' " ( and trailing ) ' " so that tokens like
    `'.env)'`, `<.env`, `"< .env`, `$(cat .env)` pass through to path check.
    """
    return token.strip("<>()'\"`")


def _command_contains_credential_path(command: str) -> bool:
    """Return True if any path-like token or substring in the command is a credential.

    Two-pass scan:
    1. shlex tokens (handles quoted paths, explicit < redirections)
    2. Raw regex scan of the whole command string (catches subshells, backticks,
       no-space redirections like `<.env`, compound commands)
    """
    # Pass 1: shlex tokens
    try:
        import shlex
        tokens = shlex.split(command)
    except ValueError:
        tokens = command.split()

    for token in tokens:
        cleaned = _strip_token_punctuation(token)
        if cleaned and _is_credential_path(cleaned):
            return True

    # Pass 2: raw scan — extract all path-candidate substrings via regex.
    # Matches sequences that look like a path (optional leading ./ or / or ~/,
    # then word chars, dots, hyphens, underscores, slashes) and also bare
    # no-space redirections like `<.env`, `if=.env`, and quoted paths like `'.env'`.
    #
    # Known non-goals (static string analysis cannot catch):
    #   - Variable-built paths: f=.env; cat $f  (path not present as literal)
    #   - Glob obfuscation: cat .e*              (glob expands at runtime)
    # These are accepted limitations, not bugs.
    for match in re.finditer(
        r"(?:^|(?<=\s)|(?<=[<>|;&()`=']))([~./]?[\w./\-]+)",
        command,
    ):
        candidate = _strip_token_punctuation(match.group(1))
        if candidate and _is_credential_path(candidate):
            return True

    return False


def _bash_reads_credential(command: str) -> bool:
    """Return True if the Bash command may expose credential file contents.

    New deny boundary (defense-in-depth, correctness over leniency):

    ALLOW only when the first effective command (after stripping prefixes) is a
    pure existence/metadata op: test / [ / ls / stat / find / file.
    These never surface file contents even when given a credential path.

    DENY when a credential path appears ANYWHERE in the command AND the first
    effective command is NOT a safe existence check.

    Over-blocking writes/deletes (rm .env, git add .env, echo x >> .env) is
    intentional — deny those too.  Defense-in-depth beats precision here.

    This function ONLY inspects the command string — it never reads file contents.
    """
    if not command:
        return False

    try:
        import shlex
        tokens = shlex.split(command)
    except ValueError:
        tokens = command.split()

    if not tokens:
        return False

    first_cmd = _first_effective_command(tokens)

    # Pure existence/metadata commands: always allow regardless of path
    if first_cmd in _SAFE_EXISTENCE_COMMANDS:
        return False

    # For everything else: deny if a credential path appears anywhere
    return _command_contains_credential_path(command)


def _deny_payload(reason: str) -> dict:
    """Return the Claude Code PreToolUse deny payload."""
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }


def evaluate_credential_access(
    tool_name: str, tool_input: dict
) -> Optional[dict]:
    """Evaluate whether the tool call attempts to read a credential file.

    Returns a deny payload dict if the call should be blocked, or None to allow.

    This is a pure function with no side effects — it only inspects the
    tool_name and tool_input strings and never reads file contents or logs values.

    Deny cases:
      - Read tool: file_path matches a credential pattern
      - Bash tool: credential path appears anywhere in command AND first effective
        command is not a safe existence check (test/ls/stat/find/file/[)
      - Grep tool: path or glob targets a credential path

    Allow cases:
      - Read of non-credential paths (and .env.example/.env.sample templates)
      - Bash with first effective command = test/ls/stat/find/file/[
      - Bash with no credential path in the command
      - Grep on non-credential paths
      - Edit/Write/WebFetch — out of scope; not in matcher
      - Any other unrecognized tool

    Note: Edit and Write are intentionally excluded from the guard scope —
    writing to a credential path is not the same threat as reading it into
    model context. WebFetch is not path-based. Both are left to the prompt rule.
    """
    if tool_name == "Read":
        path_str = tool_input.get("file_path", "")
        if _is_credential_path(path_str):
            return _deny_payload(
                f"Credential guard: reading '{path_str}' is prohibited. "
                "Use 'test -f' or 'ls' to verify file existence instead."
            )
        return None

    if tool_name == "Bash":
        command = tool_input.get("command", "")
        if _bash_reads_credential(command):
            return _deny_payload(
                "Credential guard: the command may expose credential file contents. "
                "Use 'test -f <path>' to check existence without exposing contents."
            )
        return None

    if tool_name == "Grep":
        # Grep can surface file contents; deny when path/glob targets a credential.
        # tool_input fields used by Claude Code's Grep: "path" and/or "glob".
        for field in ("path", "glob"):
            val = tool_input.get(field, "")
            if val and _is_credential_path(val):
                return _deny_payload(
                    f"Credential guard: grep on '{val}' is prohibited. "
                    "Credential file contents must not be surfaced."
                )
        return None

    # All other tools: allow (hook matcher scopes to Read|Bash|Grep)
    return None


def _load_memory_index() -> Optional[str]:
    """Load the agent-notes memory index content, or return None if unavailable.

    Shared renderer used by both the SessionStart memory-bridge hook and the
    PreCompact memory-bridge hook so both emit from one source of truth.
    """
    try:
        from .memory._common import _load_memory_config
        from ..constants import Obsidian, Wiki

        backend, path = _load_memory_config()

        if backend == "none" or backend is None:
            return None

        if backend == "obsidian":
            index_file = Path(path) / Obsidian.INDEX
        elif backend == "wiki":
            index_file = Path(path) / Wiki.DIR / Wiki.INDEX
        else:
            # local and any unknown backends: use Index.md at root
            index_file = Path(path) / "Index.md"

        if not index_file.exists():
            return None

        return index_file.read_text(encoding="utf-8")
    except Exception:
        return None


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
