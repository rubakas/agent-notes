"""Migration discovery and execution engine."""
from __future__ import annotations
from pathlib import Path

from .base import Migration
from .registry import ALL_MIGRATIONS
from ..state_store import load_state, save_state
from ...domain.state import MigrationState


def get_pending_migrations() -> list[Migration]:
    """Return migrations not yet completed."""
    state = load_state()
    if state is None:
        return list(ALL_MIGRATIONS)
    completed = set(state.memory_migrations.completed)
    return [m for m in ALL_MIGRATIONS if m.name not in completed]


def run_migration(migration: Migration, vault: Path) -> str:
    """Run one migration and record completion in state."""
    summary = migration.run(vault)
    state = load_state()
    if state is None:
        from ...domain.state import State
        state = State()
    state.memory_migrations.completed.append(migration.name)
    save_state(state)
    return summary


def run_all_pending(vault: Path) -> list[tuple[str, str]]:
    """Run all pending migrations in order. Returns [(name, summary), ...]."""
    results = []
    for m in get_pending_migrations():
        summary = run_migration(m, vault)
        results.append((m.name, summary))
    return results
