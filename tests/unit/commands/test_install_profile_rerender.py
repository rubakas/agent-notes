"""Regression tests: the healthy-path re-render in `install` must be profile-aware.

`agent-notes install --profile work` finds the existing install under the named
profile, then re-renders dist/ from persisted pins before verifying. build()
must receive that profile label — a profile-blind rebuild renders from the
DEFAULT profile's pins and silently reverts the work profile's frontmatter.
"""
import io
from unittest.mock import patch

from agent_notes.domain.state import BackendState, ScopeState, State


def _state_with_global_profile(profile_label: str) -> State:
    scope_state = ScopeState(
        installed_at="2026-01-01T00:00:00Z",
        mode="symlink",
        clis={"claude": BackendState(role_models={"worker": "claude-sonnet-4-6"})},
        profile_label=profile_label,
    )
    state = State()
    if profile_label:
        state.global_installs[profile_label] = scope_state
    else:
        state.global_install = scope_state
    return state


class TestHealthyPathRerenderIsProfileAware:
    def _run_healthy_install(self, profile_label: str) -> dict:
        state = _state_with_global_profile(profile_label)
        captured = {}

        def fake_build(**kw):
            captured.update(kw)

        with patch("agent_notes.commands.install.load_current_state", return_value=state), \
             patch("agent_notes.commands.build.build", side_effect=fake_build), \
             patch("agent_notes.commands.install._verify_install", return_value=[]), \
             patch("sys.stdout", io.StringIO()):
            from agent_notes.commands.install import install
            install(local=False, profile_label=profile_label)
        return captured

    def test_named_profile_is_forwarded_to_rebuild(self):
        captured = self._run_healthy_install("work")
        assert captured["profile_label"] == "work"
        assert captured["scope"] == "global"
        assert captured["project_path"] is None

    def test_default_profile_forwards_empty_label(self):
        captured = self._run_healthy_install("")
        assert captured["profile_label"] == ""
