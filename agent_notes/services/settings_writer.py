"""Read, merge, and write Claude Code settings.json and Codex hooks.json without clobbering user config.

The files belong to the user, so every edit is surgical and safe: a file that does not parse is
never touched, the original is copied to <file>.bak.<ts> before the first rewrite of a run, and
a rewrite goes through a temp file and os.replace so a crash cannot leave half a file.
"""
import json
import os
import shutil
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

# One agent-notes run is one process: back each file up once, warn about each broken file once.
_backed_up: dict[str, Optional[Path]] = {}   # real path -> its backup (None: the file did not exist)
_warned: set[str] = set()
_open: dict[str, dict] = {}   # files inside a transaction: real path -> the dict being edited


def _deep_merge(base: dict, override: dict) -> dict:
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


@contextmanager
def transaction(path: Path) -> Iterator[None]:
    """Edits to *path* inside the block share one dict and are written once at the end, and only
    if they changed anything: a remove-then-add that ends where it began leaves the file (and
    its mtime) alone, and the file is backed up and replaced at most once."""
    key = os.path.realpath(path)
    data = _load_settings(path, consequence=None)   # the operations inside say what they did not do
    if data is None or key in _open:
        yield   # unparseable (left alone), or already inside a transaction
        return
    before = json.dumps(data, sort_keys=True)
    _open[key] = data
    try:
        yield
    finally:
        del _open[key]
    if json.dumps(data, sort_keys=True) != before:
        _write(path, data)


def _load_settings(path: Path, consequence: Optional[str] = "agent-notes left it unchanged") -> Optional[dict]:
    """The settings dict: {} if the file is absent, None if it exists but is not a JSON object
    (the caller must then leave it alone; a warning names the file once and says what that
    meant for the caller, *consequence*; None says nothing)."""
    shared = _open.get(os.path.realpath(path))
    if shared is not None:
        return shared
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        pass
    if consequence is not None and str(path) not in _warned:
        _warned.add(str(path))
        print(f"Warning: {path} is not valid JSON; {consequence}. "
              f"Fix it, then rerun the install.", file=sys.stderr)
    return None


def _write(path: Path, data: dict) -> None:
    """Back the file up (once per run), then replace it atomically. A symlinked file (dotfiles)
    is written through the link, which stays a link."""
    from .fs import backup_copy

    if os.path.realpath(path) in _open:
        return  # written when the transaction ends
    real = Path(os.path.realpath(path))
    real.parent.mkdir(parents=True, exist_ok=True)
    if str(real) not in _backed_up:
        _backed_up[str(real)] = backup_copy(real) if real.exists() else None
    tmp = real.with_name(f".{real.name}.tmp-{os.getpid()}")
    try:
        tmp.write_text(json.dumps(data, indent=2) + "\n")
        if real.exists():
            shutil.copymode(real, tmp)
        os.replace(tmp, real)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def _hooks_of(entry) -> Optional[list]:
    return entry["hooks"] if isinstance(entry, dict) and isinstance(entry.get("hooks"), list) else None


def _has_command(entries, command: str) -> bool:
    return any(isinstance(h, dict) and h.get("command") == command
               for entry in entries if _hooks_of(entry) is not None for h in _hooks_of(entry))


def install_hook(settings_path: Path, hook_event: str, command: str, matcher: str = "") -> None:
    """Add a hook entry to settings.json. Idempotent — does not duplicate."""
    data = _load_settings(settings_path, consequence="the agent-notes hook was not installed")
    if data is None:
        return

    hooks_dict = data.get("hooks")
    if isinstance(hooks_dict, dict) and isinstance(hooks_dict.get(hook_event), list) \
            and _has_command(hooks_dict[hook_event], command):
        return  # already installed

    hooks_dict = data.setdefault("hooks", {})
    event_list = hooks_dict.setdefault(hook_event, [])
    event_list.append(
        {"matcher": matcher, "hooks": [{"type": "command", "command": command}]}
    )
    _write(settings_path, data)


def remove_hook(settings_path: Path, hook_event: str, command: str) -> None:
    """Remove our command from settings.json. Another hook sharing an entry stays; the entry
    goes only when nothing else is left in it."""
    data = _load_settings(settings_path)
    if not data:
        return

    hooks = data.get("hooks")
    entries = hooks.get(hook_event) if isinstance(hooks, dict) else None
    if not isinstance(entries, list):
        return

    changed, kept_entries = False, []
    for entry in entries:
        commands = _hooks_of(entry)
        if commands is None:
            kept_entries.append(entry)
            continue
        kept = [h for h in commands if not (isinstance(h, dict) and h.get("command") == command)]
        if len(kept) == len(commands):
            kept_entries.append(entry)
            continue
        changed = True
        if kept:
            kept_entries.append({**entry, "hooks": kept})
    if not changed:
        return

    if kept_entries:
        hooks[hook_event] = kept_entries
    else:
        hooks.pop(hook_event, None)
        if not hooks:
            data.pop("hooks", None)
    _write(settings_path, data)


def _allow_list(data: dict) -> Optional[list]:
    permissions = data.get("permissions")
    allow = permissions.get("allow") if isinstance(permissions, dict) else None
    return allow if isinstance(allow, list) else None


def install_allow_entry(settings_path: Path, pattern: str) -> None:
    """Add a pattern to permissions.allow in settings.json (idempotent)."""
    data = _load_settings(settings_path)
    if data is None:
        return

    permissions = data.setdefault("permissions", {})
    allow = permissions.setdefault("allow", [])
    if pattern in allow:
        return
    allow.append(pattern)
    _write(settings_path, data)


def remove_allow_entry(settings_path: Path, pattern: str) -> None:
    """Remove a pattern from permissions.allow in settings.json. No-op if absent."""
    data = _load_settings(settings_path)
    if not data:
        return

    allow = _allow_list(data)
    if allow is None or pattern not in allow:
        return
    allow.remove(pattern)
    _write(settings_path, data)


def _is_ours(entry, prefix: str) -> bool:
    """*entry* is the command *prefix* names, with or without arguments: "Bash(agent-notes memory *)"
    and "Bash(agent-notes:*)" for the prefix "Bash(agent-notes", not "Bash(agent-notes-mytool:*)"."""
    return isinstance(entry, str) and (entry == prefix + ")" or entry.startswith((prefix + " ", prefix + ":")))


def remove_matching_allow_entries(settings_path: Path, prefix: str) -> None:
    """Remove the permission entries for the command *prefix* names (exact command, any arguments)."""
    data = _load_settings(settings_path)
    if not data:
        return
    allow = _allow_list(data)
    if allow is None:
        return
    filtered = [e for e in allow if not _is_ours(e, prefix)]
    if len(filtered) == len(allow):
        return
    data["permissions"]["allow"] = filtered
    _write(settings_path, data)


def has_hook(settings_path: Path, hook_event: str, command: str) -> bool:
    """Return True if the hook is present in settings.json."""
    data = _load_settings(settings_path)
    hooks = (data or {}).get("hooks")
    entries = hooks.get(hook_event) if isinstance(hooks, dict) else None
    return isinstance(entries, list) and _has_command(entries, command)


def _holds_nothing(data: dict) -> bool:
    """{} or only the empty containers our own removals leave behind."""
    return all(key in ("hooks", "permissions") for key in data) \
        and data.get("hooks", {}) == {} and data.get("permissions", {}) in ({}, {"allow": []})


def drop_if_empty(settings_path: Path) -> bool:
    """Remove a settings/hooks file that this run edited and that now holds nothing ({} or only
    empty "hooks" / "permissions" objects): it was created for our entries, and so was the
    backup this run took of it, which goes too. A file that does not parse, that was not edited
    by us, or that is a symlink (its target is the user's dotfile) is never removed."""
    if settings_path.is_symlink():
        return False
    real = Path(os.path.realpath(settings_path))
    if str(real) not in _backed_up:
        return False
    data = _load_settings(settings_path)
    if data is None or not _holds_nothing(data) or not settings_path.exists():
        return False
    real.unlink()
    backup = _backed_up.pop(str(real))
    if backup is not None:
        backup.unlink(missing_ok=True)
    return True
