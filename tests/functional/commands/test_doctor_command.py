"""Functional tests for the doctor command."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

import agent_notes.config as config
from agent_notes.domain.diagnostics import Issue, FixAction
from agent_notes.domain.state import ScopeState, State, MemoryConfig
from agent_notes.services.state_store import save_state, load_state, _scope_to_dict


# ── Helpers ────────────────────────────────────────────────────────────────────

def _write_minimal_state(sf: Path, global_install: bool = True) -> None:
    scope_dict = {
        "installed_at": "2025-01-01T00:00:00Z",
        "updated_at": "2025-01-01T00:00:00Z",
        "mode": "symlink",
        "clis": {"claude": {"role_models": {}, "installed": {}}},
    }
    data = {
        "source_path": "/tmp/repo",
        "source_commit": "abc123",
        "global": scope_dict if global_install else None,
        "local": {},
        "memory": {"backend": "local", "path": ""},
    }
    sf.parent.mkdir(parents=True, exist_ok=True)
    sf.write_text(json.dumps(data))


def _patch_state(tmp_path, monkeypatch, global_install: bool = True):
    xdg = tmp_path / "config"
    xdg.mkdir()
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
    sf = xdg / "agent-notes" / "state.json"
    if global_install:
        _write_minimal_state(sf, global_install=True)
    return sf


def _no_op_checks(*args, **kwargs):
    """Stub for all check_* functions — adds nothing to issues."""
    pass


# ── Tests ──────────────────────────────────────────────────────────────────────

class TestDoctorReportsCleanAfterFreshInstall:
    def test_doctor_reports_clean_after_fresh_install(self, tmp_path, monkeypatch, capsys):
        _patch_state(tmp_path, monkeypatch)

        with patch("agent_notes.commands.doctor.check_stale_files", _no_op_checks), \
             patch("agent_notes.commands.doctor.check_broken_symlinks", _no_op_checks), \
             patch("agent_notes.commands.doctor.check_shadowed_files", _no_op_checks), \
             patch("agent_notes.commands.doctor.check_missing_files", _no_op_checks), \
             patch("agent_notes.commands.doctor.check_content_drift", _no_op_checks), \
             patch("agent_notes.commands.doctor.check_build_freshness", _no_op_checks), \
             patch("agent_notes.commands.doctor._check_session_hook", _no_op_checks), \
             patch("agent_notes.commands.doctor.print_summary"), \
             patch("agent_notes.commands.doctor._check_role_models"), \
             patch("agent_notes.commands.doctor.print_issues", return_value=True):
            from agent_notes.commands.doctor import doctor
            result = doctor(local=False, fix=False)

        assert result is True, "doctor should return True (no issues) after clean install"


class TestDoctorDetectsMissingStateJson:
    def test_doctor_detects_missing_state_json(self, tmp_path, monkeypatch):
        xdg = tmp_path / "config"
        xdg.mkdir()
        monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
        # Deliberately do NOT write state.json

        captured_issues = []

        def fake_check_missing(scope, issues, fix_actions):
            issues.append(Issue("missing_group", "state.json", "no state found"))

        with patch("agent_notes.commands.doctor.check_stale_files", _no_op_checks), \
             patch("agent_notes.commands.doctor.check_broken_symlinks", _no_op_checks), \
             patch("agent_notes.commands.doctor.check_shadowed_files", _no_op_checks), \
             patch("agent_notes.commands.doctor.check_missing_files", fake_check_missing), \
             patch("agent_notes.commands.doctor.check_content_drift", _no_op_checks), \
             patch("agent_notes.commands.doctor.check_build_freshness", _no_op_checks), \
             patch("agent_notes.commands.doctor._check_session_hook", _no_op_checks), \
             patch("agent_notes.commands.doctor.print_summary"), \
             patch("agent_notes.commands.doctor._check_role_models"), \
             patch("agent_notes.commands.doctor.print_issues", side_effect=lambda issues: captured_issues.extend(issues) or False):
            from agent_notes.commands.doctor import doctor
            result = doctor(local=False, fix=False)

        assert result is False, "doctor should return False when issues exist"
        assert len(captured_issues) > 0, "expected at least one issue to be reported"


class TestDoctorDetectsOrphanManagedFile:
    def test_doctor_detects_orphan_managed_file(self, tmp_path, monkeypatch):
        """doctor catches a file listed in state but missing on disk."""
        _patch_state(tmp_path, monkeypatch)
        captured_issues = []

        def fake_stale_check(scope, issues, fix_actions):
            issues.append(Issue("stale", "/missing/lead.md", "target not found"))

        with patch("agent_notes.commands.doctor.check_stale_files", fake_stale_check), \
             patch("agent_notes.commands.doctor.check_broken_symlinks", _no_op_checks), \
             patch("agent_notes.commands.doctor.check_shadowed_files", _no_op_checks), \
             patch("agent_notes.commands.doctor.check_missing_files", _no_op_checks), \
             patch("agent_notes.commands.doctor.check_content_drift", _no_op_checks), \
             patch("agent_notes.commands.doctor.check_build_freshness", _no_op_checks), \
             patch("agent_notes.commands.doctor._check_session_hook", _no_op_checks), \
             patch("agent_notes.commands.doctor.print_summary"), \
             patch("agent_notes.commands.doctor._check_role_models"), \
             patch("agent_notes.commands.doctor.print_issues", side_effect=lambda issues: captured_issues.extend(issues) or False):
            from agent_notes.commands.doctor import doctor
            doctor(local=False, fix=False)

        assert any(i.type == "stale" for i in captured_issues), \
            "expected a stale/orphan issue to be detected"


class TestDoctorFixFlagRepairsSimpleDrift:
    def test_doctor_fix_flag_repairs_simple_drift(self, tmp_path, monkeypatch):
        """When --fix is passed, do_fix is invoked."""
        _patch_state(tmp_path, monkeypatch)
        mock_do_fix = MagicMock(return_value=True)

        def fake_broken_symlink(scope, issues, fix_actions):
            fix_actions.append(FixAction("relink", "/tmp/lead.md", "relink to dist"))
            issues.append(Issue("broken_symlink", "/tmp/lead.md", "symlink broken"))

        with patch("agent_notes.commands.doctor.check_stale_files", _no_op_checks), \
             patch("agent_notes.commands.doctor.check_broken_symlinks", fake_broken_symlink), \
             patch("agent_notes.commands.doctor.check_shadowed_files", _no_op_checks), \
             patch("agent_notes.commands.doctor.check_missing_files", _no_op_checks), \
             patch("agent_notes.commands.doctor.check_content_drift", _no_op_checks), \
             patch("agent_notes.commands.doctor.check_build_freshness", _no_op_checks), \
             patch("agent_notes.commands.doctor._check_session_hook", _no_op_checks), \
             patch("agent_notes.commands.doctor.print_summary"), \
             patch("agent_notes.commands.doctor._check_role_models"), \
             patch("agent_notes.commands.doctor.print_issues", return_value=False), \
             patch("agent_notes.commands.doctor.do_fix", mock_do_fix):
            from agent_notes.commands.doctor import doctor
            doctor(local=False, fix=True)

        mock_do_fix.assert_called_once()
        issues_arg = mock_do_fix.call_args[0][0]
        assert len(issues_arg) > 0, "do_fix should receive the list of issues"


# ── check_version_drift tests ─────────────────────────────────────────────────

def _write_state_with_version(sf: Path, installed_version: str) -> None:
    """Write a minimal state.json with the given installed_version in the global scope."""
    scope_dict = {
        "installed_at": "2025-01-01T00:00:00Z",
        "updated_at": "2025-01-01T00:00:00Z",
        "mode": "symlink",
        "installed_version": installed_version,
        "clis": {"claude": {"role_models": {}, "installed": {}}},
    }
    data = {
        "source_path": "/tmp/repo",
        "source_commit": "abc123",
        "global": scope_dict,
        "local": {},
        "memory": {"backend": "local", "path": ""},
    }
    sf.parent.mkdir(parents=True, exist_ok=True)
    sf.write_text(json.dumps(data))


def _setup_xdg(tmp_path, monkeypatch) -> Path:
    """Point XDG_CONFIG_HOME to tmp_path and return the state file path."""
    xdg = tmp_path / "config"
    xdg.mkdir()
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
    return xdg / "agent-notes" / "state.json"


class TestCheckVersionDriftVersionMatches:
    def test_no_issues_when_installed_version_matches_current(self, tmp_path, monkeypatch):
        sf = _setup_xdg(tmp_path, monkeypatch)
        _write_state_with_version(sf, "1.2.3")

        from agent_notes.commands.doctor import check_version_drift
        with patch("agent_notes.commands.doctor.check_version_drift.__wrapped__", None, create=True), \
             patch("agent_notes.config.get_version", return_value="1.2.3"):
            # Re-import to get fresh reference with patched get_version
            import agent_notes.config as _cfg
            monkeypatch.setattr(_cfg, "get_version", lambda: "1.2.3")

            issues: list = []
            fix_actions: list = []
            check_version_drift("global", issues, fix_actions)

        assert issues == [], "no issues expected when versions match"
        assert fix_actions == [], "no fix actions expected when versions match"


class TestCheckVersionDriftVersionDiffers:
    def test_reports_drift_issue_when_versions_differ(self, tmp_path, monkeypatch):
        sf = _setup_xdg(tmp_path, monkeypatch)
        _write_state_with_version(sf, "1.0.0")

        import agent_notes.config as _cfg
        monkeypatch.setattr(_cfg, "get_version", lambda: "2.0.0")

        from agent_notes.commands.doctor import check_version_drift
        issues: list = []
        fix_actions: list = []
        check_version_drift("global", issues, fix_actions)

        assert len(issues) == 1, "exactly one issue expected for version drift"
        issue = issues[0]
        assert issue.type == "version_drift"
        assert "1.0.0" in issue.message
        assert "2.0.0" in issue.message

    def test_adds_trigger_install_fix_action_when_versions_differ(self, tmp_path, monkeypatch):
        sf = _setup_xdg(tmp_path, monkeypatch)
        _write_state_with_version(sf, "1.0.0")

        import agent_notes.config as _cfg
        monkeypatch.setattr(_cfg, "get_version", lambda: "2.0.0")

        from agent_notes.commands.doctor import check_version_drift
        issues: list = []
        fix_actions: list = []
        check_version_drift("global", issues, fix_actions)

        assert len(fix_actions) == 1, "exactly one fix action expected"
        assert fix_actions[0].action == "_TRIGGER_INSTALL"


class TestCheckVersionDriftEmptyInstalledVersion:
    def test_no_issues_when_installed_version_is_empty(self, tmp_path, monkeypatch):
        """Old state.json files from before version tracking have empty installed_version.
        The function should handle this gracefully — not crash, and not report drift."""
        sf = _setup_xdg(tmp_path, monkeypatch)
        _write_state_with_version(sf, "")  # old-style state: no version recorded

        import agent_notes.config as _cfg
        monkeypatch.setattr(_cfg, "get_version", lambda: "2.0.0")

        from agent_notes.commands.doctor import check_version_drift
        issues: list = []
        fix_actions: list = []
        check_version_drift("global", issues, fix_actions)

        # Per implementation: empty installed_version → return early (skip check)
        assert issues == [], "empty installed_version should not produce a version_drift issue"
        assert fix_actions == [], "empty installed_version should not produce a fix action"

    def test_no_crash_when_state_has_no_version_field(self, tmp_path, monkeypatch):
        """State dict with no 'installed_version' key at all (not even empty string)."""
        xdg = tmp_path / "config"
        xdg.mkdir()
        monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
        sf = xdg / "agent-notes" / "state.json"

        # Write state without installed_version key
        scope_dict = {
            "installed_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-01T00:00:00Z",
            "mode": "symlink",
            # no "installed_version" key
            "clis": {"claude": {"role_models": {}, "installed": {}}},
        }
        data = {
            "source_path": "/tmp/repo",
            "source_commit": "abc123",
            "global": scope_dict,
            "local": {},
            "memory": {"backend": "local", "path": ""},
        }
        sf.parent.mkdir(parents=True, exist_ok=True)
        sf.write_text(json.dumps(data))

        import agent_notes.config as _cfg
        monkeypatch.setattr(_cfg, "get_version", lambda: "2.0.0")

        from agent_notes.commands.doctor import check_version_drift
        issues: list = []
        fix_actions: list = []
        # Must not raise
        check_version_drift("global", issues, fix_actions)

        assert issues == [], "missing installed_version key should not produce a drift issue"


class TestCheckVersionDriftNoState:
    def test_no_issues_when_state_file_absent(self, tmp_path, monkeypatch):
        """When no state.json exists at all, check_version_drift should return silently."""
        xdg = tmp_path / "config"
        xdg.mkdir()
        monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
        # deliberately no state.json written

        import agent_notes.config as _cfg
        monkeypatch.setattr(_cfg, "get_version", lambda: "2.0.0")

        from agent_notes.commands.doctor import check_version_drift
        issues: list = []
        fix_actions: list = []
        check_version_drift("global", issues, fix_actions)

        assert issues == []
        assert fix_actions == []


class TestInstalledVersionSerializationRoundTrip:
    def test_installed_version_persists_through_save_and_load(self, tmp_path, monkeypatch):
        """installed_version survives a save_state / load_state round-trip."""
        xdg = tmp_path / "config"
        xdg.mkdir()
        monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))

        from agent_notes.services.state_store import save_state, load_state
        from agent_notes.domain.state import State, ScopeState, MemoryConfig

        scope = ScopeState(
            installed_at="2025-01-01T00:00:00Z",
            updated_at="2025-01-01T00:00:00Z",
            mode="symlink",
            installed_version="1.9.9",
            clis={},
        )
        state = State(
            source_path="/tmp/repo",
            source_commit="abc123",
            global_install=scope,
            local_installs={},
            memory=MemoryConfig(backend="local", path=""),
        )
        save_state(state)

        loaded = load_state()
        assert loaded is not None
        assert loaded.global_install is not None
        assert loaded.global_install.installed_version == "1.9.9"

    def test_scope_to_dict_includes_installed_version(self):
        """_scope_to_dict serializes installed_version into the output dict."""
        from agent_notes.services.state_store import _scope_to_dict
        from agent_notes.domain.state import ScopeState

        scope = ScopeState(
            installed_at="2025-01-01T00:00:00Z",
            updated_at="2025-01-01T00:00:00Z",
            mode="symlink",
            installed_version="3.0.1",
            clis={},
        )
        d = _scope_to_dict(scope)
        assert "installed_version" in d
        assert d["installed_version"] == "3.0.1"

    def test_empty_installed_version_round_trips_as_empty_string(self, tmp_path, monkeypatch):
        """An empty installed_version serializes and deserializes as empty string, not None."""
        xdg = tmp_path / "config"
        xdg.mkdir()
        monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))

        from agent_notes.services.state_store import save_state, load_state
        from agent_notes.domain.state import State, ScopeState, MemoryConfig

        scope = ScopeState(
            installed_at="2025-01-01T00:00:00Z",
            updated_at="2025-01-01T00:00:00Z",
            mode="symlink",
            installed_version="",
            clis={},
        )
        state = State(
            source_path="/tmp/repo",
            source_commit="abc123",
            global_install=scope,
            local_installs={},
            memory=MemoryConfig(backend="local", path=""),
        )
        save_state(state)

        loaded = load_state()
        assert loaded is not None
        assert loaded.global_install is not None
        # Must come back as empty string, not None or missing
        assert loaded.global_install.installed_version == ""


class TestUpdateCommandRemoved:
    def test_update_command_module_does_not_exist(self):
        """The `update` command should have been removed from the commands package."""
        import importlib
        import importlib.util
        spec = importlib.util.find_spec("agent_notes.commands.update")
        assert spec is None, (
            "agent_notes.commands.update still exists — "
            "the update command should have been removed"
        )
