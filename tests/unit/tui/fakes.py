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
