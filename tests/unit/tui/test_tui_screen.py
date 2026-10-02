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
