"""The manifest records what the install placed, not what dist/ happens to hold
(spec 007 FR-A05, R2). Cleanup can only remove what the manifest lists."""
import json
from pathlib import Path
from unittest.mock import patch

import pytest

import agent_notes.config as config
import agent_notes.commands.build as build_module
import agent_notes.commands.wizard.execute as wizard_execute
from agent_notes.commands.install import install
from agent_notes.commands.wizard.execute import _execute_install
from agent_notes.services.install_ownership import is_ours, tree_sha
from agent_notes.services.state_store import load_state, state_file


@pytest.fixture
def world(tmp_path, monkeypatch):
    """A tmp HOME and project, and a dist rendered from the real sources into tmp."""
    root = tmp_path / "claude-501"
    home, pkg, xdg, project = root / "home", root / "pkg", root / "xdg", root / "project"
    for d in (home, pkg, project):
        d.mkdir(parents=True)
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
    # The wizard binds both by value at import: without these it writes to the real ~/.agents.
    monkeypatch.setattr(wizard_execute, "AGENTS_HOME", root / "agents_home")
    monkeypatch.setattr(wizard_execute, "PKG_DIR", pkg)
    monkeypatch.chdir(project)
    build_module.build()
    return home, project, dist


def _skills(dist: Path) -> list[str]:
    return sorted(d.name for d in (dist / "skills").iterdir() if d.is_dir())


def _wizard(scope, *, skills, copy=False, clis=("claude",)):
    with patch("agent_notes.memory.memory_router.memory_init"):
        _execute_install(
            clis=set(clis), scope=scope, copy_mode=copy, selected_skills=list(skills),
            role_models={}, memory_backend="local", memory_path="")


def _backend(scope_state, cli="claude"):
    return scope_state.clis[cli]


class TestSelectedSkillsOnly:
    def test_the_wizard_records_the_two_skills_it_placed_out_of_all_of_them(self, world):
        home, _project, dist = world
        every = _skills(dist)
        picked = every[:2]
        assert len(every) > 2

        _wizard("global", skills=picked)

        installed = _backend(load_state().global_install).installed
        assert sorted(installed["skills"]) == picked
        assert sorted(p.name for p in (home / ".claude" / "skills").iterdir()) == picked

    def test_no_skills_selected_records_none(self, world):
        _home, _project, _dist = world

        _wizard("global", skills=[])

        installed = _backend(load_state().global_install).installed
        assert not installed.get("skills")
        assert not installed.get("skills_mirror")

    def test_the_flags_path_places_every_skill_and_records_every_skill(self, world):
        _home, project, dist = world

        install(local=True)

        installed = _backend(load_state().local_installs[str(project)]).installed
        assert sorted(installed["skills"]) == _skills(dist)
        assert sorted(p.name for p in (project / ".claude" / "skills").iterdir()) == _skills(dist)

    def test_build_install_state_takes_the_selection_directly(self, world):
        _home, _project, dist = world
        from agent_notes.services.install_state_builder import build_install_state

        state = build_install_state(mode="symlink", scope="global", repo_root=config.PKG_DIR.parent,
                                    selected_clis={"claude"}, selected_skills=_skills(dist)[:3])

        assert sorted(_backend(state.global_install).installed["skills"]) == _skills(dist)[:3]


class TestCommands:
    def test_the_commands_placed_are_recorded_with_their_targets(self, world):
        home, _project, dist = world
        shipped = sorted(p.name for p in (dist / "claude" / "commands").glob("*.md"))
        assert shipped

        _wizard("global", skills=[])

        recorded = _backend(load_state().global_install).installed["commands"]
        assert sorted(recorded) == shipped
        for name, item in recorded.items():
            assert item.target == str(home / ".claude" / "commands" / name)
            assert Path(item.target).is_symlink()

    def test_a_cli_without_commands_records_none(self, world):
        _wizard("global", skills=[], clis=("claude", "codex"))

        assert "commands" not in _backend(load_state().global_install, "codex").installed

    def test_a_local_install_records_them_under_the_project(self, world):
        _home, project, _dist = world

        install(local=True)

        recorded = _backend(load_state().local_installs[str(project)]).installed["commands"]
        assert recorded
        assert all(Path(i.target).parent == project / ".claude" / "commands" for i in recorded.values())


class TestContextFile:
    def test_the_file_the_session_hook_writes_is_recorded(self, world):
        home, _project, _dist = world

        _wizard("global", skills=[])

        context = home / ".claude" / "agent-notes-context.md"
        assert context.is_file()
        recorded = _backend(load_state().global_install).installed["context"]
        assert [i.target for i in recorded.values()] == [str(context)]

    def test_every_cli_with_a_session_hook_has_its_own(self, world):
        home, _project, _dist = world

        _wizard("global", skills=[], clis=("claude", "codex"))

        state = load_state().global_install
        assert _backend(state, "claude").installed["context"]
        assert [i.target for i in _backend(state, "codex").installed["context"].values()] == [
            str(home / ".codex" / "agent-notes-context.md")]

    def test_a_cli_without_a_session_hook_has_none(self, world):
        _wizard("global", skills=[], clis=("claude", "opencode"))

        assert "context" not in _backend(load_state().global_install, "opencode").installed

    def test_a_local_install_records_the_file_under_the_project(self, world):
        _home, project, _dist = world

        install(local=True)

        recorded = _backend(load_state().local_installs[str(project)]).installed["context"]
        assert [i.target for i in recorded.values()] == [str(project / ".claude" / "agent-notes-context.md")]


class TestSkillsMirror:
    def test_the_agents_skills_entries_are_recorded_for_a_global_install(self, world):
        _home, _project, dist = world
        picked = _skills(dist)[:2]

        _wizard("global", skills=picked)

        mirror = _backend(load_state().global_install).installed["skills_mirror"]
        assert sorted(mirror) == picked
        for name, item in mirror.items():
            assert item.target == str(config.AGENTS_HOME / "skills" / name)
            assert Path(item.target).is_symlink()

    def test_the_flags_path_records_every_mirrored_skill(self, world):
        _home, _project, dist = world

        install(local=False)

        mirror = _backend(load_state().global_install).installed["skills_mirror"]
        assert sorted(mirror) == _skills(dist)
        assert sorted(p.name for p in (config.AGENTS_HOME / "skills").iterdir()) == _skills(dist)

    def test_a_local_install_has_no_mirror(self, world):
        _home, project, _dist = world

        install(local=True)

        assert "skills_mirror" not in _backend(load_state().local_installs[str(project)]).installed
        assert not (config.AGENTS_HOME / "skills").exists()


class TestCopyMode:
    def test_every_placed_file_and_directory_carries_the_sha_of_its_whole_tree(self, world):
        _home, project, dist = world

        install(local=True, copy=True)

        installed = _backend(load_state().local_installs[str(project)]).installed
        assert {"agents", "skills", "rules", "commands", "config"} <= set(installed)
        for component, items in installed.items():
            if component == "context":
                continue
            for name, item in items.items():
                placed = Path(item.target)
                assert placed.exists() and not placed.is_symlink(), (component, name)
                assert item.sha == tree_sha(placed), (component, name)
                assert item.mode == "copy"

    def test_a_copied_skill_directory_is_ours_until_a_file_inside_it_is_edited(self, world):
        _home, project, _dist = world
        install(local=True, copy=True)
        installed = _backend(load_state().local_installs[str(project)]).installed["skills"]
        multi_file = [(i, p) for i in sorted(installed.values(), key=lambda i: i.target)
                      for p in sorted(Path(i.target).rglob("*"))
                      if p.is_file() and p.name != "SKILL.md"]
        assert multi_file, "no shipped skill has a file besides SKILL.md"
        item, extra = multi_file[0]
        placed = Path(item.target)
        assert is_ours(placed, item)

        extra.write_text(extra.read_text() + "\nmy note")

        assert not is_ours(placed, item)

    def test_a_symlink_install_keeps_the_skill_md_sha_it_always_recorded(self, world):
        _home, project, dist = world

        install(local=True)

        from agent_notes.services.state_store import sha256_of
        installed = _backend(load_state().local_installs[str(project)]).installed["skills"]
        for name, item in installed.items():
            assert item.sha == sha256_of(dist / "skills" / name / "SKILL.md")

    def test_the_copy_mirror_is_hashed_by_tree_too(self, world):
        _home, _project, dist = world
        picked = _skills(dist)[:2]

        _wizard("global", skills=picked, copy=True)

        mirror = _backend(load_state().global_install).installed["skills_mirror"]
        for item in mirror.values():
            assert item.sha == tree_sha(Path(item.target))


class TestOldStateFiles:
    def test_a_state_recorded_before_the_new_components_still_loads(self, world):
        path = state_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({
            "source_path": "/repo", "source_commit": "abc",
            "global": {"installed_at": "2025-01-01T00:00:00Z", "updated_at": "2025-01-01T00:00:00Z",
                       "mode": "symlink", "installed_version": "1.0.0",
                       "clis": {"claude": {"role_models": {}, "installed": {
                           "agents": {"lead.md": {"sha": "x", "target": "/t/lead.md", "mode": "symlink"}},
                           "skills": {"tdd": {"sha": "y", "target": "/t/tdd", "mode": "symlink"}},
                       }}}},
            "local": {}, "memory": {"backend": "local", "path": ""},
        }))

        installed = load_state().global_install.clis["claude"].installed

        assert sorted(installed) == ["agents", "skills"]
        assert installed["skills"]["tdd"].target == "/t/tdd"

    def test_the_new_components_survive_a_save_and_load(self, world):
        _home, _project, dist = world
        _wizard("global", skills=_skills(dist)[:2])
        before = _backend(load_state().global_install).installed

        from agent_notes.services.state_store import record_install_state
        record_install_state(load_state())

        assert _backend(load_state().global_install).installed == before
        assert {"commands", "context", "skills_mirror"} <= set(before)


class TestDoctorDriftIgnoresTheGeneratedContextFile:
    def test_a_rewritten_context_file_is_not_local_edits_to_a_copied_source(self, world):
        _home, project, _dist = world
        install(local=True, copy=True)
        (project / ".claude" / "agent-notes-context.md").write_text("regenerated by the session hook")
        scope_state = load_state().local_installs[str(project)]

        from agent_notes.services.diagnostics._checks import check_drift
        issues, fixes = [], []
        check_drift("local", None, issues, fixes, scope_state)

        assert [i for i in issues if i.file.endswith("agent-notes-context.md")] == []
