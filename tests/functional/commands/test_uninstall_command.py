"""Functional tests for the uninstall command."""
from __future__ import annotations

import json
import pytest
from pathlib import Path
from unittest.mock import patch

import agent_notes.config as config
from agent_notes.domain.cli_backend import CLIBackend
from agent_notes.registries.cli_registry import CLIRegistry


# ── Shared helpers ─────────────────────────────────────────────────────────────

def _make_backend(name: str, home: Path) -> CLIBackend:
    return CLIBackend(
        name=name,
        label=name.title(),
        global_home=home,
        local_dir=f".{name}",
        layout={"agents": "agents/", "config": f"{name.upper()}.md"},
        features={"agents": True, "config": True, "supports_symlink": True},
        global_template=None,
    )


def _seed_installed_files(backend_home: Path, source_dir: Path) -> list[Path]:
    """Create symlinks in agents/ pointing to source_dir (simulates installed symlinks)."""
    agents_dir = backend_home / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    source_dir.mkdir(parents=True, exist_ok=True)
    created = []
    for name in ("lead.md", "coder.md"):
        src = source_dir / name
        src.write_text(f"# {name}")
        link = agents_dir / name
        link.symlink_to(src)
        created.append(link)
    return created


def _write_minimal_state(sf: Path, scope: str = "global", project_path: str | None = None) -> None:
    scope_dict = {
        "installed_at": "2025-01-01T00:00:00Z",
        "updated_at": "2025-01-01T00:00:00Z",
        "mode": "symlink",
        "clis": {"claude": {"role_models": {}, "installed": {}}},
    }
    if scope == "global":
        data = {"source_path": "", "source_commit": "", "global": scope_dict, "local": {}, "memory": {"backend": "local", "path": ""}}
    else:
        data = {"source_path": "", "source_commit": "", "global": None, "local": {project_path: scope_dict}, "memory": {"backend": "local", "path": ""}}
    sf.parent.mkdir(parents=True, exist_ok=True)
    sf.write_text(json.dumps(data))


# ── Tests ──────────────────────────────────────────────────────────────────────

class TestUninstallRemovesManagedFiles:
    def test_uninstall_removes_managed_files(self, tmp_path, monkeypatch):
        backend_home = tmp_path / "claude_home"
        source_dir = tmp_path / "dist_agents"
        registry = CLIRegistry([_make_backend("claude", backend_home)])
        installed = _seed_installed_files(backend_home, source_dir)

        xdg = tmp_path / "config"
        xdg.mkdir()
        monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
        _write_minimal_state(xdg / "agent-notes" / "state.json")

        with patch("agent_notes.services.installer.load_registry", return_value=registry), \
             patch("agent_notes.services.installer._uninstall_universal_skills"), \
             patch("agent_notes.services.installer._uninstall_session_hook"):
            from agent_notes.commands.uninstall import uninstall
            uninstall(local=False)

        for f in installed:
            assert not f.exists(), f"{f.name} should have been removed by uninstall"


class TestUninstallLeavesUserFilesIntact:
    def test_uninstall_leaves_user_files_intact(self, tmp_path, monkeypatch):
        """A pre-existing CLAUDE.md not installed by agent-notes must survive uninstall."""
        backend_home = tmp_path / "claude_home"
        backend_home.mkdir(parents=True, exist_ok=True)
        # Pre-existing user file (not a symlink, not in agents/)
        user_file = backend_home / "CLAUDE.md"
        user_file.write_text("# My notes")

        registry = CLIRegistry([_make_backend("claude", backend_home)])
        xdg = tmp_path / "config"
        xdg.mkdir()
        monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
        _write_minimal_state(xdg / "agent-notes" / "state.json")

        with patch("agent_notes.services.installer.load_registry", return_value=registry), \
             patch("agent_notes.services.installer._uninstall_universal_skills"), \
             patch("agent_notes.services.installer._uninstall_session_hook"):
            from agent_notes.commands.uninstall import uninstall
            uninstall(local=False)

        assert user_file.exists(), "pre-existing CLAUDE.md should not be removed"
        assert user_file.read_text() == "# My notes"


class TestUninstallClearsStateJson:
    def test_uninstall_clears_state_json(self, tmp_path, monkeypatch):
        backend_home = tmp_path / "claude_home"
        registry = CLIRegistry([_make_backend("claude", backend_home)])

        xdg = tmp_path / "config"
        xdg.mkdir()
        monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
        sf = xdg / "agent-notes" / "state.json"
        _write_minimal_state(sf)

        with patch("agent_notes.services.installer.load_registry", return_value=registry), \
             patch("agent_notes.services.installer._uninstall_universal_skills"), \
             patch("agent_notes.services.installer._uninstall_session_hook"):
            from agent_notes.commands.uninstall import uninstall
            uninstall(local=False)

        # State file should be gone (only scope → whole file deleted) or global set to null
        if sf.exists():
            data = json.loads(sf.read_text())
            assert data.get("global") is None, "global scope should be cleared"
        # else it was fully deleted — also acceptable


class TestUninstallRemovesCopyModeFiles:
    def test_uninstall_removes_copy_mode_files(self, tmp_path, monkeypatch):
        """Plain files written by --copy install must be removed on uninstall."""
        backend_home = tmp_path / "claude_home"
        agents_dir = backend_home / "agents"
        agents_dir.mkdir(parents=True, exist_ok=True)
        copy_file = agents_dir / "lead.md"
        copy_file.write_text("# lead")

        registry = CLIRegistry([_make_backend("claude", backend_home)])
        xdg = tmp_path / "config"
        xdg.mkdir()
        monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))

        sf = xdg / "agent-notes" / "state.json"
        scope_dict = {"installed_at": "2025-01-01T00:00:00Z", "updated_at": "2025-01-01T00:00:00Z",
                      "mode": "copy", "clis": {"claude": {"role_models": {}, "installed": {}}}}
        data = {"source_path": "", "source_commit": "", "global": scope_dict, "local": {}, "memory": {"backend": "local", "path": ""}}
        sf.parent.mkdir(parents=True, exist_ok=True)
        sf.write_text(json.dumps(data))

        with patch("agent_notes.services.installer.load_registry", return_value=registry), \
             patch("agent_notes.services.installer._uninstall_universal_skills"), \
             patch("agent_notes.services.installer._uninstall_session_hook"):
            from agent_notes.commands.uninstall import uninstall
            uninstall(local=False)

        assert not copy_file.exists(), "copy-installed file should be removed"


class TestUninstallPreservesUnmanagedFiles:
    def test_uninstall_preserves_unmanaged_files(self, tmp_path, monkeypatch):
        """A plain file agent-notes did NOT install must survive uninstall even in copy mode."""
        backend_home = tmp_path / "claude_home"
        backend_home.mkdir(parents=True, exist_ok=True)
        unmanaged = backend_home / "random-user-file.md"
        unmanaged.write_text("user content")

        registry = CLIRegistry([_make_backend("claude", backend_home)])
        xdg = tmp_path / "config"
        xdg.mkdir()
        monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
        _write_minimal_state(xdg / "agent-notes" / "state.json")

        with patch("agent_notes.services.installer.load_registry", return_value=registry), \
             patch("agent_notes.services.installer._uninstall_universal_skills"), \
             patch("agent_notes.services.installer._uninstall_session_hook"):
            from agent_notes.commands.uninstall import uninstall
            uninstall(local=False)

        assert unmanaged.exists(), "unmanaged file should not be removed"


class TestUninstallIdempotent:
    def test_uninstall_idempotent(self, tmp_path, monkeypatch):
        """Running uninstall twice should not raise."""
        backend_home = tmp_path / "claude_home"
        registry = CLIRegistry([_make_backend("claude", backend_home)])

        xdg = tmp_path / "config"
        xdg.mkdir()
        monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
        _write_minimal_state(xdg / "agent-notes" / "state.json")

        def do_uninstall():
            with patch("agent_notes.services.installer.load_registry", return_value=registry), \
                 patch("agent_notes.services.installer._uninstall_universal_skills"), \
                 patch("agent_notes.services.installer._uninstall_session_hook"):
                from agent_notes.commands.uninstall import uninstall
                uninstall(local=False)

        do_uninstall()
        do_uninstall()  # must not raise
