"""Terminal UI primitives."""

import os
import glob
import sys
import shutil
from pathlib import Path
from typing import List, Tuple, Set

try:
    import tty
    import termios
    _HAS_TTY = True
except ImportError:
    _HAS_TTY = False

# Export for backward compatibility
__all__ = ['Color', 'ok', 'warn', 'fail', 'error', 'info', 'issue', 'linked', 'removed', 'skipped',
           '_safe_input', '_path_input', '_can_interactive',
           '_checkbox_select_fallback', '_radio_select_fallback', '_HAS_TTY']


# --- Colors ---
class Color:
    RED = "\033[0;31m"
    GREEN = "\033[0;32m"
    YELLOW = "\033[0;33m"
    BLUE = "\033[0;34m"
    MAGENTA = "\033[0;35m"
    CYAN = "\033[0;36m"
    WHITE = "\033[0;37m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    NC = "\033[0m"  # No color

    @staticmethod
    def disable():
        """Disable colors (for non-TTY output)."""
        for attr in ("RED", "GREEN", "YELLOW", "BLUE", "MAGENTA", "CYAN", "WHITE", "BOLD", "DIM", "NC"):
            setattr(Color, attr, "")


# Disable colors off a terminal, and whenever NO_COLOR is set (no-color.org).
if not sys.stdout.isatty() or os.environ.get("NO_COLOR"):
    Color.disable()


# --- Output helpers ---
def ok(msg: str, indent: int = 2) -> None:
    print(f"{' ' * indent}{Color.GREEN}OK{Color.NC}   {msg}")


def warn(msg: str, indent: int = 2) -> None:
    print(f"{' ' * indent}{Color.YELLOW}WARN{Color.NC} {msg}")


def fail(msg: str, indent: int = 2) -> None:
    print(f"{' ' * indent}{Color.RED}FAIL{Color.NC} {msg}")


def error(msg: str) -> None:
    print(f"{Color.RED}Error: {msg}{Color.NC}", file=sys.stderr)
    sys.exit(1)


def info(msg: str) -> None:
    print(f"  {Color.GREEN}✓{Color.NC} {msg}")


def issue(msg: str) -> None:
    print(f"  {Color.RED}✗{Color.NC} {msg}")


def linked(path: str) -> None:
    print(f"  {Color.GREEN}LINKED{Color.NC}  {path}")


def removed(path: str) -> None:
    print(f"  {Color.GREEN}REMOVED{Color.NC}  {path}")


def skipped(path: str, reason: str = "not a symlink — remove manually") -> None:
    print(f"  {Color.YELLOW}SKIP{Color.NC}     {path} ({reason})")


# --- TUI primitives ---
def _safe_input(prompt: str, default: str = "") -> str:
    """Safe input that handles EOF and interrupts."""
    try:
        result = input(prompt).strip()
        return result if result else default
    except (KeyboardInterrupt, EOFError):
        print("\nInstallation cancelled.")
        sys.exit(0)


def _path_input(prompt: str, default: str = "") -> str:
    """Input with filesystem tab-completion. Falls back to _safe_input."""
    try:
        import readline
    except ImportError:
        return _safe_input(prompt, default)

    def _path_completer(text: str, state: int):
        expanded = os.path.expanduser(text)
        if os.path.isdir(expanded) and not expanded.endswith(os.sep):
            expanded += os.sep
        matches = glob.glob(expanded + "*")
        dirs = [m + os.sep if os.path.isdir(m) else m for m in matches]
        if text.startswith("~"):
            home = os.path.expanduser("~")
            dirs = ["~" + d[len(home):] for d in dirs]
        return dirs[state] if state < len(dirs) else None

    old_completer = readline.get_completer()
    old_delims = readline.get_completer_delims()
    try:
        readline.set_completer(_path_completer)
        readline.set_completer_delims(" \t\n")
        if "libedit" in getattr(readline, "__doc__", "") or "":
            readline.parse_and_bind("bind ^I rl_complete")
        else:
            readline.parse_and_bind("tab: complete")
        return _safe_input(prompt, default)
    finally:
        readline.set_completer(old_completer)
        readline.set_completer_delims(old_delims)


def _can_interactive() -> bool:
    """Check if interactive TUI is available."""
    return _HAS_TTY and sys.stdin.isatty()


def _checkbox_select_fallback(title: str, options: List[Tuple[str, str]], defaults: Set[str] = None,
                              step: int = 0, total: int = 0, version: str = '') -> Set[str]:
    """Fallback checkbox using numbered input."""
    if defaults is None:
        defaults = {v for _, v in options}

    if step > 0:
        print(f"\n  {Color.BOLD}AgentNotes{Color.NC}{f' {Color.CYAN}v{version}{Color.NC}' if version else ''}  —  Step {step} of {total}\n")

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


def _radio_select_fallback(title: str, options: List[Tuple[str, str]], default: int = 0,
                           step: int = 0, total: int = 0, version: str = ''):
    """Fallback radio using numbered input."""
    if step > 0:
        print(f"\n  {Color.BOLD}AgentNotes{Color.NC}{f' {Color.CYAN}v{version}{Color.NC}' if version else ''}  —  Step {step} of {total}\n")

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