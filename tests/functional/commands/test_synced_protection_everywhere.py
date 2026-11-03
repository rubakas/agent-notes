"""The synced/.trash protection holds on EVERY place and remove path (spec 008 fix round 1, A1).

Claude Code owns ~/.claude/skills/synced and ~/.claude/skills/.trash. Neither a forged or stale
state.json manifest nor a stale reserved name in dist/skills may make install, reinstall,
uninstall or doctor --fix place over, move aside or delete them."""
import hashlib
import json
import os
from pathlib import Path

import pytest

import agent_notes.config as config
from agent_notes.commands.build import build
from agent_notes.commands.doctor import diagnose
from agent_notes.commands.install import uninstall
from agent_notes.registries.cli_registry import load_registry
from agent_notes.services import fs
from agent_notes.services.install_ownership import reserved_under_root, tree_sha
from tests.functional.commands.cleanup_world import World


@pytest.fixture
def world(tmp_path, monkeypatch):
    return World(tmp_path, monkeypatch)


def _snapshot(root: Path) -> dict:
    """path -> ("file", sha) | ("dir",) | ("link", target) for everything under *root*."""
    out = {}
    for p in sorted(root.rglob("*")):
        key = str(p.relative_to(root))
        if p.is_symlink():
            out[key] = ("link", os.readlink(p))
        elif p.is_dir():
            out[key] = ("dir",)
        else:
            out[key] = ("file", hashlib.sha256(p.read_bytes()).hexdigest())
    return out


def _plant_claude_owned(claude_skills: Path) -> None:
    (claude_skills / "synced" / "some-skill").mkdir(parents=True)
    (claude_skills / "synced" / "some-skill" / "SKILL.md").write_text("# synced from claude.ai")
    (claude_skills / ".trash" / "old").mkdir(parents=True)
    (claude_skills / ".trash" / "old" / "f.txt").write_text("leftover")


def _forge_manifest(world: World, claude_skills: Path, mode: str) -> None:
    """Add manifest records that name the protected paths, each with a matching sha."""
    state = json.loads(world.state_file.read_text())
    skills = state["global"]["clis"]["claude"]["installed"]["skills"]
    for name in ("synced", ".trash", "synced/some-skill", ".trash/old/f.txt"):
        target = claude_skills / name
        skills[name] = {"sha": tree_sha(target), "target": str(target), "mode": mode}
    world.state_file.write_text(json.dumps(state))


@pytest.fixture(params=[False, True], ids=["symlink", "copy"])
def forged(request, world, monkeypatch):
    """An installed world whose state.json lies about owning synced/ and .trash/."""
    copy = request.param
    world.use("main")
    world.wizard(copy=copy)
    claude_skills = world.home / ".claude" / "skills"
    _plant_claude_owned(claude_skills)
    _forge_manifest(world, claude_skills, "copy" if copy else "symlink")
    monkeypatch.setattr("builtins.input", lambda *_: "y")
    return world, claude_skills, copy, {
        "synced": _snapshot(claude_skills / "synced"), ".trash": _snapshot(claude_skills / ".trash")}


def _assert_untouched(claude_skills: Path, before: dict) -> None:
    assert _snapshot(claude_skills / "synced") == before["synced"]
    assert _snapshot(claude_skills / ".trash") == before[".trash"]
    assert not any(".bak" in p.name for p in claude_skills.rglob("*"))


class TestAForgedManifestCannotMakeUsDeleteProtectedPaths:
    def test_reinstall(self, forged):
        world, claude_skills, copy, before = forged
        world.wizard(copy=copy)
        _assert_untouched(claude_skills, before)

    def test_uninstall(self, forged):
        _world, claude_skills, _copy, before = forged
        uninstall(global_=True)
        _assert_untouched(claude_skills, before)

    def test_doctor_fix(self, forged):
        _world, claude_skills, _copy, before = forged
        diagnose("global", fix=True)
        _assert_untouched(claude_skills, before)


@pytest.fixture(params=[False, True], ids=["symlink", "copy"])
def forged_through_a_symlinked_skills_dir(request, world, monkeypatch):
    """~/.claude/skills is a link to a differently named dir (a dotfile manager's store), and the
    manifest names the protected paths by their real spelling, which has no "skills" in it."""
    copy = request.param
    world.use("main")
    store = world.home / "store"
    store.mkdir(parents=True)
    (world.home / ".claude").mkdir(parents=True)
    (world.home / ".claude" / "skills").symlink_to(store)
    world.wizard(copy=copy)
    (store / "synced" / "some-skill").mkdir(parents=True)
    (store / "synced" / "some-skill" / "SKILL.md").write_text("# synced from claude.ai")
    (store / ".trash" / "old").mkdir(parents=True)
    (store / ".trash" / "old" / "f.txt").write_text("leftover")
    state = json.loads(world.state_file.read_text())
    skills = state["global"]["clis"]["claude"]["installed"]["skills"]
    for name in ("synced", "synced/some-skill", ".trash"):
        skills[name] = {"sha": tree_sha(store / name), "target": str(store / name),
                        "mode": "copy" if copy else "symlink"}
    world.state_file.write_text(json.dumps(state))
    monkeypatch.setattr("builtins.input", lambda *_: "y")
    return world, store, copy, {"synced": _snapshot(store / "synced"), ".trash": _snapshot(store / ".trash")}


class TestAForgedManifestThroughASymlinkedSkillsDirCannotDeleteProtectedPaths:
    def test_reinstall(self, forged_through_a_symlinked_skills_dir):
        world, store, copy, before = forged_through_a_symlinked_skills_dir
        world.wizard(copy=copy)
        _assert_untouched(store, before)

    def test_uninstall(self, forged_through_a_symlinked_skills_dir):
        _world, store, _copy, before = forged_through_a_symlinked_skills_dir
        uninstall(global_=True)
        _assert_untouched(store, before)

    def test_doctor_fix(self, forged_through_a_symlinked_skills_dir):
        _world, store, _copy, before = forged_through_a_symlinked_skills_dir
        diagnose("global", fix=True)
        _assert_untouched(store, before)


class TestAProjectDirectoryNamedSkills:
    """A directory called "skills" above the install is not Claude Code's skills directory."""

    def test_a_local_install_places_everything_and_doctor_finds_nothing_missing(self, world, monkeypatch):
        from agent_notes.services.diagnostics import check_missing_files
        world.use("main")
        world.wizard(scope="local")
        normal = world.project / ".claude"
        expected = sorted(str(p.relative_to(normal)) for p in normal.rglob("*"))
        for component in ("skills", "agents", "rules", "commands"):
            assert any(p.parts[0] == component for p in map(Path, expected)), component

        odd = world.root / "work" / "skills"
        odd.mkdir(parents=True)
        monkeypatch.chdir(odd)
        world.wizard(scope="local")

        placed = sorted(str(p.relative_to(odd / ".claude")) for p in (odd / ".claude").rglob("*"))
        assert placed == expected
        assert len(list((odd / ".claude" / "skills").iterdir())) == len(world.skills())
        issues: list = []
        check_missing_files("local", issues, [])
        assert [i for i in issues if i.type == "missing"] == []


class TestAStaleReservedEntryInDistIsNeverPlacedByTheWizard:
    @pytest.mark.parametrize("copy", [False, True], ids=["symlink", "copy"])
    @pytest.mark.parametrize("reserved", ["Synced", ".trash"])
    def test_the_real_tree_stays_and_nothing_is_recorded(self, world, copy, reserved):
        world.use("main")
        for name in (reserved, "Synced"):
            (world.dist / "skills" / name).mkdir(parents=True, exist_ok=True)
            (world.dist / "skills" / name / "SKILL.md").write_text("# stale")
        claude_skills = world.home / ".claude" / "skills"
        _plant_claude_owned(claude_skills)
        before = {"synced": _snapshot(claude_skills / "synced"),
                  ".trash": _snapshot(claude_skills / ".trash")}
        assert reserved in world.skills() and "Synced" in world.skills()

        world.wizard(copy=copy)

        _assert_untouched(claude_skills, before)
        assert not (claude_skills / reserved).is_symlink()
        assert not (world.paths("main")["agents"] / "skills" / reserved).exists()
        recorded = json.loads(world.state_file.read_text())["global"]["clis"]["claude"]["installed"]["skills"]
        assert not [name for name in recorded if name.casefold() == "synced" or name.startswith(".")]
        # and a later uninstall has nothing of ours to delete there
        uninstall(global_=True)
        _assert_untouched(claude_skills, before)


class TestInstallComponentForBackendSkipsReservedNames:
    def test_a_planted_Synced_is_not_placed(self, world):
        from agent_notes.services.install_executor import install_component_for_backend
        world.use("main")
        (world.dist / "skills" / "Synced").mkdir(parents=True)
        (world.dist / "skills" / "Synced" / "SKILL.md").write_text("# stale")
        claude_skills = world.home / ".claude" / "skills"
        _plant_claude_owned(claude_skills)
        before = _snapshot(claude_skills / "synced")

        install_component_for_backend(load_registry().get("claude"), "skills", "global", False)

        assert _snapshot(claude_skills / "synced") == before
        assert not (claude_skills / "synced").is_symlink()
        assert any(p.is_symlink() for p in claude_skills.iterdir()), "the good skills were not placed"


class TestDoctorFixThatReallyRepairsLeavesProtectedPathsAlone:
    @pytest.mark.parametrize("copy", [False, True], ids=["symlink", "copy"])
    def test_a_missing_skill_is_restored_and_synced_and_trash_are_untouched(self, world, monkeypatch, copy):
        world.use("main")
        world.wizard(copy=copy)
        claude_skills = world.home / ".claude" / "skills"
        _plant_claude_owned(claude_skills)
        before = {"synced": _snapshot(claude_skills / "synced"),
                  ".trash": _snapshot(claude_skills / ".trash")}
        victim = next(p for p in sorted(claude_skills.iterdir()) if p.name not in ("synced", ".trash"))
        if victim.is_symlink() or victim.is_file():
            victim.unlink()
        else:
            import shutil
            shutil.rmtree(victim)
        monkeypatch.setattr("builtins.input", lambda *_: "y")

        diagnose("global", fix=True)

        assert victim.exists() or victim.is_symlink(), "doctor --fix did not repair the removed skill"
        _assert_untouched(claude_skills, before)


class TestThePredicates:
    @pytest.mark.parametrize("path", [
        "/h/.claude/skills/synced", "/h/.claude/skills/Synced", "/h/.claude/skills/SYNCED",
        "/h/.claude/skills/.trash", "/h/.agents/Skills/.hidden",
    ])
    def test_a_reserved_entry_directly_in_a_skills_dir(self, path):
        assert config.is_reserved_skill_entry(Path(path))

    @pytest.mark.parametrize("path", [
        "/h/.claude/skills", "/h/.claude/skills/git", "/h/.claude/skills/git/SKILL.md",
        "/h/.claude/agents/synced.md", "/h/.claude/synced", "/h/.claude/rules/.hidden",
        "/h/skills/.claude/skills/git", "/h/skills/.claude/agents/a.md", "/h/skills/proj/.claude/skills",
    ])
    def test_anything_else_is_not_a_reserved_entry(self, path):
        assert not config.is_reserved_skill_entry(Path(path))

    @pytest.mark.parametrize("path", ["synced", "Synced/x/y", ".trash", ".trash/old/f.txt", "git/../synced"])
    def test_the_first_component_below_a_root_decides(self, path, tmp_path):
        root = tmp_path / "root"
        root.mkdir()
        assert reserved_under_root(root / path, root)

    @pytest.mark.parametrize("path", ["git", "git/synced", "git/.hidden/x", "x/.trash"])
    def test_a_reserved_name_deeper_down_is_not_the_roots_concern(self, path, tmp_path):
        assert not reserved_under_root(tmp_path / "root" / path, tmp_path / "root")

    def test_the_root_itself_and_paths_outside_it_are_not_reserved(self, tmp_path):
        root = tmp_path / "root"
        assert not reserved_under_root(root, root)
        assert not reserved_under_root(tmp_path / "other" / "synced", root)

    def test_a_root_below_a_directory_named_skills_is_unaffected(self, tmp_path):
        root = tmp_path / "skills" / ".claude" / "skills"
        assert not reserved_under_root(root / "git", root)
        assert reserved_under_root(root / "synced", root)

    def test_a_symlinked_root_is_matched_through_its_real_path(self, tmp_path):
        store = tmp_path / "store"
        store.mkdir()
        root = tmp_path / "skills-link"
        root.symlink_to(store)
        assert reserved_under_root(store / "synced", root)
        assert reserved_under_root(root / ".trash" / "x", root)

    def test_placeable_skill_dirs_drops_reserved_names_and_files(self, tmp_path):
        for name in ("good", "Synced", ".trash", "also-good"):
            (tmp_path / name).mkdir()
        (tmp_path / "a-file").write_text("x")
        assert [d.name for d in config.placeable_skill_dirs(tmp_path)] == ["also-good", "good"]
        assert config.placeable_skill_dirs(tmp_path / "missing") == []


class TestTheSinkRefusesProtectedDestinations:
    def test_place_file_refuses_and_prints_a_safe_message(self, tmp_path, capsys):
        src = tmp_path / "src" / "skill"
        src.mkdir(parents=True)
        (src / "SKILL.md").write_text("# x")
        real = tmp_path / ".claude" / "skills" / "synced"
        real.mkdir(parents=True)
        (real / "keep.txt").write_text("keep")
        evil = tmp_path / ".claude" / "skills" / ".\x1b[2Jtrash"

        for dst in (real, evil):
            for copy_mode in (False, True):
                fs.place_file(src, dst, copy_mode)

        assert _snapshot(real) == {"keep.txt": ("file", hashlib.sha256(b"keep").hexdigest())}
        assert not evil.exists() and not evil.is_symlink()
        assert not any(".bak" in p.name for p in real.parent.iterdir())
        out = capsys.readouterr().out
        assert "reserved" in out.lower() and "\x1b" not in out

    def test_move_aside_never_moves_a_protected_path(self, tmp_path):
        real = tmp_path / ".claude" / "skills" / ".trash"
        real.mkdir(parents=True)
        (real / "f.txt").write_text("x")

        with pytest.raises(ValueError):
            fs._move_aside(real)

        assert (real / "f.txt").read_text() == "x"
        assert not any(".bak" in p.name for p in real.parent.iterdir())


class TestBuildChecksReservedNamesFirst:
    def test_a_bad_skill_name_fails_before_any_dist_file_is_regenerated(self, world, monkeypatch, tmp_path):
        sentinel = world.dist / "rules" / "stale-sentinel.md"
        sentinel.write_text("prune_dist would remove this")
        agent_file = next((world.dist / "claude" / "agents").glob("*.md"))
        agent_file.write_text("hand-edited, a regenerate would overwrite this")
        bad_source = tmp_path / "bad-skills"
        for name in ("synced", ".\x1b[2Jevil"):
            (bad_source / name).mkdir(parents=True)
            (bad_source / name / "SKILL.md").write_text("# fake")
        monkeypatch.setattr(config, "SKILLS_DIR", bad_source)

        with pytest.raises(ValueError) as raised:
            build()

        assert "synced" in str(raised.value)
        assert "\x1b" not in str(raised.value)
        assert sentinel.exists()
        assert agent_file.read_text() == "hand-edited, a regenerate would overwrite this"
