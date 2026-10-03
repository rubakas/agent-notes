"""A backup is for a file that is not ours (spec 007 FR-A09).

Our own unedited copy is replaced without a .bak, an edited one is backed up, a foreign
symlink is renamed and never unlinked, and the plan counts what place_file will do."""
import os
from pathlib import Path

import pytest

import agent_notes.config as config
from agent_notes.domain.state import BackendState, InstalledItem, ScopeState
from agent_notes.services.fs import place_file
from agent_notes.services.install_ownership import replacing, tree_sha
from agent_notes.services.install_plan import _plan_file, summarize_plan


@pytest.fixture
def dist(tmp_path, monkeypatch):
    dist = tmp_path / "pkg" / "dist"
    dist.mkdir(parents=True)
    monkeypatch.setattr(config, "DIST_DIR", dist)
    return dist


def _manifest(*recorded: Path) -> ScopeState:
    items = {p.name: InstalledItem(sha=tree_sha(p), target=str(p), mode="copy") for p in recorded}
    return ScopeState(mode="copy", clis={"claude": BackendState(installed={"agents": items})})


def _baks(directory: Path) -> list[Path]:
    return sorted(p for p in directory.iterdir() if ".bak." in p.name)


def _file(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


class TestPlaceFile:
    def test_our_unedited_copy_is_replaced_without_a_backup(self, dist, tmp_path):
        src = _file(dist / "lead.md", "new render")
        dst = _file(tmp_path / "home" / "lead.md", "old render")

        with replacing(_manifest(dst)):
            place_file(src, dst, copy_mode=True)

        assert dst.read_text() == "new render"
        assert _baks(dst.parent) == []

    def test_our_unedited_copy_identical_to_the_source_is_left_alone(self, dist, tmp_path):
        src = _file(dist / "lead.md", "same")
        dst = _file(tmp_path / "home" / "lead.md", "same")
        before = dst.stat().st_mtime_ns

        with replacing(_manifest(dst)):
            place_file(src, dst, copy_mode=True)

        assert dst.stat().st_mtime_ns == before
        assert _baks(dst.parent) == []

    def test_a_copy_the_user_edited_is_backed_up(self, dist, tmp_path):
        src = _file(dist / "lead.md", "new render")
        dst = _file(tmp_path / "home" / "lead.md", "old render")
        manifest = _manifest(dst)
        dst.write_text("old render, edited by me")

        with replacing(manifest):
            place_file(src, dst, copy_mode=True)

        assert dst.read_text() == "new render"
        (backup,) = _baks(dst.parent)
        assert backup.read_text() == "old render, edited by me"

    def test_a_file_the_manifest_never_recorded_is_backed_up(self, dist, tmp_path):
        src = _file(dist / "lead.md", "new render")
        dst = _file(tmp_path / "home" / "lead.md", "mine")

        with replacing(None):
            place_file(src, dst, copy_mode=True)

        assert len(_baks(dst.parent)) == 1

    def test_without_an_install_run_nothing_is_recorded_so_it_is_backed_up(self, dist, tmp_path):
        src = _file(dist / "lead.md", "new render")
        dst = _file(tmp_path / "home" / "lead.md", "old render")

        place_file(src, dst, copy_mode=True)

        assert len(_baks(dst.parent)) == 1

    def test_our_copied_directory_is_replaced_without_a_backup(self, dist, tmp_path):
        src = dist / "skills" / "tdd"
        _file(src / "SKILL.md", "# new")
        dst = tmp_path / "home" / "tdd"
        _file(dst / "SKILL.md", "# old")

        with replacing(_manifest(dst)):
            place_file(src, dst, copy_mode=True)

        assert (dst / "SKILL.md").read_text() == "# new"
        assert _baks(dst.parent) == []

    def test_a_copied_directory_with_a_file_the_user_added_is_backed_up(self, dist, tmp_path):
        src = dist / "skills" / "tdd"
        _file(src / "SKILL.md", "# new")
        dst = tmp_path / "home" / "tdd"
        _file(dst / "SKILL.md", "# old")
        manifest = _manifest(dst)
        _file(dst / "mine.md", "my notes")

        with replacing(manifest):
            place_file(src, dst, copy_mode=True)

        (backup,) = _baks(dst.parent)
        assert (backup / "mine.md").read_text() == "my notes"

    def test_flipping_our_copy_to_a_symlink_replaces_it_even_when_identical(self, dist, tmp_path):
        src = _file(dist / "lead.md", "same")
        dst = _file(tmp_path / "home" / "lead.md", "same")

        with replacing(_manifest(dst)):
            place_file(src, dst, copy_mode=False)

        assert dst.is_symlink() and dst.resolve() == src.resolve()
        assert _baks(dst.parent) == []

    def test_a_copy_that_is_not_ours_but_identical_is_left_as_it_was(self, dist, tmp_path):
        src = _file(dist / "lead.md", "same")
        dst = _file(tmp_path / "home" / "lead.md", "same")

        with replacing(None):
            place_file(src, dst, copy_mode=False)

        assert not dst.is_symlink()
        assert _baks(dst.parent) == []

    def test_flipping_our_symlink_to_a_copy_replaces_it(self, dist, tmp_path):
        src = _file(dist / "lead.md", "content")
        dst = tmp_path / "home" / "lead.md"
        dst.parent.mkdir()
        dst.symlink_to(src)

        place_file(src, dst, copy_mode=True)

        assert not dst.is_symlink() and dst.read_text() == "content"
        assert _baks(dst.parent) == []

    def test_a_foreign_symlink_is_renamed_to_a_backup_never_unlinked(self, dist, tmp_path):
        src = _file(dist / "lead.md", "content")
        dst = tmp_path / "home" / "lead.md"
        dst.parent.mkdir()
        dst.symlink_to("/elsewhere/lead.md")

        place_file(src, dst, copy_mode=False)

        assert dst.is_symlink() and dst.resolve() == src.resolve()
        (backup,) = _baks(dst.parent)
        assert backup.is_symlink() and os.readlink(backup) == "/elsewhere/lead.md"

    def test_a_symlink_to_the_same_source_is_just_replaced(self, dist, tmp_path):
        """A link that already points where we are about to link is nobody else's."""
        src = _file(tmp_path / "elsewhere" / "lead.md", "content")
        dst = tmp_path / "home" / "lead.md"
        dst.parent.mkdir()
        dst.symlink_to(src)

        place_file(src, dst, copy_mode=False)

        assert dst.is_symlink() and _baks(dst.parent) == []

    def test_a_link_into_an_old_package_dist_is_ours(self, dist, tmp_path):
        src = _file(dist / "lead.md", "content")
        dst = tmp_path / "home" / "lead.md"
        dst.parent.mkdir()
        dst.symlink_to("/x/site-packages/agent_notes/dist/claude/agents/lead.md")

        place_file(src, dst, copy_mode=False)

        assert _baks(dst.parent) == []


class TestThePlanUsesTheSamePredicate:
    def _action(self, src, dst, copy_mode, manifest=None):
        with replacing(manifest):
            return _plan_file(src, dst, copy_mode)

    def test_our_copy_that_will_be_replaced_is_a_write_with_no_backup(self, dist, tmp_path):
        src = _file(dist / "lead.md", "new")
        dst = _file(tmp_path / "home" / "lead.md", "old")

        action = self._action(src, dst, True, _manifest(dst))

        assert (action.action, action.backup_path) == ("install", None)
        assert summarize_plan([action]).overwrites == []

    def test_our_copy_identical_to_the_source_is_a_skip(self, dist, tmp_path):
        src = _file(dist / "lead.md", "same")
        dst = _file(tmp_path / "home" / "lead.md", "same")

        assert self._action(src, dst, True, _manifest(dst)).action == "skip"

    def test_a_copy_the_user_edited_is_a_backup(self, dist, tmp_path):
        src = _file(dist / "lead.md", "new")
        dst = _file(tmp_path / "home" / "lead.md", "old")
        manifest = _manifest(dst)
        dst.write_text("edited")

        action = self._action(src, dst, True, manifest)

        assert action.action == "overwrite" and action.backup_path is not None

    def test_our_symlink_in_copy_mode_is_a_write_not_a_skip(self, dist, tmp_path):
        """symlink -> copy used to plan 'Install 0 files'."""
        src = _file(dist / "lead.md", "content")
        dst = tmp_path / "home" / "lead.md"
        dst.parent.mkdir()
        dst.symlink_to(src)

        action = self._action(src, dst, True)

        assert action.action == "install"
        assert len(summarize_plan([action]).to_install) == 1

    def test_our_identical_copy_in_symlink_mode_is_a_write(self, dist, tmp_path):
        src = _file(dist / "lead.md", "same")
        dst = _file(tmp_path / "home" / "lead.md", "same")

        assert self._action(src, dst, False, _manifest(dst)).action == "install"

    def test_a_foreign_symlink_is_planned_as_a_backup(self, dist, tmp_path):
        src = _file(dist / "lead.md", "content")
        dst = tmp_path / "home" / "lead.md"
        dst.parent.mkdir()
        dst.symlink_to("/elsewhere/lead.md")

        action = self._action(src, dst, False)

        assert action.action == "overwrite" and action.backup_path is not None
