"""Deletion and overwrite safety (spec 007 review round 1, R1).

Nothing is deleted on the strength of a manifest alone: a path must be ours (a link into a real
package dist, or a copy still matching its record) AND inside the install's own roots, reached
without a symlink in between. Anything that cannot be judged is kept."""
import os
from pathlib import Path

import pytest

import agent_notes.config as config
from agent_notes.domain.state import BackendState, InstalledItem, ScopeState, State
from agent_notes.registries.cli_registry import load_registry
from agent_notes.services import fs
from agent_notes.services import install_cleanup as cleanup
from agent_notes.services import install_ownership as own
from agent_notes.services.install_cleanup import Claims, Stale, claims_of_others, remove_stale, stale_placements
from agent_notes.services.install_ownership import is_legacy_dist, is_ours, path_key, tree_sha, under


def confined(path, root):
    return own.confined(path, root)


def prunable_dirs(*args):
    return cleanup.prunable_dirs(*args)


@pytest.fixture
def env(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    pkg = tmp_path / "pkg"
    dist = pkg / "dist"
    for sub in ("claude/agents", "skills", "rules"):
        (dist / sub).mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(config, "PKG_DIR", pkg)
    monkeypatch.setattr(config, "DIST_DIR", dist)
    monkeypatch.setattr(config, "AGENTS_HOME", tmp_path / "agents_home")
    return home, dist, load_registry()


def _item(path, sha="x", mode="symlink") -> InstalledItem:
    return InstalledItem(sha=sha, target=path, mode=mode)


def _old(items: dict, cli="claude", **backend) -> ScopeState:
    return ScopeState(mode="symlink", clis={cli: BackendState(installed=items, **backend)})


def _stale(old, registry, scope="global", project=None, new=(), claims=None):
    return {s.path for s in stale_placements(old, scope, project, new, claims or Claims(), registry)}


class TestLegacyDistIsARealPackageDist:
    @pytest.mark.parametrize("target", [
        "/Users/x/.local/pipx/venvs/agent-notes/lib/python3.13/site-packages/agent_notes/dist/claude/agents/x.md",
        "/opt/venv/lib/python3.9/site-packages/agent_notes/dist/skills/tdd",
        "/x/site-packages/vendor/agent_notes/dist/rules/a.md",
    ])
    def test_site_packages_followed_by_agent_notes_dist(self, target):
        assert is_legacy_dist(Path(target))

    @pytest.mark.parametrize("target", [
        "/Users/x/work/agent_notes/dist/x.md",
        "/x/agent_notes/dist/claude/agents/x.md",
        "/x/agent_notes/site-packages/dist/x.md",
        "/x/site-packages/agent_notes/dist-old/x.md",
        "/x/agent_notes/dist/site-packages/x.md",
    ])
    def test_a_directory_that_merely_looks_like_one_is_not(self, target):
        assert not is_legacy_dist(Path(target))

    def test_the_dist_of_this_package_is_ours_wherever_it_lives(self, env, tmp_path):
        _home, _dist, _registry = env
        link = tmp_path / "home" / "x.md"
        link.symlink_to(config.PKG_DIR / "dist" / "claude" / "agents" / "x.md")

        assert is_ours(link)

    def test_a_users_link_into_a_checkout_named_agent_notes_is_not_ours(self, env, tmp_path):
        link = tmp_path / "home" / "x.md"
        link.symlink_to(tmp_path / "work" / "agent_notes" / "dist" / "x.md")

        assert not is_ours(link)

    def test_place_file_backs_such_a_link_up_instead_of_unlinking_it(self, env, tmp_path):
        src = tmp_path / "pkg" / "dist" / "claude" / "agents" / "x.md"
        src.write_text("x")
        dst = tmp_path / "home" / "x.md"
        user_target = tmp_path / "work" / "agent_notes" / "dist" / "x.md"
        dst.symlink_to(user_target)

        fs.place_file(src, dst)

        (backup,) = [p for p in dst.parent.iterdir() if ".bak." in p.name]
        assert os.readlink(backup) == str(user_target)


class TestConfinement:
    def test_a_symlinked_parent_below_the_root_is_refused(self, tmp_path):
        root, outside = tmp_path / "root", tmp_path / "outside"
        (root / "agents").mkdir(parents=True)
        outside.mkdir()
        (root / "agents" / "sub").symlink_to(outside)

        assert not under(root / "agents" / "sub" / "f.md", root)
        assert not confined(root / "agents" / "sub" / "f.md", root)

    def test_a_symlink_inside_the_root_that_stays_inside_is_still_refused_as_a_parent(self, tmp_path):
        root = tmp_path / "root"
        (root / "real").mkdir(parents=True)
        (root / "alias").symlink_to(root / "real")

        assert under(root / "alias" / "f.md", root)
        assert not confined(root / "alias" / "f.md", root)

    def test_a_plain_path_below_the_root_is_confined(self, tmp_path):
        root = tmp_path / "root"
        (root / "agents").mkdir(parents=True)

        assert confined(root / "agents" / "f.md", root)

    def test_a_directory_root_is_not_confined_to_itself_but_a_file_root_is(self, tmp_path):
        directory, file = tmp_path / "agents", tmp_path / "CLAUDE.md"
        directory.mkdir()
        file.write_text("x")

        assert not confined(directory, directory)
        assert confined(file, file)

    def test_remove_stale_never_removes_the_whole_component_dir(self, tmp_path):
        agents = tmp_path / "agents"
        agents.mkdir()
        (agents / "mine.md").write_text("x")
        recorded = InstalledItem(sha=tree_sha(agents), target=str(agents), mode="copy")

        assert remove_stale([Stale(agents, recorded, root=agents)]) == []
        assert (agents / "mine.md").exists()

    def test_the_config_file_itself_is_still_removable(self, tmp_path):
        config_file = tmp_path / "CLAUDE.md"
        config_file.write_text("x")
        recorded = InstalledItem(sha=tree_sha(config_file), target=str(config_file), mode="copy")

        assert remove_stale([Stale(config_file, recorded, root=config_file)]) == [config_file]

    def test_a_root_that_is_itself_a_symlink_is_fine(self, tmp_path):
        real = tmp_path / "dotfiles" / "claude"
        (real / "agents").mkdir(parents=True)
        root = tmp_path / ".claude"
        root.symlink_to(real)

        assert confined(root / "agents" / "f.md", root)

    def test_dot_dot_cannot_climb_out(self, tmp_path):
        root = tmp_path / "root"
        root.mkdir()

        assert not confined(root / ".." / "elsewhere" / "f.md", root)


class TestDotDotThroughASymlinkCannotLeave:
    """abspath collapses `link/..` lexically; the OS resolves it through the link."""

    def _world(self, tmp_path):
        root = tmp_path / "root"
        root.mkdir()
        inner = tmp_path / "outside" / "inner"
        inner.mkdir(parents=True)
        victim = tmp_path / "outside" / "victim"
        victim.write_text("precious")
        (root / "link").symlink_to(inner)
        return root, victim

    def test_a_raw_dot_dot_component_is_not_confined(self, tmp_path):
        root, _victim = self._world(tmp_path)

        assert not confined(root / "link" / ".." / "victim", root)

    def test_remove_stale_leaves_the_file_the_dot_dot_resolves_to(self, tmp_path):
        root, victim = self._world(tmp_path)
        path = root / "link" / ".." / "victim"
        item = InstalledItem(sha=tree_sha(victim), target=str(path), mode="copy")

        assert remove_stale([Stale(path, item, root=root)]) == []
        assert victim.read_text() == "precious"


    def test_doctor_fix_guard_refuses_it_too(self, env, tmp_path):
        home, dist, registry = env
        agents = home / ".claude" / "agents"
        agents.mkdir(parents=True)
        inner = tmp_path / "outside" / "inner"
        inner.mkdir(parents=True)
        (tmp_path / "outside" / "victim").symlink_to(dist / "claude" / "agents" / "x.md")
        (agents / "link").symlink_to(inner)
        deletable = cleanup.deletion_guard(State(global_install=_old({})), registry, home)

        assert not deletable(agents / "link" / ".." / "victim")


class TestAManifestCannotSteerDeletion:
    def test_the_symlinked_parent_poc_deletes_nothing(self, env, tmp_path):
        home, dist, registry = env
        agents = home / ".claude" / "agents"
        agents.mkdir(parents=True)
        victim_dir = tmp_path / "victim"
        victim_dir.mkdir()
        victim = victim_dir / "mine.md"
        victim.symlink_to(dist / "claude" / "agents" / "x.md")
        (agents / "sub").symlink_to(victim_dir)
        old = _old({"agents": {"mine.md": _item(str(agents / "sub" / "mine.md"))}})

        assert _stale(old, registry) == set()
        remove_stale([Stale(agents / "sub" / "mine.md", None, root=agents)])
        assert victim.is_symlink()

    def test_a_path_swapped_for_a_symlinked_parent_after_the_set_was_computed_is_kept(self, env, tmp_path):
        home, dist, registry = env
        agents = home / ".claude" / "agents"
        agents.mkdir(parents=True)
        victim_dir = tmp_path / "victim"
        victim_dir.mkdir()
        (victim_dir / "a.md").symlink_to(dist / "claude" / "agents" / "x.md")
        (agents / "sub").mkdir()
        (agents / "sub" / "a.md").symlink_to(dist / "claude" / "agents" / "x.md")
        old = _old({"agents": {"a.md": _item(str(agents / "sub" / "a.md"))}})
        stale = stale_placements(old, "global", None, [], Claims(), registry)
        assert [s.path for s in stale] == [agents / "sub" / "a.md"]
        (agents / "sub" / "a.md").unlink()
        (agents / "sub").rmdir()
        (agents / "sub").symlink_to(victim_dir)

        assert remove_stale(stale) == []
        assert (victim_dir / "a.md").is_symlink()

    @pytest.mark.parametrize("override", ["~", "/", "~/..", "$HOME_PARENT"])
    def test_a_global_home_override_at_or_above_home_makes_the_install_ignored(self, env, override, tmp_path):
        home, dist, registry = env
        if override == "$HOME_PARENT":
            override = str(home.parent)
        victim = home / "Documents" / "proj.md"
        victim.parent.mkdir()
        victim.symlink_to(dist / "claude" / "agents" / "x.md")
        old = _old({"agents": {"proj.md": _item(str(victim))}}, global_home_override=override)

        assert _stale(old, registry) == set()

    def test_an_override_that_names_a_real_profile_home_still_works(self, env):
        home, dist, registry = env
        profile = home / ".claude-work"
        (profile / "agents").mkdir(parents=True)
        link = profile / "agents" / "a.md"
        link.symlink_to(dist / "claude" / "agents" / "a.md")
        old = _old({"agents": {"a.md": _item(str(link))}}, global_home_override=str(profile))

        assert _stale(old, registry) == {link}

    def test_the_whole_cli_home_is_not_a_root_only_its_component_dirs_and_config_file(self, env):
        home, dist, registry = env
        claude = home / ".claude"
        (claude / "agents").mkdir(parents=True)
        agent = claude / "agents" / "a.md"
        config_file = claude / "CLAUDE.md"
        stray = claude / "stray.md"
        for link in (agent, config_file, stray):
            link.symlink_to(dist / "claude" / "agents" / "x.md")
        old = _old({"agents": {"a.md": _item(str(agent)), "stray.md": _item(str(stray))},
                    "config": {"CLAUDE.md": _item(str(config_file))}})

        assert _stale(old, registry) == {agent, config_file}

    def test_a_manifest_item_in_home_but_outside_the_install_is_ignored(self, env):
        home, dist, registry = env
        stray = home / "Documents" / "x.md"
        stray.parent.mkdir()
        stray.symlink_to(dist / "claude" / "agents" / "x.md")
        old = _old({"agents": {"x.md": _item(str(stray))}})

        assert _stale(old, registry) == set()


class TestMalformedStateCannotCrashCleanup:
    def test_a_nul_in_a_target_a_non_string_target_and_a_non_string_sha(self, env):
        home, dist, registry = env
        good = home / ".claude" / "agents" / "a.md"
        good.parent.mkdir(parents=True)
        good.symlink_to(dist / "claude" / "agents" / "a.md")
        old = _old({"agents": {
            "nul.md": _item("/x/\0/y"), "int.md": _item(42), "none.md": _item(None),
            "sha.md": InstalledItem(sha=["x"], target=str(good), mode="copy"),
            "a.md": _item(str(good))}})

        assert _stale(old, registry) == {good}

    def test_a_nul_in_a_local_install_key_does_not_break_the_claims_of_the_others(self, env, tmp_path):
        _home, _dist, registry = env
        state = State(global_install=_old({}), local_installs={"/p\0q": _old({}), "": _old({})})

        claims = claims_of_others(state, "global", None, "", registry)

        assert isinstance(claims, Claims)

    def test_is_ours_and_path_key_survive_an_embedded_nul(self, env):
        assert is_ours(Path("/x/\0/y")) is False
        assert isinstance(path_key(Path("/x/\0/y")), str)

    def test_under_survives_an_embedded_nul(self, tmp_path):
        assert under(Path("/x/\0/y"), tmp_path) is False


class TestTreeShaCoversEveryEntry:
    def _tree(self, root: Path) -> Path:
        (root / "refs").mkdir(parents=True)
        (root / "SKILL.md").write_text("# s")
        (root / "refs" / "a.md").write_text("a")
        return root

    def test_an_added_empty_directory_changes_it(self, tmp_path):
        a = self._tree(tmp_path / "a")
        before = tree_sha(a)

        (a / "empty").mkdir()

        assert tree_sha(a) != before

    def test_an_added_symlink_changes_it_and_its_target_text_counts(self, tmp_path):
        a = self._tree(tmp_path / "a")
        before = tree_sha(a)
        (a / "link").symlink_to("/one")
        with_one = tree_sha(a)
        (a / "link").unlink()
        (a / "link").symlink_to("/two")

        assert before != with_one != tree_sha(a)

    def test_a_symlink_to_a_file_is_not_the_same_as_that_files_content(self, tmp_path):
        a, b = self._tree(tmp_path / "a"), self._tree(tmp_path / "b")
        (a / "x.md").write_text("same")
        (b / "x.md").symlink_to(a / "x.md")

        assert tree_sha(a) != tree_sha(b)

    def test_a_changed_mode_changes_it(self, tmp_path):
        a = self._tree(tmp_path / "a")
        before = tree_sha(a)

        os.chmod(a / "SKILL.md", 0o755)

        assert tree_sha(a) != before

    def test_shas_recorded_by_earlier_installs_still_match(self, tmp_path):
        """Pinned from the implementation before special files were handled: a manifest
        written then must keep matching."""
        tree = tmp_path / "tree"
        (tree / "refs").mkdir(parents=True)
        (tree / "empty").mkdir()
        (tree / "SKILL.md").write_text("# s")
        (tree / "refs" / "a.md").write_text("a")
        for entry, mode in ((tree / "SKILL.md", 0o644), (tree / "refs" / "a.md", 0o755),
                            (tree / "refs", 0o755), (tree / "empty", 0o700)):
            os.chmod(entry, mode)
        (tree / "link").symlink_to("/one")
        (tmp_path / "f").write_text("hello")
        (tmp_path / "l").symlink_to("/target")

        assert tree_sha(tree) == "9d3194e94469728a85ca6740afab4b3507af4bdc7d0e9fa9763ede3201a67645"
        assert tree_sha(tmp_path / "f") == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
        assert tree_sha(tmp_path / "l") == "436c9a08d3b25a8b2aafd5124570b589b1b7f5a96a0403d9f42f6af03bcac566"

    @staticmethod
    def _finishes(path: Path) -> str:
        import threading
        result = []
        worker = threading.Thread(target=lambda: result.append(tree_sha(path)), daemon=True)
        worker.start()
        worker.join(timeout=5)
        assert not worker.is_alive(), f"tree_sha blocked reading {path}"
        return result[0]

    def test_a_fifo_inside_a_directory_is_not_read(self, tmp_path):
        tree = self._tree(tmp_path / "a")
        before = self._finishes(tree)

        os.mkfifo(tree / "pipe")

        assert self._finishes(tree) != before

    def test_a_fifo_as_the_path_itself_is_not_read(self, tmp_path):
        os.mkfifo(tmp_path / "pipe")
        (tmp_path / "empty").mkdir()

        assert self._finishes(tmp_path / "pipe") != tree_sha(tmp_path / "empty")

    def test_a_plain_file_is_still_the_sha_256_of_its_bytes(self, tmp_path):
        import hashlib
        f = tmp_path / "f.md"
        f.write_bytes(b"hello")

        assert tree_sha(f) == hashlib.sha256(b"hello").hexdigest()


class TestBackups:
    def test_a_directory_backup_keeps_symlinks_as_symlinks(self, env, tmp_path):
        src = tmp_path / "pkg" / "dist" / "skills" / "tdd"
        src.mkdir(parents=True)
        (src / "SKILL.md").write_text("new")
        dst = tmp_path / "home" / "tdd"
        dst.mkdir()
        (dst / "SKILL.md").write_text("mine")
        (dst / "link").symlink_to("/elsewhere/precious")

        fs.place_file(src, dst, copy_mode=True)

        (backup,) = [p for p in dst.parent.iterdir() if ".bak." in p.name]
        assert (backup / "link").is_symlink()
        assert os.readlink(backup / "link") == "/elsewhere/precious"

    def test_a_backup_never_overwrites_an_existing_one(self, env, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "_timestamped_backup_path", lambda dst: Path(str(dst) + ".bak.SAME"))
        src = tmp_path / "pkg" / "dist" / "a.md"
        src.write_text("new")
        dst = tmp_path / "home" / "a.md"

        dst.write_text("first")
        fs.place_file(src, dst, copy_mode=True)
        dst.write_text("second")
        fs.place_file(src, dst, copy_mode=True)

        backups = sorted(p.read_text() for p in dst.parent.iterdir() if ".bak." in p.name)
        assert backups == ["first", "second"]

    def test_a_directory_backup_never_overwrites_an_existing_one(self, env, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "_timestamped_backup_path", lambda dst: Path(str(dst) + ".bak.SAME"))
        src = tmp_path / "pkg" / "dist" / "d"
        src.mkdir()
        (src / "f").write_text("new")
        dst = tmp_path / "home" / "d"
        for text in ("first", "second"):
            dst.mkdir(exist_ok=True)
            (dst / "f").write_text(text)
            fs.place_file(src, dst, copy_mode=True)
            if dst.is_dir():
                import shutil
                shutil.rmtree(dst)

        backups = sorted((p / "f").read_text() for p in dst.parent.iterdir() if ".bak." in p.name)
        assert backups == ["first", "second"]


class TestSharedConfigFiles:
    def _local(self, project, *clis) -> ScopeState:
        return ScopeState(mode="symlink", clis={c: BackendState() for c in clis})

    def test_a_config_another_installs_other_cli_also_writes_is_claimed(self, env, tmp_path):
        """codex (default install) and opencode (profile work) both write P/AGENTS.md."""
        home, dist, registry = env
        project = tmp_path / "proj"
        project.mkdir()
        agents_md = project / "AGENTS.md"
        agents_md.symlink_to(dist / "codex" / "AGENTS.md")
        default = self._local(project, "claude", "codex")
        work = ScopeState(mode="symlink", profile_label="work", clis={"opencode": BackendState()})
        state = State(local_installs={str(project): default, f"{project}#work": work})
        claims = claims_of_others(state, "local", project, "", registry)

        assert agents_md not in _stale(default, registry, "local", project, claims=claims)

    def test_claude_md_is_claimed_the_same_way(self, env, tmp_path):
        home, dist, registry = env
        project = tmp_path / "proj"
        project.mkdir()
        claude_md = project / "CLAUDE.md"
        claude_md.symlink_to(dist / "claude" / "CLAUDE.md")
        default = self._local(project, "claude")
        work = ScopeState(mode="symlink", profile_label="work", clis={"claude": BackendState(
            local_dir_override=".claude-work")})
        state = State(local_installs={str(project): default, f"{project}#work": work})
        claims = claims_of_others(state, "local", project, "", registry)

        assert claude_md not in _stale(default, registry, "local", project, claims=claims)

    def test_without_another_install_it_is_stale(self, env, tmp_path):
        home, dist, registry = env
        project = tmp_path / "proj"
        project.mkdir()
        agents_md = project / "AGENTS.md"
        agents_md.symlink_to(dist / "codex" / "AGENTS.md")
        default = self._local(project, "claude", "codex")

        assert _stale(default, registry, "local", project, claims=Claims()) == {agents_md}


class TestPruningEmptyDirectories:
    def test_a_project_root_emptied_by_cleanup_is_never_removed(self, env, tmp_path):
        home, dist, registry = env
        project = tmp_path / "proj"
        project.mkdir()
        agents_md = project / "AGENTS.md"
        agents_md.symlink_to(dist / "codex" / "AGENTS.md")
        old = ScopeState(mode="symlink", clis={"codex": BackendState()})
        stale = stale_placements(old, "local", project, [], Claims(), registry)

        removed = remove_stale(stale, prune=prunable_dirs(old, "local", project, registry))

        assert removed == [agents_md]
        assert project.is_dir()

    def test_the_cli_component_dirs_and_home_it_emptied_are_removed(self, env, tmp_path):
        home, dist, registry = env
        agents = home / ".codex" / "agents"
        agents.mkdir(parents=True)
        (agents / "a.toml").symlink_to(dist / "codex" / "agents" / "a.toml")
        old = ScopeState(mode="symlink", clis={"codex": BackendState()})
        stale = stale_placements(old, "global", None, [], Claims(), registry)

        remove_stale(stale, prune=prunable_dirs(old, "global", None, registry))

        assert not (home / ".codex").exists()

    def test_home_itself_is_never_a_candidate(self, env):
        home, _dist, registry = env
        old = ScopeState(mode="symlink", clis={"claude": BackendState(), "codex": BackendState()})

        assert home not in prunable_dirs(old, "global", None, registry)
        assert all(home != d and home not in d.parents or d.is_relative_to(home)
                   for d in prunable_dirs(old, "global", None, registry))

    def test_an_invalid_home_override_prunes_nothing(self, env):
        home, _dist, registry = env
        old = _old({}, global_home_override="~")

        assert prunable_dirs(old, "global", None, registry) == []


class TestNamesFromDiskAreEscapedInCleanupMessages:
    def test_a_foreign_file_name_with_an_escape_sequence_is_printed_escaped(self, env, tmp_path, capsys):
        from agent_notes.services.install_executor import _remove_owned
        dst = tmp_path / "home" / ".claude" / "agents"
        dst.mkdir(parents=True)
        (dst / "a\x1b[2Jb.md").write_text("mine")

        assert _remove_owned(dst, "claude") == 0
        out = capsys.readouterr().out

        assert "Left in place" in out
        assert "a\x1b[2Jb" not in out
        assert "a\\x1b[2Jb" in out

    def test_a_file_that_could_not_be_removed_is_named_escaped(self, env, tmp_path, capsys, monkeypatch):
        victim = tmp_path / "root" / "a\x1b[2Jb.md"
        victim.parent.mkdir()
        victim.write_text("x")
        recorded = InstalledItem(sha=tree_sha(victim), target=str(victim), mode="copy")
        monkeypatch.setattr(Path, "unlink", lambda self, *a, **k: (_ for _ in ()).throw(OSError("denied")))

        remove_stale([Stale(victim, recorded, root=victim.parent)])
        out = capsys.readouterr().out

        assert "Could not remove" in out
        assert "a\x1b[2Jb" not in out
