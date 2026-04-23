"""State storage I/O operations."""

from __future__ import annotations

import os
import json
import hashlib
from pathlib import Path
from dataclasses import asdict
from typing import Optional
from datetime import datetime, timezone

from ..domain.state import State, ScopeState, BackendState, InstalledItem


def state_dir() -> Path:
    """~/.config/agent-notes/ respecting $XDG_CONFIG_HOME."""
    config_home = os.environ.get("XDG_CONFIG_HOME")
    base = Path(config_home) if config_home else (Path.home() / ".config")
    return base / "agent-notes"


def state_file() -> Path:
    return state_dir() / "state.json"


def load_state() -> Optional[State]:
    """Load state from disk. Return None if file absent or on any error."""
    file_path = state_file()
    if not file_path.exists():
        return None
    
    try:
        data = json.loads(file_path.read_text())
        state = _state_from_dict(data)
        return state
    except Exception:
        return None


def save_state(state: State) -> None:
    """Atomic write. Updates updated_at on any ScopeState that has changed — but
    caller is responsible for setting installed_at on first creation. `save_state` itself
    refreshes `updated_at` on ALL present scopes (simple semantics).
    
    Serialize as JSON with keys:
      source_path, source_commit, global, local
    
    - `global_install` serializes to key "global" (None → omit or null)
    - `local_installs` serializes to key "local"
    - `BackendState.role_models` and `BackendState.installed` serialize naturally
    - `installed[component_type]` is a dict of name → InstalledItem as dict
    """
    # Update timestamps on all scopes
    now = now_iso()
    if state.global_install:
        state.global_install.updated_at = now
    for scope_state in state.local_installs.values():
        scope_state.updated_at = now
    
    # Ensure directory exists
    file_path = state_file()
    file_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Convert to JSON-serializable dict
    data = _state_to_dict(state)
    
    # Atomic write
    tmp_path = file_path.with_suffix(".json.tmp")
    try:
        tmp_path.write_text(json.dumps(data, indent=2))
        os.replace(tmp_path, file_path)
    except Exception:
        # Cleanup on failure
        if tmp_path.exists():
            tmp_path.unlink()
        raise


def clear_state() -> None:
    """Delete state file. No error if absent."""
    file_path = state_file()
    if file_path.exists():
        file_path.unlink()


def get_scope(state: State, scope: str, project_path: Optional[Path] = None) -> Optional[ScopeState]:
    """Fetch the ScopeState for a scope. scope is 'global' or 'local'.
    For 'local', project_path MUST be provided (absolute path).
    Returns None if the scope hasn't been installed to yet."""
    if scope == "global":
        return state.global_install
    if scope == "local":
        if project_path is None:
            raise ValueError("project_path required for local scope")
        return state.local_installs.get(str(Path(project_path).resolve()))
    raise ValueError(f"Unknown scope: {scope}")


def set_scope(state: State, scope: str, scope_state: ScopeState, project_path: Optional[Path] = None) -> None:
    """Set/replace the scope state."""
    if scope == "global":
        state.global_install = scope_state
    elif scope == "local":
        if project_path is None:
            raise ValueError("project_path required for local scope")
        state.local_installs[str(Path(project_path).resolve())] = scope_state
    else:
        raise ValueError(f"Unknown scope: {scope}")


def remove_scope(state: State, scope: str, project_path: Optional[Path] = None) -> None:
    """Remove scope state (for uninstall)."""
    if scope == "global":
        state.global_install = None
    elif scope == "local":
        if project_path is None:
            raise ValueError("project_path required for local scope")
        state.local_installs.pop(str(Path(project_path).resolve()), None)


def default_state() -> State:
    """Create an empty state."""
    return State(
        source_path="",
        source_commit="",
        global_install=None,
        local_installs={}
    )


def sha256_of(path: Path) -> str:
    """Return sha256 hex digest of a file's bytes."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def now_iso() -> str:
    """Current UTC ISO 8601 timestamp, seconds precision, trailing Z."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _state_to_dict(s: State) -> dict:
    return {
        "source_path": s.source_path,
        "source_commit": s.source_commit,
        "global": _scope_to_dict(s.global_install) if s.global_install else None,
        "local": {path: _scope_to_dict(ss) for path, ss in s.local_installs.items()},
    }


def _scope_to_dict(s: ScopeState) -> dict:
    return {
        "installed_at": s.installed_at,
        "updated_at": s.updated_at,
        "mode": s.mode,
        "clis": {name: _backend_to_dict(bs) for name, bs in s.clis.items()},
    }


def _backend_to_dict(b: BackendState) -> dict:
    return {
        "role_models": dict(b.role_models),
        "installed": {
            component: {name: asdict(item) for name, item in items.items()}
            for component, items in b.installed.items()
        },
    }


def _state_from_dict(data: dict) -> State:
    """Load State from JSON dict, handling missing fields defensively."""
    global_data = data.get("global")
    global_install = _scope_from_dict(global_data) if global_data else None
    
    local_data = data.get("local", {})
    local_installs = {path: _scope_from_dict(scope_data) for path, scope_data in local_data.items()}
    
    return State(
        source_path=data.get("source_path", ""),
        source_commit=data.get("source_commit", ""),
        global_install=global_install,
        local_installs=local_installs,
    )


def _scope_from_dict(data: dict) -> ScopeState:
    """Load ScopeState from JSON dict."""
    clis_data = data.get("clis", {})
    clis = {name: _backend_from_dict(backend_data) for name, backend_data in clis_data.items()}
    
    return ScopeState(
        installed_at=data.get("installed_at", ""),
        updated_at=data.get("updated_at", ""),
        mode=data.get("mode", "symlink"),
        clis=clis,
    )


def _backend_from_dict(data: dict) -> BackendState:
    """Load BackendState from JSON dict."""
    role_models = data.get("role_models", {})
    
    installed_data = data.get("installed", {})
    installed = {}
    for component, items_data in installed_data.items():
        items = {name: InstalledItem(**item_data) for name, item_data in items_data.items()}
        installed[component] = items
    
    return BackendState(
        role_models=role_models,
        installed=installed,
    )


# I/O functions moved from install_state.py
def record_install_state(state: State) -> None:
    """Persist state via save_state()."""
    save_state(state)


def load_current_state() -> Optional[State]:
    return load_state()


def remove_install_state(scope: str, project_path: Optional[Path] = None) -> None:
    """Remove install state for the given scope without affecting other scopes.
    
    For uninstall operations - this should only remove the target scope,
    not clear the entire state file.
    """
    current_state = load_state()
    if current_state is None:
        return  # Nothing to remove
    
    remove_scope(current_state, scope, project_path)
    
    # If state is now completely empty, clear the file
    if current_state.global_install is None and not current_state.local_installs:
        clear_state()
    else:
        save_state(current_state)