"""Memory-subsystem install helpers.

Extracted from services/installer.py and services/install_executor.py.
These functions own the memory-specific portions of the session-hook
install/uninstall cycle: memory-bridge hooks, vault allow-entries, and
skill filtering by memory backend requirement.

The hook command strings (Hooks.MEMORY_BRIDGE, Hooks.PRECOMPACT_MEMORY_BRIDGE)
remain in constants.py — they are the *installed contract* matched by
settings_writer.remove_hook for every user's settings.json, not the
implementation. This module uses those constants and never re-defines them.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional


def install_memory_hooks(
    settings_path: Path,
    memory_backend: str,
) -> None:
    """Install (or remove) the SessionStart and PreCompact memory-bridge hooks.

    If memory_backend is "obsidian", installs both hooks.
    For any other backend, removes them so stale entries are cleaned up.
    Also removes the now-stale PostToolUse memory-bridge from older versions.
    """
    from ..services.settings_writer import install_hook, remove_hook
    from ..constants import Hooks

    if memory_backend == "obsidian":
        install_hook(settings_path, "SessionStart", Hooks.MEMORY_BRIDGE)
        install_hook(settings_path, "PreCompact", Hooks.PRECOMPACT_MEMORY_BRIDGE)
    else:
        remove_hook(settings_path, "SessionStart", Hooks.MEMORY_BRIDGE)
        remove_hook(settings_path, "PreCompact", Hooks.PRECOMPACT_MEMORY_BRIDGE)

    # Clean up stale PostToolUse hooks from previous versions
    remove_hook(settings_path, "PostToolUse", Hooks.MEMORY_BRIDGE)


def uninstall_memory_hooks(settings_path: Path) -> None:
    """Remove the SessionStart and PreCompact memory-bridge hooks."""
    from ..services.settings_writer import remove_hook
    from ..constants import Hooks

    remove_hook(settings_path, "SessionStart", Hooks.MEMORY_BRIDGE)
    remove_hook(settings_path, "PreCompact", Hooks.PRECOMPACT_MEMORY_BRIDGE)
    remove_hook(settings_path, "PostToolUse", Hooks.MEMORY_BRIDGE)


def install_memory_allow_entries(
    settings_path: Path,
    memory_backend: str,
    memory_path: str,
    current_state,
) -> None:
    """Install Bash/Read/Write/Edit allow entries for memory operations.

    Installs:
    - Bash(agent-notes memory *)  — always (for non-obsidian memory commands)
    - Bash(<MEMORY_BRIDGE>)       — only for obsidian backend
    - Read/Write/Edit(<vault>/**) — only for obsidian backend

    Also removes stale vault path entries from the obsidian default path and
    any custom path from the previous state, before adding fresh entries.
    """
    from ..services.settings_writer import (
        install_allow_entry,
        remove_allow_entry,
    )
    from ..constants import Hooks
    from ..config import memory_dir_for_backend

    install_allow_entry(settings_path, "Bash(agent-notes memory *)")

    if memory_backend == "obsidian":
        install_allow_entry(settings_path, f"Bash({Hooks.MEMORY_BRIDGE})")

    # Remove memory path permissions for the obsidian default path so that
    # stale entries from previous installs are cleaned up before adding fresh ones.
    default_path = memory_dir_for_backend("obsidian", "")
    if default_path:
        p = str(default_path) + "/**"
        remove_allow_entry(settings_path, f"Read({p})")
        remove_allow_entry(settings_path, f"Write({p})")
        remove_allow_entry(settings_path, f"Edit({p})")

    # Also remove any custom path recorded in old state
    if current_state and current_state.memory.backend == "obsidian" and current_state.memory.path:
        old_resolved = memory_dir_for_backend(
            current_state.memory.backend, current_state.memory.path
        )
        if old_resolved:
            old_pattern = str(old_resolved) + "/**"
            remove_allow_entry(settings_path, f"Read({old_pattern})")
            remove_allow_entry(settings_path, f"Write({old_pattern})")
            remove_allow_entry(settings_path, f"Edit({old_pattern})")

    # Add read/write/edit permissions for the new memory vault path
    if memory_backend == "obsidian":
        resolved_path = memory_dir_for_backend(memory_backend, memory_path)
        if resolved_path:
            path_pattern = str(resolved_path) + "/**"
            install_allow_entry(settings_path, f"Read({path_pattern})")
            install_allow_entry(settings_path, f"Write({path_pattern})")
            install_allow_entry(settings_path, f"Edit({path_pattern})")


def filter_skills_by_backend(skills, memory_backend: str) -> list:
    """Return skills compatible with the given memory backend.

    Skills without a requires_memory constraint are always included.
    Skills with requires_memory are included only if memory_backend appears
    in their comma-separated backend list.
    """
    result = []
    for skill in skills:
        if skill.requires_memory is None:
            result.append(skill)
        else:
            allowed = {b.strip() for b in skill.requires_memory.split(",")}
            if memory_backend in allowed:
                result.append(skill)
    return result
