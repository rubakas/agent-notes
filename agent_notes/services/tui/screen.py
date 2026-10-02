"""Painting and text fitting for the full-screen TUI."""
from __future__ import annotations

import os
import re
import shutil
import sys
from pathlib import Path
from typing import Optional, Sequence, TextIO

_ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")

BOLD, DIM = "1", "2"
RED, GREEN, YELLOW, CYAN = "31", "32", "33", "36"


def color_enabled(stream: Optional[TextIO] = None) -> bool:
    """Color only on a terminal, and never when NO_COLOR is set (no-color.org:
    any non-empty value)."""
    stream = stream if stream is not None else sys.stdout
    if os.environ.get("NO_COLOR"):
        return False
    isatty = getattr(stream, "isatty", None)
    return bool(isatty and isatty())


class Style:
    """Applies SGR codes when enabled; returns the text untouched otherwise."""

    def __init__(self, enabled: bool):
        self.enabled = enabled

    def __call__(self, text: str, *codes: str) -> str:
        codes = tuple(c for c in codes if c)
        if not self.enabled or not codes or not text:
            return text
        return f"\x1b[{';'.join(codes)}m{text}\x1b[0m"


def visible_len(text: str) -> int:
    return len(_ANSI.sub("", text))


def fit(text: str, width: int) -> str:
    """Cut *text* to *width* visible columns, ending in '…' when cut. Escape
    codes are kept and closed, so a cut line never bleeds color."""
    if width <= 0:
        return ""
    if visible_len(text) <= width:
        return text
    out, count, i = [], 0, 0
    while i < len(text) and count < width - 1:
        match = _ANSI.match(text, i)
        if match:
            out.append(match.group())
            i = match.end()
            continue
        out.append(text[i])
        count += 1
        i += 1
    reset = "\x1b[0m" if _ANSI.search(text) else ""
    return "".join(out) + "…" + reset


def pad(text: str, width: int) -> str:
    return text + " " * max(0, width - visible_len(text))


def bar(left: str, right: str, width: int) -> str:
    """*left* and *right* on one line, *width* columns apart."""
    return left + " " * max(1, width - visible_len(left) - visible_len(right)) + right


def tilde(path) -> str:
    text, home = str(path), str(Path.home())
    if text == home:
        return "~"
    if text.startswith(home + os.sep):
        return "~" + text[len(home):]
    return text


def elide_middle(text: str, width: int) -> str:
    if len(text) <= width:
        return text
    if width <= 1:
        return "…"[:width]
    head = (width - 1) // 2
    tail = width - 1 - head
    return text[:head] + "…" + (text[-tail:] if tail else "")


class Terminal:
    """The real terminal: size, alternate screen and hidden cursor while open,
    and paint (clear, then write lines cut to width)."""

    def __init__(self, stream: Optional[TextIO] = None):
        self.stream = stream if stream is not None else sys.stdout

    def __enter__(self) -> "Terminal":
        self.stream.write("\x1b[?1049h\x1b[?25l")
        self.stream.flush()
        return self

    def __exit__(self, *exc) -> bool:
        self.stream.write("\x1b[?25h\x1b[?1049l")
        self.stream.flush()
        return False

    def size(self) -> tuple[int, int]:
        size = shutil.get_terminal_size((80, 24))
        return size.columns, size.lines

    def paint(self, lines: Sequence[str]) -> None:
        width, height = self.size()
        body = "\r\n".join(fit(line, width) for line in list(lines)[:height])
        self.stream.write("\x1b[H\x1b[2J" + body)
        self.stream.flush()
