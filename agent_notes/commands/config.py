"""Config command — reconfigure role/agent/model/memory/skill assignments after install."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional


def _load_state():
    """Load state or exit with a clear message."""
    from .. import state as state_mod
    st = state_mod.load()
    if st is None:
        print("No installation found. Run `agent-notes install` first.")
        sys.exit(1)
    return st


def _get_scope_state(state, scope: Optional[str] = None, project_path: Optional[Path] = None):
    """Return (scope, project_path, scope_state) from state."""
    from ..services.state_store import get_scope

    if scope is None:
        if state.global_install is not None:
            scope = "global"
        elif state.local_installs:
            scope = "local"
        else:
            print("No installation found in state.")
            sys.exit(1)

    if scope == "local" and project_path is None:
        project_path = Path.cwd()

    scope_state = get_scope(state, scope, project_path)
    if scope_state is None:
        print(f"No {scope} installation found.")
        sys.exit(1)

    return scope, project_path, scope_state


def _validate_model(model_id: str):
    """Validate model exists in registry, exit on failure."""
    from ..registries.model_registry import load_model_registry
    registry = load_model_registry()
    try:
        return registry.get(model_id)
    except KeyError:
        print(f"Unknown model: {model_id}")
        print(f"Available models: {', '.join(registry.ids())}")
        sys.exit(1)


def _validate_role(role_name: str):
    """Validate role exists in registry, exit on failure."""
    from ..registries.role_registry import load_role_registry
    registry = load_role_registry()
    try:
        return registry.get(role_name)
    except KeyError:
        print(f"Unknown role: {role_name}")
        print(f"Available roles: {', '.join(registry.names())}")
        sys.exit(1)


def _state_snapshot(state) -> str:
    """Return a compact JSON snapshot of state for diffing."""
    from ..services.state_store import _state_to_dict
    return json.dumps(_state_to_dict(state), indent=2, sort_keys=True)


def _print_diff(before: str, after: str) -> None:
    """Print a simple line-by-line diff of two JSON strings."""
    before_lines = before.splitlines()
    after_lines = after.splitlines()

    if before_lines == after_lines:
        print("(no changes)")
        return

    # Find differing lines
    max_len = max(len(before_lines), len(after_lines))
    for i in range(max_len):
        bl = before_lines[i] if i < len(before_lines) else None
        al = after_lines[i] if i < len(after_lines) else None
        if bl != al:
            if bl is not None:
                print(f"  - {bl}")
            if al is not None:
                print(f"  + {al}")


def _apply_and_regenerate(state, before: str) -> None:
    """Show diff, prompt, then write + regenerate on Y."""
    from .. import install_state
    from ..config import Color
    from ..services.ui import _safe_input

    after = _state_snapshot(state)

    print("\nChanges to state.json:")
    _print_diff(before, after)
    print()

    try:
        choice = _safe_input("Apply these changes? [Y/n]: ", "Y").strip().lower()
    except (EOFError, KeyboardInterrupt):
        choice = "n"

    if choice not in ("", "y", "yes"):
        print("Discarded. No changes written.")
        return

    install_state.record_install_state(state)
    print("State written.")

    # Regenerate
    from .regenerate import regenerate as _regen
    _regen()

    print(f"\n{Color.GREEN}Done.{Color.NC} Restart your AI CLI to pick up changes.")


# ── Scriptable (non-interactive) actions ────────────────────────────────────

def role_model(role_name: str, model_id: str, cli_filter: Optional[str] = None) -> None:
    """Set role→model for one or both CLIs. Validates, diffs, prompts, applies."""
    state = _load_state()
    before = _state_snapshot(state)

    _validate_role(role_name)
    _validate_model(model_id)

    scope, project_path, scope_state = _get_scope_state(state)

    if cli_filter and cli_filter not in ("both",):
        # Single CLI
        target_clis = [cli_filter]
        for cli_name in target_clis:
            if cli_name not in scope_state.clis:
                print(f"CLI '{cli_name}' not in {scope} installation.")
                print(f"Installed CLIs: {', '.join(scope_state.clis.keys())}")
                sys.exit(1)
    else:
        target_clis = list(scope_state.clis.keys())

    for cli_name in target_clis:
        scope_state.clis[cli_name].role_models[role_name] = model_id
        print(f"Set {cli_name}: {role_name} -> {model_id}")

    _apply_and_regenerate(state, before)


def role_agent(role_name: str, agent_name: str, cli_filter: Optional[str] = None) -> None:
    """Set role→agent assignment (which agent files carry a given role)."""
    # Note: in the current data model, agent-to-role mapping is in agents.yaml (source)
    # not in state.json. state.json only stores role->model. The 'role' field in agents.yaml
    # drives which role tier an agent belongs to. This command updates a user_config override
    # if one exists, otherwise reports that it's source-controlled.
    print("Note: role→agent assignments are defined in agents.yaml (source-controlled).")
    print("Use `agent-notes set role` to change the model assigned to a role tier instead.")
    print()
    print(f"If you want agent '{agent_name}' to use the '{role_name}' role tier,")
    print("edit agent_notes/data/agents/agents.yaml and run `agent-notes build`.")
    sys.exit(0)


def show(state=None) -> None:
    """Print current configuration in readable form."""
    if state is None:
        state = _load_state()

    from ..registries.cli_registry import load_registry
    from ..registries.role_registry import load_role_registry
    from ..registries.model_registry import load_model_registry

    cli_registry = load_registry()
    role_registry = load_role_registry()
    model_registry = load_model_registry()

    # Memory
    mem = state.memory
    if mem.backend == "obsidian":
        mem_label = f"Obsidian ({mem.path})" if mem.path else "Obsidian"
    elif mem.backend == "local":
        mem_label = "Local markdown"
    else:
        mem_label = "Disabled"

    print("Current configuration:")
    print(f"  Memory:   {mem_label}")

    # Scopes
    scopes = []
    if state.global_install:
        scopes.append(("global", state.global_install, None))
    for path_str, ss in state.local_installs.items():
        scopes.append(("local", ss, path_str))

    if not scopes:
        print("  (no installation found)")
        return

    for scope_name, scope_state, path_str in scopes:
        scope_label = f"global" if scope_name == "global" else f"local ({path_str})"
        print(f"\n  Scope: {scope_label}  [{scope_state.mode}]")

        for cli_name, backend_state in sorted(scope_state.clis.items()):
            try:
                backend = cli_registry.get(cli_name)
                cli_label = backend.label
            except KeyError:
                cli_label = cli_name

            print(f"\n    {cli_label}:")

            if backend_state.role_models:
                for role_name in sorted(backend_state.role_models):
                    model_id = backend_state.role_models[role_name]
                    try:
                        role = role_registry.get(role_name)
                        role_label = role.label
                    except KeyError:
                        role_label = role_name
                    try:
                        model = model_registry.get(model_id)
                        model_label = model.label
                    except KeyError:
                        model_label = model_id
                    print(f"      {role_label:<20} {model_label}")
            else:
                print("      (no role assignments)")


# ── Interactive wizard ───────────────────────────────────────────────────────

def _wizard_role_model(state, before: str) -> bool:
    """Branch 1: interactive role→model reassignment. Returns True if changes were applied."""
    from ..registries.cli_registry import load_registry
    from ..registries.model_registry import load_model_registry
    from ..registries.role_registry import load_role_registry
    from ..services.ui import _safe_input

    scope, project_path, scope_state = _get_scope_state(state)

    cli_registry = load_registry()
    model_registry = load_model_registry()
    role_registry = load_role_registry()

    # Show current
    print("\nCurrent role assignments:")
    for cli_name, backend_state in sorted(scope_state.clis.items()):
        try:
            label = cli_registry.get(cli_name).label
        except KeyError:
            label = cli_name
        print(f"  {label.upper()}:")
        for role_name in sorted(backend_state.role_models):
            model_id = backend_state.role_models[role_name]
            print(f"    {role_name:<20} {model_id}")

    available_ids = model_registry.ids()
    print(f"\nAvailable models: {', '.join(available_ids)}")

    cli_names = list(scope_state.clis.keys())
    if len(cli_names) > 1:
        cli_choice = _safe_input("\nWhich CLI? (claude / opencode / both) [both]: ", "both").strip().lower()
        if cli_choice in ("both", ""):
            target_clis = cli_names
        elif cli_choice in cli_names:
            target_clis = [cli_choice]
        else:
            print(f"Unknown CLI '{cli_choice}'. No changes made.")
            return False
    else:
        target_clis = cli_names

    role_names = role_registry.names()
    role_choice = _safe_input(
        f"Which role? ({'/'.join(role_names)}): ", ""
    ).strip().lower()
    if role_choice not in role_names:
        print(f"Unknown role '{role_choice}'. No changes made.")
        return False

    model_choice = _safe_input(f"New model: ", "").strip()
    if not model_choice:
        print("No model entered. No changes made.")
        return False

    if model_choice not in available_ids:
        print(f"Unknown model '{model_choice}'.")
        print(f"Available: {', '.join(available_ids)}")
        return False

    for cli_name in target_clis:
        scope_state.clis[cli_name].role_models[role_choice] = model_choice
        print(f"Set {cli_name}: {role_choice} -> {model_choice}")

    _apply_and_regenerate(state, before)
    return True


def _wizard_memory(state, before: str) -> bool:
    """Branch 3: interactive memory backend change."""
    from ..services.ui import _safe_input

    options = {
        "1": ("local", "Local markdown files (~/.claude/agent-memory/)"),
        "2": ("obsidian", "Obsidian vault"),
        "3": ("none", "None (disable memory)"),
    }

    print("\nMemory backend options:")
    for key, (_, label) in options.items():
        print(f"  {key}) {label}")

    choice = _safe_input("Choice [1]: ", "1").strip()
    if choice not in options:
        print("Invalid choice. No changes made.")
        return False

    backend, label = options[choice]
    path = ""

    if backend == "obsidian":
        default_path = str(Path.home() / "Documents" / "Obsidian Vault" / "agent-notes")
        path = _safe_input(f"Memory folder path [{default_path}]: ", default_path).strip()
        if not path:
            path = default_path

    state.memory.backend = backend
    state.memory.path = path
    print(f"Memory set to: {label}")
    if path:
        print(f"  Path: {path}")

    _apply_and_regenerate(state, before)
    return True


def _wizard_providers() -> None:
    """Branch 6: interactive API key entry for providers."""
    import getpass
    from ..services import credentials

    print("\nConfigured providers:")
    provider_names = credentials.list_providers()
    if provider_names:
        for name in provider_names:
            configured = credentials.is_configured(name)
            print(f"  {name}  [{'configured' if configured else 'no key'}]")
    else:
        print("  (none)")
    print()

    name = input("Provider name to add/update (e.g. openrouter, anthropic): ").strip()
    if not name:
        return

    if credentials.is_configured(name):
        print(f"  {name} is already configured; entering a new key will replace it.")

    key = getpass.getpass(f"Enter API key for {name} (input hidden): ").strip()
    if not key:
        print("  No key entered, skipping.")
        return

    credentials.set_value(name, "api_key", key)

    base = input(f"Optional base_url for {name} (press enter to skip): ").strip()
    if base:
        credentials.set_value(name, "base_url", base)

    print(f"  Saved. File at {credentials.CONFIG_PATH} (mode 0600).")


def _wizard_provider_status(provider: str) -> None:
    """Print configured/no key for a single provider — never the value."""
    from ..services import credentials

    if credentials.is_configured(provider):
        print(f"{provider}: configured")
    else:
        print(f"{provider}: no key")


def _wizard_skills(state, before: str) -> bool:
    """Branch 4: interactive skill bundle toggle."""
    print("\nSkill bundles are managed during install.")
    print("To change skills, run: agent-notes install --reconfigure")
    print("Or manually copy/remove skill directories from your CLI's skills folder.")
    return False


def interactive_config() -> None:
    """Run the interactive config wizard."""
    from ..services.ui import _safe_input

    state = _load_state()
    before = _state_snapshot(state)

    # Summary header
    show(state)

    print("\nWhat do you want to change?")
    print("  1) Role -> model assignments")
    print("  2) Role -> agent assignments")
    print("  3) Memory backend")
    print("  4) Skill bundles")
    print("  5) Show full configuration (read-only)")
    print("  6) API keys / providers")
    print("  q) Quit")

    try:
        choice = _safe_input("Choice: ", "q").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("\nCancelled.")
        return

    if choice == "1":
        _wizard_role_model(state, before)
    elif choice == "2":
        role_agent("", "")
    elif choice == "3":
        _wizard_memory(state, before)
    elif choice == "4":
        _wizard_skills(state, before)
    elif choice == "5":
        show(state)
    elif choice == "6":
        _wizard_providers()
    elif choice == "q":
        print("Quit.")
    else:
        print(f"Unknown choice '{choice}'. Quit.")


# ── Entry point ──────────────────────────────────────────────────────────────

def config(action: str = "wizard", args: Optional[list] = None, cli_filter: Optional[str] = None) -> None:
    """Dispatch config subcommand."""
    if args is None:
        args = []

    if action == "wizard" or action is None:
        interactive_config()
    elif action == "show":
        show()
    elif action == "role-model":
        # args: [role_name, model_id]
        if len(args) < 2:
            print("Usage: agent-notes config role-model [--cli <cli>] <role> <model>")
            sys.exit(1)
        role_model(args[0], args[1], cli_filter=cli_filter)
    elif action == "role-agent":
        if len(args) < 2:
            print("Usage: agent-notes config role-agent <role> <agent>")
            sys.exit(1)
        role_agent(args[0], args[1], cli_filter=cli_filter)
    elif action == "providers":
        _wizard_providers()
    elif action == "provider":
        # Scriptable: agent-notes config provider <name>  → prints configured/no key
        if len(args) < 1:
            print("Usage: agent-notes config provider <name>")
            sys.exit(1)
        _wizard_provider_status(args[0])
    else:
        print(f"Unknown config action: {action}")
        print("Actions: wizard, show, role-model, role-agent, providers, provider")
        sys.exit(1)
