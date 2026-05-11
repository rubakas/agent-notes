"""Tests for agent_notes.commands.info.show_info()."""
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run_info(monkeypatch, *, global_agents_exist=False, local_agents_exist=False, state=None):
    """Call show_info() with controlled filesystem and state, return captured output."""
    import agent_notes.commands.info as info_mod

    # Patch count_skills / count_agents / count_global to avoid real filesystem hits
    monkeypatch.setattr(
        "agent_notes.commands.info.count_skills",
        lambda: 5,
    )
    monkeypatch.setattr(
        "agent_notes.commands.info.count_agents",
        lambda backend: 10,
    )
    monkeypatch.setattr(
        "agent_notes.commands.info.count_global",
        lambda: 3,
    )

    # Patch get_version
    monkeypatch.setattr(
        "agent_notes.commands.info.get_version",
        lambda: "2.99.0",
    )

    # Patch CLAUDE_HOME directory check
    fake_claude_home = MagicMock()
    fake_agents_dir = MagicMock()
    fake_agents_dir.exists.return_value = global_agents_exist
    fake_agents_dir.iterdir.return_value = iter(["somefile"]) if global_agents_exist else iter([])
    fake_claude_home.__truediv__ = lambda self, other: fake_agents_dir if other == "agents" else MagicMock()
    monkeypatch.setattr("agent_notes.commands.info.CLAUDE_HOME", fake_claude_home)

    # Patch install_state.load_current_state
    monkeypatch.setattr(
        "agent_notes.install_state.load_current_state",
        lambda: state,
    )

    # Patch registry — load_registry is imported inside the function body,
    # so we patch it at the source module.
    fake_backend = MagicMock()
    fake_backend.label = "Claude Code"
    fake_backend.global_home = Path("/fake/home/.claude")
    fake_backend.supports.return_value = True

    fake_registry = MagicMock()
    fake_registry.all.return_value = [fake_backend]

    monkeypatch.setattr(
        "agent_notes.registries.cli_registry.load_registry",
        lambda: fake_registry,
    )

    # Patch Path.exists and Path.iterdir for local .claude/agents check
    original_exists = Path.exists
    original_iterdir = Path.iterdir

    def _patched_exists(self):
        p = str(self)
        if p.endswith(".claude/agents"):
            return local_agents_exist
        return original_exists(self)

    def _patched_iterdir(self):
        p = str(self)
        if p.endswith(".claude/agents") and local_agents_exist:
            return iter(["something"])
        return original_iterdir(self)

    monkeypatch.setattr(Path, "exists", _patched_exists)
    monkeypatch.setattr(Path, "iterdir", _patched_iterdir)

    import io, sys
    captured = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = captured
    try:
        info_mod.show_info()
    finally:
        sys.stdout = old_stdout

    return captured.getvalue()


# ---------------------------------------------------------------------------
# TestShowInfoVersion
# ---------------------------------------------------------------------------

class TestShowInfoVersion:
    def test_prints_version_number(self, monkeypatch):
        output = _run_info(monkeypatch)
        assert "2.99.0" in output

    def test_prints_agent_notes_prefix(self, monkeypatch):
        output = _run_info(monkeypatch)
        assert "agent-notes" in output


# ---------------------------------------------------------------------------
# TestShowInfoComponents
# ---------------------------------------------------------------------------

class TestShowInfoComponents:
    def test_prints_components_section(self, monkeypatch):
        output = _run_info(monkeypatch)
        assert "Components:" in output

    def test_prints_skills_count(self, monkeypatch):
        output = _run_info(monkeypatch)
        assert "Skills:" in output
        assert "5" in output

    def test_prints_global_config_count(self, monkeypatch):
        output = _run_info(monkeypatch)
        assert "Global config:" in output
        assert "3" in output


# ---------------------------------------------------------------------------
# TestShowInfoStatus
# ---------------------------------------------------------------------------

class TestShowInfoStatus:
    def test_prints_status_label(self, monkeypatch):
        output = _run_info(monkeypatch)
        assert "Status:" in output

    def test_not_installed_shown_when_no_global_agents(self, monkeypatch):
        output = _run_info(monkeypatch, global_agents_exist=False)
        assert "not installed" in output

    def test_no_storage_label_in_output(self, monkeypatch):
        """Label was renamed — 'Storage:' should not appear."""
        output = _run_info(monkeypatch)
        assert "Storage:" not in output

    def test_no_backends_label_in_output(self, monkeypatch):
        """Old label 'Backends:' should not appear at section header level."""
        output = _run_info(monkeypatch)
        # 'Backends:' used to be a top-level section — verify it is not a section header
        lines_with_backends = [
            line for line in output.splitlines()
            if line.strip().startswith("Backends:")
        ]
        assert lines_with_backends == []


# ---------------------------------------------------------------------------
# TestShowInfoInstallTargets
# ---------------------------------------------------------------------------

class TestShowInfoInstallTargets:
    def test_prints_install_targets_section(self, monkeypatch):
        output = _run_info(monkeypatch)
        assert "Install targets:" in output

    def test_prints_universal_target(self, monkeypatch):
        output = _run_info(monkeypatch)
        assert "Universal" in output or "~/.agents/" in output


# ---------------------------------------------------------------------------
# TestShowInfoLastInstall
# ---------------------------------------------------------------------------

class TestShowInfoLastInstall:
    def test_no_last_install_section_when_state_is_none(self, monkeypatch):
        output = _run_info(monkeypatch, state=None)
        assert "Last install:" not in output

    def test_last_install_section_present_when_state_exists(self, monkeypatch):
        from agent_notes.domain.state import State, ScopeState
        state = State(
            source_path="/fake/path",
            source_commit="abc123",
            global_install=ScopeState(
                installed_at="2026-01-01T00:00:00Z",
                updated_at="2026-01-01T00:00:00Z",
                mode="symlink",
                installed_version="2.0.0",
            ),
            local_installs={},
        )
        output = _run_info(monkeypatch, state=state)
        assert "Last install:" in output

    def test_global_none_shown_when_no_global_scope_in_state(self, monkeypatch):
        from agent_notes.domain.state import State
        state = State(
            source_path="",
            source_commit="",
            global_install=None,
            local_installs={},
        )
        output = _run_info(monkeypatch, state=state)
        # Should indicate global is none
        assert "none" in output.lower()

    def test_local_none_shown_when_no_local_installs(self, monkeypatch):
        from agent_notes.domain.state import State, ScopeState
        state = State(
            source_path="",
            source_commit="",
            global_install=ScopeState(
                installed_at="2026-01-01T00:00:00Z",
                updated_at="2026-01-01T00:00:00Z",
                mode="symlink",
                installed_version="2.0.0",
            ),
            local_installs={},
        )
        output = _run_info(monkeypatch, state=state)
        assert "none" in output.lower()

    def test_local_install_path_shown_when_present(self, monkeypatch):
        from agent_notes.domain.state import State, ScopeState
        state = State(
            source_path="",
            source_commit="",
            global_install=None,
            local_installs={
                "/home/user/myproject": ScopeState(
                    installed_at="2026-05-01T00:00:00Z",
                    updated_at="2026-05-01T00:00:00Z",
                    mode="copy",
                    installed_version="2.0.0",
                )
            },
        )
        output = _run_info(monkeypatch, state=state)
        assert "/home/user/myproject" in output

    def test_global_install_date_shown(self, monkeypatch):
        from agent_notes.domain.state import State, ScopeState
        state = State(
            source_path="",
            source_commit="",
            global_install=ScopeState(
                installed_at="2026-03-15T12:00:00Z",
                updated_at="2026-03-15T12:00:00Z",
                mode="symlink",
                installed_version="2.0.0",
            ),
            local_installs={},
        )
        output = _run_info(monkeypatch, state=state)
        assert "2026-03-15T12:00:00Z" in output
