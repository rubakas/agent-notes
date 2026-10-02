"""Pure TUI widgets: state, render(width, height) -> lines, and
handle(key) -> outcome. None of them touches the terminal; a session paints
what they render and feeds them keys (spec 005)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional, Sequence

from .keys import DOWN, ENTER, ESCAPE, LEFT, RIGHT, UP
from .screen import BOLD, CYAN, DIM, YELLOW, Style, bar, fit, pad

DONE = "done"
CANCEL = "cancel"


def cycle_text(label: str) -> str:
    return f"‹ {label} ›"


@dataclass
class Row:
    """One labelled line, or block, of a ReviewForm.

    *lines* renders the value column (first line beside the label). A row
    with *options* cycles through them with ←→ through *get*/*set*. A row
    with *edit* opens an editor on ⏎. *line_edit*, when given, replaces the
    default line-mode handling (choose an option, or run *edit*). A row that
    is not *focusable* is dimmed and skipped by the cursor.
    """

    key: str
    label: str
    lines: Callable[[], list[str]]
    options: Sequence[tuple[str, Any]] = ()
    get: Optional[Callable[[], Any]] = None
    set: Optional[Callable[[Any], None]] = None
    edit: Optional[Callable[[], None]] = None
    line_edit: Optional[Callable[[], None]] = None
    focusable: bool = True

    def option_label(self) -> str:
        current = self.get() if self.get else None
        for label, value in self.options:
            if value == current:
                return label
        return "" if current is None else str(current)

    def cycle(self, delta: int) -> None:
        if not self.options or self.get is None or self.set is None:
            return
        values = [value for _, value in self.options]
        try:
            index = values.index(self.get())
        except ValueError:
            index = -1 if delta > 0 else 0
        self.set(values[(index + delta) % len(values)])


class ReviewForm:
    """Labelled rows under one cursor. ↑↓ move, ←→ cycle, ⏎ edit, and
    single-key *commands* run actions; a command returning DONE or CANCEL
    closes the form. Esc closes it only when *escape_closes* (editor forms);
    on the top-level review Esc does nothing (spec 005 FR-004)."""

    LABEL_WIDTH = 13

    def __init__(self, title: str, rows: Callable[[], list[Row]], *,
                 context: str = "",
                 commands: Optional[dict[str, Callable[[], Optional[str]]]] = None,
                 hints: str = "", escape_closes: bool = False,
                 status: Optional[Callable[[], str]] = None,
                 default_command: str = "", default_label: str = "done",
                 style: Optional[Style] = None):
        self.title = title
        self.rows = rows
        self.context = context
        self.commands = dict(commands or {})
        self.hints = hints
        self.escape_closes = escape_closes
        self.status = status
        self.default_command = default_command  # what Enter runs in line mode
        self.default_label = default_label
        self.style = style or Style(False)
        self.focus_key: Optional[str] = None
        self.message = ""
        self.notice: list[str] = []
        self.value: Any = None

    def focusable(self) -> list[Row]:
        return [row for row in self.rows() if row.focusable]

    @property
    def focused(self) -> Optional[Row]:
        rows = self.focusable()
        if not rows:
            return None
        for row in rows:
            if row.key == self.focus_key:
                return row
        self.focus_key = rows[0].key
        return rows[0]

    def _move(self, delta: int) -> None:
        current = self.focused
        if current is None:
            return
        keys = [row.key for row in self.focusable()]
        self.focus_key = keys[(keys.index(current.key) + delta) % len(keys)]

    def handle(self, key: str) -> Optional[str]:
        self.message = ""
        row = self.focused
        if key == UP:
            self._move(-1)
        elif key == DOWN:
            self._move(1)
        elif key in (LEFT, RIGHT) and row is not None:
            row.cycle(-1 if key == LEFT else 1)
        elif key == ENTER and row is not None and row.edit is not None:
            row.edit()
        elif key == ESCAPE:
            return DONE if self.escape_closes else None
        elif key in self.commands:
            return self.commands[key]()
        return None

    def _body(self, show_cursor: bool) -> tuple[list[str], int]:
        style = self.style
        focused = self.focused if show_cursor else None
        body: list[str] = []
        focus_line = 0
        indent = " " * (3 + self.LABEL_WIDTH + 1)
        for row in self.rows():
            values = row.lines() or [""]
            here = focused is not None and row.key == focused.key
            if here:
                focus_line = len(body)
            label = pad(row.label, self.LABEL_WIDTH)
            if not row.focusable:
                label = style(label, DIM)
                values = [style(value, DIM) for value in values]
            marker = style("›", CYAN) if here else " "
            body.append(f" {marker} {label} {values[0]}")
            body.extend(indent + extra for extra in values[1:])
        return body, focus_line

    def render(self, width: int, height: int, *, chrome: bool = True) -> list[str]:
        if not chrome:
            body, _ = self._body(show_cursor=False)
            return [fit(line, width) for line in body]
        style = self.style
        body, focus_line = self._body(show_cursor=True)
        header = bar(f" {style(self.title, BOLD)}", f"{style(self.context, DIM)} ", width)
        rule = style("─" * width, DIM)
        notice = [f"   {line}" for line in self.notice]
        if self.message:
            status = style(self.message, YELLOW)
        else:
            status = style(self.status(), DIM) if self.status else ""
        footer = bar(f" {self.hints}", f"{status} ", width)
        room = max(1, height - 4 - len(notice))
        if len(body) > room:
            top = min(max(0, focus_line - room + 1), len(body) - room)
            body = body[top:top + room]
        return [fit(line, width) for line in [header, rule, *body, *notice, rule, footer]]
