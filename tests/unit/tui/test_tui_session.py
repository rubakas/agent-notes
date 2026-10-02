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
