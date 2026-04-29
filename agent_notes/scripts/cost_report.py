"""Single cost-report entry point — detects active AI CLI and dispatches."""
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import _claude_backend, _opencode_backend


def _opencode_active() -> bool:
    return bool(os.environ.get("OPENCODE") or os.environ.get("OPENCODE_SESSION_ID"))


def _by_recency(since: float | None = None) -> int:
    """Fallback: pick whichever backend's data is newer."""
    slug = str(Path.cwd()).replace("/", "-")
    proj = Path.home() / ".claude" / "projects" / slug
    claude_mtime = 0.0
    if proj.exists():
        jsonls = list(proj.glob("*.jsonl"))
        if jsonls:
            claude_mtime = max(f.stat().st_mtime for f in jsonls)

    opencode_db = Path.home() / ".local" / "share" / "opencode" / "opencode.db"
    opencode_mtime = opencode_db.stat().st_mtime if opencode_db.exists() else 0.0

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
        return _opencode_backend.run()
    return _claude_backend.run(since=since)


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


def main() -> int:
    since: float | None = None

    args = sys.argv[1:]
    remaining = []
    i = 0
    while i < len(args):
        if args[i] == "--since":
            if i + 1 >= len(args):
                print("error: --since requires a datetime argument", file=sys.stderr)
                sys.exit(1)
            since = _parse_since(args[i + 1])
            i += 2
        elif args[i].startswith("--since="):
            since = _parse_since(args[i].split("=", 1)[1])
            i += 1
        elif args[i] in ("--help", "-h"):
            print(
                "usage: cost-report [--since <ISO-datetime>]\n"
                "\n"
                "Report token usage and cost for the current AI session.\n"
                "\n"
                "Options:\n"
                "  --since <ISO>  Only include messages at or after this UTC datetime.\n"
                "                 Accepts ISO 8601 format, e.g. 2026-04-30T12:00:00Z\n"
                "  -h, --help     Show this help message and exit\n"
            )
            return 0
        else:
            remaining.append(args[i])
            i += 1

    if os.environ.get("CLAUDECODE") or os.environ.get("CLAUDE_CODE_ENTRYPOINT"):
        return _claude_backend.run(since=since)
    if _opencode_active():
        if since is not None:
            print(
                "warning: --since is currently honored only for the Claude Code backend; "
                "OpenCode backend will ignore the filter.",
                file=sys.stderr,
            )
        return _opencode_backend.run()
    return _by_recency(since=since)


if __name__ == "__main__":
    sys.exit(main())
