"""Functional tests for the doctor command."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

import agent_notes.config as config
from agent_notes.domain.diagnostics import Issue, FixAction


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
