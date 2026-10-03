"""stale = owned(old manifest + marker scan) - new placements - claimed by other installs
(spec 007 FR-A07). Computing it writes nothing; removing it re-checks ownership."""
import shutil
from pathlib import Path

import pytest

import agent_notes.config as config
from agent_notes.domain.state import BackendState, InstalledItem, ScopeState, State
from agent_notes.registries.cli_registry import load_registry
from agent_notes.services.install_cleanup import (
    Claims, claims_of_others, dropped_hook_backends, manifest_targets, remove_stale,
    stale_placements,
)
from agent_notes.services.install_ownership import tree_sha


@pytest.fixture
def env(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    dist = tmp_path / "pkg" / "dist"
    for sub in ("claude/agents", "skills", "rules"):
        (dist / sub).mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(config, "DIST_DIR", dist)
    monkeypatch.setattr(config, "AGENTS_HOME", tmp_path / "agents_home")
    return home, dist, load_registry()


def _link(dist: Path, home: Path, component: str, name: str, cli="claude", src_dir=None) -> Path:
    src = (src_dir or dist / "skills") / name if component == "skills" else dist / cli / component / name
    src.parent.mkdir(parents=True, exist_ok=True)
    src.mkdir(exist_ok=True) if component == "skills" else src.write_text(name)
    target_dir = home / ".claude" / component
    target_dir.mkdir(parents=True, exist_ok=True)
    link = target_dir / name
    link.symlink_to(src)
    return link


def _scope(**components) -> ScopeState:
    """_scope(skills=[paths], agents=[paths]) -> one claude manifest."""
    installed = {c: {p.name: InstalledItem(sha="x", target=str(p), mode="symlink") for p in paths}
                 for c, paths in components.items()}
    return ScopeState(mode="symlink", clis={"claude": BackendState(installed=installed)})


def _stale(old, registry, new=(), claims=None, scope="global", project=None):
    return {s.path for s in stale_placements(old, scope, project, new, claims or Claims(), registry)}


class TestSetDifference:
    def test_what_the_old_manifest_lists_and_the_new_placement_does_not(self, env):
        home, dist, registry = env
        a, b, c = (_link(dist, home, "skills", n) for n in "abc")
        d = home / ".claude" / "skills" / "d"

        stale = _stale(_scope(skills=[a, b, c]), registry, new=[a, d])

        assert stale == {b, c}

    def test_a_skill_subset_leaves_the_dropped_ones_stale(self, env):
        home, dist, registry = env
        links = [_link(dist, home, "skills", f"s{i}") for i in range(5)]

        stale = _stale(_scope(skills=links), registry, new=links[:2])

        assert stale == set(links[2:])

    def test_no_old_install_means_nothing_is_stale(self, env):
        _home, _dist, registry = env

        assert stale_placements(None, "global", None, [], Claims(), registry) == []

    def test_a_foreign_link_the_manifest_lists_is_not_owned(self, env):
        home, dist, registry = env
        ours = _link(dist, home, "skills", "ours")
        theirs = home / ".claude" / "skills" / "theirs"
        theirs.symlink_to("/elsewhere/theirs")

        stale = _stale(_scope(skills=[ours, theirs]), registry)

        assert stale == {ours}

    def test_a_copy_is_stale_only_while_it_matches_what_was_recorded(self, env):
        home, _dist, registry = env
        untouched, edited = home / ".claude" / "agents" / "a.md", home / ".claude" / "agents" / "b.md"
        untouched.parent.mkdir(parents=True)
        untouched.write_text("a")
        edited.write_text("b")
        old = ScopeState(mode="copy", clis={"claude": BackendState(installed={"agents": {
            "a.md": InstalledItem(sha=tree_sha(untouched), target=str(untouched), mode="copy"),
            "b.md": InstalledItem(sha=tree_sha(edited), target=str(edited), mode="copy")}})})
        edited.write_text("b, edited by the user")

        assert _stale(old, registry) == {untouched}

    def test_computing_the_set_deletes_nothing(self, env):
        home, dist, registry = env
        link = _link(dist, home, "skills", "a")

        _stale(_scope(skills=[link]), registry)

        assert link.is_symlink()

    def test_a_path_spelled_through_a_symlinked_directory_is_still_a_new_placement(self, env, tmp_path):
        home, dist, registry = env
        link = _link(dist, home, "skills", "a")
        alias = tmp_path / "alias"
        alias.symlink_to(home)

        assert _stale(_scope(skills=[link]), registry, new=[alias / ".claude" / "skills" / "a"]) == set()


class TestMarkerScan:
    def test_our_links_in_the_component_dirs_are_found_without_a_manifest_entry(self, env):
        home, dist, registry = env
        listed = _link(dist, home, "agents", "lead.md")
        unlisted = _link(dist, home, "skills", "old-skill")

        stale = _stale(_scope(agents=[listed]), registry)

        assert stale == {listed, unlisted}

    def test_user_files_and_foreign_links_in_those_dirs_are_never_found(self, env):
        home, dist, registry = env
        _link(dist, home, "skills", "ours")
        skills = home / ".claude" / "skills"
        (skills / "mine").mkdir()
        (skills / "notes.md").write_text("mine")
        (skills / "foreign").symlink_to("/elsewhere")

        stale = _stale(_scope(agents=[]), registry)

        assert stale == {skills / "ours"}

    def test_only_the_old_installs_component_dirs_are_scanned(self, env):
        home, dist, registry = env
        _link(dist, home, "skills", "ours")
        elsewhere = home / "projects" / "app" / ".claude" / "skills"
        elsewhere.mkdir(parents=True)
        (elsewhere / "ours").symlink_to(dist / "skills" / "ours")

        assert _stale(_scope(agents=[]), registry) == {home / ".claude" / "skills" / "ours"}

    def test_a_symlinked_component_dir_is_not_walked(self, env, tmp_path):
        home, dist, registry = env
        outside = tmp_path / "outside"
        outside.mkdir()
        (outside / "ours").symlink_to(dist / "skills" / "ours")
        (home / ".claude").mkdir()
        (home / ".claude" / "skills").symlink_to(outside)

        assert _stale(_scope(agents=[]), registry) == set()

    def test_the_config_symlink_is_found(self, env):
        home, dist, registry = env
        (dist / "claude" / "CLAUDE.md").write_text("x")
        (home / ".claude").mkdir()
        (home / ".claude" / "CLAUDE.md").symlink_to(dist / "claude" / "CLAUDE.md")

        assert _stale(_scope(agents=[]), registry) == {home / ".claude" / "CLAUDE.md"}

    def test_the_agents_skills_mirror_is_scanned_for_a_global_install(self, env):
        home, dist, registry = env
        mirror = config.AGENTS_HOME / "skills"
        mirror.mkdir(parents=True)
        (mirror / "old").symlink_to(dist / "skills" / "old")
        (mirror / "foreign").symlink_to("/elsewhere")

        assert _stale(_scope(agents=[]), registry) == {mirror / "old"}

    def test_a_local_install_scans_the_project_not_the_home(self, env, tmp_path):
        home, dist, registry = env
        project = tmp_path / "project"
        (project / ".claude" / "skills").mkdir(parents=True)
        (project / ".claude" / "skills" / "old").symlink_to(dist / "skills" / "old")
        _link(dist, home, "skills", "global-one")

        assert _stale(_scope(agents=[]), registry, scope="local", project=project) == {
            project / ".claude" / "skills" / "old"}

    def test_the_old_installs_own_folder_override_decides_where_to_scan(self, env, tmp_path):
        home, dist, registry = env
        project = tmp_path / "project"
        (project / ".claude-work" / "skills").mkdir(parents=True)
        (project / ".claude-work" / "skills" / "old").symlink_to(dist / "skills" / "old")
        old = ScopeState(mode="symlink", clis={"claude": BackendState(local_dir_override=".claude-work")})

        assert _stale(old, registry, scope="local", project=project) == {
            project / ".claude-work" / "skills" / "old"}


class TestClaimsOfOtherInstalls:
    def _claims(self, state, registry, scope="global", project=None, label=""):
        return claims_of_others(state, scope, project, label, registry)

    def test_a_dir_another_install_lists_for_the_same_cli_is_kept(self, env):
        home, dist, registry = env
        link = _link(dist, home, "agents", "lead.md")
        state = State(global_install=_scope(agents=[link]), global_installs={"work": _scope(agents=[])})

        stale = _stale(state.global_install, registry,
                       claims=self._claims(state, registry))

        assert stale == set()

    def test_a_dir_no_other_install_lists_is_not_kept(self, env):
        home, dist, registry = env
        link = _link(dist, home, "agents", "lead.md")
        work = ScopeState(mode="symlink", profile_label="work", clis={"claude": BackendState(
            global_home_override=str(home / ".claude-work"))})
        state = State(global_install=_scope(agents=[link]), global_installs={"work": work})

        stale = _stale(state.global_install, registry, claims=self._claims(state, registry))

        assert stale == {link}

    def test_the_install_being_replaced_does_not_claim_itself(self, env):
        home, dist, registry = env
        link = _link(dist, home, "agents", "lead.md")
        state = State(global_install=_scope(agents=[link]))

        assert _stale(state.global_install, registry, claims=self._claims(state, registry)) == {link}

    def test_a_claim_is_per_cli(self, env):
        home, dist, registry = env
        codex = home / ".codex" / "agents"
        codex.mkdir(parents=True)
        agent = codex / "lead.toml"
        agent.symlink_to(dist / "codex" / "agents" / "lead.toml")
        old = ScopeState(mode="symlink", clis={"codex": BackendState()})
        other_cli_same_dir = ScopeState(mode="symlink", clis={"claude": BackendState(
            global_home_override=str(home / ".codex"))})
        state = State(global_install=old, global_installs={"work": other_cli_same_dir})

        assert _stale(old, registry, claims=self._claims(state, registry)) == {agent}

    def test_a_local_install_claims_the_dirs_under_its_own_project(self, env, tmp_path):
        home, dist, registry = env
        project_a, project_b = tmp_path / "a", tmp_path / "b"
        for project in (project_a, project_b):
            (project / ".codex" / "agents").mkdir(parents=True)
        agent = project_a / ".codex" / "agents" / "lead.toml"
        agent.symlink_to(dist / "codex" / "agents" / "lead.toml")
        old = ScopeState(mode="symlink", clis={"codex": BackendState()})
        state = State(local_installs={str(project_a): old,
                                      str(project_b): ScopeState(mode="symlink", clis={"codex": BackendState()})})

        assert _stale(old, registry, scope="local", project=project_a,
                      claims=self._claims(state, registry, "local", project_a)) == {agent}

        shared = State(local_installs={str(project_a): old,
                                       str(project_a) + "#work": ScopeState(
                                           mode="symlink", profile_label="work",
                                           clis={"codex": BackendState()})})
        assert _stale(old, registry, scope="local", project=project_a,
                      claims=self._claims(shared, registry, "local", project_a)) == set()

    def _mirror_entry(self, name, dist) -> Path:
        mirror = config.AGENTS_HOME / "skills"
        mirror.mkdir(parents=True, exist_ok=True)
        (mirror / name).symlink_to(dist / "skills" / name)
        return mirror / name

    def _global_with_mirror(self, *entries) -> ScopeState:
        return _scope(skills_mirror=entries)

    def test_a_mirror_entry_is_claimed_by_the_other_installs_that_record_it(self, env):
        _home, dist, registry = env
        kept, dropped = self._mirror_entry("kept", dist), self._mirror_entry("dropped", dist)
        old = self._global_with_mirror(kept, dropped)
        state = State(global_install=old, global_installs={"work": self._global_with_mirror(kept)})

        assert _stale(old, registry, claims=self._claims(state, registry)) == {dropped}

    def test_one_other_global_install_without_mirror_records_claims_the_whole_mirror(self, env):
        _home, dist, registry = env
        entries = [self._mirror_entry(n, dist) for n in ("a", "b")]
        old = self._global_with_mirror(*entries)
        state = State(global_install=old, global_installs={
            "work": self._global_with_mirror(entries[0]), "legacy": _scope(agents=[])})

        assert _stale(old, registry, claims=self._claims(state, registry)) == set()

    def test_a_local_install_does_not_claim_the_mirror(self, env, tmp_path):
        _home, dist, registry = env
        entry = self._mirror_entry("a", dist)
        old = self._global_with_mirror(entry)
        state = State(global_install=old, local_installs={str(tmp_path / "p"): _scope(agents=[])})

        assert _stale(old, registry, claims=self._claims(state, registry)) == {entry}


class TestRemoveStale:
    def test_an_owned_link_is_unlinked_and_its_emptied_directory_goes(self, env):
        home, dist, registry = env
        link = _link(dist, home, "commands", "c.md")
        stale = stale_placements(_scope(commands=[link]), "global", None, [], Claims(), registry)

        removed = remove_stale(stale)

        assert removed == [link]
        assert not link.is_symlink()
        assert not link.parent.exists()

    def test_a_directory_with_something_else_in_it_stays(self, env):
        home, dist, registry = env
        link = _link(dist, home, "commands", "c.md")
        (link.parent / "mine.md").write_text("mine")
        stale = stale_placements(_scope(commands=[link]), "global", None, [], Claims(), registry)

        remove_stale(stale)

        assert (link.parent / "mine.md").read_text() == "mine"

    def test_a_link_the_user_retargeted_after_the_set_was_computed_is_kept(self, env):
        home, dist, registry = env
        link = _link(dist, home, "skills", "a")
        stale = stale_placements(_scope(skills=[link]), "global", None, [], Claims(), registry)
        link.unlink()
        link.symlink_to("/elsewhere/a")

        assert remove_stale(stale) == []
        assert link.is_symlink()

    def test_a_copy_edited_after_the_set_was_computed_is_kept(self, env):
        home, _dist, registry = env
        skill = home / ".claude" / "skills" / "tdd"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("# tdd")
        (skill / "ref.md").write_text("ref")
        old = ScopeState(mode="copy", clis={"claude": BackendState(installed={"skills": {
            "tdd": InstalledItem(sha=tree_sha(skill), target=str(skill), mode="copy")}})})
        stale = stale_placements(old, "global", None, [], Claims(), registry)
        assert len(stale) == 1
        (skill / "ref.md").write_text("ref, edited")

        assert remove_stale(stale) == []
        assert (skill / "ref.md").read_text() == "ref, edited"

    def test_an_unedited_copied_directory_is_removed_whole(self, env):
        home, _dist, registry = env
        skill = home / ".claude" / "skills" / "tdd"
        (skill / "refs").mkdir(parents=True)
        (skill / "SKILL.md").write_text("# tdd")
        old = ScopeState(mode="copy", clis={"claude": BackendState(installed={"skills": {
            "tdd": InstalledItem(sha=tree_sha(skill), target=str(skill), mode="copy")}})})

        remove_stale(stale_placements(old, "global", None, [], Claims(), registry))

        assert not skill.exists()

    def test_each_removal_is_reported(self, env, capsys):
        home, dist, registry = env
        link = _link(dist, home, "skills", "a")

        remove_stale(stale_placements(_scope(skills=[link]), "global", None, [], Claims(), registry))

        assert f"REMOVED  {link}" in capsys.readouterr().out


class TestDroppedHooks:
    def test_a_cli_the_new_install_drops_loses_its_hook(self, env):
        home, _dist, registry = env
        old = ScopeState(mode="symlink", clis={"claude": BackendState(), "codex": BackendState()})

        dropped = dropped_hook_backends(old, ["claude"], "global", None, Claims(), registry)

        assert [b.name for b in dropped] == ["codex"]
        assert dropped[0].global_home == home / ".codex"

    def test_a_cli_without_a_session_hook_has_none_to_remove(self, env):
        _home, _dist, registry = env
        old = ScopeState(mode="symlink", clis={"opencode": BackendState()})

        assert dropped_hook_backends(old, [], "global", None, Claims(), registry) == []

    def test_another_install_using_the_same_home_keeps_the_hook(self, env):
        _home, _dist, registry = env
        old = ScopeState(mode="symlink", clis={"codex": BackendState()})
        state = State(global_install=old, global_installs={"work": ScopeState(
            mode="symlink", profile_label="work", clis={"codex": BackendState()})})
        claims = claims_of_others(state, "global", None, "", registry)

        assert dropped_hook_backends(old, [], "global", None, claims, registry) == []

    def test_a_local_hook_is_addressed_by_the_projects_absolute_path(self, env, tmp_path):
        _home, _dist, registry = env
        project = tmp_path / "project"
        old = ScopeState(mode="symlink", clis={"codex": BackendState()})

        (dropped,) = dropped_hook_backends(old, [], "local", project, Claims(), registry)

        assert Path(dropped.local_dir) == project / ".codex"


def test_manifest_targets_lists_every_recorded_path(env):
    home, dist, _registry = env
    a, b = _link(dist, home, "skills", "a"), _link(dist, home, "agents", "x.md")

    assert manifest_targets(_scope(skills=[a], agents=[b])) == {a, b}
    assert manifest_targets(None) == set()
