"""Functional tests for the install command lifecycle."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

import agent_notes.config as config
from agent_notes.domain.cli_backend import CLIBackend
from agent_notes.registries.cli_registry import CLIRegistry


# ── Shared helpers ────────────────────────────────────────────────────────────

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


def _fake_registry(tmp_path: Path) -> CLIRegistry:
    home = tmp_path / "global_home"
    home.mkdir(parents=True, exist_ok=True)
    backend = _make_backend("claude", home)
    return CLIRegistry([backend])


def _seed_dist(tmp_path: Path) -> Path:
    """Create a minimal fake dist tree so installer has files to copy."""
    dist = tmp_path / "dist"
    (dist / "claude" / "agents").mkdir(parents=True)
    (dist / "claude" / "agents" / "lead.md").write_text("# lead")
    (dist / "claude").mkdir(parents=True, exist_ok=True)
    (dist / "claude" / "CLAUDE.md").write_text("# config")
    return dist


def _setup(tmp_path, monkeypatch):
    """Redirect state.json, dist, and AGENTS_HOME to tmp; return (registry, dist)."""
    dist = _seed_dist(tmp_path)
    registry = _fake_registry(tmp_path)
    xdg = tmp_path / "config"
    xdg.mkdir()
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
    monkeypatch.setattr(config, "DIST_DIR", dist)
    monkeypatch.setattr(config, "DIST_SKILLS_DIR", dist / "skills")
    monkeypatch.setattr(config, "DIST_RULES_DIR", dist / "rules")
    monkeypatch.setattr(config, "AGENTS_HOME", tmp_path / "agents_home")
    return registry, dist


# build() is lazily imported inside install(), so patch it at its definition site.
_PATCH_BUILD = "agent_notes.commands.build.build"


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestInstallCreatesStateJson:
    def test_install_creates_state_json(self, tmp_path, monkeypatch):
        registry, _ = _setup(tmp_path, monkeypatch)

        with patch(_PATCH_BUILD), \
             patch("agent_notes.services.installer.load_registry", return_value=registry), \
             patch("agent_notes.services.installer._install_session_hook"):
            from agent_notes.commands.install import install
            install(local=False, copy=False)

        from agent_notes.services.state_store import state_file
        sf = state_file()
        assert sf.exists(), "state.json was not created"
        data = json.loads(sf.read_text())
        assert "global" in data
        assert data["global"] is not None
        assert "installed_at" in data["global"]


class TestInstallLocalWritesToLocalDir:
    def test_install_with_local_flag_writes_to_local_dir(self, tmp_path, monkeypatch):
        registry, _ = _setup(tmp_path, monkeypatch)
        project_dir = tmp_path / "myproject"
        project_dir.mkdir()
        monkeypatch.chdir(project_dir)

        with patch(_PATCH_BUILD), \
             patch("agent_notes.services.installer.load_registry", return_value=registry), \
             patch("agent_notes.services.installer._install_session_hook"):
            from agent_notes.commands.install import install
            install(local=True, copy=True)

        from agent_notes.services.state_store import load_state
        state = load_state()
        assert state is not None
        assert str(project_dir.resolve()) in state.local_installs, \
            "local install was not recorded in state"


class TestInstallCopyFlag:
    def test_install_with_copy_flag_uses_copy_not_symlink(self, tmp_path, monkeypatch):
        registry, _ = _setup(tmp_path, monkeypatch)
        project_dir = tmp_path / "proj"
        project_dir.mkdir()
        monkeypatch.chdir(project_dir)

        with patch(_PATCH_BUILD), \
             patch("agent_notes.services.installer.load_registry", return_value=registry), \
             patch("agent_notes.services.installer._install_session_hook"):
            from agent_notes.commands.install import install
            install(local=True, copy=True)

        from agent_notes.services.state_store import load_state
        state = load_state()
        assert state is not None
        key = str(project_dir.resolve())
        assert state.local_installs[key].mode == "copy"


class TestInstallIdempotent:
    def test_install_idempotent(self, tmp_path, monkeypatch):
        registry, _ = _setup(tmp_path, monkeypatch)

        with patch(_PATCH_BUILD), \
             patch("agent_notes.services.installer.load_registry", return_value=registry), \
             patch("agent_notes.services.installer._install_session_hook"), \
             patch("agent_notes.commands.install._verify_install", return_value=[]):
            from agent_notes.commands.install import install
            install(local=False, copy=False)
            # Second call detects existing install; must not corrupt state
            install(local=False, copy=False)

        from agent_notes.services.state_store import load_state
        state = load_state()
        assert state is not None
        assert state.global_install is not None


class TestInstallAbortsOnCopyWithoutLocal:
    def test_install_aborts_on_copy_without_local(self, tmp_path, monkeypatch, capsys):
        """--copy without --local prints an error and does not write state.json."""
        _setup(tmp_path, monkeypatch)

        with patch(_PATCH_BUILD):
            from agent_notes.commands.install import install
            install(local=False, copy=True)

        out = capsys.readouterr().out
        assert "copy" in out.lower() or "local" in out.lower()

        from agent_notes.services.state_store import state_file
        assert not state_file().exists(), "state.json should not exist after aborted install"
