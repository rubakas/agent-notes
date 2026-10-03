"""The diagnostics checks run unmocked against a tmp dist and a tmp HOME.

Every doctor test elsewhere mocks the check_* functions, so a broken import
inside them (the 2026-07 move of the installer module) went unseen until a
user ran `doctor`."""
from pathlib import Path

import pytest

import agent_notes.config as config
from agent_notes.domain.state import BackendState, InstalledItem, ScopeState
from agent_notes.registries.cli_registry import load_registry
from agent_notes.services.diagnostics._checks import (
    _find_dist_source,
    check_stale,
    expected_paths_for_install,
)


@pytest.fixture
def world(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    dist = tmp_path / "dist"
    (dist / "claude" / "agents").mkdir(parents=True)
    (dist / "claude" / "commands").mkdir()
    (dist / "rules").mkdir()
    (dist / "skills" / "alpha").mkdir(parents=True)
    (dist / "claude" / "agents" / "keep.md").write_text("keep")
    (dist / "claude" / "commands" / "cmd.md").write_text("cmd")
    (dist / "claude" / "CLAUDE.md").write_text("config")
    (dist / "rules" / "rule.md").write_text("rule")
    (dist / "skills" / "alpha" / "SKILL.md").write_text("skill")
    monkeypatch.setattr(config, "DIST_DIR", dist)
    monkeypatch.setattr(config, "DIST_RULES_DIR", dist / "rules")
    monkeypatch.setattr(config, "DIST_SKILLS_DIR", dist / "skills")
    monkeypatch.setattr(config, "AGENTS_HOME", tmp_path / "agents_home")
    return home, dist


def _item(target: Path) -> InstalledItem:
    return InstalledItem(sha="x", target=str(target), mode="symlink")


def test_check_stale_flags_only_the_item_whose_source_is_gone(world):
    home, _dist = world
    installed = {"agents": {"keep.md": _item(home / ".claude/agents/keep.md"),
                            "gone.md": _item(home / ".claude/agents/gone.md")}}
    scope_state = ScopeState(clis={"claude": BackendState(installed=installed)})
    issues, fixes = [], []

    check_stale("global", scope_state, load_registry(), issues, fixes)

    assert [i.file for i in issues] == [str(home / ".claude/agents/gone.md")]
    assert [i.type for i in issues] == ["stale"]
    assert [f.action for f in fixes] == ["DELETE"]


def test_expected_paths_cover_every_component_in_the_tmp_dist(world):
    home, dist = world
    claude = {(component, src.name, dst)
              for src, dst, backend, component in expected_paths_for_install(load_registry(), "global")
              if backend == "claude"}

    assert claude >= {
        ("agents", "keep.md", home / ".claude/agents/keep.md"),
        ("commands", "cmd.md", home / ".claude/commands/cmd.md"),
        ("config", "CLAUDE.md", home / ".claude/CLAUDE.md"),
        ("rules", "rule.md", home / ".claude/rules/rule.md"),
        ("skills", "alpha", home / ".claude/skills/alpha"),
    }


@pytest.mark.parametrize("relative, source", [
    (".claude/agents/keep.md", "claude/agents/keep.md"),
    (".claude/commands/cmd.md", "claude/commands/cmd.md"),
    (".claude/rules/rule.md", "rules/rule.md"),
    (".claude/skills/alpha", "skills/alpha"),
    (".claude/CLAUDE.md", "claude/CLAUDE.md"),
])
def test_find_dist_source_maps_an_installed_path_back_to_dist(world, relative, source):
    home, dist = world

    assert _find_dist_source(home / relative, "global") == dist / source


def test_find_dist_source_is_none_for_an_unknown_file(world):
    home, _dist = world

    assert _find_dist_source(home / ".claude/agents/nothing.md", "global") is None
