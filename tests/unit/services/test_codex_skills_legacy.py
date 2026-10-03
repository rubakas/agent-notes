"""Codex skills: no longer installed to ~/.codex/skills, still swept on uninstall.

Codex CLI reads skills from .agents/skills and ~/.agents/skills — never from
~/.codex/skills. The dead tree must not be recreated, but existing installs
must still be cleaned up.
"""
import os
import shutil
from pathlib import Path

import agent_notes.config as config
from agent_notes.registries.cli_registry import load_registry
from agent_notes.services.installer import (
    install_component_for_backend,
    legacy_skills_dir_for,
    target_dir_for,
    uninstall_component_for_backend,
)


def _ships_docker(legacy: Path) -> Path:
    """What an old install left behind: a copy of the skill exactly as agent-notes ships it."""
    shutil.copytree(config.DIST_SKILLS_DIR / "docker", legacy / "docker")
    return legacy / "docker"


def _codex_backend(tmp_path: Path):
    backend = load_registry().get("codex")
    return backend.with_global_home(tmp_path / "codex_home").with_local_dir(
        str(tmp_path / ".codex")
    )


class TestCodexSkillsNotInstalled:
    def test_registry_codex_does_not_support_skills(self):
        assert not load_registry().get("codex").supports("skills")

    def test_no_skills_target_dir(self, tmp_path):
        backend = _codex_backend(tmp_path)
        assert target_dir_for(backend, "skills", "global") is None
        assert target_dir_for(backend, "skills", "local") is None

    def test_install_writes_nothing_to_codex_skills_dir(self, tmp_path):
        backend = _codex_backend(tmp_path)
        install_component_for_backend(backend, "skills", "global", copy_mode=True)
        assert not (backend.global_home / "skills").exists()


class TestCodexSkillsLegacyCleanup:
    def test_legacy_dir_resolves_for_codex_only(self, tmp_path):
        backend = _codex_backend(tmp_path)
        assert legacy_skills_dir_for(backend, "global") == backend.global_home / "skills"
        assert legacy_skills_dir_for(backend, "local") == Path(backend.local_dir) / "skills"
        assert legacy_skills_dir_for(load_registry().get("claude"), "global") is None

    def test_uninstall_removes_only_skills_agent_notes_ships(self, tmp_path):
        backend = _codex_backend(tmp_path)
        legacy = backend.global_home / "skills"
        legacy.mkdir(parents=True)
        _ships_docker(legacy)

        count = uninstall_component_for_backend(backend, "skills", "global", copy_mode=True)

        assert count == 1
        assert not (legacy / "docker").exists()

    def test_uninstall_leaves_user_authored_skill_untouched(self, tmp_path):
        backend = _codex_backend(tmp_path)
        legacy = backend.global_home / "skills"
        legacy.mkdir(parents=True)
        _ships_docker(legacy)
        mine = legacy / "my-team-skill"
        mine.mkdir(parents=True)
        (mine / "SKILL.md").write_text("mine")

        uninstall_component_for_backend(backend, "skills", "global", copy_mode=True)

        assert not (legacy / "docker").exists()
        assert (mine / "SKILL.md").read_text() == "mine"

    def test_uninstall_refuses_to_follow_a_symlinked_legacy_dir(self, tmp_path):
        backend = _codex_backend(tmp_path)
        victim = tmp_path / "victim"
        (victim / "docker").mkdir(parents=True)
        (victim / "docker" / "SKILL.md").write_text("precious")
        backend.global_home.mkdir(parents=True, exist_ok=True)
        legacy = backend.global_home / "skills"
        legacy.symlink_to(victim)

        count = uninstall_component_for_backend(backend, "skills", "global", copy_mode=True)

        assert count == 0
        assert (victim / "docker" / "SKILL.md").read_text() == "precious"
        assert legacy.is_symlink()

    def test_uninstall_is_noop_when_legacy_tree_absent(self, tmp_path):
        backend = _codex_backend(tmp_path)
        assert uninstall_component_for_backend(backend, "skills", "global", copy_mode=True) == 0

    def test_install_sweeps_the_legacy_tree(self, tmp_path):
        backend = _codex_backend(tmp_path)
        legacy = backend.global_home / "skills"
        legacy.mkdir(parents=True)
        _ships_docker(legacy)
        mine = legacy / "my-team-skill"
        mine.mkdir(parents=True)

        install_component_for_backend(backend, "skills", "global", copy_mode=True)

        assert not (legacy / "docker").exists()
        assert mine.exists()


class TestTheLegacySweepJudgesOwnershipNotNames:
    """A shipped name is not proof: a user's edited copy or own link with that name stays (S1, M3)."""

    def _legacy(self, tmp_path):
        backend = _codex_backend(tmp_path)
        legacy = backend.global_home / "skills"
        legacy.mkdir(parents=True)
        return backend, legacy

    def test_a_copy_edited_by_the_user_is_kept_on_uninstall(self, tmp_path):
        backend, legacy = self._legacy(tmp_path)
        docker = _ships_docker(legacy)
        (docker / "SKILL.md").write_text("my own take on docker")

        count = uninstall_component_for_backend(backend, "skills", "global", copy_mode=True)

        assert count == 0
        assert (docker / "SKILL.md").read_text() == "my own take on docker"

    def test_a_file_the_user_added_inside_a_copy_keeps_it(self, tmp_path):
        backend, legacy = self._legacy(tmp_path)
        docker = _ships_docker(legacy)
        (docker / "my-notes.md").write_text("notes")

        uninstall_component_for_backend(backend, "skills", "global", copy_mode=True)

        assert (docker / "my-notes.md").read_text() == "notes"

    def test_a_users_own_link_with_a_shipped_name_is_kept(self, tmp_path):
        backend, legacy = self._legacy(tmp_path)
        (legacy / "docker").symlink_to("/elsewhere/docker")

        count = uninstall_component_for_backend(backend, "skills", "global", copy_mode=True)

        assert count == 0
        assert os.readlink(legacy / "docker") == "/elsewhere/docker"

    def test_our_own_link_is_removed(self, tmp_path):
        backend, legacy = self._legacy(tmp_path)
        (legacy / "docker").symlink_to(config.DIST_SKILLS_DIR / "docker")

        count = uninstall_component_for_backend(backend, "skills", "global", copy_mode=False)

        assert count == 1
        assert not (legacy / "docker").is_symlink()

    def test_our_unedited_copy_is_removed_even_when_the_state_says_symlink(self, tmp_path):
        backend, legacy = self._legacy(tmp_path)
        _ships_docker(legacy)

        count = uninstall_component_for_backend(backend, "skills", "global", copy_mode=False)

        assert count == 1
        assert not (legacy / "docker").exists()

    def test_an_edited_copy_survives_the_install_time_sweep(self, tmp_path):
        backend, legacy = self._legacy(tmp_path)
        docker = _ships_docker(legacy)
        (docker / "SKILL.md").write_text("mine")

        install_component_for_backend(backend, "skills", "global", copy_mode=True)

        assert (docker / "SKILL.md").read_text() == "mine"

    def test_a_users_link_survives_the_install_time_sweep(self, tmp_path):
        backend, legacy = self._legacy(tmp_path)
        (legacy / "docker").symlink_to("/elsewhere/docker")

        install_component_for_backend(backend, "skills", "global", copy_mode=True)

        assert os.readlink(legacy / "docker") == "/elsewhere/docker"
