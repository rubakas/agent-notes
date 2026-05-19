"""Run pending memory vault migrations."""
from ...config import Color
from . import _common


def do_migrate_memory() -> None:
    """Run all pending memory migrations."""
    backend, path = _common._load_memory_config()
    if backend != "obsidian":
        print("Memory migrations are only available for the obsidian backend.")
        return
    if path is None:
        print("Memory path not configured. Run: agent-notes install")
        return

    from ...services.migrations import get_pending_migrations, run_all_pending

    pending = get_pending_migrations()
    if not pending:
        print("No pending migrations.")
        return

    print(f"Found {len(pending)} pending migration(s):")
    for m in pending:
        print(f"  - {m.name}: {m.description}")
    print()

    results = run_all_pending(path)
    for name, summary in results:
        print(f"{Color.GREEN}{name}{Color.NC}: {summary}")
    print(f"\n{len(results)} migration(s) completed.")
