"""Hook command - Claude Code hook integrations."""

from pathlib import Path


def hook(subaction: str) -> None:
    """Handle hook subactions."""
    if subaction == "memory-bridge":
        _memory_bridge()
    elif subaction == "session-discover":
        _session_discover()


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


def _memory_bridge() -> None:
    """SessionStart hook that prints the agent-notes memory index.

    Unconditionally loads and prints the memory index so it is visible in
    context at the start of every Claude Code session.
    """
    try:
        from .memory._common import _load_memory_config
        from ..constants import Obsidian, Wiki

        backend, path = _load_memory_config()

        if backend == "none" or backend is None:
            return

        if backend == "obsidian":
            index_file = Path(path) / Obsidian.INDEX
        elif backend == "wiki":
            index_file = Path(path) / Wiki.DIR / Wiki.INDEX
        else:
            # local and any unknown backends: use Index.md at root
            index_file = Path(path) / "Index.md"

        if not index_file.exists():
            return

        content = index_file.read_text(encoding="utf-8")
        print("<!-- agent-notes memory index (auto-loaded) -->")
        print(content)
    except Exception:
        return
