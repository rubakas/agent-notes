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


def test_post_install_summary_uses_the_same_memory_names():
    from agent_notes.commands.wizard.execute import _memory_line
    assert _memory_line("local", "/m") == "built-in  →  /m"
    assert _memory_line("obsidian", "/v/projects") == "Obsidian  →  /v/projects"
