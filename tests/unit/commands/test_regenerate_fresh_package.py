"""regenerate after a fresh package install (spec 006).

A pipx reinstall ships a package with no rendered dist/, so every installed link
dangles until something renders again. regenerate must render and place every
component itself, say so when it cannot, and leave the install's CLIs alone."""
import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

import agent_notes.config as config
import agent_notes.commands.build as build_module
from agent_notes.commands.regenerate import regenerate
from agent_notes.registries.cli_registry import load_registry
from agent_notes.services.state_store import load_state


@pytest.fixture
def package(tmp_path, monkeypatch):
    """A tmp HOME, a claude-only global install, and an EMPTY dist for the package.

    The root directory is named 'claude-501' so a path-substring match on the
    CLI name would hit every file."""
    root = tmp_path / "claude-501"
    home, pkg, xdg = root / "home", root / "pkg", root / "xdg"
    home.mkdir(parents=True)
    pkg.mkdir()
    dist = pkg / "dist"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
    monkeypatch.setattr(config, "PKG_DIR", pkg)
    monkeypatch.setattr(config, "DIST_DIR", dist)
    monkeypatch.setattr(build_module, "DIST_DIR", dist)
    monkeypatch.setattr(config, "DIST_RULES_DIR", dist / "rules")
    monkeypatch.setattr(config, "DIST_SKILLS_DIR", dist / "skills")
    monkeypatch.setattr(config, "DIST_CLAUDE_DIR", dist / "claude")
    monkeypatch.setattr(config, "DIST_OPENCODE_DIR", dist / "opencode")
    monkeypatch.setattr(config, "DIST_GITHUB_DIR", dist / "copilot")
    monkeypatch.setattr(config, "AGENTS_HOME", root / "agents_home")
    state = xdg / "agent-notes" / "state.json"
    state.parent.mkdir(parents=True)
    state.write_text(json.dumps({
        "source_path": "/tmp/repo",
        "source_commit": "abc123",
        "global": {
            "installed_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-01T00:00:00Z",
            "mode": "symlink",
            "clis": {"claude": {"role_models": {}, "installed": {}}},
        },
        "local": {},
        "memory": {"backend": "local", "path": ""},
    }))
    return home, dist


def _dangling(root: Path):
    return [p for p in root.rglob("*") if p.is_symlink() and not p.exists()]


def test_regenerate_on_an_empty_dist_renders_and_places_everything(package):
    home, dist = package
    assert not dist.exists()

    regenerate(scope="global")

    claude = home / ".claude"
    assert (claude / "CLAUDE.md").exists()
    for component, pattern in (("rules", "*.md"), ("skills", "*"), ("commands", "*.md"),
                               ("agents", "*.md")):
        placed = list((claude / component).glob(pattern))
        assert placed, f"nothing placed under {claude / component}"
        assert all(p.exists() for p in placed), f"dangling link under {claude / component}"
    assert _dangling(claude) == []
    # Placed links point into the tmp dist this run rendered, not at the real one.
    assert (claude / "CLAUDE.md").resolve().is_relative_to(dist.resolve())
    skill = next((claude / "skills").iterdir())
    assert skill.resolve().is_relative_to(dist.resolve())


def test_a_component_with_no_rendered_source_is_an_error_not_a_checkmark(package, capsys):
    build_not_run = patch("agent_notes.commands.build.build")

    with build_not_run, pytest.raises(SystemExit) as exit_info:
        regenerate(scope="global")

    # A string code: config's quiet_output hides prints but carries the reason.
    assert isinstance(exit_info.value.code, str)
    assert "Claude Code" in exit_info.value.code and "agents" in exit_info.value.code
    assert "✓ skills" not in capsys.readouterr().out


def test_the_agent_count_is_the_agents_placed_not_a_path_substring(package, capsys):
    _home, dist = package

    regenerate(scope="global")

    claude_agents = list((dist / "claude").joinpath("agents").glob("*.md"))
    every_cli_agents = [p for p in dist.glob("*/agents/*") if p.is_file()]
    assert 0 < len(claude_agents) < len(every_cli_agents)
    out = capsys.readouterr().out
    assert f"✓ {len(claude_agents)} agents regenerated" in out


def test_regenerate_keeps_exactly_the_clis_of_the_install(package):
    home, _dist = package
    build_module.build()

    regenerate(scope="global")
    regenerate(scope="global")

    scope_state = load_state().global_install
    assert set(scope_state.clis) == {"claude"}
    installed = scope_state.clis["claude"].installed
    assert installed.get("skills") and installed.get("rules") and installed.get("config")
    assert not (home / ".config" / "opencode").exists()
    assert not (home / ".codex").exists()


def test_a_full_install_regenerates_without_dangling_links_in_any_cli(package):
    """codex, opencode and copilot lack rules/skills/commands (no target for
    them): regenerate skips what a CLI does not support instead of failing."""
    home, dist = package
    state_file = Path(os.environ["XDG_CONFIG_HOME"]) / "agent-notes" / "state.json"
    state = json.loads(state_file.read_text())
    state["global"]["clis"] = {name: {"role_models": {}, "installed": {}}
                               for name in ("claude", "codex", "opencode", "copilot")}
    state_file.write_text(json.dumps(state))

    regenerate(scope="global")

    registry = load_registry()
    for name in ("claude", "codex", "opencode", "copilot"):
        backend = registry.get(name)
        assert backend.global_home.is_relative_to(home)
        assert _dangling(backend.global_home) == [], name
        assert (backend.global_home / backend.layout["config"]).exists(), name
        if backend.supports("agents"):
            extension = backend.layout.get("agent_extension", "md")
            rendered = list((dist / name / "agents").glob(f"*.{extension}"))
            placed = list((backend.global_home / "agents").glob(f"*.{extension}"))
            assert rendered and len(placed) == len(rendered), name
