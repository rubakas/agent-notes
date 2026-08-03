"""Regression tests: wizard/model-effort selections must land in rendered
agent frontmatter as EXACT model version strings.

Covers the propagation path that was broken:
  wizard selections (in-memory) -> generate_agent_files(role_models=, role_efforts=)
  state.json pins               -> generate_agent_files(state=, scope=)
both of which must render `model: <exact alias>` and `effort: <pin>` for the
claude backend (use_model_class=True notwithstanding — pins always win with
exact strings; only the UNPINNED fallback stays class-based).
"""
import json
from pathlib import Path
from unittest.mock import patch

import agent_notes.config as config_mod
from agent_notes.services.rendering import generate_agent_files, load_agents_config


# Wizard-shaped selections: {cli: {role: value}}
CLAUDE_ROLE_MODELS = {
    "claude": {
        "scout": "claude-haiku-4-5",
        "worker": "claude-sonnet-4-6",
        "reasoner": "claude-opus-4-8",
    }
}
CLAUDE_ROLE_EFFORTS = {
    "claude": {
        "scout": "medium",
        "worker": "high",
        "reasoner": "xhigh",
    }
}


def _agents_subset(*names):
    agents_config = load_agents_config()
    return {n: agents_config[n] for n in names}


def _frontmatter(path: Path) -> str:
    text = path.read_text()
    assert text.startswith("---")
    return text.split("---", 2)[1]


def _render(tmp_path, monkeypatch, agents_config, **kwargs):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    dist = tmp_path / "dist"
    with patch.object(config_mod, "DIST_DIR", dist), \
         patch("agent_notes.services.user_config.load_user_config", return_value={}):
        generate_agent_files(agents_config, **kwargs)
    return dist


def _write_state(tmp_path, monkeypatch, role_models, role_efforts=None):
    """Persist a minimal state.json with global-scope pins, return loaded State."""
    from agent_notes.services.state_store import load_state
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    sf = tmp_path / "xdg" / "agent-notes" / "state.json"
    sf.parent.mkdir(parents=True, exist_ok=True)
    sf.write_text(json.dumps({
        "source_path": "/tmp/repo",
        "source_commit": "abc",
        "global": {
            "installed_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
            "mode": "symlink",
            "clis": {"claude": {"role_models": role_models,
                                "role_efforts": role_efforts or {},
                                "installed": {}}},
        },
        "local": {},
        "memory": {"backend": "local", "path": ""},
    }))
    return load_state()


class TestWizardSelectionsReachFrontmatter:
    """The bug: selections were stored in state.json but never applied to the
    rendered/installed agent files. These pins must show up verbatim."""

    def test_explicit_selections_render_exact_model_and_effort(self, tmp_path, monkeypatch):
        agents_config = _agents_subset("explorer", "coder", "architect")
        dist = _render(tmp_path, monkeypatch, agents_config,
                       role_models=CLAUDE_ROLE_MODELS, role_efforts=CLAUDE_ROLE_EFFORTS)

        explorer = _frontmatter(dist / "claude" / "agents" / "explorer.md")
        assert "model: claude-haiku-4-5" in explorer
        assert "effort: medium" in explorer

        coder = _frontmatter(dist / "claude" / "agents" / "coder.md")
        assert "model: claude-sonnet-4-6" in coder
        assert "effort: high" in coder

        architect = _frontmatter(dist / "claude" / "agents" / "architect.md")
        assert "model: claude-opus-4-8" in architect
        assert "effort: xhigh" in architect

    def test_no_bare_class_aliases_for_pinned_roles(self, tmp_path, monkeypatch):
        """`model: sonnet` etc. would let the harness pick ITS default version,
        defeating the pin."""
        agents_config = _agents_subset("explorer", "coder", "architect")
        dist = _render(tmp_path, monkeypatch, agents_config,
                       role_models=CLAUDE_ROLE_MODELS, role_efforts=CLAUDE_ROLE_EFFORTS)

        for name in ("explorer", "coder", "architect"):
            fm = _frontmatter(dist / "claude" / "agents" / f"{name}.md")
            for line in fm.splitlines():
                if line.startswith("model:"):
                    assert line.split(":", 1)[1].strip() not in ("haiku", "sonnet", "opus"), \
                        f"{name}.md pinned model flattened to class alias: {line!r}"

    def test_explicit_selections_win_over_persisted_state_pins(self, tmp_path, monkeypatch):
        """Wizard-run ordering: dist is built BEFORE the new state.json is
        written, so the in-memory selections must override stale pins."""
        agents_config = _agents_subset("coder")
        state = _write_state(tmp_path, monkeypatch, {"worker": "claude-sonnet-4-5"}, {"worker": "low"})

        dist = _render(tmp_path, monkeypatch, agents_config,
                       state=state, scope="global",
                       role_models={"claude": {"worker": "claude-sonnet-4-6"}},
                       role_efforts={"claude": {"worker": "high"}})

        coder = _frontmatter(dist / "claude" / "agents" / "coder.md")
        assert "model: claude-sonnet-4-6" in coder
        assert "effort: high" in coder

    def test_selections_apply_to_opencode_backend_too(self, tmp_path, monkeypatch):
        """Same overlay drives opencode rendering (exact provider alias)."""
        agents_config = _agents_subset("coder")
        dist = _render(tmp_path, monkeypatch, agents_config,
                       role_models={"opencode": {"worker": "claude-sonnet-4-6"}})

        coder = _frontmatter(dist / "opencode" / "agents" / "coder.md")
        # opencode's first accepted provider for this model is anthropic
        assert "model: claude-sonnet-4-6" in coder


class TestPersistedStatePinsReachFrontmatter:
    """The reinstall/upgrade path: a later `agent-notes build/install` renders
    from state.json alone and must reproduce the exact pinned strings."""

    def test_state_pins_render_exact_strings_without_overlay(self, tmp_path, monkeypatch):
        agents_config = _agents_subset("explorer", "coder")
        state = _write_state(tmp_path, monkeypatch,
                             {"scout": "claude-haiku-4-5", "worker": "claude-sonnet-4-6"},
                             {"scout": "medium", "worker": "high"})

        dist = _render(tmp_path, monkeypatch, agents_config,
                       state=state, scope="global")

        explorer = _frontmatter(dist / "claude" / "agents" / "explorer.md")
        assert "model: claude-haiku-4-5" in explorer
        assert "effort: medium" in explorer

        coder = _frontmatter(dist / "claude" / "agents" / "coder.md")
        assert "model: claude-sonnet-4-6" in coder
        assert "effort: high" in coder


class TestNamedProfilePinsReachFrontmatter:
    """The healthy-path re-render (`agent-notes install --profile work`) renders
    from the NAMED profile's pins — a profile-blind get_scope would silently
    revert dist/ to the default profile's frontmatter."""

    def _state_with_profiles(self):
        from agent_notes.domain.state import BackendState, ScopeState, State
        return State(
            global_install=ScopeState(
                clis={"claude": BackendState(role_models={"worker": "claude-sonnet-4-5"},
                                             role_efforts={"worker": "low"})}),
            global_installs={"work": ScopeState(
                profile_label="work",
                clis={"claude": BackendState(role_models={"worker": "claude-sonnet-4-6"},
                                             role_efforts={"worker": "high"})})},
        )

    def test_profile_label_renders_that_profiles_pins(self, tmp_path, monkeypatch):
        agents_config = _agents_subset("coder")
        dist = _render(tmp_path, monkeypatch, agents_config,
                       state=self._state_with_profiles(), scope="global",
                       profile_label="work")

        coder = _frontmatter(dist / "claude" / "agents" / "coder.md")
        assert "model: claude-sonnet-4-6" in coder
        assert "effort: high" in coder

    def test_default_label_still_renders_default_pins(self, tmp_path, monkeypatch):
        agents_config = _agents_subset("coder")
        dist = _render(tmp_path, monkeypatch, agents_config,
                       state=self._state_with_profiles(), scope="global")

        coder = _frontmatter(dist / "claude" / "agents" / "coder.md")
        assert "model: claude-sonnet-4-5" in coder
        assert "effort: low" in coder


class TestDistRendersDoNotCreateBackups:
    """dist/ is a derived, regenerable artifact — content-changing re-renders
    must overwrite in place, never litter dist/<cli>/ with *.bak.* files."""

    def test_two_renders_with_different_content_leave_no_bak_files(self, tmp_path, monkeypatch):
        agents_config = _agents_subset("coder")
        dist = _render(tmp_path, monkeypatch, agents_config,
                       role_models={"claude": {"worker": "claude-sonnet-4-5"}})
        _render(tmp_path, monkeypatch, agents_config,
                role_models={"claude": {"worker": "claude-sonnet-4-6"}})

        baks = sorted(dist.rglob("*.bak.*"))
        assert baks == [], f"dist renders must not create backups: {baks}"
        coder = _frontmatter(dist / "claude" / "agents" / "coder.md")
        assert "model: claude-sonnet-4-6" in coder


class TestUnpinnedRolesKeepClassRendering:
    """DECISION: unpinned roles on use_model_class backends (claude) keep the
    class-based fallback (`model: sonnet`). Pins always win with exact strings;
    the class default is only for installs with no recorded selection."""

    def test_unpinned_worker_renders_model_class(self, tmp_path, monkeypatch):
        agents_config = _agents_subset("coder")
        dist = _render(tmp_path, monkeypatch, agents_config)

        coder = _frontmatter(dist / "claude" / "agents" / "coder.md")
        assert "model: sonnet" in coder
