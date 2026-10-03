"""The one predicate for 'is this path ours to remove?' (spec 007 FR-A06, R7).

A link is ours when its LEXICAL target lies under an owned root, compared by path
parts; a copy is ours only when it is byte-identical to what the manifest recorded.
Anything doubtful is not ours."""
import hashlib
import os
from pathlib import Path
from unittest.mock import patch

import pytest

import agent_notes.config as config
from agent_notes.domain.state import BackendState, InstalledItem, ScopeState, State
from agent_notes.services.install_ownership import (
    is_legacy_dist, is_ours, lexical_target, tree_sha, under,
)
from agent_notes.services.state_store import save_state


@pytest.fixture
def dist(tmp_path, monkeypatch):
    dist = tmp_path / "pkg" / "dist"
    (dist / "claude" / "agents").mkdir(parents=True)
    monkeypatch.setattr(config, "DIST_DIR", dist)
    return dist


def _link(at: Path, target) -> Path:
    at.parent.mkdir(parents=True, exist_ok=True)
    at.symlink_to(target)
    return at


class TestLexicalTarget:
    def test_an_absolute_link_is_returned_as_written(self, tmp_path):
        link = _link(tmp_path / "home" / "a.md", "/somewhere/else/a.md")

        assert lexical_target(link) == Path("/somewhere/else/a.md")

    def test_a_relative_link_is_joined_to_its_directory_and_normalised(self, tmp_path):
        link = _link(tmp_path / "home" / "agents" / "a.md", "../../pkg/dist/./claude/agents/a.md")

        assert lexical_target(link) == tmp_path / "pkg" / "dist" / "claude" / "agents" / "a.md"

    def test_a_dangling_link_still_has_a_target(self, tmp_path):
        link = _link(tmp_path / "a.md", tmp_path / "gone" / "a.md")

        assert not link.exists()
        assert lexical_target(link) == tmp_path / "gone" / "a.md"

    def test_it_does_not_follow_a_chain_of_links(self, tmp_path):
        final = tmp_path / "final.md"
        final.write_text("x")
        middle = _link(tmp_path / "middle.md", final)
        link = _link(tmp_path / "link.md", middle)

        assert lexical_target(link) == middle


class TestUnder:
    def test_by_path_parts_not_by_string_prefix(self, tmp_path):
        assert under(tmp_path / "dist" / "claude", tmp_path / "dist")
        assert not under(tmp_path / "dist-old" / "claude", tmp_path / "dist")
        assert not under(tmp_path / "distribution", tmp_path / "dist")

    def test_the_root_itself_is_under_the_root(self, tmp_path):
        assert under(tmp_path / "dist", tmp_path / "dist")

    def test_dot_dot_cannot_climb_out_of_the_root(self, tmp_path):
        assert not under(tmp_path / "dist" / ".." / "elsewhere", tmp_path / "dist")

    def test_a_root_reached_through_a_symlinked_directory_still_matches(self, tmp_path):
        real = tmp_path / "real"
        (real / "dist" / "claude").mkdir(parents=True)
        alias = _link(tmp_path / "alias", real)

        assert under(real / "dist" / "claude" / "a.md", alias / "dist")
        assert under(alias / "dist" / "claude" / "a.md", real / "dist")


class TestIsLegacyDist:
    @pytest.mark.parametrize("target", [
        "/Users/x/.local/pipx/venvs/agent-notes/lib/python3.13/site-packages/agent_notes/dist/claude/agents/x.md",
        "/opt/venv/lib/python3.9/site-packages/agent_notes/dist/skills/tdd",
        "/Users/x/code/agent-notes/agent_notes/dist/rules/a.md",
    ])
    def test_a_dist_inside_any_agent_notes_package(self, target):
        assert is_legacy_dist(Path(target))

    @pytest.mark.parametrize("target", [
        "/x/agent_notes/dist-old/claude/agents/x.md",
        "/x/agent_notes_backup/dist/claude/agents/x.md",
        "/x/agent_notes/data/dist.md",
        "/x/dist/agent_notes/claude.md",
        "/elsewhere/agents/x.md",
    ])
    def test_nothing_else(self, target):
        assert not is_legacy_dist(Path(target))


class TestIsOursSymlink:
    def test_a_link_into_the_current_dist(self, dist, tmp_path):
        src = dist / "claude" / "agents" / "lead.md"
        src.write_text("x")

        assert is_ours(_link(tmp_path / "home" / "lead.md", src))

    def test_a_dangling_link_into_a_dist_that_is_gone(self, dist, tmp_path):
        link = _link(tmp_path / "home" / "lead.md", dist / "claude" / "agents" / "gone.md")

        assert not link.exists()
        assert is_ours(link)

    def test_a_dangling_link_into_the_dist_of_an_old_python_version(self, dist, tmp_path):
        old = ("/Users/x/.local/pipx/venvs/agent-notes/lib/python3.13/site-packages/"
               "agent_notes/dist/claude/agents/x.md")

        assert is_ours(_link(tmp_path / "home" / "x.md", old))

    def test_a_link_into_a_sibling_whose_name_starts_with_dist(self, dist, tmp_path):
        """The prefix bug: /x/dist-old counted as inside /x/dist."""
        sibling = dist.parent / "dist-old" / "claude" / "agents" / "x.md"
        sibling.parent.mkdir(parents=True)
        sibling.write_text("x")

        assert not is_ours(_link(tmp_path / "home" / "x.md", sibling))

    def test_a_link_into_an_old_package_sibling_named_dist_old(self, dist, tmp_path):
        target = "/x/site-packages/agent_notes/dist-old/claude/agents/x.md"

        assert not is_ours(_link(tmp_path / "home" / "x.md", target))

    def test_a_link_to_something_the_user_made(self, dist, tmp_path):
        assert not is_ours(_link(tmp_path / "home" / "x.md", "/elsewhere/x.md"))

    def test_a_relative_link_is_judged_by_where_it_points(self, dist, tmp_path):
        src = dist / "claude" / "agents" / "lead.md"
        src.write_text("x")
        home = tmp_path / "pkg" / "home" / "agents"
        ours = _link(home / "lead.md", "../../dist/claude/agents/lead.md")
        theirs = _link(home / "mine.md", "../../mine.md")

        assert is_ours(ours)
        assert not is_ours(theirs)

    def test_a_dist_reached_through_a_symlinked_directory(self, tmp_path, monkeypatch):
        real = tmp_path / "real"
        (real / "dist" / "claude").mkdir(parents=True)
        alias = _link(tmp_path / "alias", real)
        monkeypatch.setattr(config, "DIST_DIR", alias / "dist")

        assert is_ours(_link(tmp_path / "home" / "CLAUDE.md", real / "dist" / "claude" / "CLAUDE.md"))

    def test_a_link_into_a_chain_is_judged_by_its_own_first_hop(self, dist, tmp_path):
        """Following the chain would let a user's link to a user's link to dist
        look like ours, or ours look foreign. Only the first hop counts."""
        src = dist / "claude" / "agents" / "lead.md"
        src.write_text("x")
        theirs = _link(tmp_path / "mine.md", src)

        assert not is_ours(_link(tmp_path / "home" / "lead.md", theirs))


class TestIsOursCopy:
    def _recorded(self, path: Path) -> InstalledItem:
        return InstalledItem(sha=tree_sha(path), target=str(path), mode="copy")

    def test_a_file_whose_sha_matches_the_manifest(self, dist, tmp_path):
        f = tmp_path / "home" / "lead.md"
        f.parent.mkdir()
        f.write_text("lead")

        assert is_ours(f, self._recorded(f))

    def test_a_file_that_was_edited(self, dist, tmp_path):
        f = tmp_path / "home" / "lead.md"
        f.parent.mkdir()
        f.write_text("lead")
        recorded = self._recorded(f)
        f.write_text("lead, edited")

        assert not is_ours(f, recorded)

    def test_a_file_the_manifest_never_recorded(self, dist, tmp_path):
        f = tmp_path / "home" / "lead.md"
        f.parent.mkdir()
        f.write_text("lead")

        assert not is_ours(f)
        assert not is_ours(f, None)

    def _skill(self, tmp_path) -> Path:
        skill = tmp_path / "home" / "skills" / "tdd"
        (skill / "refs").mkdir(parents=True)
        (skill / "SKILL.md").write_text("# tdd")
        (skill / "refs" / "a.md").write_text("a")
        (skill / "refs" / "b.md").write_text("b")
        return skill

    def test_a_directory_whose_whole_tree_matches(self, dist, tmp_path):
        skill = self._skill(tmp_path)

        assert is_ours(skill, self._recorded(skill))

    def test_a_directory_with_one_byte_changed_outside_skill_md(self, dist, tmp_path):
        skill = self._skill(tmp_path)
        recorded = self._recorded(skill)
        (skill / "refs" / "a.md").write_text("A")

        assert not is_ours(skill, recorded)

    def test_a_directory_with_a_file_added(self, dist, tmp_path):
        skill = self._skill(tmp_path)
        recorded = self._recorded(skill)
        (skill / "mine.md").write_text("user notes")

        assert not is_ours(skill, recorded)

    def test_a_directory_with_a_file_removed(self, dist, tmp_path):
        skill = self._skill(tmp_path)
        recorded = self._recorded(skill)
        (skill / "refs" / "b.md").unlink()

        assert not is_ours(skill, recorded)

    def test_a_directory_recorded_only_by_its_skill_md(self, dist, tmp_path):
        """Old manifests hashed a skill dir by SKILL.md alone: not proof of the tree."""
        skill = self._skill(tmp_path)
        old = InstalledItem(sha=hashlib.sha256((skill / "SKILL.md").read_bytes()).hexdigest(),
                            target=str(skill), mode="copy")

        assert not is_ours(skill, old)

    def test_a_path_that_does_not_exist(self, dist, tmp_path):
        assert not is_ours(tmp_path / "nothing", InstalledItem(sha="x", target="x", mode="copy"))

    def test_a_link_is_judged_by_its_target_whatever_the_manifest_says(self, dist, tmp_path):
        link = _link(tmp_path / "home" / "x.md", "/elsewhere/x.md")
        claimed = InstalledItem(sha=tree_sha(Path(__file__)), target=str(link), mode="symlink")

        assert not is_ours(link, claimed)


class TestTreeSha:
    def test_a_file_is_its_sha256(self, tmp_path):
        f = tmp_path / "a.md"
        f.write_bytes(b"hello")

        assert tree_sha(f) == hashlib.sha256(b"hello").hexdigest()

    def test_a_directory_does_not_depend_on_creation_order(self, tmp_path):
        a, b = tmp_path / "a", tmp_path / "b"
        for d in (a, b):
            d.mkdir()
        (a / "x.md").write_text("1")
        (a / "y.md").write_text("2")
        (b / "y.md").write_text("2")
        (b / "x.md").write_text("1")

        assert tree_sha(a) == tree_sha(b)

    def test_a_rename_changes_it(self, tmp_path):
        a, b = tmp_path / "a", tmp_path / "b"
        for d in (a, b):
            d.mkdir()
        (a / "x.md").write_text("1")
        (b / "z.md").write_text("1")

        assert tree_sha(a) != tree_sha(b)


class TestDoctorFixUsesThePredicate:
    def _scope(self, target: Path, mode="symlink") -> ScopeState:
        return ScopeState(mode=mode, clis={"claude": BackendState(installed={
            "agents": {"x.md": InstalledItem(sha="x", target=str(target), mode=mode)}})})

    def _fix(self, file: Path):
        from agent_notes.domain.diagnostics import FixAction
        from agent_notes.services.diagnostics._fix import do_fix
        action = FixAction("DELETE", str(file), "stale")
        with patch("builtins.input", return_value="y"):
            do_fix([], [action])

    @pytest.fixture(autouse=True)
    def xdg(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    def test_a_link_into_a_dist_old_sibling_is_not_deleted(self, dist, tmp_path, capsys):
        victim = dist.parent / "dist-old" / "claude" / "agents" / "x.md"
        victim.parent.mkdir(parents=True)
        victim.write_text("x")
        link = _link(tmp_path / "home" / "x.md", victim)

        self._fix(link)

        assert link.is_symlink()
        assert "UNSAFE DELETE BLOCKED" in capsys.readouterr().out

    def test_a_link_into_our_dist_is_deleted(self, dist, tmp_path):
        link = _link(tmp_path / "home" / "x.md", dist / "claude" / "agents" / "gone.md")

        self._fix(link)

        assert not link.is_symlink()

    def test_a_path_recorded_by_a_named_global_profile_is_deleted(self, dist, tmp_path):
        stale = tmp_path / "home-work" / "agents" / "x.md"
        stale.parent.mkdir(parents=True)
        stale.write_text("user-visible copy the manifest recorded")
        state = State(global_installs={"work": self._scope(stale, mode="copy")})
        save_state(state)

        self._fix(stale)

        assert not stale.exists()

    def test_a_path_recorded_by_nothing_is_kept(self, dist, tmp_path):
        stale = tmp_path / "home" / "agents" / "x.md"
        stale.parent.mkdir(parents=True)
        stale.write_text("user file")

        self._fix(stale)

        assert stale.exists()
