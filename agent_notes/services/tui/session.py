"""Run widgets: full screen (TuiSession) or numbered prompts (LineSession).

Both expose the same methods, so the install and config rows never need to
know which one they run in (spec 005 FR-025).
"""
from __future__ import annotations

import shutil
import sys
from contextlib import ExitStack
from typing import Any, Optional, Sequence

from .keys import ENTER, ESCAPE, TtyKeys
from .screen import Style, Terminal, color_enabled, pad
from .widgets import CANCEL, DONE, Checklist, PickItem, Picker, ReviewForm, Row, TextField

try:
    import termios  # noqa: F401
    _HAS_TERMIOS = True
except ImportError:  # Windows
    _HAS_TERMIOS = False

MIN_WIDTH, MIN_HEIGHT = 60, 16


class TuiSession:
    """Full screen over a key source and a terminal. Entering it enters both
    (cbreak mode, alternate screen); leaving restores both, also on Ctrl-C."""

    def __init__(self, keys, term, style: Style):
        self.keys, self.term, self.style = keys, term, style
        self._stack: Optional[ExitStack] = None

    def __enter__(self) -> "TuiSession":
        # If the terminal fails to open, the with-block leaves cbreak mode again.
        with ExitStack() as stack:
            for context in (self.keys, self.term):
                if hasattr(context, "__enter__"):
                    stack.enter_context(context)
            self._stack = stack.pop_all()
        return self

    def __exit__(self, *exc) -> bool:
        if self._stack is not None:
            self._stack.close()
        return False

    def _paint(self, widget) -> None:
        width, height = self.term.size()
        self.term.paint(widget.render(width, height))

    def run(self, widget) -> tuple[str, Any]:
        while True:
            self._paint(widget)
            outcome = widget.handle(self.keys.read())
            if outcome in (DONE, CANCEL):
                return outcome, widget.value

    def form(self, form: ReviewForm) -> str:
        form.style = self.style
        return self.run(form)[0]

    def pick(self, title: str, items: Sequence[PickItem], *, current: Any = None,
             header: str = "", legend: str = "") -> Any:
        outcome, value = self.run(Picker(title, items, current=current, header=header,
                                         legend=legend, style=self.style))
        return value if outcome == DONE else None

    def checklist(self, title: str, items, selected, *, fixed: Sequence[str] = ()):
        outcome, value = self.run(Checklist(title, items, selected, fixed=fixed, style=self.style))
        return value if outcome == DONE else None

    def text(self, title: str, prompt: str, value: str = "", *, notes: Sequence[str] = (),
             complete=None, validate=None, secret: bool = False) -> Optional[str]:
        outcome, result = self.run(TextField(title, prompt, value, notes=notes, complete=complete,
                                             validate=validate, secret=secret, style=self.style))
        return result if outcome == DONE else None

    def confirm(self, form: ReviewForm, question: str, lines: Sequence[str] = (), *,
                default: bool = True, quit: bool = False) -> Optional[bool]:
        """⏎ yes, Esc or q no. With *quit*, q returns None: a no that also asks to
        leave (falsy, so callers that don't opt in read it as no)."""
        form.notice = list(lines)
        form.message = f"{question}   ⏎ yes · esc back" + (" · q quit" if quit else "")
        try:
            while True:
                self._paint(form)
                key = self.keys.read()
                if key == ENTER:
                    return True
                if key == ESCAPE:
                    return False
                if key == "q":
                    return None if quit else False
        finally:
            form.notice, form.message = [], ""

    def progress(self, form: ReviewForm, message: str) -> None:
        form.message = message
        self._paint(form)


class LineSession:
    """Numbered prompts, for terminals under MIN_WIDTH×MIN_HEIGHT and systems
    without termios. Editors reuse the existing numbered pickers."""

    def __init__(self, style: Optional[Style] = None):
        self.style = style or Style(color_enabled())

    def __enter__(self) -> "LineSession":
        return self

    def __exit__(self, *exc) -> bool:
        return False

    def _print(self, form: ReviewForm) -> list[Row]:
        numbered: list[Row] = []
        print(f"\n{form.title}   {form.context}".rstrip())
        for row in form.rows():
            values = row.lines() or [""]
            if row.focusable and (row.options or row.edit or row.line_edit):
                numbered.append(row)
                tag = f"{len(numbered):>2})"
            else:
                tag = "   "
            print(f"  {tag} {pad(row.label, ReviewForm.LABEL_WIDTH)} {values[0]}")
            for extra in values[1:]:
                print(" " * (7 + ReviewForm.LABEL_WIDTH) + extra)
        status = form.message or (form.status() if form.status else "")
        if status:
            print(f"  {status}")
        form.message = ""
        return numbered

    def form(self, form: ReviewForm) -> str:
        from ..ui import _safe_input
        form.style = self.style
        while True:
            numbered = self._print(form)
            quit_hint = ", q to quit" if "q" in form.commands else ""
            answer = _safe_input(
                f"Change which? (number, enter to {form.default_label}{quit_hint}): ", ""
            ).strip().lower()
            outcome = None
            if answer == "":
                command = form.commands.get(form.default_command)
                outcome = command() if command else DONE
            elif answer.isdigit() and 1 <= int(answer) <= len(numbered):
                self._change(numbered[int(answer) - 1])
            elif answer in form.commands:
                outcome = form.commands[answer]()
            else:
                form.message = f"no such choice: {answer}"
            if outcome in (DONE, CANCEL):
                return outcome

    def _change(self, row: Row) -> None:
        if row.line_edit is not None:
            row.line_edit()
        elif row.options:
            from ..ui import _radio_select_fallback
            values = [value for _, value in row.options]
            current = row.get() if row.get else None
            default = values.index(current) if current in values else 0
            row.set(_radio_select_fallback(row.label, list(row.options), default=default))
        elif row.edit is not None:
            row.edit()

    def pick(self, title: str, items: Sequence[PickItem], *, current: Any = None,
             header: str = "", legend: str = "") -> Any:
        from ..ui import _radio_select_fallback
        if not items:
            return None
        values = [item.value for item in items]
        default = values.index(current) if current in values else 0
        heading = title + (f"\n     {header}" if header else "")
        options = [(item.text + (f"  {item.tag}" if item.tag else ""), item.value) for item in items]
        return _radio_select_fallback(heading, options, default=default)

    def checklist(self, title: str, items, selected, *, fixed: Sequence[str] = ()):
        from ..ui import _checkbox_select_fallback
        for line in fixed:
            print(f"  {line}")
        return set(_checkbox_select_fallback(title, list(items), defaults=set(selected)))

    def text(self, title: str, prompt: str, value: str = "", *, notes: Sequence[str] = (),
             complete=None, validate=None, secret: bool = False) -> Optional[str]:
        from ..ui import _path_input, _safe_input
        print(f"\n{title}")
        for note in notes:
            print(f"  {note}")
        while True:
            if secret:
                import getpass
                answer = getpass.getpass(f"  {prompt} (input hidden): ")
            else:
                reader = _path_input if complete else _safe_input
                answer = reader(f"  {prompt} [{value}]: ", value)
            warning = validate(answer) if validate else ""
            if not warning:
                return answer
            print(f"  ⚠ {warning}")
            if _safe_input("  Keep it anyway? [y/N]: ", "n").strip().lower() in ("y", "yes"):
                return answer

    def confirm(self, form: ReviewForm, question: str, lines: Sequence[str] = (), *,
                default: bool = True, quit: bool = False) -> Optional[bool]:
        """y or n, or q to leave with *quit* (returns None); an empty answer
        takes *default*, shown capitalised."""
        from ..ui import _safe_input
        for line in lines:
            print(f"  {line}")
        choices = ("[Y/n" if default else "[y/N") + ("/q]" if quit else "]")
        while True:
            answer = _safe_input(f"{question} {choices}: ", "").strip().lower()
            if answer == "":
                return default
            if answer in ("y", "yes"):
                return True
            if answer in ("n", "no"):
                return False
            if answer == "q":
                return None if quit else False
            print("  please answer y, n or q" if quit else "  please answer y or n")

    def progress(self, form: ReviewForm, message: str) -> None:
        print(f"  {message}")


def open_session(stdin=None, stdout=None):
    """The session for this terminal: full screen, line mode, or None when
    stdin or stdout is not a terminal (then nothing may prompt)."""
    stdin = stdin if stdin is not None else sys.stdin
    stdout = stdout if stdout is not None else sys.stdout
    if not (stdin.isatty() and stdout.isatty()):
        return None
    width, height = shutil.get_terminal_size((80, 24))
    if not _HAS_TERMIOS or width < MIN_WIDTH or height < MIN_HEIGHT:
        return LineSession(Style(color_enabled(stdout)))
    return TuiSession(TtyKeys(stdin.fileno()), Terminal(stdout), Style(color_enabled(stdout)))
