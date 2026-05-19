"""Tests for the migrate-memory command."""
import pytest
from agent_notes.commands.memory.migrate_memory import do_migrate_memory
from agent_notes.commands.memory import _common


class TestMigrateMemoryCommand:
    def test_non_obsidian_bails(self, monkeypatch, capsys):
        monkeypatch.setattr(
            "agent_notes.commands.memory._common._load_memory_config",
            lambda: ("local", None),
        )
        do_migrate_memory()
        out = capsys.readouterr().out
        assert "only available for the obsidian backend" in out

    def test_no_pending_prints_message(self, monkeypatch, capsys, tmp_path):
        monkeypatch.setattr(
            "agent_notes.commands.memory._common._load_memory_config",
            lambda: ("obsidian", tmp_path),
        )
        monkeypatch.setattr(
            "agent_notes.services.migrations.get_pending_migrations",
            lambda: [],
        )
        do_migrate_memory()
        out = capsys.readouterr().out
        assert "No pending" in out
