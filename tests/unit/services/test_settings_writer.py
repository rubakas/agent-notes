"""Tests for agent_notes.services.settings_writer."""
import json
import pytest
from pathlib import Path

from agent_notes.services.settings_writer import (
    install_allow_entry,
    install_hook,
    remove_hook,
    has_hook,
    remove_allow_entry,
)


class TestInstallAllowEntry:
    def test_adds_pattern_to_fresh_settings(self, tmp_path):
        settings_path = tmp_path / "settings.json"
        install_allow_entry(settings_path, "Bash(cost-report)")

        data = json.loads(settings_path.read_text())
        assert data["permissions"]["allow"] == ["Bash(cost-report)"]

    def test_idempotent_does_not_duplicate(self, tmp_path):
        settings_path = tmp_path / "settings.json"
        install_allow_entry(settings_path, "Bash(cost-report)")
        install_allow_entry(settings_path, "Bash(cost-report)")

        data = json.loads(settings_path.read_text())
        assert data["permissions"]["allow"].count("Bash(cost-report)") == 1

    def test_handles_missing_settings_file(self, tmp_path):
        settings_path = tmp_path / "nonexistent" / "settings.json"
        install_allow_entry(settings_path, "Bash(cost-report)")

        assert settings_path.exists()
        data = json.loads(settings_path.read_text())
        assert "Bash(cost-report)" in data["permissions"]["allow"]

    def test_appends_to_existing_allow_list(self, tmp_path):
        settings_path = tmp_path / "settings.json"
        settings_path.write_text(json.dumps({
            "permissions": {"allow": ["Bash(existing-cmd)"]}
        }, indent=2) + "\n")

        install_allow_entry(settings_path, "Bash(cost-report)")

        data = json.loads(settings_path.read_text())
        assert "Bash(existing-cmd)" in data["permissions"]["allow"]
        assert "Bash(cost-report)" in data["permissions"]["allow"]

    def test_preserves_other_top_level_keys(self, tmp_path):
        settings_path = tmp_path / "settings.json"
        settings_path.write_text(json.dumps({
            "hooks": {"SessionStart": [{"matcher": "", "hooks": []}]},
        }, indent=2) + "\n")

        install_allow_entry(settings_path, "Bash(cost-report)")

        data = json.loads(settings_path.read_text())
        assert "hooks" in data
        assert data["permissions"]["allow"] == ["Bash(cost-report)"]

    def test_corrupt_json_resets_to_empty_and_overwrites(self, tmp_path):
        settings_path = tmp_path / "settings.json"
        settings_path.write_text("not valid json {{{")

        install_allow_entry(settings_path, "Bash(cost-report)")

        data = json.loads(settings_path.read_text())
        assert data["permissions"]["allow"] == ["Bash(cost-report)"]


class TestInstallHook:
    def test_creates_hook_entry(self, tmp_path):
        settings_path = tmp_path / "settings.json"
        install_hook(settings_path, "SessionStart", "echo hello")

        data = json.loads(settings_path.read_text())
        hooks = data["hooks"]["SessionStart"]
        commands = [h["command"] for entry in hooks for h in entry.get("hooks", [])]
        assert "echo hello" in commands

    def test_idempotent_does_not_duplicate(self, tmp_path):
        settings_path = tmp_path / "settings.json"
        install_hook(settings_path, "SessionStart", "echo hello")
        install_hook(settings_path, "SessionStart", "echo hello")

        data = json.loads(settings_path.read_text())
        hooks = data["hooks"]["SessionStart"]
        commands = [h["command"] for entry in hooks for h in entry.get("hooks", [])]
        assert commands.count("echo hello") == 1

    def test_creates_parent_dir_if_missing(self, tmp_path):
        settings_path = tmp_path / "nested" / "settings.json"
        install_hook(settings_path, "SessionStart", "echo hello")
        assert settings_path.exists()


class TestRemoveHook:
    def test_removes_existing_hook(self, tmp_path):
        settings_path = tmp_path / "settings.json"
        install_hook(settings_path, "SessionStart", "echo hello")
        assert has_hook(settings_path, "SessionStart", "echo hello")

        remove_hook(settings_path, "SessionStart", "echo hello")

        assert not has_hook(settings_path, "SessionStart", "echo hello")

    def test_noop_if_hook_missing(self, tmp_path):
        settings_path = tmp_path / "settings.json"
        settings_path.write_text(json.dumps({"permissions": {"allow": ["x"]}}) + "\n")

        remove_hook(settings_path, "SessionStart", "echo hello")

        data = json.loads(settings_path.read_text())
        assert data["permissions"]["allow"] == ["x"]

    def test_noop_if_settings_file_absent(self, tmp_path):
        settings_path = tmp_path / "settings.json"
        remove_hook(settings_path, "SessionStart", "echo hello")  # must not raise


class TestHasHook:
    def test_returns_true_when_hook_present(self, tmp_path):
        settings_path = tmp_path / "settings.json"
        install_hook(settings_path, "SessionStart", "echo hello")

        assert has_hook(settings_path, "SessionStart", "echo hello") is True

    def test_returns_false_when_hook_absent(self, tmp_path):
        settings_path = tmp_path / "settings.json"
        settings_path.write_text(json.dumps({}) + "\n")

        assert has_hook(settings_path, "SessionStart", "echo hello") is False

    def test_returns_false_when_file_absent(self, tmp_path):
        settings_path = tmp_path / "settings.json"
        assert has_hook(settings_path, "SessionStart", "echo hello") is False


class TestInstallHookMultiplePerEvent:
    def test_two_hooks_same_event_preserves_both(self, tmp_path):
        settings_path = tmp_path / "settings.json"
        install_hook(settings_path, "SessionStart", "echo first")
        install_hook(settings_path, "SessionStart", "echo second")

        data = json.loads(settings_path.read_text())
        hooks = data["hooks"]["SessionStart"]
        commands = [h["command"] for entry in hooks for h in entry.get("hooks", [])]
        assert "echo first" in commands
        assert "echo second" in commands

    def test_three_hooks_same_event_preserves_all(self, tmp_path):
        settings_path = tmp_path / "settings.json"
        install_hook(settings_path, "SessionStart", "echo one")
        install_hook(settings_path, "SessionStart", "echo two")
        install_hook(settings_path, "SessionStart", "echo three")

        data = json.loads(settings_path.read_text())
        hooks = data["hooks"]["SessionStart"]
        commands = [h["command"] for entry in hooks for h in entry.get("hooks", [])]
        assert commands == ["echo one", "echo two", "echo three"]

    def test_hooks_different_events_independent(self, tmp_path):
        settings_path = tmp_path / "settings.json"
        install_hook(settings_path, "SessionStart", "echo start")
        install_hook(settings_path, "Stop", "echo stop")

        data = json.loads(settings_path.read_text())

        start_hooks = data["hooks"]["SessionStart"]
        start_commands = [h["command"] for entry in start_hooks for h in entry.get("hooks", [])]
        assert start_commands == ["echo start"]

        stop_hooks = data["hooks"]["Stop"]
        stop_commands = [h["command"] for entry in stop_hooks for h in entry.get("hooks", [])]
        assert stop_commands == ["echo stop"]

    def test_idempotent_with_multiple_existing(self, tmp_path):
        settings_path = tmp_path / "settings.json"
        install_hook(settings_path, "SessionStart", "echo A")
        install_hook(settings_path, "SessionStart", "echo B")
        install_hook(settings_path, "SessionStart", "echo A")  # duplicate

        data = json.loads(settings_path.read_text())
        hooks = data["hooks"]["SessionStart"]
        commands = [h["command"] for entry in hooks for h in entry.get("hooks", [])]
        assert commands.count("echo A") == 1
        assert "echo B" in commands

    def test_preserves_permissions_when_adding_hooks(self, tmp_path):
        settings_path = tmp_path / "settings.json"
        settings_path.write_text(json.dumps({
            "permissions": {"allow": ["Bash(some-cmd)"]}
        }, indent=2) + "\n")

        install_hook(settings_path, "SessionStart", "echo first")
        install_hook(settings_path, "SessionStart", "echo second")

        data = json.loads(settings_path.read_text())
        assert data["permissions"]["allow"] == ["Bash(some-cmd)"]

        hooks = data["hooks"]["SessionStart"]
        commands = [h["command"] for entry in hooks for h in entry.get("hooks", [])]
        assert "echo first" in commands
        assert "echo second" in commands


class TestRemoveHookMultiple:
    def test_remove_one_of_two_preserves_other(self, tmp_path):
        settings_path = tmp_path / "settings.json"
        install_hook(settings_path, "SessionStart", "echo A")
        install_hook(settings_path, "SessionStart", "echo B")

        remove_hook(settings_path, "SessionStart", "echo A")

        data = json.loads(settings_path.read_text())
        hooks = data["hooks"]["SessionStart"]
        commands = [h["command"] for entry in hooks for h in entry.get("hooks", [])]
        assert "echo A" not in commands
        assert "echo B" in commands

    def test_remove_last_cleans_up_event_and_hooks_key(self, tmp_path):
        settings_path = tmp_path / "settings.json"
        install_hook(settings_path, "SessionStart", "echo A")
        install_hook(settings_path, "SessionStart", "echo B")

        remove_hook(settings_path, "SessionStart", "echo A")
        remove_hook(settings_path, "SessionStart", "echo B")

        data = json.loads(settings_path.read_text())
        assert "hooks" not in data


class TestRemoveAllowEntry:
    def test_removes_existing_pattern(self, tmp_path):
        settings_path = tmp_path / "settings.json"
        install_allow_entry(settings_path, "Bash(cost-report)")
        install_allow_entry(settings_path, "Bash(other-cmd)")

        remove_allow_entry(settings_path, "Bash(cost-report)")

        data = json.loads(settings_path.read_text())
        assert "Bash(cost-report)" not in data["permissions"]["allow"]
        assert "Bash(other-cmd)" in data["permissions"]["allow"]

    def test_noop_if_pattern_absent(self, tmp_path):
        settings_path = tmp_path / "settings.json"
        settings_path.write_text(json.dumps({
            "permissions": {"allow": ["Bash(other-cmd)"]}
        }) + "\n")

        remove_allow_entry(settings_path, "Bash(cost-report)")

        data = json.loads(settings_path.read_text())
        assert data["permissions"]["allow"] == ["Bash(other-cmd)"]

    def test_noop_if_settings_file_absent(self, tmp_path):
        settings_path = tmp_path / "settings.json"
        remove_allow_entry(settings_path, "Bash(cost-report)")  # must not raise
