"""Tests for _interactive_install ordering: build must run BEFORE the confirmation
step so the pre-flight 'Files to install' count is computed from the exact dist/
the install will write (a stale or missing dist shows a wrong number)."""
import io
import pytest
from unittest.mock import patch


def _run_orchestrator(monkeypatch, events, confirm_result=True, build_error=None,
                      profile=("", None, ""), confirm_capture: dict = None,
                      selections=({}, {}), scope="global", build_capture: dict = None,
                      build_calls: list = None):
    """Run _interactive_install with every wizard step stubbed out.

    Appends "build" / "confirm" / "execute" to `events` in call order.
    `build_calls`, if given, collects the kwargs of every build() invocation.
    """
    monkeypatch.setattr("agent_notes.commands.wizard._select_cli", lambda **kw: {"claude"})
    monkeypatch.setattr("agent_notes.commands.wizard._select_models_per_role", lambda *a, **kw: selections)
    monkeypatch.setattr("agent_notes.commands.wizard._select_scope", lambda *a, **kw: scope)
    monkeypatch.setattr("agent_notes.commands.wizard._select_mode", lambda **kw: False)
    monkeypatch.setattr("agent_notes.commands.wizard._select_profile", lambda **kw: profile)
    monkeypatch.setattr("agent_notes.commands.wizard._select_skills", lambda **kw: [])
    monkeypatch.setattr("agent_notes.commands.wizard._select_memory", lambda *a, **kw: ("local", "", "single-brain"))
    monkeypatch.setattr("agent_notes.commands.wizard.cost_report._select_cost_report", lambda **kw: False)
    monkeypatch.setattr("agent_notes.commands.wizard.orchestrator._clear_screen", lambda: None)

    def fake_build(**kw):
        events.append("build")
        if build_capture is not None:
            build_capture.update(kw)
        if build_calls is not None:
            build_calls.append(kw)
        if build_error is not None:
            raise build_error

    def fake_confirm(*a, **kw):
        events.append("confirm")
        if confirm_capture is not None:
            confirm_capture.update(kw)
        return confirm_result

    def fake_execute(*a, **kw):
        events.append("execute")

    monkeypatch.setattr("agent_notes.commands.wizard.orchestrator.build", fake_build)
    monkeypatch.setattr("agent_notes.commands.wizard._confirm_install", fake_confirm)
    monkeypatch.setattr("agent_notes.commands.wizard.orchestrator._execute_install", fake_execute)

    buf = io.StringIO()
    with patch("sys.stdout", buf):
        from agent_notes.commands.wizard.orchestrator import _interactive_install
        _interactive_install()

    return buf.getvalue()


class TestBuildRunsBeforeConfirm:
    def test_build_precedes_confirmation(self, monkeypatch):
        """dist/ must be rendered before the confirm screen counts files from it."""
        events = []
        _run_orchestrator(monkeypatch, events, confirm_result=True)
        assert events == ["build", "confirm", "execute"]

    def test_decline_after_build_skips_execute(self, monkeypatch):
        """User declining at the (post-build) confirmation must not install,
        and a restore build (no overlays) must undo the pre-confirm render."""
        events = []
        output = _run_orchestrator(monkeypatch, events, confirm_result=False)
        assert events == ["build", "confirm", "build"]
        assert "cancelled" in output.lower()

    def test_build_failure_aborts_before_confirmation(self, monkeypatch):
        """A failed build must abort the wizard without confirming or installing;
        a restore build is still attempted (dist/ may be half-written)."""
        events = []
        output = _run_orchestrator(monkeypatch, events, build_error=RuntimeError("boom"))
        assert events == ["build", "build"]
        assert "confirm" not in events
        assert "execute" not in events
        assert "Build failed" in output


class TestDeclineRestoresPersistedRender:
    """Declining at confirmation must not leave dist/ rendered with the rejected
    in-memory selections: existing symlink installs serve dist/ directly, so the
    wizard re-runs build WITHOUT selection overlays to restore persisted pins."""

    def test_restore_build_has_no_selection_overlays(self, monkeypatch):
        events, calls = [], []
        _run_orchestrator(monkeypatch, events, confirm_result=False,
                          selections=TestBuildReceivesWizardSelections.SELECTIONS,
                          build_calls=calls)
        assert len(calls) == 2
        pre_confirm, restore = calls
        assert pre_confirm["role_models"] == TestBuildReceivesWizardSelections.SELECTIONS[0]
        assert restore.get("role_models") is None
        assert restore.get("role_efforts") is None

    def test_restore_build_keeps_scope_and_profile(self, monkeypatch):
        from pathlib import Path
        events, calls = [], []
        _run_orchestrator(monkeypatch, events, confirm_result=False, scope="local",
                          profile=("work", {"claude": ".claude-work"}, "~/.claude-work"),
                          build_calls=calls)
        restore = calls[-1]
        assert restore["scope"] == "local"
        assert restore["project_path"] == Path.cwd()
        assert restore["profile_label"] == "work"


class TestBuildReceivesWizardSelections:
    """The wizard's model/effort selections exist only in memory when build()
    runs (state.json is written after install) — build must receive them
    explicitly or the installed dist ignores this run's choices."""

    SELECTIONS = (
        {"claude": {"scout": "claude-haiku-4-5", "worker": "claude-sonnet-4-6",
                    "reasoner": "claude-opus-4-8"}},
        {"claude": {"scout": "medium", "worker": "high", "reasoner": "xhigh"}},
    )

    def test_selections_forwarded_to_build(self, monkeypatch):
        events, captured = [], {}
        _run_orchestrator(monkeypatch, events, confirm_result=False,
                          selections=self.SELECTIONS, build_capture=captured)
        assert captured["role_models"] == self.SELECTIONS[0]
        assert captured["role_efforts"] == self.SELECTIONS[1]

    def test_global_scope_forwarded_to_build(self, monkeypatch):
        events, captured = [], {}
        _run_orchestrator(monkeypatch, events, confirm_result=False,
                          scope="global", build_capture=captured)
        assert captured["scope"] == "global"
        assert captured["project_path"] is None

    def test_local_scope_forwards_cwd_project_path(self, monkeypatch):
        from pathlib import Path
        events, captured = [], {}
        _run_orchestrator(monkeypatch, events, confirm_result=False,
                          scope="local", build_capture=captured)
        assert captured["scope"] == "local"
        assert captured["project_path"] == Path.cwd()


class TestConfirmReceivesProfileOverrides:
    def test_profile_overrides_forwarded_to_confirm(self, monkeypatch):
        """The confirm step needs the profile's folder/global-home overrides so its
        plan targets the same paths the install will write to."""
        events = []
        captured = {}
        _run_orchestrator(
            monkeypatch, events, confirm_result=False,
            profile=("work", {"claude": ".claude-work"}, "~/.claude-work"),
            confirm_capture=captured,
        )
        assert captured["folder_overrides"] == {"claude": ".claude-work"}
        assert captured["global_home_override"] == "~/.claude-work"
