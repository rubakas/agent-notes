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


class TestCheckSkillFrontmatter:
    """Tests for the warn-only check_skill_frontmatter check."""

    def _make_skill(self, tmp_path, name, frontmatter_extra=""):
        skill_dir = tmp_path / name
        skill_dir.mkdir()
        fm = f"---\nname: {name}\ndescription: \"A test skill.\"\ngroup: process\n{frontmatter_extra}---\n\n# {name}\n"
        (skill_dir / "SKILL.md").write_text(fm)
        return tmp_path

    def test_no_warning_with_valid_skills(self, tmp_path, capsys, monkeypatch):
        """No warnings printed when all skill frontmatter is valid."""
        skills_dir = self._make_skill(tmp_path, "my-skill")

        from agent_notes.registries.skill_registry import load_skill_registry, SkillRegistry
        monkeypatch.setattr(
            "agent_notes.commands.doctor.load_skill_registry",
            lambda: load_skill_registry(skills_dir=skills_dir),
        )

        from agent_notes.commands.doctor import check_skill_frontmatter
        issues: list = []
        fix_actions: list = []
        check_skill_frontmatter("global", issues, fix_actions)

        out = capsys.readouterr().out
        assert "[skill-frontmatter]" not in out
        assert issues == [], "check_skill_frontmatter must not append to issues"
        assert fix_actions == [], "check_skill_frontmatter must not append to fix_actions"

    def test_warning_on_invalid_group(self, tmp_path, capsys, monkeypatch):
        """Prints a warning for an invalid group value; does not add to issues."""
        skills_dir = self._make_skill(tmp_path, "bad-group-skill", "group: invalid-group\n")
        # Overwrite the pre-written group: process with invalid-group
        skill_md = skills_dir / "bad-group-skill" / "SKILL.md"
        text = skill_md.read_text().replace("group: process\n", "")
        skill_md.write_text(text)
        # Write skill with invalid group
        skill_md.write_text(
            "---\nname: bad-group-skill\ndescription: \"A test skill.\"\ngroup: invalid-group\n---\n\n# bad-group-skill\n"
        )

        from agent_notes.registries.skill_registry import load_skill_registry
        monkeypatch.setattr(
            "agent_notes.commands.doctor.load_skill_registry",
            lambda: load_skill_registry(skills_dir=skills_dir),
        )

        from agent_notes.commands.doctor import check_skill_frontmatter
        issues: list = []
        fix_actions: list = []
        check_skill_frontmatter("global", issues, fix_actions)

        out = capsys.readouterr().out
        assert "[skill-frontmatter]" in out
        assert "invalid-group" in out
        assert issues == [], "invalid group must NOT add a fatal Issue"
        assert fix_actions == [], "invalid group must NOT add a FixAction"

    def test_warning_on_invalid_requires_memory_token(self, tmp_path, capsys, monkeypatch):
        """Prints a warning for an invalid requires_memory token; does not add to issues."""
        skill_dir = tmp_path / "bad-memory-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\nname: bad-memory-skill\ndescription: \"A test skill.\"\ngroup: process\nrequires_memory: obsidian,notabackend\n---\n\n# bad-memory-skill\n"
        )

        from agent_notes.registries.skill_registry import load_skill_registry
        monkeypatch.setattr(
            "agent_notes.commands.doctor.load_skill_registry",
            lambda: load_skill_registry(skills_dir=tmp_path),
        )

        from agent_notes.commands.doctor import check_skill_frontmatter
        issues: list = []
        fix_actions: list = []
        check_skill_frontmatter("global", issues, fix_actions)

        out = capsys.readouterr().out
        assert "[skill-frontmatter]" in out
        assert "notabackend" in out
        assert issues == [], "invalid requires_memory token must NOT add a fatal Issue"
        assert fix_actions == [], "invalid requires_memory token must NOT add a FixAction"

    def test_doctor_exit_code_unaffected_by_skill_warning(self, tmp_path, monkeypatch, capsys):
        """doctor's return value (exit code) is unchanged by skill frontmatter warnings."""
        _patch_state(tmp_path, monkeypatch)

        skill_dir = tmp_path / "skills" / "bad-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            "---\nname: bad-skill\ndescription: \"A test skill.\"\ngroup: bogus\n---\n\n# bad-skill\n"
        )

        from agent_notes.registries.skill_registry import load_skill_registry
        monkeypatch.setattr(
            "agent_notes.commands.doctor.load_skill_registry",
            lambda: load_skill_registry(skills_dir=tmp_path / "skills"),
        )

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

        assert result is True, "skill frontmatter warning must not change doctor's exit result"
        out = capsys.readouterr().out
        assert "[skill-frontmatter]" in out


class TestCheckSkillFrontmatterNoFalsePositivesOnRealSkills:
    """Regression: check_skill_frontmatter must not warn for any skill that ships with the package.

    This guards against _VALID_GROUPS being too narrow and producing false-positive
    warnings for legitimately-grouped skills (e.g. rails-*, docker-*, kamal skills).
    Each parametrized case loads exactly one real skill in isolation so a future
    regression is pinpointed to the offending skill name.
    """

    @staticmethod
    def _real_skill_names():
        """Return (name, skills_dir) pairs for every skill in the real skill registry."""
        from agent_notes.config import SKILLS_DIR
        from agent_notes.registries.skill_registry import load_skill_registry
        registry = load_skill_registry(skills_dir=SKILLS_DIR)
        return [(s.name, SKILLS_DIR) for s in registry.all()]

    @pytest.mark.parametrize("skill_name,skills_dir", _real_skill_names.__func__())
    def test_no_warning_for_shipped_skill(self, skill_name, skills_dir, tmp_path, capsys, monkeypatch):
        """check_skill_frontmatter emits no [skill-frontmatter] warning for a real shipped skill."""
        # Build a skills_dir containing only this one skill so other skills
        # cannot mask or muffle the warning under test.
        src_dir = skills_dir / skill_name
        import shutil
        isolated = tmp_path / "skills"
        isolated.mkdir()
        shutil.copytree(src_dir, isolated / skill_name)

        from agent_notes.registries.skill_registry import load_skill_registry
        monkeypatch.setattr(
            "agent_notes.commands.doctor.load_skill_registry",
            lambda: load_skill_registry(skills_dir=isolated),
        )

        from agent_notes.commands.doctor import check_skill_frontmatter
        check_skill_frontmatter("global", [], [])

        out = capsys.readouterr().out
        assert "[skill-frontmatter]" not in out, (
            f"check_skill_frontmatter produced a false-positive warning for "
            f"real shipped skill '{skill_name}':\n{out}"
        )


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
