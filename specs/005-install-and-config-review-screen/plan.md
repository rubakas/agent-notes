# Install and Config Review Screen Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the 9-step install wizard and the numbered `config` menu with one pre-filled review screen, shared by `agent-notes install` and `agent-notes config`.

**Architecture:** A small dependency-free TUI package (`agent_notes/services/tui/`) supplies pure widgets — each is state plus `render(width, height) -> list[str]` and `handle(key) -> outcome` — and two sessions that run them: full screen (`TuiSession`) and numbered prompts (`LineSession`). The install flow builds rows from the capability registry and fixed rows, then hands the collected values to the existing build, plan and `_execute_install`. Config mode builds rows over a working copy of `state.json`, stages edits, and saves with one state write and one regenerate.

**Tech Stack:** Python 3.11+, stdlib only (`termios`, `tty`, `select`, `os`); pytest. `pexpect` only for an optional pty smoke test (skipped when not installed).

**Spec:** `specs/005-install-and-config-review-screen/spec.md` — read its "Corrections after approval" section first.

## Global Constraints

- No new runtime dependency: `pyproject.toml` `dependencies` stays `["pyyaml>=6.0", "tomli-w>=1.0.0"]` (FR-029).
- Esc means back/cancel in every editor and picker; it never confirms. A bare Esc is recognized after at most 50 ms (FR-021).
- Color only when stdout is a TTY and `NO_COLOR` is unset or empty (FR-022).
- No rendered line wider than the terminal; paths shown with `~` and elided in the middle (FR-023).
- Interactive flows print no build/regenerate output; one progress line instead (FR-024).
- Memory is named `built-in` or `Obsidian` everywhere (FR-028).
- Minimum full-screen size 60×16; smaller, or no `termios` → line mode (FR-025). No TTY on stdin or stdout → no prompts (FR-026).
- `install --local / --copy / --profile / --folder / --global-home` keep routing to the non-interactive `commands.install.install()` (spec Correction 1).
- Credential values are never rendered, printed or logged (FR-018).
- Every scriptable `agent-notes config <action>` keeps its arguments and behavior, including the interactive `config memory` and `config providers` (FR-019).
- Run tests with `uv run pytest -q` (pytest is not on PATH). Baseline before Task 1: 2241 passed, 15 deselected.
- Commit messages: conventional commits, no `Co-Authored-By` trailer (the repo's `no-ai-attribution` rule).

## Review Focus

The spec's silence on these is not permission to break them. Each line names the task whose tests pin it.

1. **A pinned model that is no longer in the catalog** (state written by an older version) — config shows the raw id with `⚠ unknown model` and the ★ recommendation, never crashes, and `u` replaces it. → Task 12.
2. **Ctrl-C anywhere in the full-screen session** — the terminal's previous mode is restored and the alternate screen left, so the shell is usable. → Task 1 (`TtyKeys`) and Task 6 (session exit).
3. **A terminal narrower than the layout** (resized after the session chose full screen) — lines are cut with `…`, never wrapped. → Task 3.
4. **A local install whose project folder was deleted** — listed as `(missing)`, never chosen automatically. → Task 11.
5. **Non-ASCII or pasted text in a path field** (`~/Документи/vault`, a pasted path) — every character arrives intact. → Task 1 (UTF-8 decode) and Task 5 (`TextField`).

## File Structure

| File | Responsibility |
|---|---|
| `agent_notes/services/tui/__init__.py` | Package marker (empty docstring). |
| `agent_notes/services/tui/keys.py` | Key names, `decode`, `TtyKeys` (cbreak mode, timed Esc, UTF-8). |
| `agent_notes/services/tui/screen.py` | `Style`, `color_enabled`, `visible_len`, `fit`, `pad`, `bar`, `tilde`, `elide_middle`, `Terminal`. |
| `agent_notes/services/tui/widgets.py` | `Row`, `ReviewForm`, `PickItem`, `Picker`, `Checklist`, `TextField`, `complete_path`, outcomes `DONE`/`CANCEL`. |
| `agent_notes/services/tui/session.py` | `TuiSession`, `LineSession`, `open_session`. |
| `agent_notes/commands/wizard/role_models.py` | `Catalog`, `roles_for`, `starred_model`, `initial_model`, `effort_options`, `default_effort`, `recommended_choices`, `set_model`, `model_items`, `role_line`, `edit_models`. |
| `agent_notes/commands/wizard/review.py` | `InstallChoices`, `ReviewContext`, `initial_choices`, `add_cli`/`remove_cli`, fixed rows, `memory_row`, `toggle_row`, `models_row`, `install_rows`. |
| `agent_notes/commands/wizard/orchestrator.py` | Rewritten flow: review → quiet build → confirm → `_execute_install`. |
| `agent_notes/commands/wizard/capabilities.py` | Registers `row` / `config_row` per capability; step runners removed. |
| `agent_notes/commands/wizard/capability_registry.py` | `CapabilityBehaviour(row, config_row, process)`. |
| `agent_notes/commands/config_review.py` | `InstallRef`, `list_installs`, `default_install`, config rows, `describe_changes`, `interactive_config`, `render_show`. |
| `tests/unit/tui/fakes.py` | `FakeStream`, `ScriptedKeys`, `typed`, `FakeTerminal`, `FakeLineInput`. |

Deleted by the end: `agent_notes/commands/wizard/cost_report.py`; from `services/ui.py` `_read_key`, `_checkbox_select`, `_radio_select`, `_render_step_header`, `_render_nav_footer`; from `wizard/__init__.py` every `_select_*`, `_render_install_summary`, `_confirm_install`; from `capabilities.py` the views, `_compute_total_steps` and `collect_*`; from `config.py` `_wizard_role_model`, `_wizard_role_effort`, `_wizard_skills`, `_prompt_target_clis`.

Phases: **A** (Tasks 1–6) adds the TUI package with no behavior change. **B** (Tasks 7–10) switches `install` to the review screen. **C** (Tasks 11–14) switches `config`. Task 15 closes docs and verification. Each phase leaves the suite green and can merge on its own.

---

## Phase A — TUI foundation

### Task 1: Key input (`keys.py`)

**Files:**
- Create: `agent_notes/services/tui/__init__.py`, `agent_notes/services/tui/keys.py`
- Create: `tests/unit/tui/__init__.py`, `tests/unit/tui/fakes.py`
- Test: `tests/unit/tui/test_tui_keys.py`

**Interfaces:**
- Produces: key-name constants `UP, DOWN, LEFT, RIGHT, ENTER, SPACE, TAB, ESCAPE, BACKSPACE`; `ESC_TIMEOUT = 0.05`; `decode(read_char, has_more) -> str`; `class TtyKeys(fd=None)` — context manager, `.read() -> str`; `class KeySource(Protocol)` with `.read() -> str`. Test fakes: `FakeStream(data, pauses=())` with `.read_char()` / `.has_more(timeout)`, `ScriptedKeys(*keys)` with `.read()` and `.consumed`, `typed(text) -> list[str]`.

- [ ] **Step 1: Create the packages and the test fakes**

`agent_notes/services/tui/__init__.py`:

```python
"""Dependency-free terminal UI: keys, screen, widgets, sessions (spec 005)."""
```

`tests/unit/tui/__init__.py`: empty file.

`tests/unit/tui/fakes.py`:

```python
"""Test doubles for the TUI: byte streams, scripted keys, a recording terminal."""
from __future__ import annotations


class FakeStream:
    """Characters for `decode`. `has_more` is False at the end, and at every
    index in *pauses* — a pause the user leaves between two key presses."""

    def __init__(self, data: str, pauses=()):
        self.data = data
        self.pos = 0
        self.pauses = set(pauses)

    def read_char(self) -> str:
        ch = self.data[self.pos]
        self.pos += 1
        return ch

    def has_more(self, timeout: float) -> bool:
        return self.pos < len(self.data) and self.pos not in self.pauses


class ScriptedKeys:
    """Replays key names; running out is a test failure, not a hang."""

    def __init__(self, *keys):
        self._keys = []
        for key in keys:
            self._keys.extend(key if isinstance(key, list) else [key])
        self.consumed = 0

    def read(self) -> str:
        if self.consumed >= len(self._keys):
            raise AssertionError(f"scripted keys exhausted after {self.consumed}: {self._keys}")
        key = self._keys[self.consumed]
        self.consumed += 1
        return key


def typed(text: str) -> list[str]:
    """Key names for typing *text* (a space is the SPACE key)."""
    return ["space" if ch == " " else ch for ch in text]
```

- [ ] **Step 2: Write the failing tests**

`tests/unit/tui/test_tui_keys.py`:

```python
"""Key decoding. The old reader read two more bytes after ESC, so a bare Esc
only registered after two further key presses (spec 005 Investigation)."""
import os
import time

import pytest

from agent_notes.services.tui.keys import (
    BACKSPACE, DOWN, ENTER, ESCAPE, LEFT, RIGHT, SPACE, TAB, UP, TtyKeys, decode,
)
from tests.unit.tui.fakes import FakeStream


def _all(stream: FakeStream) -> list[str]:
    keys = []
    while stream.pos < len(stream.data):
        keys.append(decode(stream.read_char, stream.has_more))
    return keys


def test_arrow_keys():
    assert _all(FakeStream("\x1b[A\x1b[B\x1b[C\x1b[D")) == [UP, DOWN, RIGHT, LEFT]


def test_application_mode_arrows():
    assert _all(FakeStream("\x1bOA\x1bOB")) == [UP, DOWN]


def test_bare_escape_does_not_swallow_the_next_key():
    assert _all(FakeStream("\x1bq", pauses={1})) == [ESCAPE, "q"]


def test_longer_csi_sequences_are_swallowed_whole():
    # ESC [ 3 ~ is Delete: ignored as "", and the "x" after it survives.
    assert _all(FakeStream("\x1b[3~x")) == ["", "x"]


def test_named_keys():
    assert _all(FakeStream(" \r\n\t\x7f")) == [SPACE, ENTER, ENTER, TAB, BACKSPACE]


def test_ctrl_c_raises_keyboard_interrupt():
    stream = FakeStream("\x03")
    with pytest.raises(KeyboardInterrupt):
        decode(stream.read_char, stream.has_more)


def test_printable_and_non_ascii_pass_through():
    assert _all(FakeStream("aЖ/")) == ["a", "Ж", "/"]


def test_bare_escape_on_a_real_descriptor_returns_within_100ms():
    r, w = os.pipe()
    try:
        os.write(w, b"\x1b")
        start = time.monotonic()
        key = TtyKeys(fd=r).read()
        assert key == ESCAPE
        assert time.monotonic() - start < 0.1
    finally:
        os.close(r)
        os.close(w)


def test_multibyte_utf8_arrives_as_one_character():
    r, w = os.pipe()
    try:
        os.write(w, "Ж".encode() + "дорога".encode())
        keys = TtyKeys(fd=r)
        assert [keys.read() for _ in range(7)] == list("Ждорога")
    finally:
        os.close(r)
        os.close(w)


def test_terminal_mode_is_restored_after_ctrl_c():
    import termios
    master, slave = os.openpty()
    try:
        before = termios.tcgetattr(slave)
        with pytest.raises(KeyboardInterrupt):
            with TtyKeys(fd=slave):
                assert termios.tcgetattr(slave) != before  # cbreak applied
                raise KeyboardInterrupt
        assert termios.tcgetattr(slave) == before
    finally:
        os.close(master)
        os.close(slave)
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run pytest -q tests/unit/tui/test_tui_keys.py`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent_notes.services.tui.keys'`.

- [ ] **Step 4: Implement `keys.py`**

`agent_notes/services/tui/keys.py`:

```python
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
            termios.tcsetattr(self._fd, termios.TCSADRAIN, self._saved)
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
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest -q tests/unit/tui/test_tui_keys.py`
Expected: 10 passed.

- [ ] **Step 6: Commit**

```bash
git add agent_notes/services/tui/__init__.py agent_notes/services/tui/keys.py tests/unit/tui/
git commit -m "feat(tui): key reader with timed Esc, arrows and UTF-8"
```

---

### Task 2: Screen helpers and color gating (`screen.py`)

**Files:**
- Create: `agent_notes/services/tui/screen.py`
- Modify: `agent_notes/services/ui.py:44-46` (the `Color.disable()` condition)
- Modify: `tests/unit/tui/fakes.py` (add `FakeTerminal`)
- Test: `tests/unit/tui/test_tui_screen.py`

**Interfaces:**
- Consumes: nothing from Task 1.
- Produces: SGR code constants `BOLD, DIM, RED, GREEN, YELLOW, CYAN`; `color_enabled(stream=None) -> bool`; `class Style(enabled: bool)` — callable `style(text, *codes) -> str`, attribute `.enabled`; `visible_len(text) -> int`; `fit(text, width) -> str`; `pad(text, width) -> str`; `bar(left, right, width) -> str`; `tilde(path) -> str`; `elide_middle(text, width) -> str`; `class Terminal(stream=None)` — context manager (alternate screen, hidden cursor), `.size() -> (cols, rows)`, `.paint(lines)`. Test fake `FakeTerminal(width=80, height=24)` with `.size()`, `.paint(lines)`, `.frames`, `.last`, `.text(frame=-1) -> str`.

- [ ] **Step 1: Add `FakeTerminal` to the fakes**

Append to `tests/unit/tui/fakes.py`:

```python
import re as _re

_ANSI = _re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


class FakeTerminal:
    """Fixed-size terminal that keeps every painted frame, cut to width the way
    Terminal.paint cuts it."""

    def __init__(self, width: int = 80, height: int = 24):
        self.width, self.height = width, height
        self.frames: list[list[str]] = []
        self.entered = self.exited = False

    def __enter__(self):
        self.entered = True
        return self

    def __exit__(self, *exc):
        self.exited = True
        return False

    def size(self):
        return self.width, self.height

    def paint(self, lines):
        from agent_notes.services.tui.screen import fit
        self.frames.append([fit(line, self.width) for line in list(lines)[: self.height]])

    @property
    def last(self) -> list[str]:
        return self.frames[-1]

    def text(self, frame: int = -1) -> str:
        return "\n".join(_ANSI.sub("", line) for line in self.frames[frame])
```

- [ ] **Step 2: Write the failing tests**

`tests/unit/tui/test_tui_screen.py`:

```python
import io
import os
import subprocess
import sys
from pathlib import Path

from agent_notes.services.tui.screen import (
    BOLD, CYAN, Style, Terminal, bar, color_enabled, elide_middle, fit, pad, tilde,
    visible_len,
)


class _TtyStream(io.StringIO):
    def isatty(self):
        return True


def test_color_on_for_a_tty(monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    assert color_enabled(_TtyStream()) is True


def test_no_color_turns_color_off(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    assert color_enabled(_TtyStream()) is False


def test_empty_no_color_does_not_count(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "")
    assert color_enabled(_TtyStream()) is True


def test_color_off_when_not_a_tty(monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    assert color_enabled(io.StringIO()) is False


def test_style_off_returns_text_unchanged():
    assert Style(False)("x", BOLD) == "x"


def test_style_on_wraps_and_resets():
    assert Style(True)("x", BOLD, CYAN) == "\x1b[1;36mx\x1b[0m"


def test_fit_cuts_to_visible_width_and_closes_color():
    out = fit(Style(True)("abcdefghij", CYAN), 5)
    assert visible_len(out) == 5
    assert out.endswith("…\x1b[0m")


def test_fit_leaves_short_text_alone():
    assert fit("abc", 5) == "abc"


def test_pad_counts_visible_characters_only():
    assert visible_len(pad(Style(True)("ab", BOLD), 5)) == 5


def test_bar_fills_to_width():
    assert visible_len(bar(" left", "right ", 30)) == 30


def test_tilde_shortens_home(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert tilde(tmp_path / "x" / "y") == "~/x/y"
    assert tilde(tmp_path) == "~"
    assert tilde("/etc/hosts") == "/etc/hosts"


def test_elide_middle_keeps_both_ends():
    assert elide_middle("abcdefghij", 5) == "ab…ij"
    assert elide_middle("short", 10) == "short"


def test_terminal_paint_never_writes_a_line_wider_than_the_terminal(monkeypatch):
    import shutil
    monkeypatch.setattr(shutil, "get_terminal_size", lambda fallback=None: os.terminal_size((20, 5)))
    stream = io.StringIO()
    Terminal(stream).paint(["x" * 50, "short"])
    painted = stream.getvalue().split("\x1b[2J", 1)[1]
    assert all(visible_len(line) <= 20 for line in painted.split("\r\n"))


def _color_repr(env_extra):
    """Color.RED as seen by a fresh interpreter whose stdout is a real tty."""
    master, slave = os.openpty()
    try:
        env = {k: v for k, v in os.environ.items() if k != "NO_COLOR"}
        env.update(env_extra)
        proc = subprocess.run(
            [sys.executable, "-c",
             "import sys; from agent_notes.services.ui import Color; "
             "sys.stderr.write(repr(Color.RED))"],
            stdout=slave, stderr=subprocess.PIPE, env=env, text=True,
            cwd=str(Path(__file__).resolve().parents[3]),
        )
        return proc.stderr
    finally:
        os.close(master)
        os.close(slave)


def test_ui_color_class_is_on_for_a_tty():
    assert _color_repr({}) != "''"


def test_ui_color_class_honours_no_color():
    assert _color_repr({"NO_COLOR": "1"}) == "''"
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run pytest -q tests/unit/tui/test_tui_screen.py`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent_notes.services.tui.screen'`.

- [ ] **Step 4: Implement `screen.py`**

`agent_notes/services/tui/screen.py`:

```python
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
```

- [ ] **Step 5: Make `services/ui.py` honor `NO_COLOR`**

In `agent_notes/services/ui.py`, replace:

```python
# Disable colors if not a TTY
if not sys.stdout.isatty():
    Color.disable()
```

with:

```python
# Disable colors off a terminal, and whenever NO_COLOR is set (no-color.org).
if not sys.stdout.isatty() or os.environ.get("NO_COLOR"):
    Color.disable()
```

(`os` is already imported at `ui.py:3`.)

- [ ] **Step 6: Run the tests to verify they pass**

Run: `uv run pytest -q tests/unit/tui/`
Expected: all pass (10 + 15).

- [ ] **Step 7: Commit**

```bash
git add agent_notes/services/tui/screen.py agent_notes/services/ui.py tests/unit/tui/
git commit -m "feat(tui): screen helpers; honour NO_COLOR"
```

---

### Task 3: `Row` and `ReviewForm`

**Files:**
- Create: `agent_notes/services/tui/widgets.py`
- Test: `tests/unit/tui/test_tui_review_form.py`

**Interfaces:**
- Consumes: Task 1 key names; Task 2 `Style`, `BOLD`, `DIM`, `CYAN`, `YELLOW`, `fit`, `pad`, `bar`.
- Produces: `DONE = "done"`, `CANCEL = "cancel"`; `cycle_text(label) -> str` (`‹ label ›`); `@dataclass Row(key, label, lines, options=(), get=None, set=None, edit=None, line_edit=None, focusable=True)` with `.cycle(delta)`, `.option_label()`; `class ReviewForm(title, rows, *, context="", commands=None, hints="", escape_closes=False, status=None, default_command="", default_label="done", style=None)` with attributes `.commands` (mutable dict), `.message`, `.notice: list[str]`, `.context`, `.value`, `.style`, property `.focused`, methods `.focusable()`, `.handle(key) -> Optional[str]`, `.render(width, height, *, chrome=True) -> list[str]`; class constant `LABEL_WIDTH = 13`.

- [ ] **Step 1: Write the failing tests**

`tests/unit/tui/test_tui_review_form.py`:

```python
from agent_notes.services.tui.keys import DOWN, ENTER, ESCAPE, LEFT, RIGHT, UP
from agent_notes.services.tui.screen import Style, visible_len
from agent_notes.services.tui.widgets import CANCEL, DONE, ReviewForm, Row, cycle_text


def _form(**kwargs):
    state = {"scope": "global", "edits": 0}

    def rows():
        return [
            Row("clis", "CLIs", lambda: ["Claude Code"],
                edit=lambda: state.__setitem__("edits", state["edits"] + 1)),
            Row("scope", "Scope", lambda: [cycle_text(state["scope"])],
                options=[("global", "global"), ("local", "local")],
                get=lambda: state["scope"], set=lambda v: state.__setitem__("scope", v)),
            Row("info", "Install", lambda: ["read only"], focusable=False),
            Row("models", "Models", lambda: ["reasoner  opus", "worker    sonnet"]),
        ]

    return ReviewForm("AgentNotes 9 · install", rows, context="1 agent",
                      hints="↑↓ move", **kwargs), state


def test_cursor_starts_on_the_first_focusable_row():
    form, _ = _form()
    assert form.focused.key == "clis"


def test_down_skips_rows_that_are_not_focusable_and_wraps():
    form, _ = _form()
    keys = []
    for _ in range(4):
        form.handle(DOWN)
        keys.append(form.focused.key)
    assert keys == ["scope", "models", "clis", "scope"]


def test_up_wraps_to_the_last_row():
    form, _ = _form()
    form.handle(UP)
    assert form.focused.key == "models"


def test_left_right_cycle_the_focused_row():
    form, state = _form()
    form.handle(DOWN)
    form.handle(RIGHT)
    assert state["scope"] == "local"
    form.handle(RIGHT)
    assert state["scope"] == "global"
    form.handle(LEFT)
    assert state["scope"] == "local"


def test_enter_runs_the_row_editor():
    form, state = _form()
    assert form.handle(ENTER) is None
    assert state["edits"] == 1


def test_escape_does_nothing_on_the_top_level_review():
    form, _ = _form()
    assert form.handle(ESCAPE) is None


def test_escape_closes_an_editor_form():
    form, _ = _form(escape_closes=True)
    assert form.handle(ESCAPE) == DONE


def test_commands_return_their_outcome():
    form, _ = _form(commands={"i": lambda: DONE, "q": lambda: CANCEL})
    assert form.handle("i") == DONE
    assert form.handle("q") == CANCEL


def test_a_message_lasts_until_the_next_key():
    form, _ = _form()
    form.message = "select at least one CLI"
    assert "select at least one CLI" in "\n".join(form.render(80, 24))
    form.handle(DOWN)
    assert form.message == ""


def test_render_has_header_rule_rows_and_footer():
    form, _ = _form()
    lines = form.render(60, 24)
    assert "AgentNotes 9 · install" in lines[0] and "1 agent" in lines[0]
    assert set(lines[1]) == {"─"}
    assert lines[2].startswith(" › CLIs")
    assert any("reasoner  opus" in line for line in lines)
    assert any("worker    sonnet" in line for line in lines)
    assert lines[-1].startswith(" ↑↓ move")


def test_no_line_is_wider_than_a_narrow_terminal():
    form, _ = _form()
    form.message = "x" * 200
    assert all(visible_len(line) <= 30 for line in form.render(30, 24))


def test_rows_scroll_to_keep_the_focused_row_visible():
    rows = [Row(f"r{i}", f"Row {i}", lambda i=i: [f"value {i}"]) for i in range(30)]
    form = ReviewForm("T", lambda: rows)
    for _ in range(25):
        form.handle(DOWN)
    lines = form.render(80, 10)
    assert len(lines) <= 10
    assert any("value 25" in line for line in lines)


def test_rows_that_are_not_focusable_are_dimmed():
    form, _ = _form(style=Style(True))
    info = next(line for line in form.render(80, 24) if "read only" in line)
    assert "\x1b[2m" in info


def test_render_without_chrome_is_the_static_rows_only():
    form, _ = _form()
    lines = form.render(80, 24, chrome=False)
    assert lines[0].startswith("   CLIs")
    assert not any("›" in line or "↑↓" in line for line in lines)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest -q tests/unit/tui/test_tui_review_form.py`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent_notes.services.tui.widgets'`.

- [ ] **Step 3: Implement `Row` and `ReviewForm`**

`agent_notes/services/tui/widgets.py`:

```python
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest -q tests/unit/tui/test_tui_review_form.py`
Expected: 14 passed.

- [ ] **Step 5: Commit**

```bash
git add agent_notes/services/tui/widgets.py tests/unit/tui/test_tui_review_form.py
git commit -m "feat(tui): review form with rows, cycling, editors and commands"
```

---
### Task 4: `Picker` (scrolling, annotated single choice)

**Files:**
- Modify: `agent_notes/services/tui/widgets.py` (append)
- Test: `tests/unit/tui/test_tui_picker.py`

**Interfaces:**
- Consumes: Task 3 `DONE`, `CANCEL`; Task 2 `Style`, `bar`, `fit`, `BOLD`, `DIM`, `CYAN`.
- Produces: `@dataclass PickItem(value, text, tag="", dim=False)`; `class Picker(title, items, *, current=None, header="", legend="", hints="↑↓ move   ⏎ select   esc back", style=None)` with `.handle(key)`, `.render(width, height)`, `.value`, `.cursor`.

- [ ] **Step 1: Write the failing tests**

`tests/unit/tui/test_tui_picker.py`:

```python
from agent_notes.services.tui.keys import DOWN, ENTER, ESCAPE, UP
from agent_notes.services.tui.screen import Style
from agent_notes.services.tui.widgets import CANCEL, DONE, PickItem, Picker

ITEMS = [PickItem(f"m{i}", f"model-{i}") for i in range(30)]


def test_cursor_starts_on_the_current_value():
    picker = Picker("Reasoner", ITEMS, current="m5")
    assert picker.handle(ENTER) == DONE
    assert picker.value == "m5"


def test_escape_cancels_without_a_value():
    picker = Picker("Reasoner", ITEMS, current="m5")
    picker.handle(DOWN)
    assert picker.handle(ESCAPE) == CANCEL
    assert picker.value is None


def test_up_from_the_top_wraps_to_the_bottom():
    picker = Picker("Reasoner", ITEMS)
    picker.handle(UP)
    picker.handle(ENTER)
    assert picker.value == "m29"


def test_long_lists_scroll_around_the_cursor():
    lines = Picker("Reasoner", ITEMS, current="m25").render(80, 12)
    assert len(lines) <= 12
    assert any("model-25" in line for line in lines)
    assert any("↑" in line and "more" in line for line in lines)


def test_tags_follow_the_row_text():
    picker = Picker("T", [PickItem("x", "x-text", tag="over budget")])
    assert any("x-text  over budget" in line for line in picker.render(80, 24))


def test_dim_rows_are_dimmed_unless_under_the_cursor():
    items = [PickItem("a", "alpha"), PickItem("b", "beta", tag="deprecated", dim=True)]
    lines = Picker("T", items, style=Style(True)).render(80, 24)
    beta = next(line for line in lines if "beta" in line)
    assert "\x1b[2m" in beta


def test_header_and_legend_are_shown():
    lines = Picker("Reasoner", ITEMS, header="int  coding", legend="★ recommended").render(80, 24)
    assert "★ recommended" in lines[0]
    assert any("int  coding" in line for line in lines[:4])


def test_an_empty_list_can_only_be_left():
    picker = Picker("T", [])
    assert picker.handle(ENTER) == CANCEL
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest -q tests/unit/tui/test_tui_picker.py`
Expected: FAIL — `ImportError: cannot import name 'PickItem'`.

- [ ] **Step 3: Implement `PickItem` and `Picker`**

Append to `agent_notes/services/tui/widgets.py`:

```python
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
        top = [bar(f" {style(self.title, BOLD)}", f"{style(self.legend, DIM)} ", width),
               style("─" * width, DIM)]
        if self.header:
            top.append(style(f"     {self.header}", DIM))
        bottom = [style("─" * width, DIM), f" {self.hints}"]
        room = max(1, height - len(top) - len(bottom))
        count = len(self.items)
        if count <= room:
            start, end = 0, count
        else:
            span = max(1, room - 2)  # two lines kept for the ↑/↓ markers
            start = min(max(0, self.cursor - span // 2), count - span)
            end = start + span
        body = []
        if start > 0:
            body.append(style(f"     ↑ {start} more", DIM))
        for index in range(start, end):
            item = self.items[index]
            here = index == self.cursor
            text = item.text + (f"  {item.tag}" if item.tag else "")
            if item.dim and not here:
                text = style(text, DIM)
            pointer = style("›", CYAN) if here else " "
            body.append(f" {pointer} {'●' if here else '○'} {text}")
        if end < count:
            body.append(style(f"     ↓ {count - end} more", DIM))
        return [fit(line, width) for line in top + body + bottom]
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest -q tests/unit/tui/test_tui_picker.py`
Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add agent_notes/services/tui/widgets.py tests/unit/tui/test_tui_picker.py
git commit -m "feat(tui): scrolling picker with tags and dimmed rows"
```

---

### Task 5: `Checklist`, `TextField`, `complete_path`

**Files:**
- Modify: `agent_notes/services/tui/widgets.py` (append)
- Test: `tests/unit/tui/test_tui_inputs.py`

**Interfaces:**
- Consumes: Task 1 key names (`SPACE`, `TAB`, `BACKSPACE`, …); Task 3 outcomes.
- Produces: `class Checklist(title, items, selected, *, fixed=(), hints=..., style=None)` with `.handle`, `.render`, `.value: set`; `class TextField(title, prompt, value="", *, notes=(), complete=None, validate=None, secret=False, style=None)` with `.text`, `.warning`, `.value`; `complete_path(text) -> str`.

- [ ] **Step 1: Write the failing tests**

`tests/unit/tui/test_tui_inputs.py`:

```python
from agent_notes.services.tui.keys import BACKSPACE, DOWN, ENTER, ESCAPE, SPACE, TAB
from agent_notes.services.tui.widgets import CANCEL, DONE, Checklist, TextField, complete_path
from tests.unit.tui.fakes import typed

SKILLS = [("rails — Rails app conventions", "rails"), ("docker — Dockerfile and Compose", "docker")]


def test_space_toggles_the_row_under_the_cursor():
    checklist = Checklist("Skills", SKILLS, {"rails", "docker"})
    checklist.handle(SPACE)
    assert checklist.handle(ENTER) == DONE
    assert checklist.value == {"docker"}


def test_a_toggles_all_and_none():
    checklist = Checklist("Skills", SKILLS, {"rails"})
    checklist.handle("a")
    assert checklist.selected == {"rails", "docker"}
    checklist.handle("a")
    assert checklist.selected == set()


def test_escape_leaves_the_selection_unchanged():
    checklist = Checklist("Skills", SKILLS, {"rails"})
    checklist.handle(DOWN)
    checklist.handle(SPACE)
    assert checklist.handle(ESCAPE) == CANCEL
    assert checklist.value is None


def test_fixed_lines_are_shown_above_the_choices():
    lines = Checklist("Skills", SKILLS, set(), fixed=["process (21) — always included"]).render(80, 24)
    assert any("process (21) — always included" in line for line in lines)
    assert any("[ ] rails — Rails app conventions" in line for line in lines)


def test_typing_editing_and_unicode():
    field = TextField("Vault", "Path", "")
    for key in typed("~/Док x") + [BACKSPACE, BACKSPACE]:
        field.handle(key)
    assert field.handle(ENTER) == DONE
    assert field.value == "~/Док"


def test_a_warning_needs_a_second_enter_to_keep_the_value():
    field = TextField("Vault", "Path", "/nope", validate=lambda text: "not a vault")
    assert field.handle(ENTER) is None
    assert "not a vault" in "\n".join(field.render(80, 24))
    assert field.handle(ENTER) == DONE
    assert field.value == "/nope"


def test_editing_clears_the_warning():
    field = TextField("Vault", "Path", "/nope", validate=lambda text: "not a vault" if "nope" in text else "")
    field.handle(ENTER)
    field.handle(BACKSPACE)
    assert field.warning == ""


def test_escape_cancels_the_edit():
    field = TextField("Vault", "Path", "keep")
    field.handle("x")
    assert field.handle(ESCAPE) == CANCEL
    assert field.value is None


def test_secret_text_is_never_rendered():
    field = TextField("API key", "Key", secret=True)
    frames = []
    for key in typed("sk-secret-123"):
        field.handle(key)
        frames.append("\n".join(field.render(80, 24)))
    assert all("secret" not in frame for frame in frames)
    assert "•" * len("sk-secret-123") in frames[-1]


def test_tab_runs_the_completer():
    field = TextField("Vault", "Path", "~/Ob", complete=lambda text: text + "sidian/")
    field.handle(TAB)
    assert field.text == "~/Obsidian/"


def test_complete_path_extends_to_a_unique_directory(tmp_path):
    (tmp_path / "Obsidian").mkdir()
    assert complete_path(str(tmp_path / "Obs")) == str(tmp_path / "Obsidian") + "/"


def test_complete_path_stops_at_the_common_prefix(tmp_path):
    (tmp_path / "vault-a").mkdir()
    (tmp_path / "vault-b").mkdir()
    assert complete_path(str(tmp_path / "va")) == str(tmp_path / "vault-")


def test_complete_path_keeps_a_tilde(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / "Documents").mkdir()
    assert complete_path("~/Doc") == "~/Documents/"


def test_complete_path_without_a_match_changes_nothing(tmp_path):
    assert complete_path(str(tmp_path / "zzz")) == str(tmp_path / "zzz")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest -q tests/unit/tui/test_tui_inputs.py`
Expected: FAIL — `ImportError: cannot import name 'Checklist'`.

- [ ] **Step 3: Implement**

Append to `agent_notes/services/tui/widgets.py` (add `SPACE, TAB, BACKSPACE` to the `.keys` import at the top):

```python
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
        lines = [bar(f" {style(self.title, BOLD)}", "", width), style("─" * width, DIM)]
        lines += [style(f"   {line}", DIM) for line in self.fixed]
        for index, (label, value) in enumerate(self.items):
            pointer = style("›", CYAN) if index == self.cursor else " "
            check = "✓" if value in self.selected else " "
            lines.append(f" {pointer} [{check}] {label}")
        lines += [style("─" * width, DIM), f" {self.hints}"]
        return [fit(line, width) for line in lines[:height]]


class TextField:
    """One line of text. ⏎ accepts — after a *validate* warning, only on the
    second ⏎, so a value can be kept on purpose. Esc leaves it unchanged.
    *secret* shows bullets and never the text."""

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
        shown = "•" * len(self.text) if self.secret else self.text
        hints = "type   ⏎ ok   esc back" + ("   tab complete" if self.complete else "")
        lines = [bar(f" {style(self.title, BOLD)}", "", width), style("─" * width, DIM),
                 f"   {self.prompt}  {shown}{style('▏', CYAN)}"]
        lines += [style(f"   {note}", DIM) for note in self.notes]
        if self.warning:
            lines.append(style(f"   ⚠ {self.warning} — ⏎ again to keep it", YELLOW))
        lines += [style("─" * width, DIM), f" {hints}"]
        return [fit(line, width) for line in lines[:height]]


def complete_path(text: str) -> str:
    """Tab completion: extend *text* to the longest prefix every matching path
    shares; a single directory match gets its trailing separator. Keeps `~`."""
    import glob
    import os
    expanded = os.path.expanduser(text)
    matches = sorted(glob.glob(expanded + "*"))
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest -q tests/unit/tui/test_tui_inputs.py`
Expected: 14 passed.

- [ ] **Step 5: Commit**

```bash
git add agent_notes/services/tui/widgets.py tests/unit/tui/test_tui_inputs.py
git commit -m "feat(tui): checklist, text field with validation, path completion"
```

---

### Task 6: Sessions (`TuiSession`, `LineSession`, `open_session`)

**Files:**
- Create: `agent_notes/services/tui/session.py`
- Modify: `tests/unit/tui/fakes.py` (add `FakeLineInput`, `tui_session`)
- Test: `tests/unit/tui/test_tui_session.py`

**Interfaces:**
- Consumes: Tasks 1–5.
- Produces: `MIN_WIDTH = 60`, `MIN_HEIGHT = 16`; `class TuiSession(keys, term, style)` and `class LineSession(style=None)`, both context managers with attribute `.style` and methods `form(form) -> str` (DONE/CANCEL), `pick(title, items, *, current=None, header="", legend="") -> value|None`, `checklist(title, items, selected, *, fixed=()) -> set|None`, `text(title, prompt, value="", *, notes=(), complete=None, validate=None, secret=False) -> str|None`, `confirm(form, question, lines=()) -> bool`, `progress(form, message) -> None`; `open_session(stdin=None, stdout=None) -> TuiSession | LineSession | None`. Fakes: `FakeLineInput(*answers)` — callable `(prompt, default="") -> str` recording `.prompts`; `tui_session(*keys, width=80, height=24) -> TuiSession` over `ScriptedKeys` + `FakeTerminal`.

- [ ] **Step 1: Add the session fakes**

Append to `tests/unit/tui/fakes.py`:

```python
class FakeLineInput:
    """Stands in for services.ui._safe_input / _path_input: returns the next
    scripted answer (the default when an answer is None)."""

    def __init__(self, *answers):
        self.answers = list(answers)
        self.prompts: list[str] = []

    def __call__(self, prompt: str, default: str = "") -> str:
        self.prompts.append(prompt)
        if not self.answers:
            raise AssertionError(f"no scripted answer for prompt {prompt!r}")
        answer = self.answers.pop(0)
        return default if answer is None else answer


def tui_session(*keys, width: int = 80, height: int = 24):
    from agent_notes.services.tui.screen import Style
    from agent_notes.services.tui.session import TuiSession
    return TuiSession(ScriptedKeys(*keys), FakeTerminal(width, height), Style(False))
```

- [ ] **Step 2: Write the failing tests**

`tests/unit/tui/test_tui_session.py`:

```python
import io
import os

import pytest

from agent_notes.services.tui import session as session_mod
from agent_notes.services.tui.keys import DOWN, ENTER, ESCAPE, RIGHT, SPACE
from agent_notes.services.tui.session import LineSession, TuiSession, open_session
from agent_notes.services.tui.widgets import CANCEL, DONE, PickItem, ReviewForm, Row, cycle_text
from tests.unit.tui.fakes import FakeLineInput, FakeTerminal, ScriptedKeys, tui_session, typed


class _Tty(io.StringIO):
    def isatty(self):
        return True

    def fileno(self):
        return 0


def _size(monkeypatch, cols, rows):
    monkeypatch.setattr(session_mod.shutil, "get_terminal_size",
                        lambda fallback=None: os.terminal_size((cols, rows)))


def test_no_terminal_means_no_session():
    assert open_session(io.StringIO(), _Tty()) is None
    assert open_session(_Tty(), io.StringIO()) is None


def test_a_small_terminal_gets_line_mode(monkeypatch):
    _size(monkeypatch, 59, 30)
    assert isinstance(open_session(_Tty(), _Tty()), LineSession)
    _size(monkeypatch, 100, 15)
    assert isinstance(open_session(_Tty(), _Tty()), LineSession)


def test_no_termios_gets_line_mode(monkeypatch):
    _size(monkeypatch, 100, 40)
    monkeypatch.setattr(session_mod, "_HAS_TERMIOS", False)
    assert isinstance(open_session(_Tty(), _Tty()), LineSession)


def test_a_big_enough_terminal_gets_full_screen(monkeypatch):
    _size(monkeypatch, 80, 24)
    assert isinstance(open_session(_Tty(), _Tty()), TuiSession)


def test_pick_returns_the_chosen_value_or_none():
    items = [PickItem("a", "alpha"), PickItem("b", "beta")]
    assert tui_session(DOWN, ENTER).pick("T", items) == "b"
    assert tui_session(ESCAPE).pick("T", items, current="b") is None


def test_checklist_and_text():
    assert tui_session(SPACE, ENTER).checklist("T", [("x", "x")], set()) == {"x"}
    assert tui_session(*typed("work"), ENTER).text("Profile", "Label") == "work"
    assert tui_session(ESCAPE).text("Profile", "Label", "keep") is None


def test_confirm_shows_the_question_and_clears_it_after():
    form = ReviewForm("T", lambda: [Row("a", "A", lambda: ["x"])])
    ui = tui_session(ENTER)
    assert ui.confirm(form, "Install 3 files?", ["backup a → b"]) is True
    shown = ui.term.text()
    assert "Install 3 files?   ⏎ yes · esc back" in shown and "backup a → b" in shown
    assert form.message == "" and form.notice == []
    assert tui_session(ESCAPE).confirm(form, "Install?") is False


def test_form_runs_until_a_command_closes_it():
    form = ReviewForm("T", lambda: [Row("a", "A", lambda: ["x"])], commands={"i": lambda: DONE})
    assert tui_session(DOWN, "i").form(form) == DONE


def test_ctrl_c_still_restores_the_terminal():
    class _Interrupting(ScriptedKeys):
        entered = exited = False

        def __enter__(self):
            self.entered = True
            return self

        def __exit__(self, *exc):
            self.exited = True
            return False

        def read(self):
            raise KeyboardInterrupt

    keys, term = _Interrupting(), FakeTerminal()
    form = ReviewForm("T", lambda: [Row("a", "A", lambda: ["x"])])
    from agent_notes.services.tui.screen import Style
    with pytest.raises(KeyboardInterrupt):
        with TuiSession(keys, term, Style(False)) as ui:
            ui.form(form)
    assert keys.exited and term.exited


def test_line_mode_numbers_rows_and_runs_the_default_command(monkeypatch, capsys):
    state = {"scope": "global"}
    form = ReviewForm("AgentNotes · install", lambda: [
        Row("scope", "Scope", lambda: [cycle_text(state["scope"])],
            options=[("global", "global"), ("local", "local")],
            get=lambda: state["scope"], set=lambda v: state.__setitem__("scope", v)),
        Row("info", "Install", lambda: ["read only"], focusable=False),
    ], commands={"i": lambda: DONE, "q": lambda: CANCEL},
        default_command="i", default_label="install")
    answers = FakeLineInput("1", "")
    monkeypatch.setattr("agent_notes.services.ui._safe_input", answers)
    monkeypatch.setattr("agent_notes.services.ui._radio_select_fallback",
                        lambda title, options, default=0, **kw: "local")
    assert LineSession().form(form) == DONE
    assert state["scope"] == "local"
    printed = capsys.readouterr().out
    assert " 1) Scope" in printed and "    Install" in printed
    assert answers.prompts[0] == "Change which? (number, enter to install, q to quit): "


@pytest.mark.parametrize("answer, expected", [
    ("", True), ("y", True), ("yes", True), ("Y", True),
    ("n", False), ("no", False), ("N", False), ("NO", False), (" n ", False),
])
def test_line_mode_confirm_defaults_to_yes(monkeypatch, answer, expected):
    form = ReviewForm("T", lambda: [])
    monkeypatch.setattr("agent_notes.services.ui._safe_input",
                        lambda prompt, default="": (answer.strip() or default))
    assert LineSession().confirm(form, "Install 3 files?") is expected
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run pytest -q tests/unit/tui/test_tui_session.py`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent_notes.services.tui.session'`.

- [ ] **Step 4: Implement `session.py`**

`agent_notes/services/tui/session.py`:

```python
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
        self._stack = ExitStack()
        for context in (self.keys, self.term):
            if hasattr(context, "__enter__"):
                self._stack.enter_context(context)
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

    def confirm(self, form: ReviewForm, question: str, lines: Sequence[str] = ()) -> bool:
        """Ask on the form's own screen: ⏎ yes, Esc no."""
        form.notice, form.message = list(lines), f"{question}   ⏎ yes · esc back"
        try:
            while True:
                self._paint(form)
                key = self.keys.read()
                if key == ENTER:
                    return True
                if key == ESCAPE:
                    return False
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

    def confirm(self, form: ReviewForm, question: str, lines: Sequence[str] = ()) -> bool:
        from ..ui import _safe_input
        for line in lines:
            print(f"  {line}")
        return _safe_input(f"{question} [Y/n]: ", "Y").strip().lower() not in ("n", "no")

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
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest -q tests/unit/tui/`
Expected: all TUI tests pass (10 + 15 + 14 + 8 + 14 + 19 = 80).

- [ ] **Step 6: Run the whole suite — Phase A changes nothing outside the new package and `NO_COLOR`**

Run: `uv run pytest -q`
Expected: 2321 passed (2241 + 80), 15 deselected.

- [ ] **Step 7: Commit**

```bash
git add agent_notes/services/tui/session.py tests/unit/tui/
git commit -m "feat(tui): full-screen and line-mode sessions"
```

---

## Phase B — Install review screen

### Task 7: Role models — recommendations, effort options, Models editor

**Files:**
- Create: `agent_notes/commands/wizard/role_models.py`
- Modify: `agent_notes/commands/config.py:67-99` (`compatible_models_for` gains a `registry` parameter; `model_columns` split into `model_metrics`)
- Test: `tests/unit/commands/test_review_role_models.py`

**Interfaces:**
- Consumes: Task 6 `TuiSession`/`LineSession` (`ui.pick`, `ui.form`, `ui.style`); Task 3 `ReviewForm`, `Row`, `cycle_text`; Task 4 `PickItem`; existing `_default_model_for_role`, `_effort_provider_for_model`, `_effort_default_choice` (stay in `wizard/__init__.py`), `select_model_for_role`, `_role_sort_key`.
- Produces: `class Catalog(registry=None)` with `.registry`, `.compatible(backend) -> list[Model]`, `.get(model_id) -> Model | None`; `roles_for(backend) -> list[Role]`; `budget_text(role) -> str`; `starred_model(catalog, backend, role) -> Model | None`; `initial_model(catalog, backend, role) -> Model | None`; `effort_options(backend, model) -> list[str]`; `default_effort(backend, model, role) -> str | None`; `recommended_choices(catalog, backend) -> (dict, dict)`; `set_model(catalog, backend, role, model_id, models, efforts)`; `reset_role(catalog, backend, role, models, efforts)`; `model_items(catalog, backend, role) -> list[PickItem]`; `role_line(role, models, efforts) -> str`; `edit_models(ui, catalog, backend, models, efforts)`; constants `PICKER_HEADER`, `PICKER_LEGEND`. In `config.py`: `compatible_models_for(backend, registry=None)`, `model_metrics(model) -> str`.

- [ ] **Step 1: Write the failing tests**

`tests/unit/commands/test_review_role_models.py`:

```python
"""Per-role choices for the review screen. ★ must be the resolver's own pick
(spec 005 SC-003) and offered efforts exactly what `config role-effort`
accepts (SC-004)."""
import pytest

from agent_notes.commands.config import compatible_models_for
from agent_notes.commands.wizard.role_models import (
    Catalog, edit_models, effort_options, model_items, recommended_choices,
    roles_for, set_model, starred_model,
)
from agent_notes.domain.model import Model
from agent_notes.domain.role import Role
from agent_notes.registries.cli_registry import load_registry
from agent_notes.registries.role_registry import load_role_registry
from agent_notes.services.model_resolver import select_model_for_role
from agent_notes.services.tui.keys import DOWN, ENTER, ESCAPE, RIGHT
from tests.unit.tui.fakes import tui_session


@pytest.fixture(scope="module")
def catalog():
    return Catalog()


def _backend(name):
    return load_registry().get(name)


def _role(name):
    return load_role_registry().get(name)


def _agent_backends(catalog):
    return [b for b in load_registry().available()
            if b.supports("agents") and catalog.compatible(b)]


def test_claude_roles_leave_out_orchestrator_in_canonical_order():
    assert [r.name for r in roles_for(_backend("claude"))] == ["reasoner", "worker", "scout"]


def test_other_agent_backends_keep_orchestrator_first():
    assert [r.name for r in roles_for(_backend("codex"))] == [
        "orchestrator", "reasoner", "worker", "scout"]


def test_star_is_the_resolver_pick_for_every_backend_and_role(catalog):
    checked = 0
    for backend in _agent_backends(catalog):
        for role in roles_for(backend):
            expected, _ = select_model_for_role(compatible_models_for(backend), role, backend)
            star = starred_model(catalog, backend, role)
            assert (star and star.id) == (expected and expected.id), f"{backend.name}/{role.name}"
            checked += 1
    assert checked >= 11  # claude 3 + codex 4 + opencode 4


def test_effort_options_match_the_config_role_effort_checks(catalog, monkeypatch, capsys):
    from agent_notes.commands.config import _check_effort_valid
    from agent_notes.domain.state import BackendState, ScopeState
    from agent_notes.registries import cli_registry, model_registry, provider_registry

    clis = load_registry()
    providers = provider_registry.load_provider_registry()
    # _check_effort_valid reloads all three registries per call; serve them from memory.
    monkeypatch.setattr(model_registry, "load_model_registry", lambda *a, **k: catalog.registry)
    monkeypatch.setattr(cli_registry, "load_registry", lambda *a, **k: clis)
    monkeypatch.setattr(provider_registry, "load_provider_registry", lambda *a, **k: providers)
    vocabulary = {e for name in providers.names() for e in providers.get(name).efforts}
    for backend in _agent_backends(catalog):
        for model in catalog.compatible(backend):
            state = ScopeState(clis={backend.name: BackendState(role_models={"worker": model.id})})
            accepted = {e for e in vocabulary if _check_effort_valid(state, backend.name, "worker", e)}
            assert set(effort_options(backend, model)) == accepted, f"{backend.name}/{model.id}"
    capsys.readouterr()


def test_codex_offers_only_the_efforts_the_cli_accepts(catalog):
    codex = _backend("codex")
    gpt = next(m for m in catalog.compatible(codex) if m.family == "gpt")
    assert effort_options(codex, gpt) == ["minimal", "low", "medium", "high", "xhigh"]


def test_claude_offers_the_full_anthropic_vocabulary(catalog):
    assert effort_options(_backend("claude"), catalog.get("claude-opus-5-5")) == [
        "low", "medium", "high", "xhigh", "max"]


def test_a_model_without_effort_support_or_an_unknown_model_offers_none(catalog):
    claude = _backend("claude")
    assert effort_options(claude, catalog.get("claude-haiku-4-5")) == []
    assert effort_options(claude, catalog.get("claude-not-a-model")) == []


def test_recommended_choices_are_the_shipped_defaults(catalog):
    models, efforts = recommended_choices(catalog, _backend("claude"))
    assert models == {"reasoner": "claude-opus-5-5", "worker": "claude-sonnet-5-5",
                      "scout": "claude-haiku-4-5"}
    assert efforts == {"reasoner": "high", "worker": "medium"}


def test_the_model_list_is_the_config_role_model_list_in_order(catalog):
    claude = _backend("claude")
    for role in roles_for(claude):
        assert [i.value for i in model_items(catalog, claude, role)] == [
            m.id for m in compatible_models_for(claude)]


def test_the_model_list_marks_star_budget_and_deprecation(catalog):
    items = {i.value: i for i in model_items(catalog, _backend("claude"), _role("reasoner"))}
    assert "★" in items["claude-opus-5-5"].text
    assert "★" not in items["claude-opus-5"].text
    assert items["claude-fable-5-1"].tag == "over budget"
    assert items["claude-opus-4-6"].tag.startswith("deprecated") and items["claude-opus-4-6"].dim


def test_set_model_clears_effort_for_a_model_without_effort_support(catalog):
    models, efforts = {"worker": "claude-sonnet-5-5"}, {"worker": "medium"}
    set_model(catalog, _backend("claude"), _role("worker"), "claude-haiku-4-5", models, efforts)
    assert models == {"worker": "claude-haiku-4-5"} and efforts == {}


def test_set_model_keeps_an_effort_the_new_model_allows(catalog):
    models, efforts = {"worker": "claude-sonnet-5-5"}, {"worker": "medium"}
    set_model(catalog, _backend("claude"), _role("worker"), "claude-opus-5", models, efforts)
    assert efforts == {"worker": "medium"}


def test_set_model_resets_an_effort_the_new_model_rejects(catalog):
    claude = _backend("claude")
    models, efforts = {"worker": "claude-sonnet-5-5"}, {"worker": "minimal"}
    set_model(catalog, claude, _role("worker"), "claude-opus-5", models, efforts)
    assert efforts == {"worker": "medium"}  # worker's typical effort


def _model(model_id, coding, deprecated=False):
    return Model(id=model_id, label=model_id, family="claude", model_class="opus",
                 aliases={"anthropic": model_id}, coding_index=coding, price_in=1.0,
                 deprecated=deprecated)


def test_initial_pick_prefers_a_current_model_over_a_better_deprecated_one():
    from agent_notes.commands.wizard import _default_model_for_role
    role = Role(name="reasoner", label="Reasoner", description="", budget=5.0)
    picked = _default_model_for_role(
        role, [_model("claude-opus-9", 90.0, deprecated=True), _model("claude-opus-8", 80.0)],
        _backend("claude"))
    assert picked.id == "claude-opus-8"


def test_initial_pick_falls_back_to_the_best_deprecated_model():
    from agent_notes.commands.wizard import _default_model_for_role
    role = Role(name="reasoner", label="Reasoner", description="", budget=5.0)
    picked = _default_model_for_role(
        role, [_model("claude-opus-9", 90.0, deprecated=True),
               _model("claude-opus-8", 80.0, deprecated=True)], _backend("claude"))
    assert picked.id == "claude-opus-9"


def test_role_table_cycles_effort_resets_and_changes_model(catalog):
    claude = _backend("claude")
    models, efforts = recommended_choices(catalog, claude)
    values = [i.value for i in model_items(catalog, claude, _role("worker"))]
    to_haiku = values.index("claude-haiku-4-5") - values.index("claude-sonnet-5-5")
    ui = tui_session(RIGHT, "r", RIGHT, DOWN, ENTER, *[DOWN] * to_haiku, ENTER, ESCAPE)
    edit_models(ui, catalog, claude, models, efforts)
    assert efforts["reasoner"] == "xhigh"
    assert models["worker"] == "claude-haiku-4-5" and "worker" not in efforts
    assert any("Worker · Claude Code · budget $2/M in" in "\n".join(f) for f in ui.term.frames)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest -q tests/unit/commands/test_review_role_models.py`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent_notes.commands.wizard.role_models'`.

- [ ] **Step 3: Split `model_columns` and let `compatible_models_for` take a registry**

In `agent_notes/commands/config.py`, replace `compatible_models_for` and `model_columns` with:

```python
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
```

(The `PROVISIONAL_MARK` / `PROVISIONAL_LEGEND` constants already exist from spec 004; keep one copy, placed above `model_metrics`.)

- [ ] **Step 4: Implement `role_models.py`**

`agent_notes/commands/wizard/role_models.py`:

```python
"""Per-role model and effort choices, shared by the install review and config.

★ is select_model_for_role's own pick, and effort options pass the same three
checks as `config role-effort`, so a screen never offers a choice that a build
would silently drop (spec 005 FR-008, FR-009).
"""
from __future__ import annotations

import contextlib
import io
from typing import Optional

from ...services.tui.screen import DIM, YELLOW, pad
from ...services.tui.widgets import PickItem, ReviewForm, Row, cycle_text

PICKER_HEADER = f"{'':<24}    {'int':>5}  {'coding':>6}  {'$/M in':>8}"
PICKER_LEGEND = "★ recommended   * provisional"


class Catalog:
    """Model data for one session, read once — the catalog loader parses
    seed.json and rules.yaml on every call."""

    def __init__(self, registry=None):
        if registry is None:
            from ...registries.model_registry import load_model_registry
            registry = load_model_registry()
        self.registry = registry
        self._compatible: dict[str, list] = {}

    def compatible(self, backend) -> list:
        from ..config import compatible_models_for
        if backend.name not in self._compatible:
            self._compatible[backend.name] = compatible_models_for(backend, self.registry)
        return self._compatible[backend.name]

    def get(self, model_id: str):
        """The model, or None when the id is not in the catalog."""
        try:
            return self.registry.get(model_id)
        except KeyError:
            return None


def roles_for(backend) -> list:
    from ...registries.role_registry import load_role_registry
    from ._common import _role_sort_key
    roles = sorted(load_role_registry().all(), key=_role_sort_key)
    # Claude Code picks its lead model itself (`/model`); an orchestrator pin
    # would render nowhere there.
    return [role for role in roles
            if not (backend.name == "claude" and role.name == "orchestrator")]


def budget_text(role) -> str:
    return "unbounded" if role.budget is None else f"${role.budget:g}/M in"


def starred_model(catalog, backend, role):
    """The resolver's own pick (★), or None when no rated model fits the budget."""
    from ...services.model_resolver import select_model_for_role
    # It warns on stderr when it widens to a deprecated model; that warning
    # must not land on a full-screen view.
    with contextlib.redirect_stderr(io.StringIO()):
        model, _resolved = select_model_for_role(catalog.compatible(backend), role, backend)
    return model


def initial_model(catalog, backend, role):
    """The pre-selected model: ★, else the first compatible model. None only
    when the CLI has no compatible model at all."""
    from . import _default_model_for_role
    compatible = catalog.compatible(backend)
    if not compatible:
        return None
    with contextlib.redirect_stderr(io.StringIO()):
        return _default_model_for_role(role, compatible, backend)


def _provider(backend, model):
    from . import _effort_provider_for_model
    from ...registries.provider_registry import default_provider_registry
    name = _effort_provider_for_model(backend, model)
    if name is None:
        return None
    try:
        return default_provider_registry().get(name)
    except KeyError:
        return None


def effort_options(backend, model) -> list[str]:
    """The efforts a role may use with *model* on *backend*: the model accepts
    one at all, the provider's vocabulary, then the CLI's subset — the three
    checks `config role-effort` applies (`_check_effort_valid`)."""
    if model is None or not model.capabilities.get("effort_support", True):
        return []
    provider = _provider(backend, model)
    if provider is None:
        return []
    return [effort for effort in provider.efforts
            if not backend.efforts or effort in backend.efforts]


def default_effort(backend, model, role) -> Optional[str]:
    from . import _effort_default_choice
    options = effort_options(backend, model)
    if not options:
        return None
    choice = _effort_default_choice(role, _provider(backend, model))
    return choice if choice in options else options[0]


def recommended_choices(catalog, backend) -> tuple[dict[str, str], dict[str, str]]:
    """(role → model id, role → effort) to start from; both empty when the CLI
    has no compatible model."""
    models: dict[str, str] = {}
    efforts: dict[str, str] = {}
    for role in roles_for(backend):
        model = initial_model(catalog, backend, role)
        if model is None:
            break
        models[role.name] = model.id
        effort = default_effort(backend, model, role)
        if effort:
            efforts[role.name] = effort
    return models, efforts


def set_model(catalog, backend, role, model_id, models, efforts) -> None:
    """Pick *model_id* for *role*; keep the effort only if the new model allows it."""
    models[role.name] = model_id
    model = catalog.get(model_id)
    options = effort_options(backend, model)
    if not options:
        efforts.pop(role.name, None)
    elif efforts.get(role.name) not in options:
        efforts[role.name] = default_effort(backend, model, role)


def reset_role(catalog, backend, role, models, efforts) -> None:
    """Back to the recommended model and its default effort."""
    model = initial_model(catalog, backend, role)
    if model is None:
        return
    models[role.name] = model.id
    effort = default_effort(backend, model, role)
    if effort:
        efforts[role.name] = effort
    else:
        efforts.pop(role.name, None)


def model_items(catalog, backend, role) -> list[PickItem]:
    """Every compatible model, in catalog order, marked for *role*."""
    from ..config import model_metrics
    star = starred_model(catalog, backend, role)
    items = []
    for model in catalog.compatible(backend):
        tags = []
        if model.deprecated:
            tags.append("deprecated")
        if role.budget is not None and model.price_in is not None and model.price_in > role.budget:
            tags.append("over budget")
        mark = "★" if star is not None and model.id == star.id else " "
        items.append(PickItem(model.id, f"{model.id:<24} {mark}  {model_metrics(model)}",
                              tag=" · ".join(tags), dim=model.deprecated))
    return items


def role_line(role, models, efforts) -> str:
    """One role on the review screen: name, model, effort."""
    return (f"{pad(role.name, 10)} {pad(models.get(role.name, '—'), 20)} "
            f"{efforts.get(role.name) or '—'}")


def edit_models(ui, catalog, backend, models, efforts) -> None:
    """The role table for one CLI: ←→ effort, ⏎ model list, r recommended."""
    style = ui.style
    roles = [role for role in roles_for(backend) if role.name in models]

    def pick_model(role) -> None:
        chosen = ui.pick(f"{role.label} · {backend.label} · budget {budget_text(role)}",
                         model_items(catalog, backend, role), current=models.get(role.name),
                         header=PICKER_HEADER, legend=PICKER_LEGEND)
        if chosen:
            set_model(catalog, backend, role, chosen, models, efforts)

    def row_for(role) -> Row:
        model = catalog.get(models[role.name])
        star = starred_model(catalog, backend, role)
        options = [(effort, effort) for effort in effort_options(backend, model)]

        def lines() -> list[str]:
            mark = style("★", YELLOW) if star is not None and star.id == models[role.name] else " "
            effort = efforts.get(role.name)
            effort_text = cycle_text(effort) if effort else style("—", DIM)
            price = (f"{model.price_in:>6.2f}"
                     if model is not None and model.price_in is not None else "     —")
            return [f"{pad(models[role.name], 22)} {mark}  {pad(effort_text, 12)} {price}"]

        def line_edit() -> None:
            pick_model(role)
            choices = effort_options(backend, catalog.get(models[role.name]))
            if choices:
                effort = ui.pick(f"{role.label} · effort", [PickItem(e, e) for e in choices],
                                 current=efforts.get(role.name))
                if effort:
                    efforts[role.name] = effort

        return Row(role.name, role.label, lines, options=options,
                   get=lambda: efforts.get(role.name),
                   set=lambda value: efforts.__setitem__(role.name, value),
                   edit=lambda: pick_model(role), line_edit=line_edit)

    form = ReviewForm(f"Models · {backend.label}", lambda: [row_for(role) for role in roles],
                      hints="↑↓ role   ←→ effort   ⏎ change model   r recommended   esc done",
                      escape_closes=True, default_label="finish", style=style)

    def reset() -> None:
        role = next(role for role in roles if role.name == form.focused.key)
        reset_role(catalog, backend, role, models, efforts)

    form.commands["r"] = reset
    ui.form(form)
```

- [ ] **Step 5: Run the new tests and the config/list tests that render model tables**

Run: `uv run pytest -q tests/unit/commands/test_review_role_models.py tests/unit/commands/test_config_role_model_index.py tests/unit/commands/test_list_command.py`
Expected: all pass (`model_columns` output is byte-identical after the split).

- [ ] **Step 6: Commit**

```bash
git add agent_notes/commands/wizard/role_models.py agent_notes/commands/config.py tests/unit/commands/test_review_role_models.py
git commit -m "feat(wizard): role models for the review screen — star, efforts, editor"
```

---
### Task 8: Install choices and review rows

**Files:**
- Create: `agent_notes/commands/wizard/review.py`
- Modify: `agent_notes/commands/wizard/capability_registry.py` (add optional `row` / `config_row`; `view` stays until Task 9)
- Modify: `agent_notes/commands/wizard/capabilities.py` (register a `row` for each capability)
- Test: `tests/unit/commands/test_review_install_rows.py`

**Interfaces:**
- Consumes: Task 7 (`Catalog`, `recommended_choices`, `roles_for`, `role_line`, `edit_models`); Tasks 3–6 widgets and sessions; existing `_get_skill_groups`, `_detect_obsidian_vaults`, `_validate_vault_path`, `MemoryConfig`, `Obsidian`, `DEFAULT_VAULT_DIR`, `DEFAULT_VAULT_NAME`.
- Produces: `@dataclass InstallChoices(clis, role_models, role_efforts, scope, copy_mode, skills, memory: MemoryConfig, plugins, profile_label, local_folder, global_home)` with properties `folder_overrides -> dict | None` and `global_home_override -> str`; `@dataclass ReviewContext(choices, ui, catalog, cli_registry)`; `initial_choices(catalog, cli_registry, capabilities=None) -> InstallChoices`; `add_cli(choices, catalog, backend)`; `remove_cli(choices, name)`; rows `backends_rows(ctx)`, `models_row(ctx, backend, *, label, show_cli)`, `scope_row(ctx)`, `mode_row(ctx)`, `skills_row(ctx)`, `profile_row(ctx)`, `memory_row(ui, memory: MemoryConfig) -> Row`, `toggle_row(ui, name, label, plugins: dict) -> Row`; `edit_obsidian(ui, memory)`; `memory_label(memory) -> str`; `install_rows(ctx, capabilities=None) -> Callable[[], list[Row]]`. In the registry: `CapabilityBehaviour.row`, `.config_row`; `register(..., row=None, config_row=None)`.

- [ ] **Step 1: Write the failing tests**

`tests/unit/commands/test_review_install_rows.py`:

```python
"""Rows of the install review screen (spec 005 FR-002, FR-003, FR-010–FR-013)."""
import dataclasses
from pathlib import Path

import pytest

from agent_notes.commands.wizard import review
from agent_notes.commands.wizard.capabilities import _build_registry, default_capability_registry
from agent_notes.commands.wizard.review import (
    InstallChoices, ReviewContext, edit_obsidian, initial_choices, install_rows, memory_row,
    models_row, toggle_row,
)
from agent_notes.commands.wizard.role_models import Catalog, recommended_choices
from agent_notes.domain.capability import KIND_TOGGLE, Capability
from agent_notes.domain.state import MemoryConfig
from agent_notes.registries.cli_registry import load_registry
from agent_notes.services.tui.keys import BACKSPACE, DOWN, ENTER, ESCAPE, RIGHT, SPACE
from agent_notes.services.tui.screen import visible_len
from agent_notes.services.tui.widgets import ReviewForm
from tests.unit.tui.fakes import tui_session, typed


@pytest.fixture(scope="module")
def catalog():
    return Catalog()


def _ctx(catalog, *keys):
    clis = load_registry()
    return ReviewContext(initial_choices(catalog, clis), tui_session(*keys), catalog, clis)


def _rows(ctx):
    return {row.key: row for row in install_rows(ctx)()}


def test_initial_values_are_the_recommendation(catalog):
    from agent_notes.commands.wizard._common import _get_skill_groups
    choices = _ctx(catalog).choices
    assert choices.clis == {"claude"}
    assert (choices.scope, choices.copy_mode, choices.profile_label) == ("global", False, "")
    assert choices.folder_overrides is None and choices.global_home_override == ""
    assert choices.memory == MemoryConfig()
    assert choices.plugins == {"cost-report": False}
    assert choices.skills == [s for skills in _get_skill_groups().values() for s in skills]
    assert choices.role_models == {"claude": recommended_choices(catalog, load_registry().get("claude"))[0]}


def test_rows_come_in_the_spec_order(catalog):
    assert [row.key for row in install_rows(_ctx(catalog))()] == [
        "clis", "models:claude", "scope", "mode", "skills", "memory", "toggle:cost-report", "profile"]


def test_cost_report_is_a_toggle_that_starts_off():
    cap = default_capability_registry().capability("cost-report")
    assert cap.kind == KIND_TOGGLE and cap.default is False


def test_a_registered_toggle_adds_its_own_row(catalog):
    registry = _build_registry()
    registry.register(Capability(name="demo", kind=KIND_TOGGLE, default=True, order=1),
                      row=lambda ctx: [toggle_row(ctx.ui, "demo", "Demo", ctx.choices.plugins)])
    ctx = _ctx(catalog)
    ctx.choices.plugins["demo"] = True
    keys = [row.key for row in install_rows(ctx, registry)()]
    assert keys.index("toggle:demo") == keys.index("toggle:cost-report") + 1


def test_adding_a_cli_fills_its_recommended_models(catalog):
    names = [b.name for b in sorted(load_registry().available(), key=lambda b: b.name)]
    ctx = _ctx(catalog, *[DOWN] * names.index("codex"), SPACE, ENTER)
    _rows(ctx)["clis"].edit()
    codex = load_registry().get("codex")
    assert ctx.choices.clis == {"claude", "codex"}
    assert ctx.choices.role_models["codex"] == recommended_choices(catalog, codex)[0]
    rows = _rows(ctx)
    assert rows["models:claude"].label == "Models" and rows["models:codex"].label == ""
    assert rows["models:codex"].lines()[0] == "Codex CLI"


def test_removing_every_cli_drops_the_models_and_says_so(catalog):
    ctx = _ctx(catalog, SPACE, ENTER)
    _rows(ctx)["clis"].edit()
    rows = _rows(ctx)
    assert ctx.choices.clis == set() and ctx.choices.role_models == {}
    assert "models:claude" not in rows
    assert "select at least one" in rows["clis"].lines()[0]


def test_a_cli_without_compatible_models_is_shown_but_not_editable(catalog):
    nowhere = dataclasses.replace(load_registry().get("claude"), name="nowhere",
                                  label="Nowhere", accepted_providers=("none",))
    row = models_row(_ctx(catalog), nowhere, label="Models", show_cli=False)
    assert row.focusable is False
    assert "no compatible models" in row.lines()[0]


def test_choosing_obsidian_points_at_the_first_detected_vault(monkeypatch, tmp_path):
    monkeypatch.setattr("agent_notes.commands.wizard._detect_obsidian_vaults",
                        lambda: [tmp_path / "Vault"])
    memory = MemoryConfig()
    row = memory_row(tui_session(), memory)
    row.cycle(1)
    assert memory.backend == "obsidian"
    assert memory.path == str(tmp_path / "Vault" / "projects")
    row.cycle(1)
    assert (memory.backend, memory.path, memory.strategy) == ("local", "", "single-brain")


def test_without_a_detected_vault_the_default_is_obsidian_agent_notes(monkeypatch, tmp_path):
    monkeypatch.setattr("agent_notes.commands.wizard._detect_obsidian_vaults", lambda: [])
    monkeypatch.setenv("HOME", str(tmp_path))
    memory = MemoryConfig()
    memory_row(tui_session(), memory).cycle(1)
    assert memory.path == str(tmp_path / "Obsidian" / "agent-notes" / "projects")


def test_obsidian_editor_sets_strategy_and_vault(monkeypatch, tmp_path):
    vault = tmp_path / "MyVault"
    (vault / ".obsidian").mkdir(parents=True)
    monkeypatch.setattr("agent_notes.commands.wizard._detect_obsidian_vaults", lambda: [])
    memory = MemoryConfig(backend="obsidian", path=str(tmp_path / "Other" / "projects"))
    ui = tui_session(RIGHT, DOWN, ENTER, *[BACKSPACE] * 300, *typed(str(vault)), ENTER, ESCAPE)
    edit_obsidian(ui, memory)
    assert memory.strategy == "per-project"
    assert memory.path == str(vault / "projects")


def test_a_folder_that_is_not_a_vault_needs_a_second_enter(monkeypatch, tmp_path):
    monkeypatch.setattr("agent_notes.commands.wizard._detect_obsidian_vaults", lambda: [])
    memory = MemoryConfig(backend="obsidian", path=str(tmp_path / "Other" / "projects"))
    target = tmp_path / "plain"
    target.mkdir()
    ui = tui_session(DOWN, ENTER, *[BACKSPACE] * 300, *typed(str(target)), ENTER, ENTER, ESCAPE)
    edit_obsidian(ui, memory)
    assert memory.path == str(target / "projects")
    assert any("isn't an Obsidian vault" in "\n".join(f) for f in ui.term.frames)


def test_skills_editor_keeps_process_skills_and_drops_a_deselected_one(monkeypatch, catalog):
    monkeypatch.setattr("agent_notes.commands.wizard._common._get_skill_groups",
                        lambda: {"process": ["p1", "p2"], "rails": ["rails"], "docker": ["docker"]})
    monkeypatch.setattr(review, "_skill_descriptions",
                        lambda: {"rails": "Rails app conventions. More text here."})
    ctx = _ctx(catalog, SPACE, ENTER)
    assert ctx.choices.skills == ["p1", "p2", "rails", "docker"]
    _rows(ctx)["skills"].edit()
    assert ctx.choices.skills == ["p1", "p2", "docker"]
    shown = "\n".join(ctx.ui.term.frames[0])
    assert "rails — Rails app conventions" in shown
    assert "process (2) — always included" in shown


def test_a_profile_label_derives_folder_and_home(catalog):
    ctx = _ctx(catalog, ENTER, *typed("work"), ENTER, ESCAPE)
    _rows(ctx)["profile"].edit()
    assert ctx.choices.profile_label == "work"
    assert ctx.choices.folder_overrides == {"claude": ".claude-work"}
    assert ctx.choices.global_home_override == "~/.claude-work"


def test_clearing_the_profile_label_drops_the_overrides(catalog):
    ctx = _ctx(catalog, ENTER, *[BACKSPACE] * 10, ENTER, ESCAPE)
    ctx.choices.profile_label = "work"
    ctx.choices.local_folder = ".claude-custom"
    _rows(ctx)["profile"].edit()
    assert ctx.choices.profile_label == ""
    assert ctx.choices.folder_overrides is None and ctx.choices.global_home_override == ""


def test_one_cli_review_fits_80_by_24(catalog):
    ctx = _ctx(catalog)
    form = ReviewForm("AgentNotes 2.36.0 · install", install_rows(ctx),
                      context="56 agents · 25 skills · 3 rules",
                      hints="↑↓ move   ⏎ edit   ←→ change   i install   q quit")
    lines = form.render(80, 24)
    assert len(lines) <= 24
    assert all(visible_len(line) <= 80 for line in lines)
    assert not any(line.rstrip().endswith("…") for line in lines[2:-2])
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest -q tests/unit/commands/test_review_install_rows.py`
Expected: FAIL — `ImportError: cannot import name 'review'` (module missing).

- [ ] **Step 3: Let capabilities carry rows**

In `agent_notes/commands/wizard/capability_registry.py`, replace `CapabilityBehaviour` and `register` with:

```python
@dataclass(frozen=True)
class CapabilityBehaviour:
    view: Optional[Callable] = None        # legacy step view; removed in Task 9
    process: Optional[Callable] = None
    config_view: Optional[Callable] = None  # legacy; removed in Task 9
    row: Optional[Callable] = None          # (ReviewContext) -> list[Row] for the install review
    config_row: Optional[Callable] = None   # (ConfigContext) -> list[Row] for `agent-notes config`


class CapabilityRegistry:
    def __init__(self) -> None:
        self._entries: dict[str, tuple[Capability, CapabilityBehaviour]] = {}

    def register(self, capability: Capability, *, view=None, process=None, config_view=None,
                 row=None, config_row=None) -> None:
        if capability.name in self._entries:
            raise ValueError(f"Capability {capability.name!r} already registered")
        self._entries[capability.name] = (
            capability,
            CapabilityBehaviour(view, process, config_view, row, config_row),
        )
```

(The rest of the class is unchanged.)

In `agent_notes/commands/wizard/capabilities.py`, add above `_build_registry`:

```python
def _backends_rows(ctx) -> list:
    # lazy import: review imports this module for the registry
    from .review import backends_rows
    return backends_rows(ctx)


def _memory_rows(ctx) -> list:
    from .review import memory_row
    return [memory_row(ctx.ui, ctx.choices.memory)]


def _cost_report_rows(ctx) -> list:
    from .review import toggle_row
    return [toggle_row(ctx.ui, "cost-report", "Cost report", ctx.choices.plugins)]
```

and change the three `register` calls in `_build_registry` to add the rows:

```python
    reg.register(BACKENDS, view=_backends_view, config_view=_backends_config_view,
                 row=_backends_rows)
    reg.register(COST_REPORT, view=_cost_report_view, row=_cost_report_rows)
    reg.register(MEMORY, view=_memory_view, row=_memory_rows)
```

- [ ] **Step 4: Implement `review.py`**

`agent_notes/commands/wizard/review.py`:

```python
"""The install review screen: every setting on one screen, pre-filled with
the recommendation (spec 005 FR-001 – FR-013)."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from ...constants import DEFAULT_VAULT_DIR, DEFAULT_VAULT_NAME, Obsidian
from ...domain.capability import KIND_BACKEND, KIND_PROVIDER, KIND_TOGGLE
from ...domain.state import MemoryConfig
from ...services.tui.screen import DIM, YELLOW, elide_middle, tilde
from ...services.tui.widgets import PickItem, ReviewForm, Row, complete_path, cycle_text
from .role_models import Catalog, edit_models, recommended_choices, role_line, roles_for


@dataclass
class InstallChoices:
    """Everything the review collects; the orchestrator hands it to build,
    plan and _execute_install."""

    clis: set = field(default_factory=set)
    role_models: dict = field(default_factory=dict)    # cli -> role -> model id
    role_efforts: dict = field(default_factory=dict)   # cli -> role -> effort
    scope: str = "global"
    copy_mode: bool = False
    skills: list = field(default_factory=list)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    plugins: dict = field(default_factory=dict)        # toggle capability -> on
    profile_label: str = ""
    local_folder: str = ""   # "" = derived from the label
    global_home: str = ""    # "" = derived from the label

    @property
    def folder_overrides(self) -> Optional[dict]:
        if not self.profile_label:
            return None
        return {"claude": self.local_folder or f".claude-{self.profile_label}"}

    @property
    def global_home_override(self) -> str:
        if not self.profile_label:
            return ""
        return self.global_home or f"~/.claude-{self.profile_label}"


@dataclass
class ReviewContext:
    choices: InstallChoices
    ui: Any
    catalog: Catalog
    cli_registry: Any


def add_cli(choices: InstallChoices, catalog: Catalog, backend) -> None:
    choices.clis.add(backend.name)
    if backend.supports("agents"):
        models, efforts = recommended_choices(catalog, backend)
        if models:
            choices.role_models[backend.name] = models
            choices.role_efforts[backend.name] = efforts


def remove_cli(choices: InstallChoices, name: str) -> None:
    choices.clis.discard(name)
    choices.role_models.pop(name, None)
    choices.role_efforts.pop(name, None)


def initial_choices(catalog: Catalog, cli_registry, capabilities=None) -> InstallChoices:
    """The recommended setup (spec 005 FR-003)."""
    from ._common import _get_skill_groups
    from .capabilities import default_capability_registry
    registry = capabilities if capabilities is not None else default_capability_registry()
    choices = InstallChoices()
    available = {backend.name for backend in cli_registry.available()}
    for name in sorted({"claude"} & available):
        add_cli(choices, catalog, cli_registry.get(name))
    choices.skills = [skill for skills in _get_skill_groups().values() for skill in skills]
    choices.plugins = {cap.name: cap.default for cap in registry.by_kind(KIND_TOGGLE)}
    return choices


# ── CLIs and Models ──────────────────────────────────────────────────────────

def backends_rows(ctx: ReviewContext) -> list[Row]:
    choices = ctx.choices

    def cli_lines() -> list[str]:
        labels = [ctx.cli_registry.get(name).label for name in sorted(choices.clis)]
        return [", ".join(labels) if labels else ctx.ui.style("none — select at least one", YELLOW)]

    def edit_clis() -> None:
        items = [(b.label, b.name) for b in sorted(ctx.cli_registry.available(), key=lambda b: b.name)]
        picked = ctx.ui.checklist("CLIs", items, set(choices.clis))
        if picked is None:
            return
        for name in sorted(set(choices.clis) - picked):
            remove_cli(choices, name)
        for name in sorted(picked - set(choices.clis)):
            add_cli(choices, ctx.catalog, ctx.cli_registry.get(name))

    rows = [Row("clis", "CLIs", cli_lines, edit=edit_clis)]
    agent_clis = [ctx.cli_registry.get(name) for name in sorted(choices.clis)
                  if ctx.cli_registry.get(name).supports("agents")]
    for index, backend in enumerate(agent_clis):
        rows.append(models_row(ctx, backend, label="Models" if index == 0 else "",
                               show_cli=len(agent_clis) > 1))
    return rows


def models_row(ctx: ReviewContext, backend, *, label: str, show_cli: bool) -> Row:
    key = f"models:{backend.name}"
    models = ctx.choices.role_models.get(backend.name)
    if not models:
        return Row(key, label, lambda: [
            f"{backend.label}: no compatible models — uses legacy tier resolution"],
            focusable=False)
    efforts = ctx.choices.role_efforts.setdefault(backend.name, {})

    def lines() -> list[str]:
        out = [backend.label] if show_cli else []
        out += [role_line(role, models, efforts) for role in roles_for(backend)
                if role.name in models]
        return out

    return Row(key, label, lines,
               edit=lambda: edit_models(ctx.ui, ctx.catalog, backend, models, efforts))


# ── Scope, install mode, skills ──────────────────────────────────────────────

def _target_path(ctx: ReviewContext) -> str:
    choices = ctx.choices
    names = sorted(choices.clis)
    if not names:
        return ""
    backend = ctx.cli_registry.get(names[0])
    if choices.scope == "global":
        home = choices.global_home_override if backend.name == "claude" else ""
        path = Path(home).expanduser() if home else backend.global_home
    else:
        folders = choices.folder_overrides or {}
        path = Path.cwd() / folders.get(backend.name, backend.local_dir)
    more = f"  +{len(names) - 1} more" if len(names) > 1 else ""
    return elide_middle(tilde(path), 44) + more


def scope_row(ctx: ReviewContext) -> Row:
    choices = ctx.choices
    return Row("scope", "Scope",
               lambda: [f"{cycle_text(choices.scope)}   {ctx.ui.style(_target_path(ctx), DIM)}"],
               options=[("global", "global"), ("local", "local")],
               get=lambda: choices.scope, set=lambda value: setattr(choices, "scope", value))


_MODE_NOTES = {False: "updates when agent-notes updates", True: "standalone files you can edit"}


def mode_row(ctx: ReviewContext) -> Row:
    choices = ctx.choices
    return Row("mode", "Install as",
               lambda: [f"{cycle_text('copy' if choices.copy_mode else 'symlink')}  "
                        f"{ctx.ui.style(_MODE_NOTES[choices.copy_mode], DIM)}"],
               options=[("symlink", False), ("copy", True)],
               get=lambda: choices.copy_mode, set=lambda value: setattr(choices, "copy_mode", value))


def _skill_descriptions() -> dict:
    try:
        from ...registries import default_skill_registry
        return {skill.name: skill.description for skill in default_skill_registry().all()}
    except Exception:
        return {}


def _first_sentence(text: str) -> str:
    return " ".join((text or "").split()).split(". ")[0].rstrip(".")


def skills_row(ctx: ReviewContext) -> Row:
    from ._common import _get_skill_groups
    choices = ctx.choices
    groups = _get_skill_groups()
    process = list(groups.get("process", []))
    domain = [skill for name, skills in groups.items() if name != "process" for skill in skills]

    def lines() -> list[str]:
        chosen = sum(1 for skill in domain if skill in choices.skills)
        return [f"process {len(process)} · domain {chosen} of {len(domain)}"]

    def edit() -> None:
        descriptions = _skill_descriptions()
        items = [(f"{skill} — {_first_sentence(descriptions[skill])}" if descriptions.get(skill)
                  else skill, skill) for skill in domain]
        picked = ctx.ui.checklist("Skills", items, {s for s in domain if s in choices.skills},
                                  fixed=[f"process ({len(process)}) — always included"])
        if picked is not None:
            choices.skills = process + [skill for skill in domain if skill in picked]

    return Row("skills", "Skills", lines, edit=edit if domain else None)


# ── Memory and toggles (shared with config) ──────────────────────────────────

MEMORY_OPTIONS = [("built-in", "local"), ("Obsidian", "obsidian")]


def memory_label(memory: MemoryConfig) -> str:
    """The one name each memory backend has everywhere (spec 005 FR-028)."""
    if memory.backend == "obsidian":
        where = f" · {tilde(memory.path)}" if memory.path else ""
        return f"Obsidian · {memory.strategy}{where}"
    return "built-in"


def _default_vault() -> str:
    from . import _detect_obsidian_vaults
    candidates = _detect_obsidian_vaults()
    return str(candidates[0]) if candidates else str(Path.home() / DEFAULT_VAULT_DIR / DEFAULT_VAULT_NAME)


def memory_row(ui, memory: MemoryConfig) -> Row:
    def set_backend(value: str) -> None:
        memory.backend = value
        if value == "obsidian":
            if not memory.path:
                memory.path = str(Path(_default_vault()).expanduser() / Obsidian.SUBFOLDER)
        else:
            memory.path, memory.strategy = "", "single-brain"

    def lines() -> list[str]:
        if memory.backend != "obsidian":
            return [cycle_text("built-in")]
        return [f"{cycle_text('Obsidian')}   {memory.strategy} · "
                f"{ui.style(tilde(Path(memory.path).parent), DIM)}"]

    def edit() -> None:
        if memory.backend == "obsidian":
            edit_obsidian(ui, memory)

    def line_edit() -> None:
        value = ui.pick("Memory", [PickItem(value, label) for label, value in MEMORY_OPTIONS],
                        current=memory.backend)
        if value:
            set_backend(value)
        edit()

    return Row("memory", "Memory", lines, options=MEMORY_OPTIONS,
               get=lambda: memory.backend, set=set_backend, edit=edit, line_edit=line_edit)


def edit_obsidian(ui, memory: MemoryConfig) -> None:
    """Strategy (←→) and vault path (⏎) for Obsidian memory."""
    from . import _detect_obsidian_vaults, _validate_vault_path

    def vault() -> str:
        return str(Path(memory.path).parent) if memory.path else _default_vault()

    def edit_vault() -> None:
        current = vault()
        notes = [f"detected: {tilde(path)}" for path in _detect_obsidian_vaults()[:3]]
        notes.append(f"notes go in <vault>/{Obsidian.SUBFOLDER}")
        chosen = ui.text("Memory · Obsidian vault", "Vault", current, notes=notes,
                         complete=complete_path,
                         validate=lambda text: _validate_vault_path(text or current)[1])
        if chosen is not None:
            memory.path = str(Path(chosen.strip() or current).expanduser() / Obsidian.SUBFOLDER)

    def rows() -> list[Row]:
        return [
            Row("strategy", "Strategy", lambda: [cycle_text(memory.strategy)],
                options=[("single-brain", "single-brain"), ("per-project", "per-project")],
                get=lambda: memory.strategy,
                set=lambda value: setattr(memory, "strategy", value)),
            Row("vault", "Vault", lambda: [tilde(vault())], edit=edit_vault),
        ]

    ui.form(ReviewForm("Memory · Obsidian", rows, hints="↑↓ move   ←→ change   ⏎ edit   esc done",
                       escape_closes=True, style=ui.style))


def toggle_row(ui, name: str, label: str, plugins: dict) -> Row:
    return Row(f"toggle:{name}", label, lambda: [cycle_text("on" if plugins.get(name) else "off")],
               options=[("off", False), ("on", True)],
               get=lambda: bool(plugins.get(name)),
               set=lambda value: plugins.__setitem__(name, value))


# ── Profile ──────────────────────────────────────────────────────────────────

def profile_row(ctx: ReviewContext) -> Row:
    choices = ctx.choices

    def lines() -> list[str]:
        if not choices.profile_label:
            return ["default"]
        return [f"{choices.profile_label} · {choices.folder_overrides['claude']} · "
                f"{choices.global_home_override}"]

    return Row("profile", "Profile", lines, edit=lambda: edit_profile(ctx))


def edit_profile(ctx: ReviewContext) -> None:
    """Label, local folder and global home; folder and home follow the label
    until edited (spec 005 FR-013)."""
    choices, ui = ctx.choices, ctx.ui

    def set_label(value: str) -> None:
        choices.profile_label = value.strip()
        if not choices.profile_label:
            choices.local_folder = choices.global_home = ""

    def field_row(key, label, shown, current, store) -> Row:
        def edit() -> None:
            value = ui.text(f"Profile · {label}", label, current())
            if value is not None:
                store(value)
        return Row(key, label, lambda: [shown() or ui.style("—", DIM)], edit=edit)

    def rows() -> list[Row]:
        out = [field_row("label", "Label", lambda: choices.profile_label,
                         lambda: choices.profile_label, set_label)]
        if choices.profile_label:
            out.append(field_row("folder", "Local folder",
                                 lambda: choices.folder_overrides["claude"],
                                 lambda: choices.folder_overrides["claude"],
                                 lambda v: setattr(choices, "local_folder", v.strip())))
            out.append(field_row("home", "Global home", lambda: choices.global_home_override,
                                 lambda: choices.global_home_override,
                                 lambda v: setattr(choices, "global_home", v.strip())))
        return out

    ui.form(ReviewForm("Profile", rows, hints="↑↓ move   ⏎ edit   esc done",
                       escape_closes=True, style=ui.style))


# ── The whole screen ─────────────────────────────────────────────────────────

def install_rows(ctx: ReviewContext, capabilities=None) -> Callable[[], list[Row]]:
    """Rows in spec order (FR-002): backend capabilities (CLIs, Models), the
    fixed scope / install-as / skills rows, provider capabilities (Memory),
    toggle capabilities, then Profile. Recomputed on every render."""
    from .capabilities import default_capability_registry
    registry = capabilities if capabilities is not None else default_capability_registry()

    def rows() -> list[Row]:
        out: list[Row] = []
        for cap in registry.by_kind(KIND_BACKEND):
            out += registry.get(cap.name).row(ctx)
        out += [scope_row(ctx), mode_row(ctx), skills_row(ctx)]
        for kind in (KIND_PROVIDER, KIND_TOGGLE):
            for cap in registry.by_kind(kind):
                out += registry.get(cap.name).row(ctx)
        out.append(profile_row(ctx))
        return out

    return rows
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest -q tests/unit/commands/test_review_install_rows.py`
Expected: 15 passed.

- [ ] **Step 6: Run the whole suite — the old wizard still runs on `view`**

Run: `uv run pytest -q`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add agent_notes/commands/wizard/review.py agent_notes/commands/wizard/capabilities.py agent_notes/commands/wizard/capability_registry.py tests/unit/commands/test_review_install_rows.py
git commit -m "feat(wizard): install review rows from the capability registry"
```

---
### Task 9: Switch `install` to the review screen; delete the step flow

**Files:**
- Rewrite: `agent_notes/commands/wizard/orchestrator.py`
- Rewrite: `agent_notes/commands/wizard/__init__.py` (keep only the helpers listed below)
- Modify: `agent_notes/commands/wizard/capabilities.py`, `agent_notes/commands/wizard/capability_registry.py` (rows only)
- Delete: `agent_notes/commands/wizard/cost_report.py`
- Modify: `agent_notes/services/ui.py` (delete the full-screen selectors)
- Test (new): `tests/unit/commands/test_review_install_flow.py`
- Test (edit): `tests/unit/commands/test_capability_registry.py`, `test_wizard_effort_selection.py`, `test_wizard_role_model_default.py`, `test_wizard_role_ordering.py`, `test_wizard_toggle_step.py`, `test_config_role_model_index.py`
- Test (delete): `tests/unit/commands/test_wizard_backend_config.py`, `test_wizard_backend_step.py`, `test_wizard_provider_step.py`, `test_wizard_total_steps.py`, `test_wizard_accept_all_models.py`, `test_wizard_orchestrator_skip.py`, `test_wizard_steps.py`, `test_toggle_capabilities.py`, `test_wizard_confirm_build_order.py`, `test_wizard_preflight.py`, `tests/unit/commands/wizard/test_cost_report_step.py`, `tests/functional/commands/test_wizard_happy_path.py`

**Interfaces:**
- Consumes: Tasks 6–8.
- Produces: `interactive_install(session_factory=open_session)`, `_interactive_install(session_factory=open_session)`, `_review(ui, choices, catalog, cli_registry) -> bool`, `_build(choices) -> str | None` (error text), `_restore(choices)`, `_restore_persisted_render(scope, profile_label)` (unchanged), `_plan_summary(choices, cli_registry) -> (question, lines)`, `_install(choices)`; `CapabilityBehaviour(row, config_row=None, process=None)` and `register(capability, *, row, config_row=None, process=None)` rejecting `row=None`.

Every behavior the deleted tests guarded keeps a test. Where each one now lives:

| Behavior (from the deleted or edited tests) | New home |
|---|---|
| build → confirm → execute; decline restores; build failure restores and never confirms | `test_review_install_flow.py` (this task) |
| pre-confirm build gets the selections, scope, project path, profile | `test_review_install_flow.py` |
| restore build has no overlays and keeps scope/path/profile | `test_review_install_flow.py` |
| `plan_install` gets skills verbatim, profile overrides, `""` → `None` | `test_review_install_flow.py` |
| file count, backup lines, plan failure logged and non-fatal | `test_review_install_flow.py` |
| Enter / y / n confirm semantics | `test_tui_session.py::test_line_mode_confirm_defaults_to_yes` (Task 6) |
| choices reach `_execute_install` unchanged | `test_review_install_flow.py::test_two_keypresses_install_the_recommended_setup` |
| defaults: CLI, scope, mode, profile, skills, memory, cost report | `test_review_install_rows.py::test_initial_values_are_the_recommendation` (Task 8) |
| claude omits orchestrator; others keep it; canonical order | `test_review_role_models.py` (Task 7) |
| default model non-deprecated first, deprecated fallback | `test_review_role_models.py::test_initial_pick_*` (Task 7) |
| recommended = per-role defaults; model options = `config role-model` list | `test_review_role_models.py` (Task 7) |
| effort options narrowed to the CLI; no effort for unsupported models | `test_review_role_models.py` (Task 7) |
| memory: local/obsidian only, `<vault>/projects`, strategy, detected/default vault, validation loop | `test_review_install_rows.py` (Task 8) |
| skills: process always included, deselected domain skill excluded | `test_review_install_rows.py` (Task 8) |
| cost-report is a toggle, off by default | `test_review_install_rows.py` (Task 8) |

- [ ] **Step 1: Write the failing flow tests**

`tests/unit/commands/test_review_install_flow.py`:

```python
"""The install flow around the review screen (spec 005 FR-001, FR-005, FR-026):
build before confirm, restore on decline, and the collected values reach build,
plan and _execute_install unchanged."""
import logging
from pathlib import Path
from types import SimpleNamespace

import pytest

from agent_notes.commands.wizard import orchestrator
from agent_notes.commands.wizard.review import InstallChoices
from agent_notes.registries.cli_registry import load_registry
from agent_notes.services.tui.keys import DOWN, ENTER, ESCAPE, RIGHT, SPACE
from agent_notes.services.tui.session import LineSession
from tests.unit.tui.fakes import FakeLineInput, tui_session


class _Calls(list):
    plan = None

    def kinds(self):
        return [kind for kind, _ in self]

    def of(self, kind):
        return [kwargs for k, kwargs in self if k == kind]


@pytest.fixture
def calls(monkeypatch):
    log = _Calls()
    log.plan = SimpleNamespace(to_install=["a", "b", "c"], overwrites=[])

    def fake_plan_install(**kwargs):
        log.append(("plan", kwargs))
        return "manifest"

    monkeypatch.setattr(orchestrator, "build", lambda **kw: log.append(("build", kw)))
    monkeypatch.setattr(orchestrator, "_execute_install", lambda **kw: log.append(("execute", kw)))
    monkeypatch.setattr("agent_notes.services.installer.plan_install", fake_plan_install)
    monkeypatch.setattr("agent_notes.services.installer.summarize_plan", lambda manifest: log.plan)
    return log


def _run(*keys, session=None):
    ui = session or tui_session(*keys)
    orchestrator._interactive_install(session_factory=lambda: ui)
    return ui


def test_two_keypresses_install_the_recommended_setup(calls):
    _run("i", ENTER)
    assert calls.kinds() == ["build", "plan", "execute"]
    run = calls.of("execute")[0]
    assert (run["clis"], run["scope"], run["copy_mode"]) == ({"claude"}, "global", False)
    assert run["role_models"]["claude"]["reasoner"] == "claude-opus-5-5"
    assert (run["memory_backend"], run["memory_path"], run["memory_strategy"]) == (
        "local", "", "single-brain")
    assert (run["profile_label"], run["folder_overrides"], run["global_home_override"]) == (
        "", None, "")
    assert run["enabled_plugins"] == {"cost-report": False}


def test_the_build_gets_the_selections_before_confirming(calls):
    _run("i", ENTER)
    build, run = calls.of("build")[0], calls.of("execute")[0]
    assert build["role_models"] == run["role_models"]
    assert build["role_efforts"] == run["role_efforts"]
    assert (build["scope"], build["project_path"], build["profile_label"]) == ("global", None, "")


def test_local_scope_builds_for_the_current_folder(calls):
    _run(DOWN, DOWN, RIGHT, "i", ENTER)  # CLIs → Models → Scope, then local
    assert calls.of("build")[0]["project_path"] == Path.cwd()
    assert calls.of("execute")[0]["scope"] == "local"


def test_declining_restores_the_persisted_render_and_installs_nothing(calls, capsys):
    _run("i", ESCAPE, "q")
    assert calls.kinds() == ["build", "plan", "build"]
    restore = calls.of("build")[1]
    assert "role_models" not in restore and "role_efforts" not in restore
    assert "Installation cancelled." in capsys.readouterr().out


def test_the_restore_keeps_scope_and_profile(calls, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    orchestrator._restore(InstallChoices(scope="local", profile_label="work"))
    restore = calls.of("build")[0]
    assert restore["scope"] == "local" and restore["profile_label"] == "work"
    assert Path(restore["project_path"]).resolve() == tmp_path.resolve()


def test_a_failed_build_restores_shows_why_and_never_confirms(calls, monkeypatch):
    def failing_build(**kwargs):
        calls.append(("build", kwargs))
        if "role_models" in kwargs:
            raise RuntimeError("disk full")

    monkeypatch.setattr(orchestrator, "build", failing_build)
    ui = _run("i", "q")
    assert calls.kinds() == ["build", "build"]
    assert "Build failed: disk full" in ui.term.text()


def test_no_cli_selected_refuses_to_build(calls):
    ui = _run(ENTER, SPACE, ENTER, "i", "q")
    assert calls.kinds() == []
    assert "select at least one CLI" in ui.term.text()


def test_plan_gets_the_skills_verbatim_and_the_profile_overrides(calls):
    orchestrator._plan_summary(InstallChoices(clis={"claude"}, skills=[], profile_label="work"),
                               load_registry())
    plan = calls.of("plan")[0]
    assert plan["selected_skills"] == []
    assert plan["folder_overrides"] == {"claude": ".claude-work"}
    assert plan["global_home_override"] == "~/.claude-work"


def test_no_profile_passes_no_overrides(calls):
    orchestrator._plan_summary(InstallChoices(clis={"claude"}), load_registry())
    plan = calls.of("plan")[0]
    assert plan["folder_overrides"] is None and plan["global_home_override"] is None


def test_the_question_counts_files_and_lists_at_most_five_backups(calls):
    calls.plan.overwrites = [SimpleNamespace(dst=f"/x/{i}.md", backup_path=f"/x/{i}.md.bak")
                             for i in range(7)]
    question, lines = orchestrator._plan_summary(InstallChoices(clis={"claude"}), load_registry())
    assert question == "Install 3 files (7 backed up)?"
    assert lines[0] == "backup  /x/0.md  →  /x/0.md.bak"
    assert len(lines) == 6 and lines[-1] == "… 2 more"


def test_no_backup_lines_without_overwrites(calls):
    question, lines = orchestrator._plan_summary(InstallChoices(clis={"claude"}), load_registry())
    assert (question, lines) == ("Install 3 files (0 backed up)?", [])


def test_a_plan_failure_is_logged_and_the_install_can_still_go_ahead(calls, monkeypatch, caplog):
    def broken(**kwargs):
        raise OSError("unreadable")

    monkeypatch.setattr("agent_notes.services.installer.plan_install", broken)
    with caplog.at_level(logging.DEBUG, logger="agent_notes.commands.wizard.orchestrator"):
        question, lines = orchestrator._plan_summary(InstallChoices(clis={"claude"}),
                                                     load_registry())
    assert (question, lines) == ("Install?", [])
    assert "plan_install failed" in caplog.text


def test_without_a_terminal_the_recommended_setup_installs_without_prompts(calls):
    orchestrator._interactive_install(session_factory=lambda: None)
    assert calls.kinds() == ["build", "execute"]


def test_ctrl_c_prints_cancelled(capsys):
    def interrupted():
        raise KeyboardInterrupt

    orchestrator.interactive_install(session_factory=interrupted)
    assert "Cancelled." in capsys.readouterr().out


def test_line_mode_installs_with_two_enters(calls, monkeypatch):
    monkeypatch.setattr("agent_notes.services.ui._safe_input", FakeLineInput("", ""))
    _run(session=LineSession())
    assert calls.kinds() == ["build", "plan", "execute"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest -q tests/unit/commands/test_review_install_flow.py`
Expected: FAIL — `TypeError: _interactive_install() got an unexpected keyword argument 'session_factory'` (and missing `_restore` / `_plan_summary`).

- [ ] **Step 3: Rewrite `orchestrator.py`**

`agent_notes/commands/wizard/orchestrator.py`:

```python
"""Install flow: recommended values → review screen → quiet build → confirm →
install (spec 005 FR-001, FR-005, FR-024, FR-026)."""
from __future__ import annotations

import contextlib
import io
import logging
from pathlib import Path
from typing import Optional

from ...config import Color, get_version
from ...services.tui.screen import tilde
from ...services.tui.session import open_session
from ...services.tui.widgets import CANCEL, DONE, ReviewForm
from ..build import build
from .._install_helpers import count_agents, count_skills
from ._common import _count_rules
from .execute import _execute_install
from .review import InstallChoices, ReviewContext, initial_choices, install_rows
from .role_models import Catalog

log = logging.getLogger(__name__)

HINTS = "↑↓ move   ⏎ edit   ←→ change   i install   q quit"


def interactive_install(session_factory=open_session) -> None:
    """Run the install review."""
    try:
        _interactive_install(session_factory)
    except KeyboardInterrupt:
        print(f"\n\n  {Color.YELLOW}Cancelled.{Color.NC}")


def _interactive_install(session_factory=open_session) -> None:
    from ...registries.cli_registry import load_registry
    cli_registry = load_registry()
    catalog = Catalog()
    choices = initial_choices(catalog, cli_registry)
    session = session_factory()
    if session is None:
        # stdin or stdout is not a terminal: nothing may prompt (FR-026).
        print("No terminal attached — installing the recommended setup.")
        error = _build(choices)
        if error:
            print(f"{Color.RED}Build failed: {error}{Color.NC}")
            _restore(choices)
            return
        _install(choices)
        return
    with session as ui:
        confirmed = _review(ui, choices, catalog, cli_registry)
    if confirmed:
        _install(choices)
    else:
        print("Installation cancelled.")


def _counts(cli_registry) -> str:
    agents = sum(count_agents(b) for b in cli_registry.all() if b.supports("agents"))
    return f"{agents} agents · {count_skills()} skills · {_count_rules()} rules"


def _review(ui, choices: InstallChoices, catalog: Catalog, cli_registry) -> bool:
    ctx = ReviewContext(choices, ui, catalog, cli_registry)
    form = ReviewForm(f"AgentNotes {get_version()} · install", install_rows(ctx),
                      context=_counts(cli_registry), hints=HINTS,
                      default_command="i", default_label="install", style=ui.style)

    def install_command() -> Optional[str]:
        if not choices.clis:
            form.message = "select at least one CLI"
            return None
        ui.progress(form, "Building…")
        error = _build(choices)
        if error:
            _restore(choices)
            form.message = f"Build failed: {error}"
            return None
        question, lines = _plan_summary(choices, cli_registry)
        if ui.confirm(form, question, lines):
            return DONE
        _restore(choices)
        return None

    form.commands.update({"i": install_command, "q": lambda: CANCEL})
    return ui.form(form) == DONE


@contextlib.contextmanager
def _quiet():
    """Keep build and restore output off the screen (FR-024)."""
    sink = io.StringIO()
    with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
        yield


def _build(choices: InstallChoices) -> Optional[str]:
    """Render dist/ with this run's choices, before confirming: the file count
    must come from what this install will write. Returns the error, if any."""
    from ...services.fs import silent_ops
    try:
        with silent_ops(), _quiet():
            build(role_models=choices.role_models, role_efforts=choices.role_efforts,
                  scope=choices.scope,
                  project_path=Path.cwd() if choices.scope == "local" else None,
                  profile_label=choices.profile_label)
    except Exception as e:
        return str(e) or type(e).__name__
    return None


def _restore_persisted_render(scope: str, profile_label: str) -> None:
    """Re-render dist/ from persisted state pins (no in-memory selection overlays).

    The pre-confirm build bakes this run's selections into dist/; if the user
    declines (or the build aborts half-written), existing symlink installs would
    keep serving the rejected picks. Rebuilding without overlays restores the
    persisted-pin rendering."""
    from ...services.fs import silent_ops
    try:
        with silent_ops():
            build(scope=scope, project_path=Path.cwd() if scope == "local" else None,
                  profile_label=profile_label)
    except Exception as e:
        print(f"{Color.YELLOW}Warning: could not restore rendered files: {e}{Color.NC}")


def _restore(choices: InstallChoices) -> None:
    with _quiet():
        _restore_persisted_render(choices.scope, choices.profile_label)


def _plan_summary(choices: InstallChoices, cli_registry) -> tuple[str, list[str]]:
    """The confirmation question and up to five backup lines."""
    from ...services.installer import plan_install, summarize_plan
    try:
        # skills pass as-is: an empty selection must plan zero skills (None
        # would mean "all skills", which the install will not write).
        manifest = plan_install(scope=choices.scope, registry=cli_registry,
                                selected_clis=set(choices.clis), selected_skills=choices.skills,
                                copy_mode=choices.copy_mode,
                                folder_overrides=choices.folder_overrides,
                                global_home_override=choices.global_home_override or None)
        summary = summarize_plan(manifest)
    except Exception:
        log.debug("plan_install failed during pre-flight", exc_info=True)
        return "Install?", []
    backups = summary.overwrites
    lines = [f"backup  {tilde(a.dst)}  →  {tilde(a.backup_path)}" for a in backups[:5]]
    if len(backups) > 5:
        lines.append(f"… {len(backups) - 5} more")
    return f"Install {len(summary.to_install)} files ({len(backups)} backed up)?", lines


def _install(choices: InstallChoices) -> None:
    _execute_install(
        clis=choices.clis,
        scope=choices.scope,
        copy_mode=choices.copy_mode,
        selected_skills=choices.skills,
        role_models=choices.role_models,
        role_efforts=choices.role_efforts,
        memory_backend=choices.memory.backend,
        memory_path=choices.memory.path,
        memory_strategy=choices.memory.strategy,
        profile_label=choices.profile_label,
        folder_overrides=choices.folder_overrides,
        global_home_override=choices.global_home_override,
        enabled_plugins=dict(choices.plugins),
    )
```

- [ ] **Step 4: Run the flow tests to verify they pass**

Run: `uv run pytest -q tests/unit/commands/test_review_install_flow.py`
Expected: 15 passed.

- [ ] **Step 5: Rewrite `wizard/__init__.py` down to the shared helpers**

Replace the whole file with the module docstring and imports below, followed by these six functions copied **unchanged** from the current file: `_default_model_for_role`, `_effort_provider_for_model`, `_effort_default_choice`, `_validate_vault_path`, `_detect_obsidian_vaults`, `_format_role_model_display`. Delete everything else (`_select_profile`, `_select_cli`, `_select_accept_all_models`, `_select_models_per_role`, `_select_scope`, `_select_mode`, `_select_skills`, `_select_memory`, `_render_install_summary`, `_confirm_install`).

```python
"""Interactive install for agent-notes: the review screen (spec 005).

The flow is in orchestrator.py and the rows in review.py / role_models.py.
This module keeps the helpers they and the post-install summary share.
"""

from pathlib import Path
from typing import List, Optional

from ._common import _ROLE_ANSI, _get_skill_groups, _count_rules, _role_sort_key
from .execute import (
    install_skills_filtered,
    install_agents_filtered,
    install_config_filtered,
    _execute_install,
)
from .orchestrator import interactive_install, _interactive_install

# ... the six helper functions, unchanged ...

__all__ = [
    "interactive_install",
    "_interactive_install",
    "_default_model_for_role",
    "_effort_provider_for_model",
    "_effort_default_choice",
    "_validate_vault_path",
    "_detect_obsidian_vaults",
    "_format_role_model_display",
    "install_skills_filtered",
    "install_agents_filtered",
    "install_config_filtered",
    "_execute_install",
    "_get_skill_groups",
    "_count_rules",
    "_role_sort_key",
]
```

`_detect_obsidian_vaults` uses `Path` and `List`; `_effort_default_choice` and `_format_role_model_display` use `Optional`. Drop the imports the deleted functions alone needed (`sys`, `Color`, `DEFAULT_VAULT_*`, `Obsidian`, `configured_providers`, the `services.ui` selectors).

- [ ] **Step 6: Make capabilities rows-only**

`agent_notes/commands/wizard/capability_registry.py` — new docstring, `CapabilityBehaviour` and `register`:

```python
"""Code-side registry: capability name -> its review row(s) + install process.

Manifests/kinds are pure data (domain.Capability); behavior is registered here
in code. `row(ctx)` returns the capability's rows on the install review;
`config_row(ctx)`, when given, its rows on `agent-notes config`. `process` is
reserved for applying a value at install time.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from ...domain.capability import Capability


@dataclass(frozen=True)
class CapabilityBehaviour:
    row: Callable
    config_row: Optional[Callable] = None
    process: Optional[Callable] = None


class CapabilityRegistry:
    def __init__(self) -> None:
        self._entries: dict[str, tuple[Capability, CapabilityBehaviour]] = {}

    def register(self, capability: Capability, *, row, config_row=None, process=None) -> None:
        if capability.name in self._entries:
            raise ValueError(f"Capability {capability.name!r} already registered")
        if row is None:
            raise ValueError(f"Capability {capability.name!r} has no review row")
        self._entries[capability.name] = (capability, CapabilityBehaviour(row, config_row, process))
```

(`get`, `capability`, `by_kind`, `names` unchanged.)

`agent_notes/commands/wizard/capabilities.py` — keep the module docstring (reworded to "Registration of the built-in capabilities and their review rows."), the three `Capability` constants, `_backends_rows`, `_memory_rows`, `_cost_report_rows`, and replace the rest with:

```python
def _build_registry() -> CapabilityRegistry:
    reg = CapabilityRegistry()
    reg.register(BACKENDS, row=_backends_rows)
    reg.register(COST_REPORT, row=_cost_report_rows)
    reg.register(MEMORY, row=_memory_rows)
    return reg


@lru_cache(maxsize=1)
def default_capability_registry() -> CapabilityRegistry:
    return _build_registry()
```

Delete `_backends_view`, `_backends_config_view`, `_cost_report_view`, `_memory_view`, `_compute_total_steps`, `collect_toggle_selections`, `collect_provider_selections`, `collect_backend_selections`, `collect_backend_config`, and the `from .cost_report import _select_cost_report` line. Delete `agent_notes/commands/wizard/cost_report.py`.

- [ ] **Step 7: Delete the full-screen selectors from `services/ui.py`**

Delete `_terminal_width`, `_clear_screen`, `_render_step_header`, `_render_nav_footer`, `_read_key`, `_checkbox_select`, `_radio_select`, and drop them from `__all__`. Keep `Color`, the status helpers, `_safe_input`, `_path_input`, `_can_interactive`, `_checkbox_select_fallback`, `_radio_select_fallback`, `_HAS_TTY`. Delete `import tty, termios` only if nothing left uses them (`_HAS_TTY` still needs the try/except import).

- [ ] **Step 8: Update the tests that partly survive**

- `tests/unit/commands/test_capability_registry.py`: replace `_noop_view(step, total, version)` with `def _noop_row(ctx): return []`, every `view=_noop_view` with `row=_noop_row`, and `.view is _noop_view` with `.row is _noop_row`. Add:

```python
def test_a_capability_without_a_review_row_is_rejected():
    reg = CapabilityRegistry()
    with pytest.raises(ValueError, match="no review row"):
        reg.register(Capability(name="x", kind=KIND_TOGGLE), row=None)
```

- `test_wizard_effort_selection.py`: delete `_run_wizard` and class `TestEffortOptionsNarrowedToBackend` (now in `test_review_role_models.py`); keep `TestEffortProviderForModel` and `TestEffortDefaultChoice`.
- `test_wizard_role_model_default.py`: in class `TestWizardRoleModelDefault`, delete the two wizard-driven tests and the `_run_model_selection` harness (now `test_initial_pick_*` in Task 7); the class keeps `test_model_deprecated_field_is_loaded_as_boolean_from_yaml`. Keep `TestCatalogRetention`.
- `test_wizard_role_ordering.py`: delete `TestSelectModelsPerRoleOrdering` and `TestInstallSummaryOrdering`; keep `TestRoleSortKey` and `TestConfigurationSectionOrdering`.
- `test_wizard_toggle_step.py`: delete `test_orchestrator_uses_toggle_runner`; keep `test_execute_install_takes_enabled_plugins_not_cost_report_flag`.
- `test_config_role_model_index.py`: delete `TestWizardAndCliShareTheSameList` and the now-unused `import agent_notes.commands.wizard as wiz`.
- Delete the twelve files listed under **Test (delete)** above.

- [ ] **Step 9: Check nothing still references the deleted names**

Run: `grep -rnE "_select_(cli|profile|scope|mode|skills|memory|models_per_role|accept_all_models|cost_report)|_confirm_install|_render_install_summary|_compute_total_steps|collect_(toggle|provider|backend)_|config_view|_radio_select\(|_checkbox_select\(|_render_step_header|_render_nav_footer|_read_key|_clear_screen" agent_notes tests --include='*.py'`
Expected: no output.

- [ ] **Step 10: Run the whole suite**

Run: `uv run pytest -q`
Expected: all pass. The count drops by the deleted tests and rises by the new ones; record both numbers in the commit message.

- [ ] **Step 11: Commit**

```bash
git add -A agent_notes/commands/wizard agent_notes/services/ui.py tests/unit/commands tests/functional/commands
git commit -m "feat(install): one review screen replaces the 9-step wizard"
```

---

### Task 10: One memory vocabulary; end-to-end pty check

**Files:**
- Modify: `agent_notes/commands/wizard/execute.py:292-302` (memory line of the post-install summary)
- Test: `tests/unit/commands/test_review_install_rows.py` (add), `tests/functional/test_install_review_pty.py` (new)

**Interfaces:**
- Consumes: Task 8 `memory_label`; Task 9 orchestrator.
- Produces: `execute._memory_line(backend, path) -> str`.

- [ ] **Step 1: Write the failing test for the post-install memory line**

Append to `tests/unit/commands/test_review_install_rows.py`:

```python
def test_post_install_summary_uses_the_same_memory_names():
    from agent_notes.commands.wizard.execute import _memory_line
    assert _memory_line("local", "/m") == "built-in  →  /m"
    assert _memory_line("obsidian", "/v/projects") == "Obsidian  →  /v/projects"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest -q tests/unit/commands/test_review_install_rows.py -k memory_names`
Expected: FAIL — `ImportError: cannot import name '_memory_line'`.

- [ ] **Step 3: Extract `_memory_line` in `execute.py`**

Add above `_execute_install`:

```python
def _memory_line(backend: str, path) -> str:
    """The post-install memory line, in the names the review uses (FR-028)."""
    name = "Obsidian" if backend == "obsidian" else "built-in"
    return f"{name}  →  {path}"
```

and replace the `if memory_backend == "obsidian": … else: …` label block inside `_execute_install` with `memory_label = _memory_line(memory_backend, _mem_path)`.

- [ ] **Step 4: Write the pty smoke test**

`tests/functional/test_install_review_pty.py`:

```python
"""End-to-end: the real binary in a pseudo-terminal, sandboxed HOME.

Skipped unless pexpect is installed — run it with
`uv run --with pexpect pytest tests/functional/test_install_review_pty.py`.
It renders into the repo's git-ignored agent_notes/dist/, like any build.
"""
import io
import os
import re
import sys

import pytest

pexpect = pytest.importorskip("pexpect")

ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


def test_install_review_end_to_end(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    env = {k: v for k, v in os.environ.items() if k != "NO_COLOR"}
    env.update(HOME=str(home), XDG_CONFIG_HOME=str(home / ".config"),
               XDG_CACHE_HOME=str(home / ".cache"), TERM="xterm-256color")
    child = pexpect.spawn(sys.executable, ["-m", "agent_notes", "install"], env=env,
                          cwd=str(home), dimensions=(24, 80), timeout=120, encoding="utf-8")
    log = io.StringIO()
    child.logfile_read = log
    child.expect("i install")
    child.send("i")
    child.expect("esc back")
    child.send("\r")
    child.expect(pexpect.EOF)
    child.close()
    output = log.getvalue()

    assert child.exitstatus == 0
    # Only the full-screen part must fit 80 columns; the post-install summary
    # printed after leaving the alternate screen may hold long paths.
    full_screen = output.split("\x1b[?1049l")[0]
    frames = [ANSI.sub("", frame) for frame in full_screen.split("\x1b[2J")[1:]]
    assert frames, "no full-screen frames painted"
    assert all(len(line) <= 80 for frame in frames for line in frame.split("\r\n"))   # SC-002
    assert "Step 1 of" not in output                                                     # FR-001
    assert "Generating agent files" not in output                                        # SC-009
    architect = home / ".claude" / "agents" / "architect.md"
    assert "model: claude-opus-5-5" in architect.read_text()
```

- [ ] **Step 5: Run the unit test and the pty test**

Run: `uv run pytest -q tests/unit/commands/test_review_install_rows.py`
Expected: all pass.

Run: `uv run --with pexpect pytest -q tests/functional/test_install_review_pty.py`
Expected: 1 passed. (Without `--with pexpect` it reports 1 skipped.)

- [ ] **Step 6: Commit**

```bash
git add agent_notes/commands/wizard/execute.py tests/unit/commands/test_review_install_rows.py tests/functional/test_install_review_pty.py
git commit -m "feat(install): built-in/Obsidian wording; pty end-to-end check"
```

---

## Phase C — `agent-notes config`

### Task 11: Find the install to configure

**Files:**
- Create: `agent_notes/commands/config_review.py`
- Test: `tests/unit/commands/test_config_review_installs.py`

**Interfaces:**
- Consumes: `state_store.get_scope`; `tilde` (Task 2).
- Produces: `@dataclass(frozen=True) InstallRef(scope, project_path, profile_label="")` with `.missing -> bool`, `.label() -> str`, `.get(state) -> ScopeState | None`; `list_installs(state) -> list[InstallRef]`; `default_install(refs, cwd) -> InstallRef | None`.

- [ ] **Step 1: Write the failing tests**

`tests/unit/commands/test_config_review_installs.py`:

```python
"""Which install `agent-notes config` opens (spec 005 FR-014, SC-005)."""
from agent_notes.commands.config_review import InstallRef, default_install, list_installs
from agent_notes.domain.state import ScopeState, State


def _state(tmp_path, *, global_=False, profiles=(), locals_=()):
    return State(
        global_install=ScopeState() if global_ else None,
        global_installs={label: ScopeState() for label in profiles},
        local_installs={key: ScopeState() for key in locals_},
    )


def test_installs_are_listed_global_then_profiles_then_local(tmp_path):
    refs = list_installs(_state(tmp_path, global_=True, profiles=["work"], locals_=[str(tmp_path)]))
    assert refs == [InstallRef("global", None), InstallRef("global", None, "work"),
                    InstallRef("local", tmp_path)]


def test_a_profile_suffix_is_split_off_a_local_key(tmp_path):
    [ref] = list_installs(_state(tmp_path, locals_=[f"{tmp_path}#work"]))
    assert (ref.project_path, ref.profile_label) == (tmp_path, "work")


def test_a_hash_inside_an_existing_folder_name_stays_in_the_path(tmp_path):
    folder = tmp_path / "a#b"
    folder.mkdir()
    [ref] = list_installs(_state(tmp_path, locals_=[str(folder)]))
    assert (ref.project_path, ref.profile_label) == (folder, "")


def test_the_current_folder_install_wins(tmp_path):
    refs = list_installs(_state(tmp_path, global_=True, locals_=[str(tmp_path)]))
    assert default_install(refs, tmp_path) == InstallRef("local", tmp_path)


def test_the_default_profile_beats_a_named_one_in_the_same_folder(tmp_path):
    refs = list_installs(_state(tmp_path, locals_=[f"{tmp_path}#work", str(tmp_path)]))
    assert default_install(refs, tmp_path) == InstallRef("local", tmp_path)


def test_global_when_the_current_folder_has_no_install(tmp_path):
    other = tmp_path / "other"
    other.mkdir()
    refs = list_installs(_state(tmp_path, global_=True, locals_=[str(other)]))
    assert default_install(refs, tmp_path) == InstallRef("global", None)


def test_only_local_installs_elsewhere_means_ask(tmp_path):
    a, b, here = tmp_path / "a", tmp_path / "b", tmp_path / "here"
    for folder in (a, b, here):
        folder.mkdir()
    refs = list_installs(_state(tmp_path, locals_=[str(a), str(b)]))
    assert default_install(refs, here) is None


def test_a_single_install_is_chosen(tmp_path):
    a, here = tmp_path / "a", tmp_path / "here"
    a.mkdir()
    here.mkdir()
    refs = list_installs(_state(tmp_path, locals_=[str(a)]))
    assert default_install(refs, here) == InstallRef("local", a)


def test_a_deleted_project_is_marked_missing_and_never_chosen(tmp_path):
    gone, here = tmp_path / "gone", tmp_path / "here"
    here.mkdir()
    refs = list_installs(_state(tmp_path, locals_=[str(gone)]))
    assert refs[0].missing and refs[0].label().endswith("(missing)")
    assert default_install(refs, here) is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest -q tests/unit/commands/test_config_review_installs.py`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent_notes.commands.config_review'`.

- [ ] **Step 3: Implement**

`agent_notes/commands/config_review.py`:

```python
"""`agent-notes config` on the review screen (spec 005 FR-014 – FR-020)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ..services.tui.screen import tilde


@dataclass(frozen=True)
class InstallRef:
    """Where an install lives: enough to find its state and regenerate it."""

    scope: str                      # "global" | "local"
    project_path: Optional[Path]    # local only
    profile_label: str = ""

    @property
    def missing(self) -> bool:
        return self.scope == "local" and not self.project_path.is_dir()

    def label(self) -> str:
        where = "global" if self.scope == "global" else f"local · {tilde(self.project_path)}"
        if self.profile_label:
            where += f" · {self.profile_label}"
        return where + (" (missing)" if self.missing else "")

    def get(self, state):
        from ..services.state_store import get_scope
        return get_scope(state, self.scope, self.project_path, self.profile_label)


def _split_local_key(key: str) -> tuple[Path, str]:
    """A local key is 'path' or 'path#profile' (state_store._local_key). A '#'
    that belongs to an existing folder's name stays part of the path."""
    path, sep, label = key.rpartition("#")
    if not sep or Path(key).is_dir():
        return Path(key), ""
    return Path(path), label


def list_installs(state) -> list[InstallRef]:
    refs = []
    if state.global_install is not None:
        refs.append(InstallRef("global", None))
    refs += [InstallRef("global", None, label) for label in sorted(state.global_installs)]
    for key in sorted(state.local_installs):
        path, label = _split_local_key(key)
        refs.append(InstallRef("local", path, label))
    return refs


def default_install(refs: list[InstallRef], cwd: Path) -> Optional[InstallRef]:
    """The current folder's install, else the global one, else the only one.
    None means ask (spec 005 FR-014). A missing folder is never chosen."""
    cwd = Path(cwd).resolve()
    here = [r for r in refs if r.scope == "local" and r.project_path.resolve() == cwd]
    for candidates in ([r for r in here if not r.profile_label], here,
                       [r for r in refs if r.scope == "global" and not r.profile_label]):
        if candidates:
            return candidates[0]
    if len(refs) == 1 and not refs[0].missing:
        return refs[0]
    return None
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest -q tests/unit/commands/test_config_review_installs.py`
Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git add agent_notes/commands/config_review.py tests/unit/commands/test_config_review_installs.py
git commit -m "feat(config): find the install to configure"
```

---

### Task 12: Config rows — flagged pins, memory, toggles, API keys

**Files:**
- Modify: `agent_notes/commands/config_review.py` (append)
- Modify: `agent_notes/commands/wizard/capabilities.py` (register `config_row`s)
- Test: `tests/unit/commands/test_config_review_rows.py`

**Interfaces:**
- Consumes: Task 7 (`Catalog`, `roles_for`, `role_line`, `starred_model`, `initial_model`, `default_effort`, `edit_models`); Task 8 (`memory_row`, `toggle_row`); Task 11.
- Produces: `@dataclass ConfigContext(ui, state, ref, catalog, cli_registry, plugins)` with `.scope_state()`; `pin_flag(catalog, backend, role, model_id) -> str`; `is_flagged(catalog, model_id) -> bool`; `config_models_rows(ctx) -> list[Row]`; `upgrade_flagged(ctx) -> int`; `api_keys_row(ctx) -> Row`; `reinstall_row(ctx) -> Row`; `config_rows(ctx, *, part="all", capabilities=None) -> Callable[[], list[Row]]` with `part` in `{"all", "global", "install"}`; `enabled_toggles(capabilities=None) -> dict[str, bool]`.

- [ ] **Step 1: Write the failing tests**

`tests/unit/commands/test_config_review_rows.py`:

```python
"""Config-mode rows (spec 005 FR-015 – FR-018)."""
import pytest

from agent_notes.commands import config_review
from agent_notes.commands.config_review import (
    ConfigContext, InstallRef, config_rows, upgrade_flagged,
)
from agent_notes.commands.wizard.role_models import Catalog
from agent_notes.domain.state import BackendState, ScopeState, State
from agent_notes.registries.cli_registry import load_registry
from agent_notes.services.tui.keys import ENTER
from tests.unit.tui.fakes import tui_session, typed


@pytest.fixture(scope="module")
def catalog():
    return Catalog()


def _ctx(catalog, tmp_path, *keys, pins=None, efforts=None):
    pins = pins or {"reasoner": "claude-opus-4-6", "worker": "claude-sonnet-5-5",
                    "scout": "claude-gone-1"}
    backend = BackendState(role_models=dict(pins), role_efforts=dict(efforts or {"reasoner": "high"}))
    state = State(local_installs={str(tmp_path): ScopeState(clis={"claude": backend})})
    return ConfigContext(tui_session(*keys), state, InstallRef("local", tmp_path), catalog,
                         load_registry(), {"cost-report": False})


def _rows(ctx):
    return {row.key: row for row in config_rows(ctx)()}


def _model_lines(ctx):
    return {line.split()[0]: line for line in _rows(ctx)["models:claude"].lines()}


def test_rows_in_order(catalog, tmp_path):
    assert list(_rows(_ctx(catalog, tmp_path))) == [
        "models:claude", "memory", "toggle:cost-report", "api-keys", "reinstall"]


def test_a_deprecated_pin_is_flagged_with_the_recommendation(catalog, tmp_path):
    assert "⚠ deprecated  ★ claude-opus-5-5" in _model_lines(_ctx(catalog, tmp_path))["reasoner"]


def test_the_recommended_pin_gets_a_bare_star(catalog, tmp_path):
    assert _model_lines(_ctx(catalog, tmp_path))["worker"].rstrip().endswith("★")


def test_a_current_pin_that_differs_only_hints(catalog, tmp_path):
    line = _model_lines(_ctx(catalog, tmp_path, pins={"worker": "claude-opus-5"}))["worker"]
    assert "★ claude-sonnet-5-5" in line and "⚠" not in line


def test_a_pin_missing_from_the_catalog_is_flagged_not_fatal(catalog, tmp_path):
    assert "⚠ unknown model  ★ claude-haiku-4-5" in _model_lines(_ctx(catalog, tmp_path))["scout"]


def test_u_moves_every_flagged_pin_to_its_star(catalog, tmp_path):
    ctx = _ctx(catalog, tmp_path)
    assert upgrade_flagged(ctx) == 2
    backend = ctx.scope_state().clis["claude"]
    assert backend.role_models == {"reasoner": "claude-opus-5-5", "worker": "claude-sonnet-5-5",
                                   "scout": "claude-haiku-4-5"}
    assert backend.role_efforts == {"reasoner": "high"}


def test_memory_and_cost_report_edit_the_working_copy(catalog, tmp_path, monkeypatch):
    monkeypatch.setattr("agent_notes.commands.wizard._detect_obsidian_vaults", lambda: [])
    ctx = _ctx(catalog, tmp_path)
    rows = _rows(ctx)
    rows["memory"].cycle(1)
    rows["toggle:cost-report"].cycle(1)
    assert ctx.state.memory.backend == "obsidian"
    assert ctx.plugins == {"cost-report": True}


def test_api_keys_show_status_only(catalog, tmp_path, monkeypatch):
    from agent_notes.services import credentials
    monkeypatch.setattr(credentials, "list_providers", lambda: ["anthropic"])
    monkeypatch.setattr(credentials, "is_configured", lambda name: name == "anthropic")
    assert _rows(_ctx(catalog, tmp_path))["api-keys"].lines() == ["anthropic ✓ · openai —"]


def test_an_entered_key_is_saved_and_never_shown(catalog, tmp_path, monkeypatch):
    from agent_notes.services import credentials
    saved = []
    monkeypatch.setattr(credentials, "list_providers", lambda: [])
    monkeypatch.setattr(credentials, "is_configured", lambda name: False)
    monkeypatch.setattr(credentials, "set_value", lambda *args: saved.append(args))
    ctx = _ctx(catalog, tmp_path, ENTER, *typed("sk-test-123"), ENTER, ENTER)
    _rows(ctx)["api-keys"].edit()
    assert saved == [("anthropic", "api_key", "sk-test-123")]
    assert all("sk-test-123" not in "\n".join(frame) for frame in ctx.ui.term.frames)


def test_an_empty_key_changes_nothing(catalog, tmp_path, monkeypatch):
    from agent_notes.services import credentials
    saved = []
    monkeypatch.setattr(credentials, "list_providers", lambda: [])
    monkeypatch.setattr(credentials, "is_configured", lambda name: False)
    monkeypatch.setattr(credentials, "set_value", lambda *args: saved.append(args))
    ctx = _ctx(catalog, tmp_path, ENTER, ENTER)
    _rows(ctx)["api-keys"].edit()
    assert saved == []


def test_settings_that_move_files_are_shown_read_only(catalog, tmp_path):
    row = _rows(_ctx(catalog, tmp_path))["reinstall"]
    assert row.focusable is False
    assert "install --reconfigure" in row.lines()[0]


def test_toggles_start_from_the_saved_plugin_config(monkeypatch):
    from agent_notes.registries import plugin_registry
    monkeypatch.setattr("agent_notes.services.user_config.load_user_config", lambda *a, **k: {})
    monkeypatch.setattr(plugin_registry.PluginRegistry, "enabled",
                        lambda self, cfg: [type("P", (), {"name": "cost-report"})()])
    assert config_review.enabled_toggles() == {"cost-report": True}
```


- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest -q tests/unit/commands/test_config_review_rows.py`
Expected: FAIL — `ImportError: cannot import name 'ConfigContext'`.

- [ ] **Step 3: Implement the rows**

Append to `agent_notes/commands/config_review.py` (and add `from dataclasses import dataclass`, `from typing import Any, Callable` to its imports):

```python
from ..domain.capability import KIND_BACKEND, KIND_PROVIDER, KIND_TOGGLE
from ..services.tui.screen import DIM, YELLOW
from ..services.tui.widgets import PickItem, Row
from .wizard.role_models import (
    Catalog, default_effort, edit_models, initial_model, role_line, roles_for, starred_model,
)


@dataclass
class ConfigContext:
    ui: Any
    state: Any                 # a working copy of state.json; saved only on `s`
    ref: InstallRef
    catalog: Catalog
    cli_registry: Any
    plugins: dict              # toggle capability -> on (staged)

    def scope_state(self):
        return self.ref.get(self.state)


def pin_flag(catalog, backend, role, model_id: str) -> str:
    """'★' when the pin is the recommendation; '★ <id>' when it differs;
    '⚠ deprecated  ★ <id>' or '⚠ unknown model  ★ <id>' when it should move."""
    star = starred_model(catalog, backend, role)
    recommended = f"★ {star.id}" if star is not None else ""
    model = catalog.get(model_id)
    if model is None:
        return f"⚠ unknown model  {recommended}".rstrip()
    if model.deprecated:
        return f"⚠ deprecated  {recommended}".rstrip()
    if star is not None and star.id == model_id:
        return "★"
    return recommended


def is_flagged(catalog, model_id: str) -> bool:
    model = catalog.get(model_id)
    return model is None or model.deprecated


def _agent_backends(ctx) -> list:
    backends = []
    for name in sorted(ctx.scope_state().clis):
        try:
            backend = ctx.cli_registry.get(name)
        except KeyError:
            continue
        if backend.supports("agents"):
            backends.append(backend)
    return backends


def config_models_rows(ctx: ConfigContext) -> list[Row]:
    style = ctx.ui.style
    backends = _agent_backends(ctx)
    rows = []
    for index, backend in enumerate(backends):
        state = ctx.scope_state().clis[backend.name]
        models, efforts = state.role_models, state.role_efforts

        def lines(backend=backend, models=models, efforts=efforts) -> list[str]:
            out = [backend.label] if len(backends) > 1 else []
            for role in roles_for(backend):
                if role.name in models:
                    flag = pin_flag(ctx.catalog, backend, role, models[role.name])
                    color = YELLOW if flag.startswith("⚠") else DIM
                    out.append(f"{role_line(role, models, efforts)}   {style(flag, color)}")
            return out or [style("no pins — the recommendation applies at build time", DIM)]

        rows.append(Row(f"models:{backend.name}", "Models" if index == 0 else "", lines,
                        edit=(lambda b=backend, m=models, e=efforts:
                              edit_models(ctx.ui, ctx.catalog, b, m, e)) if models else None))
    return rows


def upgrade_flagged(ctx: ConfigContext) -> int:
    """Move every ⚠ pin to its ★ model and default effort (the `u` key)."""
    moved = 0
    for backend in _agent_backends(ctx):
        state = ctx.scope_state().clis[backend.name]
        for role in roles_for(backend):
            model_id = state.role_models.get(role.name)
            if model_id is None or not is_flagged(ctx.catalog, model_id):
                continue
            target = (starred_model(ctx.catalog, backend, role)
                      or initial_model(ctx.catalog, backend, role))
            if target is None:
                continue
            state.role_models[role.name] = target.id
            effort = default_effort(backend, target, role)
            if effort:
                state.role_efforts[role.name] = effort
            else:
                state.role_efforts.pop(role.name, None)
            moved += 1
    return moved


def _provider_names() -> list[str]:
    from ..registries.provider_registry import default_provider_registry
    from ..services import credentials
    return sorted(set(default_provider_registry().names()) | set(credentials.list_providers()))


def api_keys_row(ctx: ConfigContext) -> Row:
    """Status only — a key value is never rendered, printed or logged (FR-018).
    Keys are written when entered: they live in the credentials file, outside
    state.json (spec 005 Correction 2)."""
    from ..services import credentials

    def lines() -> list[str]:
        return [" · ".join(f"{name} {'✓' if credentials.is_configured(name) else '—'}"
                           for name in _provider_names())]

    def edit() -> None:
        items = [PickItem(name, f"{name:<14} {'key stored' if credentials.is_configured(name) else 'no key'}")
                 for name in _provider_names()]
        name = ctx.ui.pick("API keys", items)
        if not name:
            return
        key = ctx.ui.text(f"API key · {name}", "Key", "", secret=True,
                          notes=["input hidden · empty keeps the current key"])
        if not key or not key.strip():
            return
        credentials.set_value(name, "api_key", key.strip())
        base = ctx.ui.text(f"API key · {name}", "base_url", "", notes=["optional · empty to skip"])
        if base and base.strip():
            credentials.set_value(name, "base_url", base.strip())

    return Row("api-keys", "API keys", lines, edit=edit)


def reinstall_row(ctx: ConfigContext) -> Row:
    def lines() -> list[str]:
        scope_state = ctx.scope_state()
        labels = []
        for name in sorted(scope_state.clis):
            try:
                labels.append(ctx.cli_registry.get(name).label)
            except KeyError:
                labels.append(name)
        return [f"{', '.join(labels)} · {scope_state.mode} · change with: install --reconfigure"]

    return Row("reinstall", "Install", lines, focusable=False)


def config_rows(ctx: ConfigContext, *, part: str = "all", capabilities=None) -> Callable[[], list[Row]]:
    """Config-mode rows. *part*: "install" (Models and the read-only line),
    "global" (Memory, toggles, API keys), or "all"."""
    from .wizard.capabilities import default_capability_registry
    registry = capabilities if capabilities is not None else default_capability_registry()

    def from_kind(kind) -> list[Row]:
        out = []
        for cap in registry.by_kind(kind):
            behaviour = registry.get(cap.name)
            if behaviour.config_row is not None:
                out += behaviour.config_row(ctx)
        return out

    def rows() -> list[Row]:
        out: list[Row] = []
        if part in ("all", "install"):
            out += from_kind(KIND_BACKEND)
        if part in ("all", "global"):
            out += from_kind(KIND_PROVIDER) + from_kind(KIND_TOGGLE)
            out.append(api_keys_row(ctx))
        if part in ("all", "install"):
            out.append(reinstall_row(ctx))
        return out

    return rows


def enabled_toggles(capabilities=None) -> dict[str, bool]:
    """Each toggle capability's saved on/off, from the plugin config."""
    from ..registries.plugin_registry import default_plugin_registry
    from ..services.user_config import load_user_config
    from .wizard.capabilities import default_capability_registry
    registry = capabilities if capabilities is not None else default_capability_registry()
    on = {plugin.name for plugin in default_plugin_registry().enabled(load_user_config())}
    return {cap.name: cap.name in on for cap in registry.by_kind(KIND_TOGGLE)}
```

In `agent_notes/commands/wizard/capabilities.py`, add the config rows and register them:

```python
def _backends_config_rows(ctx) -> list:
    from ..config_review import config_models_rows
    return config_models_rows(ctx)


def _memory_config_rows(ctx) -> list:
    from .review import memory_row
    return [memory_row(ctx.ui, ctx.state.memory)]


def _cost_report_config_rows(ctx) -> list:
    from .review import toggle_row
    return [toggle_row(ctx.ui, "cost-report", "Cost report", ctx.plugins)]


def _build_registry() -> CapabilityRegistry:
    reg = CapabilityRegistry()
    reg.register(BACKENDS, row=_backends_rows, config_row=_backends_config_rows)
    reg.register(COST_REPORT, row=_cost_report_rows, config_row=_cost_report_config_rows)
    reg.register(MEMORY, row=_memory_rows, config_row=_memory_config_rows)
    return reg
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest -q tests/unit/commands/test_config_review_rows.py`
Expected: 13 passed.

- [ ] **Step 5: Commit**

```bash
git add agent_notes/commands/config_review.py agent_notes/commands/wizard/capabilities.py tests/unit/commands/test_config_review_rows.py
git commit -m "feat(config): review rows with flagged pins, memory, toggles, API keys"
```

---

### Task 13: Config session — stage, save once, quit safely

**Files:**
- Modify: `agent_notes/commands/config_review.py` (append)
- Modify: `agent_notes/commands/config.py` (`interactive_config` delegates; delete `_wizard_role_model`, `_wizard_role_effort`, `_wizard_skills`, `_prompt_target_clis`)
- Test: `tests/unit/commands/test_config_review_flow.py`
- Test (edit): `tests/functional/commands/test_config_command.py::test_quit_does_nothing`, `tests/unit/commands/test_config_wizard_non_fatal.py`

**Interfaces:**
- Consumes: Tasks 11–12; `state_store.load_state`, `record_install_state`; `commands.regenerate.regenerate`; `commands.plugins.enable_plugin` / `disable_plugin`.
- Produces: `describe_changes(original, working, ref, plugins_before, plugins_after) -> list[str]`; `apply_changes(working, ref, plugins_before, plugins_after)`; `interactive_config(session_factory=None, cwd=None)`; `CONFIG_HINTS`; `SUBCOMMANDS`.

- [ ] **Step 1: Write the failing tests**

`tests/unit/commands/test_config_review_flow.py`:

```python
"""`agent-notes config` session (spec 005 FR-014, FR-016, FR-017, SC-005, SC-007)."""
from unittest.mock import MagicMock

import pytest

from agent_notes.commands import config_review
from agent_notes.domain.state import BackendState, ScopeState, State
from agent_notes.services import state_store
from agent_notes.services.tui.keys import DOWN, ENTER, ESCAPE, RIGHT, TAB
from tests.unit.tui.fakes import tui_session


@pytest.fixture
def env(tmp_path, monkeypatch):
    """A saved state with one local install in tmp_path/project, and every
    write path replaced by a recorder."""
    project = tmp_path / "project"
    project.mkdir()
    state = State(local_installs={str(project.resolve()): ScopeState(clis={"claude": BackendState(
        role_models={"reasoner": "claude-opus-4-6", "worker": "claude-sonnet-5-5",
                     "scout": "claude-haiku-4-5"},
        role_efforts={"reasoner": "high", "worker": "medium"})})})
    monkeypatch.setattr(state_store, "load_state", lambda: state)
    mocks = {name: MagicMock() for name in ("record", "regenerate", "enable", "disable")}
    monkeypatch.setattr("agent_notes.services.state_store.record_install_state", mocks["record"])
    monkeypatch.setattr("agent_notes.commands.regenerate.regenerate", mocks["regenerate"])
    monkeypatch.setattr("agent_notes.commands.plugins.enable_plugin", mocks["enable"])
    monkeypatch.setattr("agent_notes.commands.plugins.disable_plugin", mocks["disable"])
    monkeypatch.setattr(config_review, "enabled_toggles", lambda *a: {"cost-report": False})
    monkeypatch.setattr("agent_notes.commands.wizard._detect_obsidian_vaults", lambda: [])
    mocks["project"], mocks["state"] = project, state
    return mocks


def _run(env, *keys, cwd=None):
    ui = tui_session(*keys)
    config_review.interactive_config(session_factory=lambda: ui, cwd=cwd or env["project"])
    return ui


def test_quitting_without_changes_writes_nothing(env):
    _run(env, "q")
    env["record"].assert_not_called()
    env["regenerate"].assert_not_called()


def test_three_edits_save_with_one_write_and_one_regenerate(env):
    # Models row is focused: u, then Memory → Obsidian, Cost report → on.
    ui = _run(env, "u", DOWN, RIGHT, DOWN, RIGHT, "s", ENTER)
    env["record"].assert_called_once()
    saved = env["record"].call_args.args[0]
    install = saved.local_installs[str(env["project"].resolve())]
    assert install.clis["claude"].role_models["reasoner"] == "claude-opus-5-5"
    assert saved.memory.backend == "obsidian"
    env["regenerate"].assert_called_once_with(scope="local", project_path=env["project"].resolve(),
                                              profile_label="")
    env["enable"].assert_called_once_with("cost-report")
    shown = "\n".join("\n".join(frame) for frame in ui.term.frames)
    assert "claude reasoner: claude-opus-4-6 → claude-opus-5-5" in shown
    assert "cost-report: off → on" in shown
    assert env["state"].memory.backend == "local"  # the loaded state itself is untouched


def test_quit_with_staged_edits_asks_and_escape_keeps_editing(env):
    ui = _run(env, "u", "q", ESCAPE, "q", ENTER)
    env["record"].assert_not_called()
    assert any("Discard 1 change?" in "\n".join(frame) for frame in ui.term.frames)


def test_tab_switches_installs_only_without_staged_edits(env, tmp_path):
    other = tmp_path / "other"
    other.mkdir()
    env["state"].local_installs[str(other.resolve())] = ScopeState(clis={"claude": BackendState()})
    # TAB to the other install and back, stage an edit, then TAB is refused.
    ui = _run(env, TAB, TAB, "u", TAB, "q", ENTER)
    frames = ["\n".join(frame) for frame in ui.term.frames]
    assert "other" in frames[1].splitlines()[0]
    assert "other" not in frames[2].splitlines()[0]
    assert any("save or discard changes before switching" in frame for frame in frames)


def test_only_local_installs_elsewhere_ask_which_one(env, tmp_path):
    second = tmp_path / "second"
    second.mkdir()
    env["state"].local_installs[str(second.resolve())] = ScopeState(clis={"claude": BackendState()})
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    ui = _run(env, ENTER, "q", cwd=elsewhere)
    assert "Which install?" in "\n".join(ui.term.frames[0])


def test_a_failed_save_says_so_and_stays_open(env):
    env["regenerate"].side_effect = RuntimeError("boom")
    ui = _run(env, "u", "s", ENTER, "q", ENTER)
    assert any("Save failed: boom" in "\n".join(frame) for frame in ui.term.frames)


def test_no_terminal_prints_the_settings_and_the_subcommands(env, capsys):
    config_review.interactive_config(session_factory=lambda: None, cwd=env["project"])
    out = capsys.readouterr().out
    assert "Current configuration:" in out   # `show` ran (its layout is Task 14's)
    assert "agent-notes config show | role-model" in out
    env["record"].assert_not_called()


def test_no_installs_exits_1(env, capsys):
    env["state"].local_installs.clear()
    with pytest.raises(SystemExit) as exit_info:
        config_review.interactive_config(session_factory=lambda: None, cwd=env["project"])
    assert exit_info.value.code == 1
    assert "No installation found — run agent-notes install" in capsys.readouterr().out
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest -q tests/unit/commands/test_config_review_flow.py`
Expected: FAIL — `AttributeError: module 'agent_notes.commands.config_review' has no attribute 'interactive_config'`.

- [ ] **Step 3: Implement the session**

Append to `agent_notes/commands/config_review.py` (add `import contextlib, copy, io, sys` to the imports):

```python
from ..services.tui.keys import TAB
from ..services.tui.widgets import CANCEL, DONE, ReviewForm

CONFIG_HINTS = "↑↓ move  ⏎ edit  ←→ change  u use ★  tab next install  s save  q quit"
SUBCOMMANDS = ("show", "role-model", "role-effort", "role-agent", "provider", "providers",
               "memory", "cost-report")


def _changes_text(count: int) -> str:
    return f"{count} change{'' if count == 1 else 's'}"


def describe_changes(original, working, ref: InstallRef, plugins_before: dict,
                     plugins_after: dict) -> list[str]:
    """One line per staged edit: `<cli> <role>: <old> → <new>` (FR-017)."""
    from .wizard.review import memory_label
    lines = []
    old_scope, new_scope = ref.get(original), ref.get(working)
    if old_scope is not None and new_scope is not None:
        for cli in sorted(new_scope.clis):
            old, new = old_scope.clis.get(cli), new_scope.clis[cli]
            if old is None:
                continue
            for field, suffix in (("role_models", ""), ("role_efforts", " effort")):
                before, after = getattr(old, field), getattr(new, field)
                for role in sorted(set(before) | set(after)):
                    if before.get(role) != after.get(role):
                        lines.append(f"{cli} {role}{suffix}: {before.get(role) or '—'} → "
                                     f"{after.get(role) or '—'}")
    if original.memory != working.memory:
        lines.append(f"memory: {memory_label(original.memory)} → {memory_label(working.memory)}")
    for name in sorted(set(plugins_before) | set(plugins_after)):
        before, after = bool(plugins_before.get(name)), bool(plugins_after.get(name))
        if before != after:
            lines.append(f"{name}: {'on' if before else 'off'} → {'on' if after else 'off'}")
    return lines


@contextlib.contextmanager
def _quiet():
    sink = io.StringIO()
    with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
        yield


def apply_changes(working, ref: InstallRef, plugins_before: dict, plugins_after: dict) -> None:
    """One state write and one regenerate — of the edited install, not
    whatever regenerate would auto-detect (spec 005 Correction 3)."""
    from ..services.state_store import record_install_state
    from .plugins import disable_plugin, enable_plugin
    from .regenerate import regenerate
    with _quiet():
        record_install_state(working)
        for name in sorted(plugins_after):
            if bool(plugins_after[name]) != bool(plugins_before.get(name)):
                (enable_plugin if plugins_after[name] else disable_plugin)(name)
        regenerate(scope=ref.scope, project_path=ref.project_path, profile_label=ref.profile_label)


def interactive_config(session_factory=None, cwd: Optional[Path] = None) -> None:
    """`agent-notes config` with no action (spec 005 FR-014)."""
    from ..services.state_store import load_state
    from ..services.tui.session import open_session
    state = load_state()
    refs = list_installs(state) if state is not None else []
    if not refs:
        print("No installation found — run agent-notes install")
        sys.exit(1)
    session = (session_factory or open_session)()
    if session is None:
        from .config import show
        show(state)
        print("\nChange settings with: agent-notes config " + " | ".join(SUBCOMMANDS))
        return
    with session as ui:
        message = _config_review(ui, state, refs, Path(cwd) if cwd else Path.cwd())
    if message:
        print(message)


def _config_review(ui, state, refs: list[InstallRef], cwd: Path) -> str:
    from ..config import get_version
    from ..registries.cli_registry import load_registry
    ref = default_install(refs, cwd)
    if ref is None:
        ref = ui.pick("Which install?", [PickItem(r, r.label(), dim=r.missing) for r in refs])
        if ref is None:
            return ""
    working = copy.deepcopy(state)
    plugins_before = enabled_toggles()
    ctx = ConfigContext(ui, working, ref, Catalog(), load_registry(), dict(plugins_before))

    def changes() -> list[str]:
        return describe_changes(state, working, ctx.ref, plugins_before, ctx.plugins)

    form = ReviewForm(f"AgentNotes {get_version()} · config", config_rows(ctx),
                      context=ref.label(), hints=CONFIG_HINTS, default_command="s",
                      default_label="save", style=ui.style,
                      status=lambda: _changes_text(len(changes())) if changes() else "")

    def save():
        diff = changes()
        if not diff:
            form.message = "no changes to save"
            return None
        if not ui.confirm(form, f"Apply {_changes_text(len(diff))}?", diff):
            return None
        ui.progress(form, "Saving…")
        try:
            apply_changes(working, ctx.ref, plugins_before, ctx.plugins)
        except (Exception, SystemExit) as e:
            form.message = f"Save failed: {e}"
            return None
        form.value = f"Saved {_changes_text(len(diff))}. Restart your AI CLI to pick up changes."
        return DONE

    def quit_():
        count = len(changes())
        if count and not ui.confirm(form, f"Discard {_changes_text(count)}?"):
            return None
        return CANCEL

    def next_install():
        if len(refs) < 2:
            return None
        if changes():
            form.message = "save or discard changes before switching"
            return None
        ctx.ref = refs[(refs.index(ctx.ref) + 1) % len(refs)]
        form.context = ctx.ref.label()
        return None

    def use_recommended():
        moved = upgrade_flagged(ctx)
        form.message = (f"{moved} pin{'' if moved == 1 else 's'} moved to ★" if moved
                        else "nothing flagged")
        return None

    form.commands.update({"s": save, "q": quit_, TAB: next_install, "u": use_recommended})
    return form.value if ui.form(form) == DONE else ""
```

- [ ] **Step 4: Point `config.py` at it and delete the numbered menu**

In `agent_notes/commands/config.py`, replace the body of `interactive_config` with:

```python
def interactive_config() -> None:
    """`agent-notes config` with no action: the review screen (spec 005)."""
    from .config_review import interactive_config as review
    review()
```

Delete `_wizard_role_model`, `_wizard_role_effort`, `_wizard_skills` and `_prompt_target_clis`. Keep `_wizard_memory`, `_wizard_providers`, `_wizard_provider_status`, `interactive_config_memory`: `config memory` and `config providers` still use them (FR-019).

- [ ] **Step 5: Update the old config tests**

- `tests/unit/commands/test_config_wizard_non_fatal.py`: delete `TestUnknownCliStaysInteractive` and `TestUnknownModelStaysInteractive` and the `_answers` helper they use; keep `TestScriptablePathsStayFatal`.
- `tests/functional/commands/test_config_command.py`: replace `test_quit_does_nothing` with:

```python
def test_quit_does_nothing(state_file):
    """The config review quits without touching state.json."""
    from agent_notes.commands import config_review
    from tests.unit.tui.fakes import tui_session

    original = state_file.read_text()
    with _patch_state_file(state_file):
        config_review.interactive_config(session_factory=lambda: tui_session("q"))
    assert state_file.read_text() == original
```

- [ ] **Step 6: Run the tests**

Run: `uv run pytest -q tests/unit/commands/test_config_review_flow.py tests/unit/commands/test_config_wizard_non_fatal.py tests/functional/commands/test_config_command.py`
Expected: all pass.

Run: `grep -rnE "_wizard_role_model|_wizard_role_effort|_wizard_skills|_prompt_target_clis" agent_notes tests --include='*.py'`
Expected: no output.

- [ ] **Step 7: Commit**

```bash
git add -A agent_notes/commands/config.py agent_notes/commands/config_review.py tests/unit/commands tests/functional/commands
git commit -m "feat(config): review screen with staged edits, one save, safe quit"
```

---

### Task 14: `config show` in the review layout

**Files:**
- Modify: `agent_notes/commands/config_review.py` (append `render_show`)
- Modify: `agent_notes/commands/config.py` (`show`)
- Test: `tests/unit/commands/test_config_review_rows.py` (add), `tests/functional/commands/test_config_command.py::test_show_prints_current_state`

**Interfaces:**
- Consumes: Tasks 11–12.
- Produces: `render_show(state, width=100, style=None) -> list[str]`.

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/commands/test_config_review_rows.py`:

```python
def test_show_prints_shared_settings_once_then_each_install(catalog, tmp_path, monkeypatch):
    from agent_notes.commands.config_review import render_show
    monkeypatch.setattr(config_review, "enabled_toggles", lambda *a: {"cost-report": False})
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir()
    b.mkdir()
    pins = BackendState(role_models={"reasoner": "claude-opus-4-6"})
    state = State(local_installs={str(a): ScopeState(clis={"claude": pins}),
                                  str(b): ScopeState(clis={"claude": BackendState()})})
    text = "\n".join(render_show(state, 120))
    assert text.count("Memory") == 1 and text.count("Cost report") == 1
    assert "built-in" in text
    assert "⚠ deprecated  ★ claude-opus-5-5" in text
    assert "local · " in text and "no pins" in text
    assert "›" not in text and "↑↓" not in text
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest -q tests/unit/commands/test_config_review_rows.py -k show_prints`
Expected: FAIL — `ImportError: cannot import name 'render_show'`.

- [ ] **Step 3: Implement**

Append to `agent_notes/commands/config_review.py`:

```python
def render_show(state, width: int = 100, style=None) -> list[str]:
    """`config show`: the config screen without cursor or footer — shared
    settings once, then each install (spec 005 FR-020)."""
    from types import SimpleNamespace
    from ..registries.cli_registry import load_registry
    from ..services.tui.screen import BOLD, Style
    style = style or Style(False)
    refs = list_installs(state)
    if not refs:
        return ["(no installation found)"]
    ui = SimpleNamespace(style=style)
    catalog, clis, plugins = Catalog(), load_registry(), enabled_toggles()

    def static(ref, part) -> list[str]:
        ctx = ConfigContext(ui, state, ref, catalog, clis, plugins)
        return ReviewForm("", config_rows(ctx, part=part), style=style).render(
            width, 10_000, chrome=False)

    lines = static(refs[0], "global")
    for ref in refs:
        lines += ["", style(ref.label(), BOLD)] + static(ref, "install")
    return lines
```

In `agent_notes/commands/config.py`, replace the body of `show` with:

```python
def show(state=None) -> None:
    """Print the current configuration in the config screen's layout (FR-020)."""
    import shutil
    from .config_review import render_show
    from ..services.tui.screen import Style, color_enabled
    if state is None:
        state = _load_state()
    print("Current configuration:")
    width = shutil.get_terminal_size((100, 24)).columns
    for line in render_show(state, width, Style(color_enabled())):
        print(line)
```

- [ ] **Step 4: Update the functional `show` test**

In `tests/functional/commands/test_config_command.py`, change `test_show_prints_current_state` to pin a role Claude Code renders (an orchestrator pin is inert there and the review leaves it out):

```python
def test_show_prints_current_state(capsys, tmp_path):
    from agent_notes.commands.config import show

    sf = tmp_path / "state.json"
    sf.write_text(json.dumps(_minimal_state_dict(role="worker")))
    with _patch_state_file(sf):
        show()

    out = capsys.readouterr().out
    assert "worker" in out
    assert "claude-sonnet-4-6" in out
```

- [ ] **Step 5: Run the tests**

Run: `uv run pytest -q tests/unit/commands/test_config_review_rows.py tests/functional/commands/test_config_command.py`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add agent_notes/commands/config.py agent_notes/commands/config_review.py tests/unit/commands/test_config_review_rows.py tests/functional/commands/test_config_command.py
git commit -m "feat(config): show uses the review layout and flags outdated pins"
```

---

### Task 15: Docs, changelog, and the spec's verification

**Files:**
- Modify: `README.md` (install and config sections), `CHANGELOG.md` (`[Unreleased]`), `specs/005-install-and-config-review-screen/spec.md` (status, `## Verification`)

- [ ] **Step 1: README**

In the install section, replace the description of the step-by-step wizard with: `agent-notes install` opens one review screen with every setting pre-filled; `i` installs, `⏎` edits a row, `←→` changes simple values, `q` quits; small terminals get numbered prompts; with no terminal the recommended setup installs without prompts. In the config section: `agent-notes config` opens the same screen on an existing install (`u` moves deprecated pins to ★, `tab` switches installs, `s` saves everything at once); the scriptable subcommands are unchanged.

- [ ] **Step 2: CHANGELOG**

Under `## [Unreleased]`: **Changed** — the install wizard and the interactive `config` menu are replaced by one review screen (what it does, keys, line mode, no-terminal behavior; piped answers to `install` are no longer read — it installs the recommended setup); `config show` uses the same layout and flags outdated pins. **Fixed** — Esc no longer confirms a choice, and a bare Esc no longer waits for two more keys; `NO_COLOR` is honoured; `agent-notes config` no longer exits with "No local installation found" when run outside a project with only local installs; config saves regenerate the install that was edited.

- [ ] **Step 3: Measure the success criteria**

Run each and record the numbers in a `## Verification` section of the spec:

- SC-001 / SC-002 / SC-009: `uv run --with pexpect pytest -q tests/functional/test_install_review_pty.py` (one review screen, `i` + ⏎, no line over 80, no build log).
- SC-003 / SC-004: `uv run pytest -q tests/unit/commands/test_review_role_models.py -k "star_is or effort_options_match"`.
- SC-005 / SC-007: `uv run pytest -q tests/unit/commands/test_config_review_installs.py tests/unit/commands/test_config_review_flow.py`.
- SC-006: `uv run pytest -q tests/unit/tui/test_tui_keys.py -k escape` plus the Esc tests in `test_tui_review_form.py`, `test_tui_picker.py`, `test_tui_inputs.py`.
- SC-008: `uv run pytest -q tests/unit/tui/test_tui_screen.py -k no_color`.
- SC-010: `uv run pytest -q` (record the count) and `git diff develop -- pyproject.toml` (expect no change to `dependencies`).
- Mutation checks, one at a time, each restored after: make `decode` wait for two bytes after ESC → the 100 ms test fails; make `ReviewForm.handle` return DONE on ESCAPE always → `test_escape_does_nothing_on_the_top_level_review` fails; make `effort_options` skip the CLI subset → `test_effort_options_match_the_config_role_effort_checks` fails; make `apply_changes` call `regenerate()` without arguments → `test_three_edits_save_with_one_write_and_one_regenerate` fails.

- [ ] **Step 4: Mark the spec implemented and commit**

Set `**Status**: Implemented <date>` in the spec.

```bash
git add README.md CHANGELOG.md specs/005-install-and-config-review-screen/spec.md
git commit -m "docs(specs): spec 005 verification; review screen in README and CHANGELOG"
```
