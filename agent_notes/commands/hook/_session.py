"""Session-discover hook handler."""

from __future__ import annotations

from pathlib import Path


def _session_discover() -> None:
    """Discover all agent-notes profiles for the current project and emit combined context."""
    try:
        from ...services.state_store import load_state, get_profiles_for_project
        from ...registries.cli_registry import load_registry

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
