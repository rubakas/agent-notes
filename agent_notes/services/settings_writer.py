"""Read, merge, and write Claude Code settings.json without clobbering user config."""
import json
from pathlib import Path


def _deep_merge(base: dict, override: dict) -> dict:
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _load_settings(path: Path) -> dict:
    """Load settings dict from path. Returns {} if absent or invalid JSON."""
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return {}


def install_hook(settings_path: Path, hook_event: str, command: str) -> None:
    """Add a hook entry to settings.json. Idempotent — does not duplicate."""
    data = _load_settings(settings_path)

    # Check if already present
    existing = data.get("hooks", {}).get(hook_event, [])
    for entry in existing:
        for h in entry.get("hooks", []):
            if h.get("command") == command:
                return  # already installed

    hooks_dict = data.setdefault("hooks", {})
    event_list = hooks_dict.setdefault(hook_event, [])
    event_list.append(
        {"matcher": "", "hooks": [{"type": "command", "command": command}]}
    )
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps(data, indent=2) + "\n")


def remove_hook(settings_path: Path, hook_event: str, command: str) -> None:
    """Remove a specific hook entry from settings.json."""
    if not settings_path.exists():
        return
    data = _load_settings(settings_path)
    if not data:
        return

    hooks = data.get("hooks", {}).get(hook_event, [])
    cleaned = [
        entry for entry in hooks
        if not any(h.get("command") == command for h in entry.get("hooks", []))
    ]
    if cleaned:
        data["hooks"][hook_event] = cleaned
    else:
        data.get("hooks", {}).pop(hook_event, None)
        if not data.get("hooks"):
            data.pop("hooks", None)
    settings_path.write_text(json.dumps(data, indent=2) + "\n")


def install_allow_entry(settings_path: Path, pattern: str) -> None:
    """Add a pattern to permissions.allow in settings.json (idempotent)."""
    data = _load_settings(settings_path)

    permissions = data.setdefault("permissions", {})
    allow = permissions.setdefault("allow", [])
    if pattern in allow:
        return  # early-return: file exists, parent dir already exists
    allow.append(pattern)
    # mkdir is safe here: early-return above fires only when the file already
    # exists (implying the parent directory exists); we reach this line only
    # when we have new content to write.
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps(data, indent=2) + "\n")


def remove_allow_entry(settings_path: Path, pattern: str) -> None:
    """Remove a pattern from permissions.allow in settings.json. No-op if absent."""
    data = _load_settings(settings_path)
    if not data:
        return

    allow = data.get("permissions", {}).get("allow", [])
    if pattern not in allow:
        return
    allow.remove(pattern)
    settings_path.write_text(json.dumps(data, indent=2) + "\n")


def remove_matching_allow_entries(settings_path: Path, prefix: str) -> None:
    """Remove all permission entries that start with the given prefix."""
    data = _load_settings(settings_path)
    allow = data.get("permissions", {}).get("allow", [])
    filtered = [e for e in allow if not e.startswith(prefix)]
    if len(filtered) == len(allow):
        return
    data.setdefault("permissions", {})["allow"] = filtered
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps(data, indent=2) + "\n")


def has_hook(settings_path: Path, hook_event: str, command: str) -> bool:
    """Return True if the hook is present in settings.json."""
    data = _load_settings(settings_path)
    for entry in data.get("hooks", {}).get(hook_event, []):
        for h in entry.get("hooks", []):
            if h.get("command") == command:
                return True
    return False
