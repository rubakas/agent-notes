"""Config command — reconfigure role/agent/model/memory/skill assignments after install."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Optional

from ..constants import DEFAULT_VAULT_DIR, DEFAULT_VAULT_NAME, Obsidian


def _load_state():
    """Load state or exit with a clear message."""
    from ..services.state_store import load_state
    st = load_state()
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


def _validate_model(model_id: str, fatal: bool = True):
    """Validate model exists in registry.

    Returns the model, or None when it is unknown and *fatal* is False. The
    scriptable commands exit 1 on an unknown id; the wizard passes fatal=False
    so a typo drops back to the menu instead of killing the session.
    """
    from ..registries.model_registry import load_model_registry
    registry = load_model_registry()
    try:
        return registry.get(model_id)
    except KeyError:
        print(f"Unknown model: {model_id}")
        print(f"Available models: {', '.join(registry.ids())}")
        if fatal:
            sys.exit(1)
        return None


def compatible_models_for(backend) -> list:
    """Models the given CLI backend can serve, in registry order (frontier first).

    The registry is already globally ordered, so this only filters — sorting
    here again would be a second, divergent ordering.

    Shared by the install wizard and `config role-model` so the numbered list a
    user sees is the same one indices are resolved against.
    """
    from ..registries.model_registry import load_model_registry
    models = load_model_registry().all()
    return [m for m in models if backend.first_alias_for(m.aliases) is not None]


MODEL_COLUMNS_HEADER = f"{'model':<28} {'int':>5}  {'coding':>6}  {'$/M in':>8}"


def model_columns(model) -> str:
    """One row of the shared model table: id, intelligence index, coding index,
    USD per 1M INPUT tokens.

    Every model list in the product renders through this one function, so the
    columns cannot drift between `list models`, `config role-model` and the
    install wizard. A missing metric prints an em dash — 0.0 is a real score
    upstream and must stay distinguishable from "not measured".

    Output prices differ from input prices, so the price column is always
    labelled `$/M in` rather than a bare `$`.
    """
    intelligence = "—" if model.intelligence_index is None else f"{model.intelligence_index:.1f}"
    coding = "—" if model.coding_index is None else f"{model.coding_index:.1f}"
    price = "—" if model.price_in is None else f"{model.price_in:.2f}"
    return f"{model.id:<28} {intelligence:>5}  {coding:>6}  {price:>8}"


def _backend_for(cli_name: str):
    """Return the CLI backend descriptor, exit on unknown name."""
    from ..registries.cli_registry import load_registry
    try:
        return load_registry().get(cli_name)
    except KeyError:
        print(f"Unknown CLI '{cli_name}'.")
        sys.exit(1)


def _print_model_choices(cli_name: str) -> None:
    """Print the numbered model list `config role-model` accepts indices against."""
    backend = _backend_for(cli_name)
    models = compatible_models_for(backend)
    print(f"\nModels available for {cli_name}:")
    if not models:
        print("  (none compatible)")
        return
    print(f"  {'#':>2}  {MODEL_COLUMNS_HEADER}")
    for index, model in enumerate(models, 1):
        print(f"  {index:>2}  {model_columns(model)}")


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


def _check_effort_valid(scope_state, cli_name: str, role_name: str, effort: str) -> bool:
    """Check effort against the role's currently-assigned model's provider on
    cli_name. Prints the provider name and its valid effort list on failure.
    Returns True/False — does not exit (callers decide fatal vs. non-fatal).

    NO cross-provider mapping/translation — the value is checked against exactly
    the provider that serves the role's current model, nothing more.
    """
    from ..registries.model_registry import load_model_registry
    from ..registries.cli_registry import load_registry
    from ..registries.provider_registry import load_provider_registry

    model_id = scope_state.clis[cli_name].role_models.get(role_name)
    if not model_id:
        print(f"No model assigned to role '{role_name}' for CLI '{cli_name}'.")
        print("Set a model first with `agent-notes config role-model`.")
        return False

    model_registry = load_model_registry()
    try:
        model = model_registry.get(model_id)
    except KeyError:
        print(f"Unknown model '{model_id}' assigned to role '{role_name}'.")
        return False

    cli_registry = load_registry()
    try:
        backend = cli_registry.get(cli_name)
    except KeyError:
        print(f"Unknown CLI '{cli_name}'.")
        return False

    resolved = backend.first_alias_for(model.aliases)
    if resolved is None:
        print(f"Model '{model_id}' has no compatible provider for CLI '{cli_name}'.")
        return False
    provider_name, _alias = resolved

    provider_registry = load_provider_registry()
    try:
        provider = provider_registry.get(provider_name)
    except KeyError:
        print(f"Provider '{provider_name}' does not support effort configuration.")
        return False

    if effort not in provider.efforts:
        print(f"Invalid effort '{effort}' for provider '{provider_name}'.")
        print(f"Valid efforts for {provider_name}: {', '.join(provider.efforts)}")
        return False

    return True


def _validate_effort(scope_state, cli_name: str, role_name: str, effort: str) -> None:
    """Validate effort, exiting with the printed error on failure."""
    if not _check_effort_valid(scope_state, cli_name, role_name, effort):
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
    from ..services.state_store import record_install_state
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

    record_install_state(state)
    print("State written.")

    # Regenerate
    from .regenerate import regenerate as _regen
    _regen()

    print(f"\n{Color.GREEN}Done.{Color.NC} Restart your AI CLI to pick up changes.")


# ── Scriptable (non-interactive) actions ────────────────────────────────────

def _resolve_index(raw_index: str, target_clis: list) -> str:
    """Resolve a 1-based list index to a model id. Exits on ambiguity or range."""
    if len(target_clis) != 1:
        print("An index is ambiguous: model numbering differs per CLI.")
        print(f"Installed CLIs: {', '.join(target_clis)}")
        print("Re-run with --cli <cli> to pick one.")
        sys.exit(1)

    cli_name = target_clis[0]
    models = compatible_models_for(_backend_for(cli_name))
    index = int(raw_index)
    if not 1 <= index <= len(models):
        print(f"Index {index} out of range for {cli_name}: valid range is 1-{len(models)}.")
        sys.exit(1)

    model_id = models[index - 1].id
    print(f"{index} -> {model_id}")
    return model_id


def _target_clis(scope_state, cli_filter: Optional[str], scope: str,
                 fatal: bool = True) -> Optional[list]:
    """CLIs a role command applies to: one named CLI, or every installed CLI.

    A falsy filter or the literal "both" means all of them. An unknown name is
    never silently widened to "both" — that would write the change to CLIs the
    user did not ask for. It exits 1 for the scriptable commands, or returns
    None when *fatal* is False so the wizard can stay interactive.
    """
    if not cli_filter or cli_filter == "both":
        return list(scope_state.clis.keys())
    if cli_filter not in scope_state.clis:
        print(f"CLI '{cli_filter}' not in {scope} installation.")
        print(f"Installed CLIs: {', '.join(scope_state.clis.keys())}")
        if fatal:
            sys.exit(1)
        return None
    return [cli_filter]


def _prompt_target_clis(scope_state, scope: str, fatal: bool = True) -> Optional[list]:
    """Ask which installed CLI a wizard branch applies to, defaulting to all.

    Thin prompt around _target_clis so the wizard and the scriptable commands
    resolve a CLI choice through exactly one code path.
    """
    from ..services.ui import _safe_input

    cli_names = list(scope_state.clis.keys())
    if len(cli_names) <= 1:
        return cli_names
    prompt = f"\nWhich CLI? ({' / '.join(cli_names)} / both) [both]: "
    cli_choice = _safe_input(prompt, "both").strip().lower()
    return _target_clis(scope_state, cli_choice, scope, fatal=fatal)


def role_model(role_name: str, model_id: Optional[str] = None,
               cli_filter: Optional[str] = None) -> None:
    """Set role→model for one or both CLIs. Validates, diffs, prompts, applies.

    `model_id` may be a model id or a 1-based index into the CLI's model list.
    Omit it to print that list without writing anything.
    """
    state = _load_state()
    before = _state_snapshot(state)

    _validate_role(role_name)

    scope, project_path, scope_state = _get_scope_state(state)

    target_clis = _target_clis(scope_state, cli_filter, scope)

    if model_id is None:
        for cli_name in target_clis:
            _print_model_choices(cli_name)
        print("\nPick one with: agent-notes config role-model "
              f"[--cli <cli>] {role_name} <index|model-id>")
        return

    if re.fullmatch(r"\d+", model_id):
        model_id = _resolve_index(model_id, target_clis)

    _validate_model(model_id)

    for cli_name in target_clis:
        scope_state.clis[cli_name].role_models[role_name] = model_id
        print(f"Set {cli_name}: {role_name} -> {model_id}")

    _apply_and_regenerate(state, before)


def role_effort(role_name: str, effort: str, cli_filter: Optional[str] = None) -> None:
    """Set role→effort for one or both CLIs. Validates against the role's current
    model's provider, diffs, prompts, applies."""
    state = _load_state()
    before = _state_snapshot(state)

    _validate_role(role_name)

    scope, project_path, scope_state = _get_scope_state(state)

    target_clis = _target_clis(scope_state, cli_filter, scope)

    for cli_name in target_clis:
        _validate_effort(scope_state, cli_name, role_name, effort)

    for cli_name in target_clis:
        scope_state.clis[cli_name].role_efforts[role_name] = effort
        print(f"Set {cli_name}: {role_name} -> {effort}")

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
        mem_label = f"Obsidian session ({mem.path})" if mem.path else "Obsidian session"
    elif mem.backend == "local":
        mem_label = "Local markdown"
    else:
        mem_label = "Disabled"

    from ..services.user_config import load_user_config
    from ..registries.plugin_registry import default_plugin_registry
    _ucfg = load_user_config()
    cost_report_enabled = any(
        p.name == "cost-report" for p in default_plugin_registry().enabled(_ucfg)
    )
    cost_report_label = "enabled" if cost_report_enabled else "disabled"

    print("Current configuration:")
    print(f"  Memory:      {mem_label}")
    print(f"  Cost report: {cost_report_label}")

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

            if backend_state.role_efforts:
                print("      Effort:")
                for role_name in sorted(backend_state.role_efforts):
                    effort = backend_state.role_efforts[role_name]
                    try:
                        role = role_registry.get(role_name)
                        role_label = role.label
                    except KeyError:
                        role_label = role_name
                    print(f"      {role_label:<20} {effort}")


# ── Interactive wizard ───────────────────────────────────────────────────────

def _wizard_role_model(state, before: str) -> bool:
    """Branch 1: interactive role→model reassignment. Returns True if changes were applied."""
    from ..registries.cli_registry import load_registry
    from ..registries.role_registry import load_role_registry
    from ..services.ui import _safe_input

    scope, project_path, scope_state = _get_scope_state(state)

    cli_registry = load_registry()
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

    target_clis = _prompt_target_clis(scope_state, scope, fatal=False)
    if target_clis is None:
        print("No changes made.")
        return False

    role_names = role_registry.names()
    role_choice = _safe_input(
        f"Which role? ({'/'.join(role_names)}): ", ""
    ).strip().lower()
    if role_choice not in role_names:
        print(f"Unknown role '{role_choice}'. No changes made.")
        return False

    for cli_name in target_clis:
        _print_model_choices(cli_name)

    model_choice = _safe_input("\nNew model (index or id): ", "").strip()
    if not model_choice:
        print("No model entered. No changes made.")
        return False

    if re.fullmatch(r"\d+", model_choice):
        model_choice = _resolve_index(model_choice, target_clis)
    if _validate_model(model_choice, fatal=False) is None:
        print("No changes made.")
        return False

    for cli_name in target_clis:
        scope_state.clis[cli_name].role_models[role_choice] = model_choice
        print(f"Set {cli_name}: {role_choice} -> {model_choice}")

    _apply_and_regenerate(state, before)
    return True


def _wizard_role_effort(state, before: str) -> bool:
    """Branch 7: interactive role→effort reassignment. Returns True if changes were applied."""
    from ..registries.cli_registry import load_registry
    from ..registries.role_registry import load_role_registry
    from ..services.ui import _safe_input

    scope, project_path, scope_state = _get_scope_state(state)

    cli_registry = load_registry()
    role_registry = load_role_registry()

    # Show current
    print("\nCurrent effort assignments:")
    for cli_name, backend_state in sorted(scope_state.clis.items()):
        try:
            label = cli_registry.get(cli_name).label
        except KeyError:
            label = cli_name
        print(f"  {label.upper()}:")
        for role_name in sorted(backend_state.role_efforts):
            effort = backend_state.role_efforts[role_name]
            print(f"    {role_name:<20} {effort}")

    target_clis = _prompt_target_clis(scope_state, scope, fatal=False)
    if target_clis is None:
        print("No changes made.")
        return False

    role_names = role_registry.names()
    role_choice = _safe_input(
        f"Which role? ({'/'.join(role_names)}): ", ""
    ).strip().lower()
    if role_choice not in role_names:
        print(f"Unknown role '{role_choice}'. No changes made.")
        return False

    effort_choice = _safe_input(f"New effort: ", "").strip().lower()
    if not effort_choice:
        print("No effort entered. No changes made.")
        return False

    for cli_name in target_clis:
        if not _check_effort_valid(scope_state, cli_name, role_choice, effort_choice):
            print("No changes made.")
            return False

    for cli_name in target_clis:
        scope_state.clis[cli_name].role_efforts[role_choice] = effort_choice
        print(f"Set {cli_name}: {role_choice} -> {effort_choice}")

    _apply_and_regenerate(state, before)
    return True


def _wizard_memory(state, before: str) -> bool:
    """Branch 3: interactive memory backend change."""
    from ..services.ui import _safe_input, _path_input

    provider_options = {
        "1": ("local", "default — the CLI's native memory / Claude Code built-in md files"),
        "2": ("obsidian", "external Obsidian vault"),
    }

    print("\nMemory provider options:")
    for key, (_, label) in provider_options.items():
        print(f"  {key}) {label}")

    choice = _safe_input("Choice [1]: ", "1").strip()
    if choice not in provider_options:
        print("Invalid choice. No changes made.")
        return False

    backend, label = provider_options[choice]
    path = ""
    strategy = "single-brain"

    if backend == "obsidian":
        strategy_options = {
            "1": ("single-brain", "one shared vault across all projects"),
            "2": ("per-project", "memory organized per project"),
        }
        print("\nObsidian strategy:")
        for key, (_, slabel) in strategy_options.items():
            print(f"  {key}) {slabel}")
        s_choice = _safe_input("Choice [1]: ", "1").strip()
        if s_choice in strategy_options:
            strategy, _ = strategy_options[s_choice]

        subfolder = Obsidian.SUBFOLDER
        default_vault = str(Path.home() / DEFAULT_VAULT_DIR / DEFAULT_VAULT_NAME)
        print(f"  Folder name: {subfolder}")
        print("  Press Tab to autocomplete paths")
        raw = _path_input(f"  Vault path [{default_vault}]: ", default_vault).strip()
        vault = raw or default_vault
        path = str(Path(vault) / subfolder)
        print(f"  → {path}")

    state.memory.backend = backend
    state.memory.path = path
    state.memory.strategy = strategy
    print(f"Memory set to: {label}")
    if path:
        print(f"  Path: {path}")
    if backend == "obsidian":
        print(f"  Strategy: {strategy}")

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
    print("  3) Memory storage")
    print("  4) Skill bundles")
    print("  5) Show full configuration (read-only)")
    print("  6) API keys / providers")
    print("  7) Role -> effort assignments")
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
    elif choice == "7":
        _wizard_role_effort(state, before)
    elif choice == "q":
        print("Quit.")
    else:
        print(f"Unknown choice '{choice}'. Quit.")


def interactive_config_memory() -> None:
    """Run the interactive memory config wizard."""
    state = _load_state()
    before = _state_snapshot(state)
    _wizard_memory(state, before)


def cost_report_toggle(value: str) -> None:
    """Enable or disable cost reporting via the plugin system."""
    from .plugins import enable_plugin, disable_plugin
    (enable_plugin if value == "on" else disable_plugin)("cost-report")


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
        # args: [role_name] to list, [role_name, model_id_or_index] to set
        if not args:
            print("Usage: agent-notes config role-model [--cli <cli>] <role> [<index>|<model>]")
            sys.exit(1)
        role_model(args[0], args[1] if len(args) > 1 else None, cli_filter=cli_filter)
    elif action == "role-agent":
        if len(args) < 2:
            print("Usage: agent-notes config role-agent <role> <agent>")
            sys.exit(1)
        role_agent(args[0], args[1], cli_filter=cli_filter)
    elif action == "role-effort":
        # args: [role_name, effort]
        if len(args) < 2:
            print("Usage: agent-notes config role-effort [--cli <cli>] <role> <effort>")
            sys.exit(1)
        role_effort(args[0], args[1], cli_filter=cli_filter)
    elif action == "providers":
        _wizard_providers()
    elif action == "provider":
        # Scriptable: agent-notes config provider <name>  → prints configured/no key
        if len(args) < 1:
            print("Usage: agent-notes config provider <name>")
            sys.exit(1)
        _wizard_provider_status(args[0])
    elif action == "memory":
        interactive_config_memory()
    elif action == "cost-report":
        if len(args) != 1 or args[0] not in ("on", "off"):
            print("Usage: agent-notes config cost-report <on|off>")
            sys.exit(1)
        cost_report_toggle(args[0])
    else:
        print(f"Unknown config action: {action}")
        print("Actions: wizard, show, role-model, role-agent, role-effort, providers, provider, memory, cost-report")
        sys.exit(1)
