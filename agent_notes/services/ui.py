"""Terminal UI primitives."""

import sys
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
           '_safe_input', '_can_interactive', '_read_key', '_checkbox_select', '_radio_select', 
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


# Disable colors if not a TTY
if not sys.stdout.isatty():
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

    # Number of lines the previous render occupied — used to move up and clear
    # before redrawing. Zero on first render.
    prev_lines = 0

    def render():
        nonlocal prev_lines
        # Erase previous frame: move up prev_lines, then clear each line (K)
        # as we write over it. Using "\r\033[K" per line guarantees any tail
        # residue (e.g. when a new label is shorter than the old one) is wiped.
        if prev_lines:
            sys.stdout.write(f"\033[{prev_lines}A")
        lines = []
        # Title may contain embedded newlines — count them.
        header = f"{title} (↑↓ navigate, space toggle, enter confirm)"
        lines.extend(header.split("\n"))
        lines.append("")  # blank separator
        for i, (label, value) in enumerate(options):
            check = "✓" if value in selected else " "
            pointer = "›" if i == cursor else " "
            lines.append(f"  {pointer} [{check}] {label}")
        lines.append("")  # trailing blank
        for line in lines:
            sys.stdout.write(f"\r\033[K{line}\n")
        sys.stdout.flush()
        prev_lines = len(lines)

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

        render()

    return selected


def _radio_select(title: str, options: List[Tuple[str, str]], default: int = 0):
    """Interactive single-choice selector.

    Args:
        title: Header text (may contain \\n for multi-line titles)
        options: List of (label, value) tuples
        default: Index of default selection

    Returns:
        Selected value
    """
    cursor = default

    if not _can_interactive():
        return options[default][1]

    prev_lines = 0

    def render():
        nonlocal prev_lines
        if prev_lines:
            sys.stdout.write(f"\033[{prev_lines}A")
        lines = []
        header = f"{title} (↑↓ navigate, enter confirm)"
        lines.extend(header.split("\n"))
        lines.append("")
        for i, (label, value) in enumerate(options):
            dot = "●" if i == cursor else "○"
            pointer = "›" if i == cursor else " "
            lines.append(f"  {pointer} {dot} {label}")
        lines.append("")
        for line in lines:
            sys.stdout.write(f"\r\033[K{line}\n")
        sys.stdout.flush()
        prev_lines = len(lines)

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