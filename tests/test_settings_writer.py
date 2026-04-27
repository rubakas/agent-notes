"""Tests for agent_notes/services/settings_writer.py."""
import json
import pytest
from pathlib import Path

from agent_notes.services.settings_writer import install_hook, remove_hook, has_hook


HOOK_EVENT = "PreToolUse"
COMMAND = "/usr/local/bin/agent-notes-context"


class TestInstallHook:
    """install_hook() must write a well-formed settings.json."""

    def test_creates_settings_file_when_absent(self, tmp_path):
        settings = tmp_path / "settings.json"
        install_hook(settings, HOOK_EVENT, COMMAND)
        assert settings.exists()

    def test_settings_file_is_valid_json(self, tmp_path):
        settings = tmp_path / "settings.json"
        install_hook(settings, HOOK_EVENT, COMMAND)
        data = json.loads(settings.read_text())
        assert isinstance(data, dict)

    def test_hook_event_key_present_in_hooks(self, tmp_path):
        settings = tmp_path / "settings.json"
        install_hook(settings, HOOK_EVENT, COMMAND)
        data = json.loads(settings.read_text())
        assert HOOK_EVENT in data.get("hooks", {})

    def test_command_present_in_hook_entry(self, tmp_path):
        settings = tmp_path / "settings.json"
        install_hook(settings, HOOK_EVENT, COMMAND)
        data = json.loads(settings.read_text())
        entries = data["hooks"][HOOK_EVENT]
        commands = [
            h.get("command")
            for entry in entries
            for h in entry.get("hooks", [])
        ]
        assert COMMAND in commands

    def test_idempotent_does_not_duplicate_entry(self, tmp_path):
        settings = tmp_path / "settings.json"
        install_hook(settings, HOOK_EVENT, COMMAND)
        install_hook(settings, HOOK_EVENT, COMMAND)
        data = json.loads(settings.read_text())
        entries = data["hooks"][HOOK_EVENT]
        commands = [
            h.get("command")
            for entry in entries
            for h in entry.get("hooks", [])
        ]
        assert commands.count(COMMAND) == 1

    def test_merges_with_existing_other_keys(self, tmp_path):
        settings = tmp_path / "settings.json"
        existing = {"someOtherKey": "someValue", "model": "claude-sonnet"}
        settings.write_text(json.dumps(existing))

        install_hook(settings, HOOK_EVENT, COMMAND)

        data = json.loads(settings.read_text())
        assert data.get("someOtherKey") == "someValue"
        assert data.get("model") == "claude-sonnet"
        assert HOOK_EVENT in data.get("hooks", {})

    def test_merges_with_existing_hooks_under_different_event(self, tmp_path):
        settings = tmp_path / "settings.json"
        existing = {
            "hooks": {
                "PostToolUse": [
                    {"matcher": "", "hooks": [{"type": "command", "command": "other-cmd"}]}
                ]
            }
        }
        settings.write_text(json.dumps(existing))

        install_hook(settings, HOOK_EVENT, COMMAND)

        data = json.loads(settings.read_text())
        assert "PostToolUse" in data["hooks"]
        assert HOOK_EVENT in data["hooks"]

    def test_handles_corrupt_settings_file(self, tmp_path):
        settings = tmp_path / "settings.json"
        settings.write_text("this is not json {{{{")

        # Must not raise
        install_hook(settings, HOOK_EVENT, COMMAND)

        data = json.loads(settings.read_text())
        assert HOOK_EVENT in data.get("hooks", {})

    def test_handles_empty_settings_file(self, tmp_path):
        settings = tmp_path / "settings.json"
        settings.write_text("")

        install_hook(settings, HOOK_EVENT, COMMAND)

        data = json.loads(settings.read_text())
        assert HOOK_EVENT in data.get("hooks", {})

    def test_creates_parent_directories(self, tmp_path):
        settings = tmp_path / "nested" / "dir" / "settings.json"
        install_hook(settings, HOOK_EVENT, COMMAND)
        assert settings.exists()


class TestRemoveHook:
    """remove_hook() must cleanly excise a previously installed hook."""

    def test_removes_installed_hook(self, tmp_path):
        settings = tmp_path / "settings.json"
        install_hook(settings, HOOK_EVENT, COMMAND)
        remove_hook(settings, HOOK_EVENT, COMMAND)
        assert not has_hook(settings, HOOK_EVENT, COMMAND)

    def test_removes_hook_event_key_when_empty(self, tmp_path):
        settings = tmp_path / "settings.json"
        install_hook(settings, HOOK_EVENT, COMMAND)
        remove_hook(settings, HOOK_EVENT, COMMAND)

        data = json.loads(settings.read_text())
        assert HOOK_EVENT not in data.get("hooks", {})

    def test_removes_hooks_key_when_no_hooks_remain(self, tmp_path):
        settings = tmp_path / "settings.json"
        install_hook(settings, HOOK_EVENT, COMMAND)
        remove_hook(settings, HOOK_EVENT, COMMAND)

        data = json.loads(settings.read_text())
        assert "hooks" not in data

    def test_preserves_other_hook_events(self, tmp_path):
        settings = tmp_path / "settings.json"
        other_cmd = "other-command"
        install_hook(settings, "PostToolUse", other_cmd)
        install_hook(settings, HOOK_EVENT, COMMAND)

        remove_hook(settings, HOOK_EVENT, COMMAND)

        data = json.loads(settings.read_text())
        assert "PostToolUse" in data.get("hooks", {})

    def test_noop_when_file_does_not_exist(self, tmp_path):
        settings = tmp_path / "nonexistent.json"
        # Must not raise
        remove_hook(settings, HOOK_EVENT, COMMAND)

    def test_noop_when_hook_already_absent(self, tmp_path):
        settings = tmp_path / "settings.json"
        settings.write_text(json.dumps({"model": "claude"}))

        remove_hook(settings, HOOK_EVENT, COMMAND)

        data = json.loads(settings.read_text())
        assert data.get("model") == "claude"


class TestHasHook:
    """has_hook() must accurately report whether a hook is installed."""

    def test_returns_true_when_hook_installed(self, tmp_path):
        settings = tmp_path / "settings.json"
        install_hook(settings, HOOK_EVENT, COMMAND)
        assert has_hook(settings, HOOK_EVENT, COMMAND) is True

    def test_returns_false_when_hook_absent(self, tmp_path):
        settings = tmp_path / "settings.json"
        settings.write_text(json.dumps({}))
        assert has_hook(settings, HOOK_EVENT, COMMAND) is False

    def test_returns_false_when_file_missing(self, tmp_path):
        settings = tmp_path / "missing.json"
        assert has_hook(settings, HOOK_EVENT, COMMAND) is False

    def test_returns_false_after_removal(self, tmp_path):
        settings = tmp_path / "settings.json"
        install_hook(settings, HOOK_EVENT, COMMAND)
        remove_hook(settings, HOOK_EVENT, COMMAND)
        assert has_hook(settings, HOOK_EVENT, COMMAND) is False

    def test_returns_false_for_corrupt_file(self, tmp_path):
        settings = tmp_path / "settings.json"
        settings.write_text("not-valid-json")
        assert has_hook(settings, HOOK_EVENT, COMMAND) is False

    def test_does_not_match_different_command(self, tmp_path):
        settings = tmp_path / "settings.json"
        install_hook(settings, HOOK_EVENT, COMMAND)
        assert has_hook(settings, HOOK_EVENT, "some-other-command") is False
