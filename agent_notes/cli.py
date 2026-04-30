"""CLI entry point with argument parsing."""

import argparse
import sys

from .config import Color


DESCRIPTION = "AgentNotes is a hub for installing AI best-practices (agents, skills, rules) across AI CLIs."

# Pre-colored usage line: "agent-notes <command> [options]"
# - "agent-notes" magenta (violet)
# - "<command>"   cyan (matches the command-name color in the Commands section)
# - "[options]"   green (matches the flag color)
USAGE = (
    f"{Color.MAGENTA}agent-notes{Color.NC} "
    f"{Color.CYAN}<command>{Color.NC} "
    f"{Color.GREEN}[options]{Color.NC}"
)

# Per-command default-behavior hints shown inline next to the description.
# These describe what happens when the command is run with no flags.
COMMAND_DEFAULTS = {
    "install":   "default: interactive wizard",
    "uninstall": "default: global",
    "update":    "default: pull, show diff, ask to apply",
    "doctor":    "default: global scope, read-only",
}

# (command, explanation) pairs — rendered with color in _build_epilog()
EXAMPLES = [
    ("agent-notes install",                    "Interactive wizard (recommended)"),
    ("agent-notes install --local",            "Install into current project (Claude + OpenCode, symlinks)"),
    ("agent-notes install --local --copy",     "Same, but copy files (allows local edits)"),
    ("agent-notes update --dry-run",           "Show what would change, don't apply"),
    ("agent-notes update --only agents --yes", "Apply only agent changes, no prompt"),
    ("agent-notes doctor --fix",               "Check and repair installation"),
    ("agent-notes list agents",                "List all configured agents"),
]


def _heading(label: str) -> str:
    """Section heading — no color (terminal default)."""
    return label


def _colorize_command(cmd: str) -> str:
    """Color a command line with the same scheme as the Usage: line.

    - "agent-notes" → magenta
    - tokens starting with "-" → green (flags, including their values when joined)
    - other tokens → cyan (subcommand names, positional values)
    """
    parts = cmd.split(" ")
    out = []
    for tok in parts:
        if tok == "agent-notes":
            out.append(f"{Color.MAGENTA}{tok}{Color.NC}")
        elif tok.startswith("-"):
            out.append(f"{Color.GREEN}{tok}{Color.NC}")
        else:
            out.append(f"{Color.CYAN}{tok}{Color.NC}")
    return " ".join(out)


def _build_epilog() -> str:
    """Render the Examples section with ANSI colors (auto-stripped on non-TTY)."""
    # Width is based on the visible (uncolored) length so columns align.
    width = max(len(cmd) for cmd, _ in EXAMPLES)
    lines = [_heading("Examples:")]
    for cmd, note in EXAMPLES:
        padding = " " * (width - len(cmd))
        colored = _colorize_command(cmd)
        lines.append(
            f"  {colored}{padding}  {Color.DIM}{note}{Color.NC}"
        )
    return "\n".join(lines)


def _collect_flags(sub_parser: argparse.ArgumentParser) -> list[tuple[str, str, str]]:
    """Extract (flag_string, help_text, default_repr) tuples from a subparser.

    - Skips -h/--help.
    - Joins short/long forms: `-y, --yes`.
    - Positionals become `<name>` or `[{choice1|choice2}]`.
    - default_repr is `(default: X)` for positionals with a non-None default, else "".
    """
    items: list[tuple[str, str, str]] = []
    for action in sub_parser._actions:
        if isinstance(action, argparse._HelpAction):
            continue

        default_repr = ""
        if action.default is not None and action.default is not False and not isinstance(action, argparse._StoreTrueAction):
            # Show default only if it is a real value (not False from store_true).
            default_repr = f"(default: {action.default})"

        if action.option_strings:
            flag = ", ".join(action.option_strings)
            # Show what value the flag accepts (choices or free-form metavar)
            if action.choices:
                flag = f"{flag} {{{','.join(map(str, action.choices))}}}"
            elif action.nargs != 0 and not isinstance(action, argparse._StoreTrueAction) \
                    and not isinstance(action, argparse._StoreFalseAction) \
                    and not isinstance(action, argparse._StoreConstAction):
                metavar = action.metavar or f"<{action.dest}>"
                flag = f"{flag} {metavar}"
            items.append((flag, action.help or "", default_repr))
        else:
            if action.choices:
                name = "{" + "|".join(map(str, action.choices)) + "}"
            else:
                name = f"<{action.dest}>"
            if action.nargs == "?":
                name = f"[{name}]"
            items.append((name, action.help or "", default_repr))
    return items


def _render_commands_section(subparsers_action: argparse._SubParsersAction) -> str:
    """Build the Commands section manually, with per-command flags inlined."""
    lines = [_heading("Commands:")]
    for name, sub in subparsers_action.choices.items():
        help_text = ""
        for action in subparsers_action._choices_actions:
            if action.dest == name:
                help_text = action.help or ""
                break
        default_hint = COMMAND_DEFAULTS.get(name, "")
        suffix = f" {Color.DIM}({default_hint}){Color.NC}" if default_hint else ""
        lines.append(
            f"  {Color.CYAN}{name:<11}{Color.NC} {help_text}{suffix}"
        )
        flags = _collect_flags(sub)
        # Compute per-command flag column width (min 20 for visual rhythm).
        flag_col = max([20, *(len(flag) for flag, _, _ in flags)])
        for flag, flag_help, default_repr in flags:
            default_tail = f" {Color.DIM}{default_repr}{Color.NC}" if default_repr else ""
            padding = " " * (flag_col - len(flag))
            lines.append(
                f"              {Color.GREEN}{flag}{Color.NC}{padding} "
                f"{Color.DIM}{flag_help}{Color.NC}{default_tail}"
            )
        lines.append("")
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)


class _AgentNotesHelp(argparse.RawDescriptionHelpFormatter):
    """Help formatter: plain 'Usage:' prefix and colored global options."""

    def add_usage(self, usage, actions, groups, prefix=None):
        if prefix is None:
            prefix = "Usage: "
        return super().add_usage(usage, actions, groups, prefix)

    def _format_action_invocation(self, action):
        """Colorize -h/--help and -v/--version in green."""
        text = super()._format_action_invocation(action)
        if action.option_strings and any(
            opt in ("-h", "--help", "-v", "--version") for opt in action.option_strings
        ):
            text = f"{Color.GREEN}{text}{Color.NC}"
        return text


class _AgentNotesParser(argparse.ArgumentParser):
    """Parser with custom help layout: description → usage → commands → options → examples."""

    def format_help(self) -> str:
        formatter = self._get_formatter()

        # 1. Description (blue)
        if self.description:
            formatter.add_text(f"{Color.BLUE}{self.description}{Color.NC}")

        # 2. Usage (plain "Usage:" prefix; usage line has its parts colored)
        formatter.add_usage(
            self.usage, self._actions, self._mutually_exclusive_groups,
            prefix="Usage: ",
        )

        # 3. Commands — hand-rolled to show per-command flags
        subparsers_action = next(
            (a for a in self._actions if isinstance(a, argparse._SubParsersAction)),
            None,
        )
        if subparsers_action is not None:
            formatter.add_text(_render_commands_section(subparsers_action))

        # 4. Options (global) — custom heading color
        optional_group = next(
            (g for g in self._action_groups
             if g.title in ("options", "optional arguments") and g._group_actions),
            None,
        )
        if optional_group is not None:
            formatter.start_section(_heading("Options"))
            formatter.add_text(optional_group.description)
            formatter.add_arguments(optional_group._group_actions)
            formatter.end_section()

        # 5. Examples
        formatter.add_text(_build_epilog())

        return formatter.format_help()


def main():
    parser = _AgentNotesParser(
        prog="agent-notes",
        description=DESCRIPTION,
        usage=USAGE,
        formatter_class=_AgentNotesHelp,
    )
    parser.add_argument("-v", "--version", action="store_true", help="Show version")

    subparsers = parser.add_subparsers(
        dest="command",
        title="Commands",
        metavar="",
        parser_class=argparse.ArgumentParser,  # subparsers use default formatting
    )
    
    # install
    p_install = subparsers.add_parser("install", help="Build and install components")
    p_install.add_argument("--local", action="store_true", help="Install to current project")
    p_install.add_argument("--copy", action="store_true", help="Copy instead of symlink (with --local)")
    p_install.add_argument("--reconfigure", action="store_true",
        help="Clear existing state for this scope and re-run the wizard")
    
    # build
    subparsers.add_parser("build", help="Build agent configuration files from source")
    
    # uninstall
    p_uninstall = subparsers.add_parser("uninstall", help="Remove installed components")
    p_uninstall.add_argument("--local", action="store_true", help="Remove from current project")
    
    # update
    p_update = subparsers.add_parser("update", help="Pull latest, show diff, reinstall")
    p_update.add_argument("--dry-run", action="store_true", help="Show diff only, do not reinstall")
    p_update.add_argument("-y", "--yes", action="store_true", help="Skip confirmation prompt")
    p_update.add_argument("--only", action="append", choices=["agents","skills","rules","commands","config","settings"],
        help="Filter diff to these component types (repeatable)")
    p_update.add_argument("--since", help="Override 'before' commit label (cosmetic only for now)")
    p_update.add_argument("--skip-pull", action="store_true", help="Skip git pull")
    
    # doctor
    p_doctor = subparsers.add_parser("doctor", help="Check installation health")
    p_doctor.add_argument("--local", action="store_true", help="Check local installation")
    p_doctor.add_argument("--fix", action="store_true", help="Fix found issues")
    
    # info
    subparsers.add_parser("info", help="Show status and component counts")
    
    # list
    p_list = subparsers.add_parser("list", help="List installed components")
    p_list.add_argument("filter", nargs="?", default="all",
        choices=["agents", "skills", "rules", "clis", "models", "roles", "all"],
        help="Which components to list")
    
    # validate
    subparsers.add_parser("validate", help="Lint source configuration files")
    
    # set
    p_set = subparsers.add_parser("set", help="Configure installation")
    p_set_subparsers = p_set.add_subparsers(dest="entity", help="What to configure")
    p_set_role = p_set_subparsers.add_parser("role", help="Set role→model assignment")
    p_set_role.add_argument("role_name", help="Role name")
    p_set_role.add_argument("model_id", help="Model ID")
    p_set_role.add_argument("--cli", help="Target CLI (auto-detect if omitted)")
    p_set_role.add_argument("--scope", choices=["global", "local"], help="Install scope")
    p_set_role.add_argument("--local", action="store_true", help="Use local scope")
    
    # regenerate 
    p_regen = subparsers.add_parser("regenerate", help="Rebuild files from state")
    p_regen.add_argument("--scope", choices=["global", "local"], help="Install scope")
    p_regen.add_argument("--cli", help="Regenerate specific CLI only")
    p_regen.add_argument("--local", action="store_true", help="Use local scope")
    
    # memory
    p_memory = subparsers.add_parser("memory", help="Manage agent memory")
    p_memory.add_argument("action", nargs="?", default="list",
        choices=["init", "list", "vault", "index", "add", "size", "show", "reset", "export", "import"],
        help="Memory action")
    p_memory.add_argument("name", nargs="?", help="Agent name / note title (for show/reset/add)")
    p_memory.add_argument("extra", nargs="*", help="Additional args (for add: body [type] [agent] [project])")

    # cost-report
    p_cost_report = subparsers.add_parser("cost-report", help="Report token usage and cost for the current AI session")
    p_cost_report.add_argument("--since", help="Only include messages at or after this UTC datetime (ISO 8601)")
    p_cost_report.add_argument("--session", help="Session ID to report on (Claude Code only)")

    # config
    p_config = subparsers.add_parser("config", help="Reconfigure role/agent/model/memory/skill assignments after install")
    p_config.add_argument("action", nargs="?", default="wizard",
        choices=["wizard", "show", "role-model", "role-agent"],
        help="Config action (default: wizard)")
    p_config.add_argument("extra", nargs="*", help="Additional positional args (role, model, agent)")
    p_config.add_argument("--cli", help="Target CLI (claude / opencode / both)")
    
    args = parser.parse_args()
    
    if args.version:
        from .config import get_version
        print(f"agent-notes {get_version()}")
        return
    
    if not args.command:
        parser.print_help()
        return
    
    # Route to modules
    if args.command == "build":
        from .commands.build import build
        build()
    elif args.command == "install":
        if args.local or args.copy:
            from .commands.install import install
            install(local=args.local, copy=args.copy, reconfigure=args.reconfigure)
        else:
            from .commands.wizard import interactive_install
            interactive_install()
    elif args.command == "uninstall":
        from .commands.install import uninstall
        uninstall(local=args.local)
    elif args.command == "update":
        from .commands.update import update
        update(
            dry_run=args.dry_run,
            yes=args.yes,
            only=args.only,
            since=args.since,
            skip_pull=args.skip_pull,
        )
    elif args.command == "doctor":
        from .commands.doctor import doctor
        doctor(local=args.local, fix=args.fix)
    elif args.command == "info":
        from .commands.info import show_info
        show_info()
    elif args.command == "list":
        from .commands.list import list_components
        list_components(args.filter)
    elif args.command == "validate":
        from .commands.validate import validate
        validate()
    elif args.command == "set":
        if args.entity == "role":
            from .commands.set_role import set_role
            set_role(args.role_name, args.model_id, cli=args.cli, scope=args.scope, local=args.local)
    elif args.command == "regenerate":
        from .commands.regenerate import regenerate
        regenerate(scope=args.scope, cli=args.cli, local=args.local)
    elif args.command == "memory":
        from .commands.memory import memory
        memory(args.action, args.name, getattr(args, "extra", None))
    elif args.command == "config":
        from .commands.config import config
        config(action=args.action, args=getattr(args, "extra", None) or [], cli_filter=args.cli)
    elif args.command == "cost-report":
        # Rebuild sys.argv slice so cost_report.main() can parse it normally
        argv = []
        if args.since:
            argv += ["--since", args.since]
        if args.session:
            argv += ["--session", args.session]
        import sys
        old_argv = sys.argv
        sys.argv = ["agent-notes cost-report"] + argv
        try:
            from .scripts.cost_report import main as _cost_report_main
            sys.exit(_cost_report_main())
        finally:
            sys.argv = old_argv

if __name__ == "__main__":
    main()