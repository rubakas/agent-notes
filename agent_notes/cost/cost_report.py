"""Single cost-report entry point — detects active AI CLI and dispatches."""
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import _claude_backend, _opencode_backend
from ._claude_backend import _resolve_claude_homes
from ._opencode_backend import DB as _OPENCODE_DB


def _opencode_active() -> bool:
    return bool(os.environ.get("OPENCODE") or os.environ.get("OPENCODE_SESSION_ID"))


def _by_recency(since: float | None = None, session_id: str | None = None) -> int:
    """Fallback: pick whichever backend's data is newer."""
    slug = str(Path.cwd().resolve()).replace("/", "-")
    claude_mtime = 0.0
    proj = None
    for home in _resolve_claude_homes():
        candidate = home / "projects" / slug
        if candidate.exists():
            jsonls = list(candidate.glob("*.jsonl"))
            if jsonls:
                mtime = max(f.stat().st_mtime for f in jsonls)
                if mtime > claude_mtime:
                    claude_mtime = mtime
                    proj = candidate

    opencode_mtime = _OPENCODE_DB.stat().st_mtime if _OPENCODE_DB.exists() else 0.0

    if claude_mtime == 0.0 and opencode_mtime == 0.0:
        print("No session data found (no Claude Code transcripts or OpenCode database).")
        return 0

    if opencode_mtime > claude_mtime:
        if since is not None:
            print(
                "warning: --since is currently honored only for the Claude Code backend; "
                "OpenCode backend will ignore the filter.",
                file=sys.stderr,
            )
        if session_id is not None:
            print(
                "warning: --session is not supported for the OpenCode backend; ignoring.",
                file=sys.stderr,
            )
        return _opencode_backend.run()
    return _claude_backend.run(since=since, session_id=session_id)


def _parse_since(value: str) -> float:
    """Parse an ISO datetime string (with optional Z suffix) to a UTC timestamp."""
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except ValueError:
        print(f"error: --since value {value!r} is not a valid ISO datetime", file=sys.stderr)
        sys.exit(1)


def main(since: float | None = None, session_id: str | None = None) -> int:
    from ..services.user_config import load_user_config
    from ..registries.plugin_registry import default_plugin_registry
    cfg = load_user_config()
    if not any(p.name == "cost-report" for p in default_plugin_registry().enabled(cfg)):
        print("Cost reporting is disabled. Enable with: agent-notes plugins enable cost-report")
        return 0

    if session_id is not None and _opencode_active():
        print(
            "warning: --session is not supported for the OpenCode backend; ignoring.",
            file=sys.stderr,
        )
        session_id = None

    if os.environ.get("CLAUDECODE") or os.environ.get("CLAUDE_CODE_ENTRYPOINT"):
        if session_id is None:
            session_id = os.environ.get("CLAUDE_CODE_SESSION_ID")
        return _claude_backend.run(since=since, session_id=session_id)
    if _opencode_active():
        if since is not None:
            print(
                "warning: --since is currently honored only for the Claude Code backend; "
                "OpenCode backend will ignore the filter.",
                file=sys.stderr,
            )
        return _opencode_backend.run()
    return _by_recency(since=since, session_id=session_id)
