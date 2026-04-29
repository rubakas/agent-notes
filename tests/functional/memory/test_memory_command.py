"""Functional tests for the memory command dispatch layer."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


# ── Helpers ────────────────────────────────────────────────────────────────────

def _setup_local_backend(tmp_path, monkeypatch):
    """Configure local memory backend pointing at tmp_path."""
    xdg = tmp_path / "config"
    xdg.mkdir()
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))

    import agent_notes.config as config
    monkeypatch.setattr(config, "MEMORY_DIR", tmp_path / "memory")
    monkeypatch.setattr(config, "BACKUP_DIR", tmp_path / "backup")

    # No state.json → _load_memory_config falls back to local + MEMORY_DIR
    return tmp_path / "memory"


def _setup_obsidian_backend(tmp_path, monkeypatch):
    """Configure obsidian memory backend pointing at tmp_path vault."""
    xdg = tmp_path / "config"
    xdg.mkdir()
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))

    vault = tmp_path / "vault"
    vault.mkdir()

    sf = xdg / "agent-notes" / "state.json"
    sf.parent.mkdir(parents=True, exist_ok=True)
    sf.write_text(json.dumps({
        "source_path": "/tmp/repo",
        "source_commit": "abc123",
        "global": None,
        "local": {},
        "memory": {"backend": "obsidian", "path": str(vault)},
    }))
    return vault


# ── Tests ──────────────────────────────────────────────────────────────────────

class TestMemoryListWhenEmpty:
    def test_memory_list_when_empty(self, tmp_path, monkeypatch, capsys):
        mem_dir = tmp_path / "memory"
        # mem_dir does not exist yet → no memories
        # Patch _load_memory_config so no real state file or MEMORY_DIR is consulted.
        import agent_notes.commands.memory as mem_mod
        monkeypatch.setattr(mem_mod, "_load_memory_config", lambda: ("local", mem_dir))

        from agent_notes.commands.memory import memory
        memory(action="list")  # must not raise

        out = capsys.readouterr().out
        assert "No agent memories" in out or "not found" in out.lower() or "disabled" in out.lower()


class TestMemoryAddPatternWritesToVault:
    def test_memory_add_pattern_writes_to_vault(self, tmp_path, monkeypatch, capsys):
        vault = _setup_obsidian_backend(tmp_path, monkeypatch)

        from agent_notes.commands.memory import memory
        memory(
            action="add",
            name="My Pattern",
            extra=["Body text", "pattern", "coder"],
        )

        out = capsys.readouterr().out
        assert "saved" in out.lower() or "note" in out.lower()

        # File should land in vault/Patterns/
        patterns_dir = vault / "Patterns"
        assert patterns_dir.exists(), "Patterns/ folder was not created"
        notes = list(patterns_dir.glob("*.md"))
        assert len(notes) >= 1, "No note was written to Patterns/"


class TestMemoryIndexRegeneratesIndexMd:
    def test_memory_index_regenerates_index_md(self, tmp_path, monkeypatch, capsys):
        vault = _setup_obsidian_backend(tmp_path, monkeypatch)
        # Seed at least one category folder so index has something to scan
        (vault / "Patterns").mkdir()
        (vault / "Patterns" / "note.md").write_text("# note\n")

        from agent_notes.commands.memory import memory
        memory(action="index")

        assert (vault / "Index.md").exists(), "Index.md was not created by memory index"


class TestMemoryShowUnknownAgentErrors:
    def test_memory_show_unknown_agent_errors(self, tmp_path, monkeypatch, capsys):
        mem_dir = _setup_local_backend(tmp_path, monkeypatch)
        mem_dir.mkdir(parents=True)  # Exists but no "phantom_agent" subdir

        from agent_notes.commands.memory import memory
        with pytest.raises(SystemExit) as exc_info:
            memory(action="show", name="phantom_agent")

        assert exc_info.value.code != 0
        out = capsys.readouterr().out
        assert "phantom_agent" in out or "not found" in out.lower()


class TestMemoryVaultPrintsBackendPath:
    def test_memory_vault_prints_backend_path(self, tmp_path, monkeypatch, capsys):
        vault = _setup_obsidian_backend(tmp_path, monkeypatch)

        from agent_notes.commands.memory import memory
        memory(action="vault")

        out = capsys.readouterr().out
        assert "obsidian" in out.lower()
        assert str(vault) in out
