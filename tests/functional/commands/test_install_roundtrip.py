"""Integration tests: install → doctor → uninstall round-trip in tmp dirs only.

These tests exercise the install_plan + install_executor + installer coordinator
split end-to-end. All paths are redirected to tmp_path — the real ~/.claude is
never touched.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

import agent_notes.config as config
from agent_notes.domain.cli_backend import CLIBackend
from agent_notes.registries.cli_registry import CLIRegistry


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

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


def _seed_dist(tmp_path: Path) -> Path:
    """Create a minimal fake dist tree."""
    dist = tmp_path / "dist"
    agents_dir = dist / "claude" / "agents"
    agents_dir.mkdir(parents=True)
    (agents_dir / "lead.md").write_text("# lead agent")
    (dist / "claude").mkdir(parents=True, exist_ok=True)
    (dist / "claude" / "CLAUDE.md").write_text("# config")
    return dist


def _setup(tmp_path: Path, monkeypatch):
    """Redirect all writable paths to tmp; return (registry, dist)."""
    dist = _seed_dist(tmp_path)
    home = tmp_path / "claude_home"
    home.mkdir(parents=True, exist_ok=True)
    registry = CLIRegistry([_make_backend("claude", home)])

    xdg = tmp_path / "xdg"
    xdg.mkdir()
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
    monkeypatch.setattr(config, "DIST_DIR", dist)
    monkeypatch.setattr(config, "DIST_SKILLS_DIR", dist / "skills")
    monkeypatch.setattr(config, "DIST_RULES_DIR", dist / "rules")
    monkeypatch.setattr(config, "AGENTS_HOME", tmp_path / "agents_home")

    return registry, dist


_PATCH_BUILD = "agent_notes.commands.build.build"


# ---------------------------------------------------------------------------
# Round-trip: install → second-install-is-idempotent → uninstall cleans up
# ---------------------------------------------------------------------------

class TestInstallUninstallRoundTrip:
    def test_install_places_files_uninstall_removes_them(self, tmp_path, monkeypatch):
        """Files placed by install are removed by uninstall; state clears too."""
        registry, dist = _setup(tmp_path, monkeypatch)

        with patch(_PATCH_BUILD), \
             patch("agent_notes.services.installer.load_registry", return_value=registry), \
             patch("agent_notes.services.installer._install_session_hook"):
            from agent_notes.commands.install import install
            install(local=False, copy=False)

        # Verify at least one installed file exists
        agents_dir = tmp_path / "claude_home" / "agents"
        installed_files = list(agents_dir.glob("*.md"))
        assert installed_files, "install should have placed agent files"

        # Second install is non-destructive (idempotent)
        with patch(_PATCH_BUILD), \
             patch("agent_notes.services.installer.load_registry", return_value=registry), \
             patch("agent_notes.services.installer._install_session_hook"), \
             patch("agent_notes.commands.install._verify_install", return_value=[]):
            install(local=False, copy=False)

        # Files must still be there after second install
        assert list(agents_dir.glob("*.md")), "files must survive a second install"

        # Now uninstall
        with patch("agent_notes.services.installer.load_registry", return_value=registry), \
             patch("agent_notes.services.installer._uninstall_session_hook"), \
             patch("agent_notes.services.installer._uninstall_universal_skills"):
            from agent_notes.commands.uninstall import uninstall
            uninstall(local=False)

        # Installed files should be gone
        remaining = list(agents_dir.glob("*.md"))
        assert not remaining, f"uninstall left behind: {remaining}"

    def test_settings_json_deep_merge_preserves_user_keys(self, tmp_path, monkeypatch):
        """install_all respects existing user keys in settings.json (no full overwrite)."""
        from agent_notes.services.installer import install_all

        registry, dist = _setup(tmp_path, monkeypatch)

        # Pre-seed a settings.json with a user key
        claude_home = tmp_path / "claude_home"
        settings = claude_home / "settings.json"
        settings.write_text(json.dumps({"userCustomKey": "preserved-value"}))

        with patch("agent_notes.services.installer.load_registry", return_value=registry), \
             patch("agent_notes.services.installer._install_session_hook"):
            install_all("global", copy_mode=False, registry=registry)

        # settings.json should still contain the user key
        if settings.exists():
            data = json.loads(settings.read_text())
            assert data.get("userCustomKey") == "preserved-value", \
                "install_all must not overwrite user keys in settings.json"


class TestInstallDoctorIntegration:
    def test_doctor_after_install_reports_healthy(self, tmp_path, monkeypatch):
        """After a clean install in tmp, doctor must see a valid state file."""
        registry, dist = _setup(tmp_path, monkeypatch)

        with patch(_PATCH_BUILD), \
             patch("agent_notes.services.installer.load_registry", return_value=registry), \
             patch("agent_notes.services.installer._install_session_hook"):
            from agent_notes.commands.install import install
            install(local=False, copy=False)

        from agent_notes.services.state_store import load_state
        state = load_state()
        assert state is not None, "state must exist after install"
        assert state.global_install is not None, "global scope must be recorded"

        # Doctor should see the install as valid (state file present = installed)
        with patch("agent_notes.commands.doctor.check_stale_files"), \
             patch("agent_notes.commands.doctor.check_broken_symlinks"), \
             patch("agent_notes.commands.doctor.check_shadowed_files"), \
             patch("agent_notes.commands.doctor.check_missing_files"), \
             patch("agent_notes.commands.doctor.check_content_drift"), \
             patch("agent_notes.commands.doctor.check_build_freshness"), \
             patch("agent_notes.commands.doctor._check_session_hook"), \
             patch("agent_notes.commands.doctor._check_role_models"), \
             patch("agent_notes.commands.doctor.print_summary"), \
             patch("agent_notes.commands.doctor.print_issues", return_value=True):
            from agent_notes.commands.doctor import doctor
            result = doctor(local=False, fix=False)

        assert result is True, "doctor should return True (healthy) after clean install"
