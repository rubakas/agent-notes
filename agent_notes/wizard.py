"""Interactive install wizard for agent-notes."""

import sys
from pathlib import Path
from typing import List, Dict, Set, Tuple

try:
    import tty
    import termios
    _HAS_TTY = True
except ImportError:
    _HAS_TTY = False

from .config import (
    DIST_CLAUDE_DIR, DIST_OPENCODE_DIR, DIST_GITHUB_DIR, DIST_SKILLS_DIR, DIST_RULES_DIR,
    CLAUDE_HOME, OPENCODE_HOME, GITHUB_HOME, AGENTS_HOME, Color, get_version
)
from .build import build
from .install import (
    place_file, place_dir_contents, install_rules_global, install_rules_local,
    count_agents_claude, count_agents_opencode, count_global, count_skills
)


def _safe_input(prompt: str, default: str = "") -> str:
    """Safe input that handles EOF and interrupts."""
    try:
        result = input(prompt).strip()
        return result if result else default
    except (KeyboardInterrupt, EOFError):
        print("\nInstallation cancelled.")
        sys.exit(0)


def _can_interactive() -> bool:
    """Check if interactive TUI is available."""
    return _HAS_TTY and sys.stdin.isatty()


def _read_key():
    """Read a single keypress."""
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        if ch == '\x1b':  # Escape sequence
            ch2 = sys.stdin.read(1)
            ch3 = sys.stdin.read(1)
            if ch2 == '[':
                if ch3 == 'A': return 'up'
                if ch3 == 'B': return 'down'
            return 'escape'
        if ch == ' ': return 'space'
        if ch in ('\r', '\n'): return 'enter'
        if ch == '\x03': raise KeyboardInterrupt
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def _checkbox_select(title: str, options: List[Tuple[str, str]], defaults: Set[str] = None) -> Set[str]:
    """Interactive checkbox selector.

    Args:
        title: Header text
        options: List of (label, value) tuples
        defaults: Set of values that are pre-selected

    Returns:
        Set of selected values
    """
    if defaults is None:
        defaults = {v for _, v in options}

    selected = set(defaults)
    cursor = 0

    if not _can_interactive():
        return selected

    def render():
        sys.stdout.write(f"\r{title} (↑↓ navigate, space toggle, enter confirm)\n\n")
        for i, (label, value) in enumerate(options):
            check = "✓" if value in selected else " "
            pointer = "›" if i == cursor else " "
            sys.stdout.write(f"  {pointer} [{check}] {label}\n")
        sys.stdout.write(f"\n")
        sys.stdout.flush()

    render()

    while True:
        key = _read_key()

        if key == 'up':
            cursor = (cursor - 1) % len(options)
        elif key == 'down':
            cursor = (cursor + 1) % len(options)
        elif key == 'space':
            value = options[cursor][1]
            if value in selected:
                selected.discard(value)
            else:
                selected.add(value)
        elif key == 'enter':
            return selected
        elif key == 'escape':
            return selected

        lines_to_clear = len(options) + 3
        sys.stdout.write(f"\033[{lines_to_clear}A")
        render()

    return selected


def _radio_select(title: str, options: List[Tuple[str, str]], default: int = 0):
    """Interactive single-choice selector.

    Args:
        title: Header text
        options: List of (label, value) tuples
        default: Index of default selection

    Returns:
        Selected value
    """
    cursor = default

    if not _can_interactive():
        return options[default][1]

    def render():
        sys.stdout.write(f"\r{title} (↑↓ navigate, enter confirm)\n\n")
        for i, (label, value) in enumerate(options):
            dot = "●" if i == cursor else "○"
            pointer = "›" if i == cursor else " "
            sys.stdout.write(f"  {pointer} {dot} {label}\n")
        sys.stdout.write(f"\n")
        sys.stdout.flush()

    render()

    while True:
        key = _read_key()

        if key == 'up':
            cursor = (cursor - 1) % len(options)
        elif key == 'down':
            cursor = (cursor + 1) % len(options)
        elif key == 'enter':
            return options[cursor][1]
        elif key == 'escape':
            return options[cursor][1]

        lines_to_clear = len(options) + 3
        sys.stdout.write(f"\033[{lines_to_clear}A")
        render()


def _checkbox_select_fallback(title: str, options: List[Tuple[str, str]], defaults: Set[str] = None) -> Set[str]:
    """Fallback checkbox using numbered input."""
    if defaults is None:
        defaults = {v for _, v in options}

    print(f"{title}\n")
    for i, (label, value) in enumerate(options, 1):
        marker = "*" if value in defaults else " "
        print(f"  {i}) [{marker}] {label}")
    print(f"\n  Enter numbers to toggle (comma-separated), or press enter for defaults.")

    choice = _safe_input("Choice: ", "").strip()
    if not choice:
        return set(defaults)

    selected = set(defaults)
    for part in choice.split(","):
        try:
            idx = int(part.strip()) - 1
            if 0 <= idx < len(options):
                value = options[idx][1]
                if value in selected:
                    selected.discard(value)
                else:
                    selected.add(value)
        except ValueError:
            continue
    return selected


def _radio_select_fallback(title: str, options: List[Tuple[str, str]], default: int = 0):
    """Fallback radio using numbered input."""
    print(f"{title}\n")
    for i, (label, value) in enumerate(options, 1):
        marker = "*" if i - 1 == default else " "
        print(f"  {i}) {marker} {label}")
    print("")

    choice = _safe_input(f"Choice [{default + 1}]: ", str(default + 1))
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(options):
            return options[idx][1]
    except ValueError:
        pass
    return options[default][1]


def _get_skill_groups() -> Dict[str, List[str]]:
    """Get skill names grouped by technology."""
    if not DIST_SKILLS_DIR.exists():
        return {}

    all_skills = [d.name for d in DIST_SKILLS_DIR.iterdir() if d.is_dir()]

    groups = {
        "Rails": [s for s in all_skills if s.startswith("rails-") and s != "rails-kamal"],
        "Docker": [s for s in all_skills if s.startswith("docker-")],
        "Kamal": [s for s in all_skills if s == "rails-kamal"],
        "Git": [s for s in all_skills if s == "git"]
    }

    return {k: v for k, v in groups.items() if v}


def _count_rules() -> int:
    """Count rule files."""
    if not DIST_RULES_DIR.exists():
        return 0
    return len(list(DIST_RULES_DIR.glob("*.md")))


def _select_cli() -> Set[str]:
    """Step 1: CLI selection."""
    options = [
        ("Claude Code", "claude"),
        ("OpenCode", "opencode"),
    ]
    if _can_interactive():
        result = _checkbox_select("Which CLI do you use?", options, defaults={"claude", "opencode"})
    else:
        result = _checkbox_select_fallback("Which CLI do you use?", options, defaults={"claude", "opencode"})

    labels = [label for label, val in options if val in result]
    print(f"  {Color.GREEN}✓{Color.NC} CLI: {', '.join(labels) if labels else 'None'}")
    return result


def _select_scope() -> str:
    """Step 2: Install scope."""
    options = [
        ("Global (~/.claude, ~/.config/opencode)", "global"),
        ("Local (current project)", "local"),
    ]
    if _can_interactive():
        result = _radio_select("Where to install?", options, default=0)
    else:
        result = _radio_select_fallback("Where to install?", options, default=0)

    label = "Global" if result == "global" else "Local"
    print(f"  {Color.GREEN}✓{Color.NC} Scope: {label}")
    return result


def _select_mode() -> bool:
    """Step 3: Install mode."""
    options = [
        ("Symlink (auto-updates when source changes)", "symlink"),
        ("Copy (standalone, allows local customization)", "copy"),
    ]
    if _can_interactive():
        result = _radio_select("How to install?", options, default=0)
    else:
        result = _radio_select_fallback("How to install?", options, default=0)

    label = "Symlink" if result == "symlink" else "Copy"
    print(f"  {Color.GREEN}✓{Color.NC} Mode: {label}")
    return result == "copy"


def _select_skills() -> List[str]:
    """Step 4: Skill selection."""
    skill_groups = _get_skill_groups()

    if not skill_groups:
        return []

    descriptions = {
        "Rails": "models, controllers, views, routes, testing",
        "Docker": "Dockerfile, Compose patterns",
        "Kamal": "deployment with Kamal",
        "Git": "commit workflow, conventional commits",
    }

    options = []
    for group_name, skills in skill_groups.items():
        desc = descriptions.get(group_name, group_name.lower())
        count = len(skills)
        label = f"{group_name} — {desc} ({count} {'skill' if count == 1 else 'skills'})"
        options.append((label, group_name))

    all_group_names = {name for name in skill_groups.keys()}

    if _can_interactive():
        selected_groups = _checkbox_select("Which skills to include?", options, defaults=all_group_names)
    else:
        selected_groups = _checkbox_select_fallback("Which skills to include?", options, defaults=all_group_names)

    selected_skills = []
    skill_summary_parts = []
    for group_name, skills in skill_groups.items():
        if group_name in selected_groups:
            selected_skills.extend(skills)
            skill_summary_parts.append(f"{group_name} ({len(skills)})")

    summary = ", ".join(skill_summary_parts) if skill_summary_parts else "None"
    print(f"  {Color.GREEN}✓{Color.NC} Skills: {summary}")
    return selected_skills


def _confirm_install(clis: Set[str], scope: str, copy_mode: bool, selected_skills: List[str]) -> bool:
    """Step 5: Confirmation."""
    skill_groups = _get_skill_groups()

    print("\nReady to install:\n")

    # CLI
    if len(clis) == 2:
        cli_desc = "Claude Code + OpenCode"
    elif "claude" in clis:
        cli_desc = "Claude Code"
    else:
        cli_desc = "OpenCode"
    print(f"  CLI:      {cli_desc}")

    # Scope
    if scope == "global":
        scope_desc = "Global (~/.claude, ~/.config/opencode)"
    else:
        scope_desc = "Local (current project)"
    print(f"  Scope:    {scope_desc}")

    # Mode
    mode_desc = "Copy" if copy_mode else "Symlink"
    print(f"  Mode:     {mode_desc}")

    # Skills
    if selected_skills:
        skill_counts = {}
        for group_name, group_skills in skill_groups.items():
            count = sum(1 for skill in selected_skills if skill in group_skills)
            if count > 0:
                skill_counts[group_name] = count

        if skill_counts:
            skill_desc = ", ".join(f"{name} ({count})" for name, count in skill_counts.items())
        else:
            skill_desc = "None"
    else:
        skill_desc = "None"
    print(f"  Skills:   {skill_desc}")

    # Agents
    if "claude" in clis and "opencode" in clis:
        print(f"  Agents:   {count_agents_claude()} (Claude Code) + {count_agents_opencode()} (OpenCode)")
    elif "claude" in clis:
        print(f"  Agents:   {count_agents_claude()} (Claude Code)")
    else:
        print(f"  Agents:   {count_agents_opencode()} (OpenCode)")

    # Config
    config_files = []
    if "claude" in clis:
        config_files.append("CLAUDE.md")
    if "opencode" in clis:
        config_files.append("AGENTS.md")
    config_desc = ", ".join(config_files) if config_files else "None"
    print(f"  Config:   {config_desc}")

    # Rules
    rules_count = _count_rules()
    print(f"  Rules:    {rules_count}")

    print("")
    choice = _safe_input("Proceed? [Y/n]: ", "Y").lower()
    return choice != "n"


def install_skills_filtered(skill_names: List[str], targets: List[Path], copy_mode: bool = False) -> None:
    """Install only specified skills to target directories."""
    if not skill_names or not DIST_SKILLS_DIR.exists():
        return

    for target_dir in targets:
        print(f"Installing skills to {target_dir} ...")
        target_dir.mkdir(parents=True, exist_ok=True)

        for skill_name in sorted(skill_names):
            skill_dir = DIST_SKILLS_DIR / skill_name
            if skill_dir.is_dir():
                place_file(skill_dir, target_dir / skill_name, copy_mode)


def install_agents_filtered(clis: Set[str], scope: str, copy_mode: bool = False) -> None:
    """Install agents for selected CLIs only."""
    if "claude" in clis:
        if scope == "global":
            print("Installing Claude Code agents to ~/.claude/agents/ ...")
            place_dir_contents(DIST_CLAUDE_DIR / "agents", CLAUDE_HOME / "agents", "*.md", copy_mode)
        else:
            print("Installing Claude Code agents to .claude/agents/ ...")
            place_dir_contents(DIST_CLAUDE_DIR / "agents", Path(".claude/agents"), "*.md", copy_mode)

    if "opencode" in clis:
        if scope == "global":
            print("Installing OpenCode agents to ~/.config/opencode/agents/ ...")
            place_dir_contents(DIST_OPENCODE_DIR / "agents", OPENCODE_HOME / "agents", "*.md", copy_mode)
        else:
            print("Installing OpenCode agents to .opencode/agents/ ...")
            place_dir_contents(DIST_OPENCODE_DIR / "agents", Path(".opencode/agents"), "*.md", copy_mode)


def install_config_filtered(clis: Set[str], scope: str, copy_mode: bool = False) -> None:
    """Install config files for selected CLIs only."""
    if scope == "global":
        print("Installing global config ...")

        if "claude" in clis:
            claude_global = DIST_CLAUDE_DIR / "CLAUDE.md"
            if claude_global.exists():
                place_file(claude_global, CLAUDE_HOME / "CLAUDE.md", copy_mode)

            if DIST_RULES_DIR.exists():
                place_dir_contents(DIST_RULES_DIR, CLAUDE_HOME / "rules", "*.md", copy_mode)

            # Copilot → ~/.github/copilot-instructions.md
            copilot_global = DIST_GITHUB_DIR / "copilot-instructions.md"
            if copilot_global.exists():
                place_file(copilot_global, GITHUB_HOME / "copilot-instructions.md", copy_mode)

        if "opencode" in clis:
            agents_global = DIST_OPENCODE_DIR / "AGENTS.md"
            if agents_global.exists():
                place_file(agents_global, OPENCODE_HOME / "AGENTS.md", copy_mode)
    else:
        print("Installing project rules ...")

        if "claude" in clis:
            claude_global = DIST_CLAUDE_DIR / "CLAUDE.md"
            if claude_global.exists():
                place_file(claude_global, Path("./CLAUDE.md"), copy_mode)

            if DIST_RULES_DIR.exists():
                place_dir_contents(DIST_RULES_DIR, Path(".claude/rules"), "*.md", copy_mode)

        if "opencode" in clis:
            agents_global = DIST_OPENCODE_DIR / "AGENTS.md"
            if agents_global.exists():
                place_file(agents_global, Path("./AGENTS.md"), copy_mode)


def interactive_install() -> None:
    """Run the interactive install wizard."""
    # Welcome
    version = get_version()
    n_agents = count_agents_claude()
    n_skills = count_skills()
    n_rules = _count_rules()

    print(f"\n  AgentNotes {Color.CYAN}v{version}{Color.NC}")
    print(f"  AI agent configuration manager for Claude Code and OpenCode.\n")
    print(f"  Includes {n_agents} agents, {n_skills} skills, and {n_rules} rules.\n")

    # Step 1: CLI selection
    clis = _select_cli()

    if not clis:
        print("No CLI selected. Installation cancelled.")
        return

    # Step 2: Install scope
    scope = _select_scope()

    # Step 3: Install mode (always shown)
    copy_mode = _select_mode()

    # Step 4: Skill selection
    selected_skills = _select_skills()

    # Step 5: Confirmation
    if not _confirm_install(clis, scope, copy_mode, selected_skills):
        print("Installation cancelled.")
        return

    # Build first
    print("\nBuilding from source...")
    try:
        build()
    except Exception as e:
        print(f"{Color.RED}Build failed: {e}{Color.NC}")
        return

    # Execute installation
    print(f"\nInstalling ({scope}, {'copy' if copy_mode else 'symlink'}) ...")
    print("")

    # Install skills
    if selected_skills:
        if scope == "global":
            targets = [CLAUDE_HOME / "skills", OPENCODE_HOME / "skills", AGENTS_HOME / "skills"]
            if len(clis) == 1:
                if "claude" in clis:
                    targets = [CLAUDE_HOME / "skills", AGENTS_HOME / "skills"]
                else:
                    targets = [OPENCODE_HOME / "skills", AGENTS_HOME / "skills"]
        else:
            targets = [Path(".claude/skills"), Path(".opencode/skills")]
            if len(clis) == 1:
                if "claude" in clis:
                    targets = [Path(".claude/skills")]
                else:
                    targets = [Path(".opencode/skills")]

        install_skills_filtered(selected_skills, targets, copy_mode)

    # Install agents
    install_agents_filtered(clis, scope, copy_mode)

    # Install config
    install_config_filtered(clis, scope, copy_mode)

    print("")
    print(f"{Color.GREEN}Done.{Color.NC} Restart Claude Code / OpenCode to pick up changes.")
