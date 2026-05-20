"""Main wizard flow — entry point for the interactive install wizard."""

from ...config import Color, get_version
from ...services.ui import _clear_screen
from ..build import build
from .._install_helpers import count_agents, count_skills
from ._common import _count_rules
from .execute import _execute_install


def interactive_install() -> None:
    """Run the interactive install wizard."""
    try:
        _interactive_install()
    except KeyboardInterrupt:
        print(f"\n\n  {Color.YELLOW}Cancelled.{Color.NC}")


def _interactive_install() -> None:
    """Inner implementation — called by interactive_install() with KeyboardInterrupt guard."""
    # Import step functions at call time to avoid circular import with __init__
    import agent_notes.commands.wizard as _wiz

    version = get_version()
    from ...registries.cli_registry import load_registry
    registry = load_registry()

    total_agents = 0
    for backend in registry.all():
        if backend.supports("agents"):
            total_agents += count_agents(backend)

    n_skills = count_skills()
    n_rules = _count_rules()

    TOTAL_STEPS = 8

    _clear_screen()
    print(f"\n  {Color.BOLD}AgentNotes{Color.NC} {Color.CYAN}v{version}{Color.NC}")
    print(f"  {Color.DIM}AI agent configuration manager for Claude Code and OpenCode.{Color.NC}\n")
    print(f"  Includes {total_agents} agents, {n_skills} skills, and {n_rules} rules.\n")

    # Step 1: CLI selection
    clis = _wiz._select_cli(step=1, total=TOTAL_STEPS, version=version)

    if not clis:
        print("No CLI selected. Installation cancelled.")
        return

    # Step 2: Model selection per role (for CLIs that support agents)
    role_models = _wiz._select_models_per_role(clis, step=2, total=TOTAL_STEPS, version=version)

    # Step 3: Install scope
    scope = _wiz._select_scope(clis=clis, step=3, total=TOTAL_STEPS, version=version)

    # Step 4: Install mode (always shown)
    copy_mode = _wiz._select_mode(step=4, total=TOTAL_STEPS, version=version)

    # Step 5: Profile (optional, for multi-subscription setups)
    profile_label, folder_overrides, global_home_override = _wiz._select_profile(
        step=5, total=TOTAL_STEPS, version=version)

    # Step 6: Skill selection
    selected_skills = _wiz._select_skills(step=6, total=TOTAL_STEPS, version=version)

    # Step 7: Memory backend
    memory_backend, memory_path = _wiz._select_memory(step=7, total=TOTAL_STEPS, version=version)

    # Step 8: Confirmation
    if not _wiz._confirm_install(clis, scope, copy_mode, selected_skills, role_models, version=version,
                                 memory_backend=memory_backend, memory_path=memory_path):
        print("Installation cancelled.")
        return

    # Build first
    print("\nBuilding from source...")
    try:
        build()
    except Exception as e:
        print(f"{Color.RED}Build failed: {e}{Color.NC}")
        return

    _execute_install(
        clis=clis,
        scope=scope,
        copy_mode=copy_mode,
        selected_skills=selected_skills,
        role_models=role_models,
        memory_backend=memory_backend,
        memory_path=memory_path,
        profile_label=profile_label,
        folder_overrides=folder_overrides,
        global_home_override=global_home_override,
    )
