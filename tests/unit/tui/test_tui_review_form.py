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
    assert all(line.startswith("   ") for line in lines)
    assert not any("↑↓" in line for line in lines)


def test_a_message_takes_the_whole_footer_line():
    hints = "↑↓ move   ⏎ edit   ←→ change   i install   q quit"
    form, _ = _form()
    form.hints = hints
    message = "Build failed: disk full; restore failed: locked — run agent-notes regen"
    assert len(message) >= 70
    form.message = message
    last = form.render(80, 24)[-1]
    assert message in last and "…" not in last and "↑↓ move" not in last
    form.handle(DOWN)
    assert "↑↓ move" in form.render(80, 24)[-1]
