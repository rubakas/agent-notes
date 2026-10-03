"""settings.json and hooks.json belong to the user: edits are surgical, atomic and backed up
(spec 007 review round 1, M4)."""
import json
import os
from pathlib import Path

import pytest

from agent_notes.services import settings_writer as sw


@pytest.fixture(autouse=True)
def fresh_run():
    for name in ("_backed_up", "_warned"):
        getattr(sw, name, set()).clear()


def _new_run():
    getattr(sw, "_backed_up", set()).clear()


def _baks(path: Path) -> list[Path]:
    return sorted(p for p in path.parent.iterdir() if ".bak." in p.name)


def _write(path: Path, data) -> None:
    path.write_text(data if isinstance(data, str) else json.dumps(data, indent=2))


class TestAFileThatDoesNotParse:
    @pytest.mark.parametrize("call", [
        lambda p: sw.install_hook(p, "SessionStart", "cmd"),
        lambda p: sw.remove_hook(p, "SessionStart", "cmd"),
        lambda p: sw.install_allow_entry(p, "Bash(x)"),
        lambda p: sw.remove_allow_entry(p, "Bash(x)"),
        lambda p: sw.remove_matching_allow_entries(p, "Bash(agent-notes"),
    ], ids=["install_hook", "remove_hook", "install_allow", "remove_allow", "remove_matching"])
    def test_is_never_overwritten_and_the_warning_names_it(self, tmp_path, capsys, call):
        path = tmp_path / "settings.json"
        _write(path, '{ "permissions": { "allow": [ "Bash(mine)" ,, ] } ')
        before = path.read_bytes()

        call(path)

        assert path.read_bytes() == before
        assert str(path) in capsys.readouterr().err
        assert _baks(path) == []

    def test_the_warning_is_printed_once_per_file(self, tmp_path, capsys):
        path = tmp_path / "settings.json"
        _write(path, "{ not json")

        sw.install_hook(path, "SessionStart", "a")
        sw.install_hook(path, "SessionStart", "b")
        sw.install_allow_entry(path, "Bash(x)")

        assert capsys.readouterr().err.count(str(path)) == 1

    def test_has_hook_is_false(self, tmp_path):
        path = tmp_path / "settings.json"
        _write(path, "{ not json")

        assert sw.has_hook(path, "SessionStart", "cmd") is False

    def test_a_missing_file_is_still_created(self, tmp_path):
        path = tmp_path / "sub" / "settings.json"

        sw.install_hook(path, "SessionStart", "cmd")

        assert sw.has_hook(path, "SessionStart", "cmd")


class TestABackupBeforeTheFirstRewrite:
    def test_one_per_run_holding_the_original_bytes(self, tmp_path):
        path = tmp_path / "settings.json"
        _write(path, {"theme": "dark", "userKey": 1})
        original = path.read_bytes()

        sw.install_hook(path, "SessionStart", "a")
        sw.install_hook(path, "Stop", "b")
        sw.install_allow_entry(path, "Bash(x)")

        (backup,) = _baks(path)
        assert backup.read_bytes() == original
        assert json.loads(path.read_text())["theme"] == "dark"

    def test_a_file_that_does_not_exist_yet_has_nothing_to_back_up(self, tmp_path):
        path = tmp_path / "settings.json"

        sw.install_hook(path, "SessionStart", "a")

        assert _baks(path) == []

    def test_an_unchanged_file_is_not_rewritten_and_not_backed_up(self, tmp_path):
        path = tmp_path / "settings.json"
        sw.install_hook(path, "SessionStart", "a")
        _new_run()

        sw.install_hook(path, "SessionStart", "a")

        assert _baks(path) == []

    def test_a_second_run_backs_up_again(self, tmp_path):
        path = tmp_path / "settings.json"
        _write(path, {"a": 1})
        sw.install_hook(path, "SessionStart", "a")
        _new_run()

        sw.install_hook(path, "SessionStart", "b")

        assert len(_baks(path)) == 2


class TestAtomicWrites:
    def test_the_write_goes_through_a_temp_file_and_os_replace(self, tmp_path, monkeypatch):
        path = tmp_path / "settings.json"
        _write(path, {"a": 1})
        replaced = []
        real = os.replace
        monkeypatch.setattr(os, "replace", lambda src, dst: (replaced.append((Path(src), Path(dst))), real(src, dst))[1])

        sw.install_hook(path, "SessionStart", "a")

        assert [dst for _src, dst in replaced] == [path]
        assert replaced[0][0].parent == path.parent and replaced[0][0] != path
        assert not [p for p in path.parent.iterdir() if "tmp" in p.name]

    def test_a_failed_write_leaves_the_original_intact(self, tmp_path, monkeypatch):
        path = tmp_path / "settings.json"
        _write(path, {"a": 1})
        before = path.read_bytes()

        def boom(src, dst):
            raise OSError("disk full")

        monkeypatch.setattr(os, "replace", boom)
        with pytest.raises(OSError):
            sw.install_hook(path, "SessionStart", "a")

        assert path.read_bytes() == before
        assert not [p for p in path.parent.iterdir() if "tmp" in p.name]

    def test_a_symlinked_settings_file_stays_a_symlink(self, tmp_path):
        real = tmp_path / "dotfiles" / "settings.json"
        real.parent.mkdir()
        _write(real, {"a": 1})
        link = tmp_path / "settings.json"
        link.symlink_to(real)

        sw.install_hook(link, "SessionStart", "a")

        assert link.is_symlink()
        assert "SessionStart" in json.loads(real.read_text())["hooks"]

    def test_the_file_mode_is_kept(self, tmp_path):
        path = tmp_path / "settings.json"
        _write(path, {"a": 1})
        os.chmod(path, 0o600)

        sw.install_hook(path, "SessionStart", "a")

        assert path.stat().st_mode & 0o777 == 0o600


class TestRemoveHookIsSurgical:
    def test_only_our_command_leaves_an_entry_that_has_other_hooks(self, tmp_path):
        path = tmp_path / "settings.json"
        _write(path, {"hooks": {"SessionStart": [{"matcher": "", "hooks": [
            {"type": "command", "command": "mine"},
            {"type": "command", "command": "ours"},
        ]}]}})

        sw.remove_hook(path, "SessionStart", "ours")

        data = json.loads(path.read_text())
        assert data["hooks"]["SessionStart"][0]["hooks"] == [{"type": "command", "command": "mine"}]

    def test_the_entry_goes_when_nothing_else_is_in_it(self, tmp_path):
        path = tmp_path / "settings.json"
        _write(path, {"hooks": {"SessionStart": [
            {"matcher": "", "hooks": [{"type": "command", "command": "ours"}]},
            {"matcher": "", "hooks": [{"type": "command", "command": "mine"}]}]}})

        sw.remove_hook(path, "SessionStart", "ours")

        entries = json.loads(path.read_text())["hooks"]["SessionStart"]
        assert [e["hooks"][0]["command"] for e in entries] == ["mine"]

    def test_the_event_and_hooks_keys_go_when_they_end_up_empty(self, tmp_path):
        path = tmp_path / "settings.json"
        _write(path, {"theme": "dark", "hooks": {"SessionStart": [
            {"matcher": "", "hooks": [{"type": "command", "command": "ours"}]}]}})

        sw.remove_hook(path, "SessionStart", "ours")

        assert json.loads(path.read_text()) == {"theme": "dark"}

    def test_an_entry_without_a_hooks_list_is_left_alone(self, tmp_path):
        path = tmp_path / "settings.json"
        _write(path, {"hooks": {"SessionStart": [{"matcher": "x"}, "weird"]}})
        before = path.read_bytes()

        sw.remove_hook(path, "SessionStart", "ours")

        assert path.read_bytes() == before


class TestRemoveMatchingAllowEntriesIsExact:
    def test_our_entries_go_and_a_neighbouring_command_stays(self, tmp_path):
        path = tmp_path / "settings.json"
        _write(path, {"permissions": {"allow": [
            "Bash(agent-notes memory *)", "Bash(agent-notes cost-report)",
            "Bash(agent-notes hook memory-bridge)", "Bash(agent-notes:*)",
            "Bash(agent-notes-mytool:*)", "Bash(agent-notes2 run)", "Bash(git status)"]}})

        sw.remove_matching_allow_entries(path, "Bash(agent-notes")

        assert json.loads(path.read_text())["permissions"]["allow"] == [
            "Bash(agent-notes-mytool:*)", "Bash(agent-notes2 run)", "Bash(git status)"]


class TestDropIfEmpty:
    OURS = {"SessionStart": [{"matcher": "", "hooks": [{"type": "command", "command": "ours"}]}]}

    def test_the_file_and_the_backup_taken_for_it_go_and_the_directory_can_be_pruned(self, tmp_path):
        directory = tmp_path / ".codex"
        directory.mkdir()
        path = directory / "hooks.json"
        _write(path, {"hooks": self.OURS})

        sw.remove_hook(path, "SessionStart", "ours")
        assert len(_baks(path)) == 1
        assert sw.drop_if_empty(path)

        assert not path.exists()
        assert list(directory.iterdir()) == []

    @pytest.mark.parametrize("left", [
        {}, {"hooks": {}}, {"permissions": {}}, {"permissions": {"allow": []}},
        {"hooks": {}, "permissions": {"allow": []}},
    ])
    def test_a_file_left_with_only_empty_containers_is_dropped(self, tmp_path, left):
        path = tmp_path / "settings.json"
        _write(path, {"hooks": self.OURS, "permissions": {"allow": ["Bash(agent-notes:*)"]}})

        sw.remove_hook(path, "SessionStart", "ours")
        sw.remove_matching_allow_entries(path, "Bash(agent-notes")
        _write(path, left)
        assert sw.drop_if_empty(path)

        assert not path.exists()

    @pytest.mark.parametrize("left", [
        {"permissions": {"deny": []}}, {"model": "x"}, {"hooks": {"Stop": []}},
        {"permissions": {"allow": ["Bash(git status)"]}}, {"hooks": [], "permissions": {}},
    ])
    def test_a_file_that_still_holds_something_is_kept(self, tmp_path, left):
        path = tmp_path / "settings.json"
        _write(path, {"hooks": self.OURS})
        sw.remove_hook(path, "SessionStart", "ours")
        _write(path, left)

        assert not sw.drop_if_empty(path)

        assert path.exists()

    def test_a_symlinked_settings_file_is_never_removed_nor_is_its_target(self, tmp_path):
        target = tmp_path / "dotfiles" / "settings.json"
        target.parent.mkdir()
        _write(target, {"hooks": self.OURS})
        link = tmp_path / "settings.json"
        link.symlink_to(target)

        sw.remove_hook(link, "SessionStart", "ours")
        assert json.loads(target.read_text()) == {}
        assert not sw.drop_if_empty(link)

        assert link.is_symlink()
        assert target.exists()


class TestTheWarningSaysWhatHappened:
    def test_an_install_says_the_hook_was_not_installed_once(self, tmp_path, capsys):
        path = tmp_path / "settings.json"
        _write(path, "{ not json")

        with sw.transaction(path):
            sw.install_hook(path, "SessionStart", "cmd")

        err = capsys.readouterr().err
        assert err.count("hook was not installed") == 1
        assert err.count(str(path)) == 1

    def test_a_removal_still_says_it_left_the_file_unchanged(self, tmp_path, capsys):
        path = tmp_path / "settings.json"
        _write(path, "{ not json")

        with sw.transaction(path):
            sw.remove_hook(path, "SessionStart", "cmd")

        assert "left it unchanged" in capsys.readouterr().err
