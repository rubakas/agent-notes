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
