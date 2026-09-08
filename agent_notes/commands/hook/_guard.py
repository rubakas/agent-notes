"""Credential guard — pure functions that detect attempts to read credential files.

All logic here is stateless: it only inspects tool_name and tool_input strings
and never reads file contents, makes network calls, or produces side effects.

Moved verbatim from commands/hook.py (was: _guard_credentials and its helpers).
The entry-point function _guard_credentials lives in __init__.py so that
``patch("agent_notes.commands.hook.evaluate_credential_access", ...)``
intercepts its call correctly in tests.
"""

from __future__ import annotations

import re
from typing import Optional


# ---------------------------------------------------------------------------
# Credential patterns (from safety.md "Credentials — ABSOLUTE PROHIBITION")
# ---------------------------------------------------------------------------

# Template markers denoting non-secret scaffolding files. A basename is a
# template when one of these is a dotted component (.env.example,
# credentials.example.yml, secrets.sample.json, config.template.yml) — these
# hold placeholders, never real secrets.
_TEMPLATE_MARKERS = frozenset({"example", "sample", "template", "dist"})

# Extensions that are NEVER exempt, even if a template marker is also present
# (guards against e.g. foo.example.key). Encrypted stores + key material.
_HARD_SECRET_EXTS = (
    ".enc", ".key", ".pem", ".p12", ".pfx", ".jks", ".keystore", ".truststore",
)

# Source-code extensions. A file of source is code, not a credential store —
# `credentials.py` is a module, not a secret. Deliberately narrow: every data
# and config extension (.toml/.yaml/.yml/.json/.ini/.env/...) stays denied,
# because those are the formats credentials are actually stored in.
_SOURCE_EXTS = (
    ".py", ".pyi", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx",
    ".go", ".rs", ".rb", ".java", ".kt", ".swift", ".c", ".h",
    ".cc", ".cpp", ".hpp", ".cs", ".php",
)

# Filename-level patterns: matched against the basename of the path.
# Order: most specific first; the .env allowlist check runs BEFORE these.
_CREDENTIAL_BASENAME_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^service-account.*\.json$", re.IGNORECASE),
    re.compile(r"^credentials\.", re.IGNORECASE),
    re.compile(r"^secrets\.", re.IGNORECASE),
    re.compile(r"^.*-secrets\.", re.IGNORECASE),
    re.compile(r"^.+\.env$", re.IGNORECASE),            # bare *.env
    re.compile(r"^\.env(\.|$)", re.IGNORECASE),         # .env, .env.production, etc.
    re.compile(r"^.+\.key$", re.IGNORECASE),
    re.compile(r"^.+\.pem$", re.IGNORECASE),
    re.compile(r"^.+\.p12$", re.IGNORECASE),
    re.compile(r"^.+\.pfx$", re.IGNORECASE),
    re.compile(r"^.+\.jks$", re.IGNORECASE),
    re.compile(r"^.+\.keystore$", re.IGNORECASE),
    re.compile(r"^.+\.truststore$", re.IGNORECASE),
]

# Word-boundary separators for keyword matching within a path segment.
# A keyword only matches when surrounded by start/end of segment or one of these.
_SEG_SEPS = re.compile(r"[-_.\s]")

# Shell/quote/paren punctuation used to decompose compound tokens (e.g. the
# single shlex token "cat credentials.toml" inside a -c argument).
_TOKEN_SPLIT = re.compile(r"""[\s()'"<>|;&`]+""")

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


def _is_template_file(basename: str) -> bool:
    """Return True if basename is a non-secret template/scaffolding file.

    A template marker (example / sample / template / dist) appearing as a dotted
    component marks a placeholder file checked into the repo. A file that also
    ends in a hard-secret extension (.enc / .key / .pem / ...) is never a template.

    A marker appearing BEFORE a `.env` suffix does not make the file a template:
    `.env.example` is scaffolding (marker is the suffix), but `example.env` and
    `prod.template.env` are live credential stores (`.env` is the suffix).
    """
    lower = basename.lower()
    if lower.endswith(_HARD_SECRET_EXTS):
        return False
    # Marker before .env does not exempt — example.env / prod.template.env are real.
    if lower.endswith(".env"):
        return False
    return bool(set(lower.split(".")) & _TEMPLATE_MARKERS)


def _is_path_shaped(token: str) -> bool:
    """Return True if token looks like a file-system path.

    A token is path-shaped when it contains a `/` (slash-separated path),
    starts with `.` (hidden file or relative ref), or ends with a file
    extension (a dot followed by 1-6 alphanumeric characters).
    Non-path tokens like variable names, option arguments, or issue titles
    are not path-shaped and are not checked against credential patterns.
    """
    if not token:
        return False
    if "/" in token:
        return True
    if token.startswith("."):
        return True
    return bool(re.search(r"\.\w{1,6}$", token))


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
    1. Explicit allow: non-secret template files (.env.example, credentials.example.yml …)
    2. Explicit deny: hard-secret extensions (.enc, .key, .pem, …)
    3. Basename against known credential file patterns (skipped for source files).
    4. Credential-related DELIMITED keywords in path segments.
       Source files are only exempt from BASENAME keyword checks, not directory checks.
       e.g. secret/config.py → denied (directory "secret"); src/apikey.py → allowed.
    5. Explicit allow: source-code extensions (.py, .js, .ts, …) — runs last so
       directory-level keywords (step 4) are evaluated first.

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

    # 1. Allow non-secret template files before any deny pattern fires
    if _is_template_file(basename):
        return False

    lower_basename = basename.lower()

    # 2. Hard-secret extensions are always denied (covers .enc and reinforces
    #    .key/.pem/etc. that are also in the basename patterns below).
    #    A stem is required: "id_rsa.key" is a key file, but a bare ".key" is not
    #    a filename — it appears as a jq/JSON selector fragment when a command
    #    string is decomposed, and denying it blocks benign commands.
    if any(
        lower_basename.endswith(ext) and len(lower_basename) > len(ext)
        for ext in _HARD_SECRET_EXTS
    ):
        return True

    is_source_file = lower_basename.endswith(_SOURCE_EXTS)

    # 3. Basename pattern match (skipped for source files — credentials.py is a module)
    if not is_source_file:
        for pattern in _CREDENTIAL_BASENAME_PATTERNS:
            if pattern.match(basename):
                return True

    # 4. Delimited keyword match in path segments.
    #    Source extensions do NOT exempt from directory-level keyword checks;
    #    only the basename segment is skipped for source files so that
    #    secret/config.py is denied while src/apikey.py remains allowed.
    check_segments = segments[:-1] if is_source_file else segments
    for seg in check_segments:
        for keyword in _CREDENTIAL_SEGMENT_KEYWORDS:
            if _keyword_in_segment(keyword, seg):
                return True

    # 5. Source-code files are code, not credential stores — final allow after
    #    all deny checks have run.
    if is_source_file:
        return False

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
    """Return True if any path-shaped token in the command is a credential path.

    Tokenizes with shlex; on parse error falls back to whitespace splitting.
    Only tokens that look like file paths (contain /, start with ., or carry a
    file extension) are checked against credential patterns — option values,
    issue titles, variable names, and other non-path tokens are skipped.

    Each shlex token is also decomposed using shell/quote/punctuation splits so
    that a credential path embedded inside a compound argument (e.g. the single
    token "cat credentials.toml" from `bash -c '...'`) is still detected.
    The value half of any key=value operand (e.g. `if=credentials.toml`) is also
    extracted and checked.

    Known non-goals (static string analysis cannot catch):
      - Variable-built paths: f=.env; cat $f  (path not present as literal)
      - Glob obfuscation: cat .e*              (glob expands at runtime)
    These are accepted limitations, not bugs.
    """
    try:
        import shlex
        tokens = shlex.split(command)
    except ValueError:
        tokens = command.split()

    for token in tokens:
        cleaned = _strip_token_punctuation(token)
        if not cleaned:
            continue

        # Build the candidate list: the token itself, plus any pieces obtained by
        # splitting on shell metacharacters (covers bash -c '...' style args) and
        # the value half of key=value operands (covers dd if=...).
        candidates = [cleaned]
        if _TOKEN_SPLIT.search(cleaned):
            candidates.extend(_TOKEN_SPLIT.split(cleaned))
        # Split on "=" unconditionally — this covers both plain key=value
        # operands (dd if=...) and flag-style tokens (--config=credentials.toml).
        # The guard against false positives is _is_path_shaped, not startswith("-"):
        # non-path values such as "json" or "2" are not path-shaped and are ignored.
        if "=" in cleaned:
            candidates.append(cleaned.partition("=")[2])

        for cand in candidates:
            c = _strip_token_punctuation(cand)
            if c and _is_path_shaped(c) and _is_credential_path(c):
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
