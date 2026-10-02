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
