from agent_notes.services.tui.keys import BACKSPACE, DOWN, ENTER, ESCAPE, SPACE, TAB
from agent_notes.services.tui.screen import visible_len
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


def test_secret_text_is_never_rendered_nor_its_length():
    field = TextField("API key", "Key", secret=True)
    assert "•" not in "\n".join(field.render(80, 24))
    frames = []
    for key in typed("sk-secret-123"):
        field.handle(key)
        frames.append(field.render(80, 24)[2])
    assert all("secret" not in frame for frame in frames)
    assert len(set(frames)) == 1          # one placeholder, whatever the length
    assert "••••••••" in frames[-1]


def test_a_long_value_shows_its_tail_and_the_cursor():
    value = "/".join(f"dir{i:02d}" for i in range(24))   # 119 characters
    field = TextField("Vault", "Path", value)
    line = field.render(80, 24)[2]
    assert visible_len(line) <= 80
    assert line.endswith("dir22/dir23▏")
    assert "   Path  …" in line


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


def test_long_checklists_scroll_and_keep_the_footer():
    items = [(f"skill-{i}", f"s{i}") for i in range(30)]
    checklist = Checklist("Skills", items, set())
    for _ in range(25):
        checklist.handle(DOWN)
    lines = checklist.render(80, 12)
    assert len(lines) <= 12
    assert any("skill-25" in line for line in lines)
    assert lines[-1].startswith(" ↑↓ move")
    assert any("more" in line for line in lines)


def test_complete_path_handles_brackets_in_names(tmp_path):
    (tmp_path / "Notes [work]").mkdir()
    assert complete_path(str(tmp_path / "Notes [work]")) == str(tmp_path / "Notes [work]") + "/"


def test_a_title_one_column_short_of_the_width_is_not_cut():
    title = "T" * 38
    first = Checklist(title, SKILLS, set()).render(40, 10)[0]
    assert first.rstrip() == f" {title}" and "…" not in first
