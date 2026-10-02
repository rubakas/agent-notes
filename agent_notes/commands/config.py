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


def compatible_models_for(backend, registry=None) -> list:
    """Models the given CLI backend can serve, in registry order (frontier first).

    The registry is already globally ordered, so this only filters — sorting
    here again would be a second, divergent ordering.

    Shared by the install review and `config role-model` so the list a user
    sees is the same one indices are resolved against. Pass *registry* to
    reuse one already loaded.
    """
    if registry is None:
        from ..registries.model_registry import load_model_registry
        registry = load_model_registry()
    return [m for m in registry.all() if backend.first_alias_for(m.aliases) is not None]


MODEL_COLUMNS_HEADER = f"{'model':<28} {'int':>5}  {'coding':>6}  {'$/M in':>8}"

PROVISIONAL_MARK = "*"
PROVISIONAL_LEGEND = f"{PROVISIONAL_MARK} provisional score — not yet rated upstream (rules.yaml)"


def model_metrics(model) -> str:
    """The numeric columns of the shared model table: intelligence index,
    coding index, USD per 1M INPUT tokens.

    A missing metric prints an em dash — 0.0 is a real score upstream and must
    stay distinguishable from "not measured". A provisional stand-in from
    rules.yaml prints with a trailing `*` (`78.1*`) so it never reads as a
    benchmark result. Output prices differ from input prices, so the price
    column is always labelled `$/M in`.
    """
    intelligence = "—" if model.intelligence_index is None else f"{model.intelligence_index:.1f}"
    if model.coding_index is not None:
        coding = f"{model.coding_index:.1f}"
    elif model.provisional_coding_index is not None:
        coding = f"{model.provisional_coding_index:.1f}{PROVISIONAL_MARK}"
    else:
        coding = "—"
    price = "—" if model.price_in is None else f"{model.price_in:.2f}"
    return f"{intelligence:>5}  {coding:>6}  {price:>8}"


def model_columns(model) -> str:
    """One row of the shared model table: id, then `model_metrics`. Every
    model list in the product renders through these, so the columns cannot
    drift between `list models`, `config role-model` and the review screen."""
    return f"{model.id:<28} {model_metrics(model)}"


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
    """Check effort for the role's currently-assigned model on cli_name, narrowing
    through three gates in order: the model's own `effort_support` capability, the
    provider's effort vocabulary, then the CLI backend's subset of it (when the
    backend declares one). Prints the offending model, provider or CLI on failure.
    Returns True/False — does not exit (callers decide fatal vs. non-fatal).

    NO cross-provider mapping/translation — the value is checked against exactly
    the provider that serves the role's current model.
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

    # Per-MODEL gate: some models accept no effort setting at all, independently of
    # their provider's vocabulary. Mirrors rendering.py's effort_support check, which
    # would otherwise drop the pin silently at render time.
    if not model.capabilities.get("effort_support", True):
        print(f"Model '{model_id}' does not accept an effort setting.")
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

    # A CLI can accept a strict subset of the provider vocabulary (Codex rejects
    # 'none'); an undeclared list constrains nothing. Mirrors rendering's
    # _constrain_effort_to_backend, which would silently drop the value.
    if backend.efforts and effort not in backend.efforts:
        print(f"Invalid effort '{effort}' for CLI '{cli_name}'.")
        print(f"Valid efforts for {cli_name}: {', '.join(backend.efforts)}")
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
    """Print the current configuration in the config screen's layout (FR-020)."""
    import shutil
    from .config_review import render_show
    from ..services.tui.screen import Style, color_enabled
    if state is None:
        state = _load_state()
    print("Current configuration:")
    # Fit a terminal; piped output stays whole (it is for grep, not a screen).
    width = shutil.get_terminal_size((100, 24)).columns if sys.stdout.isatty() else 10_000
    for line in render_show(state, width, Style(color_enabled())):
        print(line)


# ── Interactive line prompts (config memory, config providers) ───────────────

def _wizard_memory(state, before: str) -> bool:
    """Branch 3: interactive memory backend change."""
    from ..services.ui import _safe_input, _path_input
    from .wizard.review import MEMORY_OPTIONS   # the one name per backend (FR-028)

    provider_options = {str(number): (value, label)
                        for number, (label, value) in enumerate(MEMORY_OPTIONS, 1)}

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


def interactive_config() -> None:
    """`agent-notes config` with no action: the review screen (spec 005)."""
    from .config_review import interactive_config as review
    review()


def interactive_config_memory() -> None:
    """`agent-notes config memory`: choose the memory backend with line prompts."""
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
