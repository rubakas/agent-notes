"""Pure TUI widgets: state, render(width, height) -> lines, and
handle(key) -> outcome. None of them touches the terminal; a session paints
what they render and feeds them keys (spec 005)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional, Sequence

from .keys import BACKSPACE, DOWN, ENTER, ESCAPE, LEFT, RIGHT, SPACE, TAB, UP
from .screen import BOLD, CYAN, DIM, YELLOW, Style, bar, elide_middle, fit, pad, visible_len

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
        title = f" {style(self.title, BOLD)}"
        # Cut the context in the middle: its end (project, profile) must show.
        context = elide_middle(self.context, width - visible_len(title) - 2)
        header = bar(title, f"{style(context, DIM)} ", width)
        rule = style("─" * width, DIM)
        notice = [f"   {line}" for line in self.notice]
        if self.message:
            footer = f" {style(self.message, YELLOW)}"
        else:
            status = style(self.status(), DIM) if self.status else ""
            footer = bar(f" {self.hints}", f"{status} ", width)
        room = max(1, height - 4 - len(notice))
        if len(body) > room:
            top = min(max(0, focus_line - room + 1), len(body) - room)
            body = body[top:top + room]
        return [fit(line, width) for line in [header, rule, *body, *notice, rule, footer]]


def _title_bar(style: Style, title: str, width: int, right: str = "") -> list[str]:
    """The title (with *right* at the far end) and a rule: every editor's top."""
    return [bar(f" {style(title, BOLD)}", f"{style(right, DIM)} ", width), style("─" * width, DIM)]


def _hint_bar(style: Style, hints: str, width: int) -> list[str]:
    """A rule and the key hints: every editor's bottom."""
    return [style("─" * width, DIM), f" {hints}"]


def _list_screen(style: Style, width: int, height: int, title: str, lines: list[str],
                cursor: int, hints: str, *, right: str = "", above: Sequence[str] = ()) -> list[str]:
    """A titled list that scrolls to keep line *cursor* on screen, with
    ↑/↓ counts for what is cut off."""
    top = _title_bar(style, title, width, right) + list(above)
    bottom = _hint_bar(style, hints, width)
    room = max(1, height - len(top) - len(bottom))
    count = len(lines)
    body = lines
    if count > room:
        span = max(1, room - 2)  # two lines kept for the ↑/↓ markers
        start = min(max(0, cursor - span // 2), count - span)
        end = start + span
        body = lines[start:end]
        if start > 0:
            body.insert(0, style(f"     ↑ {start} more", DIM))
        if end < count:
            body.append(style(f"     ↓ {count - end} more", DIM))
    return [fit(line, width) for line in top + body + bottom]


@dataclass
class PickItem:
    """One choice: *text* holds the already-formatted columns."""

    value: Any
    text: str
    tag: str = ""
    dim: bool = False


class Picker:
    """Single choice from a list that scrolls inside the screen. ⏎ picks the
    row under the cursor, Esc leaves with nothing picked."""

    def __init__(self, title: str, items: Sequence[PickItem], *, current: Any = None,
                 header: str = "", legend: str = "",
                 hints: str = "↑↓ move   ⏎ select   esc back",
                 style: Optional[Style] = None):
        self.title = title
        self.items = list(items)
        self.header = header
        self.legend = legend
        self.hints = hints
        self.style = style or Style(False)
        values = [item.value for item in self.items]
        self.cursor = values.index(current) if current in values else 0
        self.value: Any = None

    def handle(self, key: str) -> Optional[str]:
        if not self.items:
            return CANCEL if key in (ENTER, ESCAPE) else None
        if key == UP:
            self.cursor = (self.cursor - 1) % len(self.items)
        elif key == DOWN:
            self.cursor = (self.cursor + 1) % len(self.items)
        elif key == ENTER:
            self.value = self.items[self.cursor].value
            return DONE
        elif key == ESCAPE:
            return CANCEL
        return None

    def render(self, width: int, height: int) -> list[str]:
        style = self.style
        lines = []
        for index, item in enumerate(self.items):
            here = index == self.cursor
            text = item.text + (f"  {item.tag}" if item.tag else "")
            if item.dim and not here:
                text = style(text, DIM)
            pointer = style("›", CYAN) if here else " "
            lines.append(f" {pointer} {'●' if here else '○'} {text}")
        above = [style(f"     {self.header}", DIM)] if self.header else []
        return _list_screen(style, width, height, self.title, lines, self.cursor, self.hints,
                           right=self.legend, above=above)


class Checklist:
    """Multiple choice: space toggles, `a` toggles all, ⏎ keeps the selection,
    Esc leaves it unchanged."""

    def __init__(self, title: str, items: Sequence[tuple[str, Any]], selected, *,
                 fixed: Sequence[str] = (),
                 hints: str = "↑↓ move   space toggle   a all   ⏎ done   esc back",
                 style: Optional[Style] = None):
        self.title = title
        self.items = list(items)
        self.selected = set(selected)
        self.fixed = list(fixed)
        self.hints = hints
        self.style = style or Style(False)
        self.cursor = 0
        self.value: Any = None

    def handle(self, key: str) -> Optional[str]:
        values = [value for _, value in self.items]
        if key == UP and values:
            self.cursor = (self.cursor - 1) % len(values)
        elif key == DOWN and values:
            self.cursor = (self.cursor + 1) % len(values)
        elif key == SPACE and values:
            self.selected ^= {values[self.cursor]}
        elif key == "a":
            self.selected = set() if set(values) <= self.selected else set(values)
        elif key == ENTER:
            self.value = set(self.selected)
            return DONE
        elif key == ESCAPE:
            return CANCEL
        return None

    def render(self, width: int, height: int) -> list[str]:
        style = self.style
        lines = []
        for index, (label, value) in enumerate(self.items):
            pointer = style("›", CYAN) if index == self.cursor else " "
            check = "✓" if value in self.selected else " "
            lines.append(f" {pointer} [{check}] {label}")
        above = [style(f"   {line}", DIM) for line in self.fixed]
        return _list_screen(style, width, height, self.title, lines, self.cursor, self.hints,
                           above=above)


class TextField:
    """One line of text. ⏎ accepts — after a *validate* warning, only on the
    second ⏎, so a value can be kept on purpose. Esc leaves it unchanged.
    *secret* shows a fixed placeholder: never the text, nor its length.
    Text longer than the line shows its tail, where the cursor is."""

    SECRET_PLACEHOLDER = "••••••••"

    def __init__(self, title: str, prompt: str, value: str = "", *,
                 notes: Sequence[str] = (),
                 complete: Optional[Callable[[str], str]] = None,
                 validate: Optional[Callable[[str], str]] = None,
                 secret: bool = False, style: Optional[Style] = None):
        self.title = title
        self.prompt = prompt
        self.text = value
        self.notes = list(notes)
        self.complete = complete
        self.validate = validate
        self.secret = secret
        self.style = style or Style(False)
        self.warning = ""
        self.value: Any = None

    def handle(self, key: str) -> Optional[str]:
        if key == ENTER:
            warning = self.validate(self.text) if self.validate else ""
            if warning and warning != self.warning:
                self.warning = warning
                return None
            self.value = self.text
            return DONE
        if key == ESCAPE:
            return CANCEL
        if key == BACKSPACE:
            self.text = self.text[:-1]
        elif key == TAB:
            if self.complete is None:
                return None
            self.text = self.complete(self.text)
        elif key == SPACE:
            self.text += " "
        elif len(key) == 1 and key.isprintable():
            self.text += key
        else:
            return None
        self.warning = ""
        return None

    def render(self, width: int, height: int) -> list[str]:
        style = self.style
        lead = f"   {self.prompt}  "
        if self.secret:
            shown = self.SECRET_PLACEHOLDER if self.text else ""
        else:
            room = max(2, width - visible_len(lead) - 1)   # one column for the cursor
            shown = self.text if len(self.text) <= room else "…" + self.text[-(room - 1):]
        hints = "type   ⏎ ok   esc back" + ("   tab complete" if self.complete else "")
        lines = _title_bar(style, self.title, width) + [f"{lead}{shown}{style('▏', CYAN)}"]
        lines += [style(f"   {note}", DIM) for note in self.notes]
        if self.warning:
            lines.append(style(f"   ⚠ {self.warning} — ⏎ again to keep it", YELLOW))
        lines += _hint_bar(style, hints, width)
        return [fit(line, width) for line in lines[:height]]


def complete_path(text: str) -> str:
    """Tab completion: extend *text* to the longest prefix every matching path
    shares; a single directory match gets its trailing separator. Keeps `~`."""
    import glob
    import os
    expanded = os.path.expanduser(text)
    matches = sorted(glob.glob(glob.escape(expanded) + "*"))
    if not matches:
        return text
    common = os.path.commonprefix(matches)
    if len(matches) == 1 and os.path.isdir(common):
        common += os.sep
    if text.startswith("~"):
        home = os.path.expanduser("~")
        if common.startswith(home):
            common = "~" + common[len(home):]
    return common if len(common) >= len(text) else text
