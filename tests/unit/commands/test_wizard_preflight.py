"""Tests for _confirm_install pre-flight summary in agent_notes.commands.wizard."""
import io
import logging
import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from agent_notes.services.installer import InstallAction


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_install_action(action: str, dst_name: str = "CLAUDE.md", backup: Path = None) -> InstallAction:
    src = Path("/fake/src") / dst_name
    dst = Path("/fake/dst") / dst_name
    return InstallAction(action=action, src=src, dst=dst, backup_path=backup)


def _run_confirm_install(monkeypatch, manifest, user_input: str = "Y"):
    """Call _confirm_install with all heavy side-effects mocked out.

    local imports inside _confirm_install:
      from ..services.ui import _clear_screen, _render_step_header
      from ..registries.cli_registry import load_registry
      from ..services.installer import plan_install

    We patch the source modules so the local imports pick up the stubs.
    """
    # Suppress screen-clearing and step headers (patched at source)
    monkeypatch.setattr("agent_notes.services.ui._clear_screen", lambda: None)
    monkeypatch.setattr("agent_notes.services.ui._render_step_header", lambda *a, **kw: None)

    # plan_install is imported from services.installer inside the function
    monkeypatch.setattr("agent_notes.services.installer.plan_install", lambda **kw: manifest)

    # load_registry is imported from registries.cli_registry inside the function
    monkeypatch.setattr(
        "agent_notes.registries.cli_registry.load_registry",
        lambda *a, **kw: MagicMock(),
    )

    # Stub out module-level helpers in wizard
    monkeypatch.setattr("agent_notes.commands.wizard._render_install_summary", lambda *a, **kw: None)
    monkeypatch.setattr("agent_notes.commands.wizard._get_skill_groups", lambda: {})

    # Drive _safe_input (module-level import in wizard)
    monkeypatch.setattr("agent_notes.commands.wizard._safe_input", lambda prompt, default: user_input)

    # Redirect stdout to capture prints
    buf = io.StringIO()
    with patch("sys.stdout", buf):
        from agent_notes.commands.wizard import _confirm_install
        result = _confirm_install(
            clis={"claude"},
            scope="local",
            copy_mode=False,
            selected_skills=[],
            role_models={},
        )

    return result, buf.getvalue()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestConfirmInstallFileCount:
    def test_shows_files_to_install_count(self, monkeypatch):
        """The 'Files to install: N' line must show the correct non-skip count."""
        manifest = [
            _make_install_action("install", "a.md"),
            _make_install_action("install", "b.md"),
            _make_install_action("install", "c.md"),
            _make_install_action("skip", "d.md"),  # not counted
        ]
        _result, output = _run_confirm_install(monkeypatch, manifest, user_input="Y")

        assert "Files to install:" in output
        # The count of non-skip actions is 3
        assert "3" in output

    def test_skip_actions_excluded_from_count(self, monkeypatch):
        """All-skip manifest reports 0 files to install."""
        manifest = [_make_install_action("skip", f"{i}.md") for i in range(5)]
        _result, output = _run_confirm_install(monkeypatch, manifest, user_input="Y")

        assert "Files to install:" in output
        assert "0" in output


class TestConfirmInstallBackupLines:
    def test_lists_each_backup_path_when_overwrites_present(self, monkeypatch, tmp_path):
        """Each overwrite action with a backup_path must appear in its own output line."""
        bak1 = tmp_path / "CLAUDE.md.bak.20260430T022500000001Z"
        bak2 = tmp_path / "settings.json.bak.20260430T022500000002Z"
        manifest = [
            _make_install_action("install", "agents/role.md"),
            InstallAction(
                action="overwrite",
                src=Path("/fake/src/CLAUDE.md"),
                dst=tmp_path / "CLAUDE.md",
                backup_path=bak1,
            ),
            InstallAction(
                action="overwrite",
                src=Path("/fake/src/settings.json"),
                dst=tmp_path / "settings.json",
                backup_path=bak2,
            ),
        ]
        _result, output = _run_confirm_install(monkeypatch, manifest, user_input="Y")

        assert str(bak1) in output, f"Expected backup path {bak1} in output:\n{output}"
        assert str(bak2) in output, f"Expected backup path {bak2} in output:\n{output}"

    def test_backup_section_header_present_when_overwrites_exist(self, monkeypatch, tmp_path):
        bak = tmp_path / "CLAUDE.md.bak.20260430T022500000001Z"
        manifest = [
            InstallAction(
                action="overwrite",
                src=Path("/fake/src/CLAUDE.md"),
                dst=tmp_path / "CLAUDE.md",
                backup_path=bak,
            ),
        ]
        _result, output = _run_confirm_install(monkeypatch, manifest, user_input="Y")

        assert "back up" in output.lower() or "backup" in output.lower(), (
            f"Expected a backup section header in output:\n{output}"
        )

    def test_no_backup_section_when_no_overwrites(self, monkeypatch):
        """If no overwrites, the backup listing block must not appear."""
        manifest = [
            _make_install_action("install", "a.md"),
            _make_install_action("skip", "b.md"),
        ]
        _result, output = _run_confirm_install(monkeypatch, manifest, user_input="Y")

        # "back up" section only appears when there are overwrites
        assert "→" not in output, (
            "No backup arrow (→) should appear when there are no overwrites"
        )


class TestConfirmInstallPlanInstallException:
    def test_plan_install_exception_does_not_raise_to_user(self, monkeypatch):
        """When plan_install raises, _confirm_install must not propagate the exception."""
        monkeypatch.setattr("agent_notes.services.ui._clear_screen", lambda: None)
        monkeypatch.setattr("agent_notes.services.ui._render_step_header", lambda *a, **kw: None)
        monkeypatch.setattr("agent_notes.commands.wizard._render_install_summary", lambda *a, **kw: None)
        monkeypatch.setattr("agent_notes.commands.wizard._get_skill_groups", lambda: {})
        monkeypatch.setattr(
            "agent_notes.registries.cli_registry.load_registry",
            lambda *a, **kw: MagicMock(),
        )
        monkeypatch.setattr("agent_notes.commands.wizard._safe_input", lambda prompt, default: "Y")

        def exploding_plan_install(**kw):
            raise RuntimeError("simulated plan_install failure")

        monkeypatch.setattr("agent_notes.services.installer.plan_install", exploding_plan_install)

        # Should not raise
        from agent_notes.commands.wizard import _confirm_install
        result = _confirm_install(
            clis={"claude"},
            scope="local",
            copy_mode=False,
            selected_skills=[],
            role_models={},
        )
        # User answered Y, so result should be True (proceed)
        assert result is True

    def test_plan_install_exception_emits_debug_log(self, monkeypatch, caplog):
        """When plan_install raises, a debug-level log must be emitted."""
        monkeypatch.setattr("agent_notes.services.ui._clear_screen", lambda: None)
        monkeypatch.setattr("agent_notes.services.ui._render_step_header", lambda *a, **kw: None)
        monkeypatch.setattr("agent_notes.commands.wizard._render_install_summary", lambda *a, **kw: None)
        monkeypatch.setattr("agent_notes.commands.wizard._get_skill_groups", lambda: {})
        monkeypatch.setattr(
            "agent_notes.registries.cli_registry.load_registry",
            lambda *a, **kw: MagicMock(),
        )
        monkeypatch.setattr("agent_notes.commands.wizard._safe_input", lambda prompt, default: "Y")

        def exploding_plan_install(**kw):
            raise ValueError("boom")

        monkeypatch.setattr("agent_notes.services.installer.plan_install", exploding_plan_install)

        with caplog.at_level(logging.DEBUG, logger="agent_notes.commands.wizard"):
            from agent_notes.commands.wizard import _confirm_install
            _confirm_install(
                clis={"claude"},
                scope="local",
                copy_mode=False,
                selected_skills=[],
                role_models={},
            )

        assert any(
            "plan_install" in r.message.lower() or "pre-flight" in r.message.lower()
            for r in caplog.records
        ), f"Expected a debug log mentioning plan_install/pre-flight, got: {caplog.records}"


class TestConfirmInstallAbort:
    def test_returns_false_when_user_answers_n(self, monkeypatch):
        """When user answers 'n', _confirm_install must return False."""
        manifest = [_make_install_action("install", "a.md")]
        result, _output = _run_confirm_install(monkeypatch, manifest, user_input="n")
        assert result is False

    def test_returns_true_when_user_answers_y(self, monkeypatch):
        manifest = [_make_install_action("install", "a.md")]
        result, _output = _run_confirm_install(monkeypatch, manifest, user_input="Y")
        assert result is True

    def test_no_install_called_when_user_aborts(self, monkeypatch):
        """Confirming 'n' must not trigger any install side-effects.
        _confirm_install only returns a bool — actual install is the caller's job.
        We verify the return value is False (caller must check it).
        """
        manifest = [_make_install_action("install", "a.md")]
        result, _output = _run_confirm_install(monkeypatch, manifest, user_input="n")
        assert result is False, "Return value False signals caller should not proceed"
