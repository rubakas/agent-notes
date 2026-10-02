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
