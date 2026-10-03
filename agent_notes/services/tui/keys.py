"""Keyboard input for the full-screen TUI: one key name per press.

`decode` turns terminal input into names. `TtyKeys` reads from a terminal in
cbreak mode. Tests replay keys with tests/unit/tui/fakes.py.
"""
from __future__ import annotations

import os
import select
import sys
from typing import Callable, Optional, Protocol

UP, DOWN, LEFT, RIGHT = "up", "down", "left", "right"
ENTER, SPACE, TAB, ESCAPE, BACKSPACE = "enter", "space", "tab", "escape", "backspace"

# How long to wait after ESC for the rest of an escape sequence. Arrow keys
# arrive as one burst (ESC [ A); a bare Esc press is the ESC byte alone.
ESC_TIMEOUT = 0.05

_ARROWS = {"A": UP, "B": DOWN, "C": RIGHT, "D": LEFT}


class KeySource(Protocol):
    def read(self) -> str: ...


def decode(read_char: Callable[[], str], has_more: Callable[[float], bool]) -> str:
    """Read one key press and return its name.

    *read_char* returns the next character; *has_more(timeout)* says whether
    another arrives within *timeout* seconds. An escape sequence we do not
    know returns "" so callers ignore it.
    """
    ch = read_char()
    if ch == "\x1b":
        if not has_more(ESC_TIMEOUT):
            return ESCAPE
        intro = read_char()
        if intro not in ("[", "O"):
            return ESCAPE
        final = read_char() if has_more(ESC_TIMEOUT) else ""
        # Longer CSI sequences (ESC [ 3 ~ for Delete) end on a byte in @..~.
        while final and not ("@" <= final <= "~") and has_more(ESC_TIMEOUT):
            final = read_char()
        return _ARROWS.get(final, "")
    if ch == " ":
        return SPACE
    if ch in ("\r", "\n"):
        return ENTER
    if ch == "\t":
        return TAB
    if ch in ("\x7f", "\x08"):
        return BACKSPACE
    if ch == "\x03":
        raise KeyboardInterrupt
    return ch


def _utf8_length(first: int) -> int:
    if first >= 0xF0:
        return 4
    if first >= 0xE0:
        return 3
    if first >= 0xC0:
        return 2
    return 1


class TtyKeys:
    """Keys from a terminal descriptor. As a context manager it sets cbreak
    mode (no echo, no line buffering; Ctrl-C still raises KeyboardInterrupt)
    and restores the previous mode on exit, exceptions included."""

    def __init__(self, fd: Optional[int] = None):
        self._fd = sys.stdin.fileno() if fd is None else fd
        self._saved = None

    def __enter__(self) -> "TtyKeys":
        import termios
        import tty
        self._saved = termios.tcgetattr(self._fd)
        tty.setcbreak(self._fd)
        return self

    def __exit__(self, *exc) -> bool:
        import termios
        if self._saved is not None:
            # TCSAFLUSH, not TCSADRAIN: on a macOS pty a TCSADRAIN restore kept
            # the cbreak lflags (no echo after exit). It also drops unread keys.
            termios.tcsetattr(self._fd, termios.TCSAFLUSH, self._saved)
            self._saved = None
        return False

    def _read_char(self) -> str:
        first = os.read(self._fd, 1)
        if not first:
            raise EOFError("terminal closed")
        need = _utf8_length(first[0]) - 1
        rest = b""
        while len(rest) < need:
            chunk = os.read(self._fd, need - len(rest))
            if not chunk:
                break
            rest += chunk
        return (first + rest).decode("utf-8", errors="replace")

    def _has_more(self, timeout: float) -> bool:
        ready, _, _ = select.select([self._fd], [], [], timeout)
        return bool(ready)

    def read(self) -> str:
        return decode(self._read_char, self._has_more)
