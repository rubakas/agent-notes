"""Tests for Codex CLI-specific installer logic."""
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from agent_notes.services.installer import (
    _agent_glob,
    _hooks_filename,
    _install_codex_session_hook,
    _uninstall_codex_session_hook,
    _plan_codex_session_hook,
    plan_install,
    InstallAction,
)
from agent_notes.services.settings_writer import has_hook, install_hook
from agent_notes.registries.cli_registry import load_registry
from agent_notes.domain.cli_backend import CLIBackend


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_codex_backend(tmp_path: Path) -> CLIBackend:
    """Build a codex CLIBackend pointing to tmp_path."""
    global_home = tmp_path / "codex_global"
    global_home.mkdir(parents=True, exist_ok=True)
    return CLIBackend(
        name="codex",
        label="Codex CLI",
        global_home=global_home,
        local_dir=str(tmp_path / ".codex"),
        layout={
            "agents": "agents/",
            "skills": "skills/",
            "config": "AGENTS.md",
            "hooks": "hooks.json",
        },
        features={
            "agents": True,
            "skills": True,
            "rules": False,
            "commands": False,
            "memory": False,
            "frontmatter": "codex",
        },
        global_template="global-codex.md",
        accepted_providers=("openai",),
    )


@pytest.fixture
def codex_backend(tmp_path):
    return _make_codex_backend(tmp_path)


@pytest.fixture(autouse=True)
def patch_session_deps(tmp_path):
    """Patch session-context and state-store dependencies used by hook installers."""
    with patch("agent_notes.services.session_context.write_context"), \
         patch("agent_notes.registries.skill_registry.default_skill_registry") as mock_reg, \
         patch("agent_notes.services.state_store.load_state") as mock_state, \
         patch("agent_notes.config.get_version", return_value="0.0.0-test"), \
         patch("agent_notes.config.memory_dir_for_backend", return_value=None), \
         patch("agent_notes.services.installer.load_state") as mock_state2:
        mock_reg.return_value.all.return_value = []
        mock_state.return_value = None
        mock_state2.return_value = None
        yield


# ---------------------------------------------------------------------------
# _agent_glob
# ---------------------------------------------------------------------------

class TestAgentGlob:
    def test_codex_backend_returns_toml_glob(self, codex_backend):
        assert _agent_glob(codex_backend) == "*.toml"

    def test_non_codex_backend_returns_md_glob(self):
        registry = load_registry()
        try:
            claude = registry.get("claude")
        except KeyError:
            pytest.skip("claude backend not in registry")
        assert _agent_glob(claude) == "*.md"


# ---------------------------------------------------------------------------
# _hooks_filename
# ---------------------------------------------------------------------------

class TestHooksFilename:
    def test_codex_uses_hooks_json(self, codex_backend):
        assert _hooks_filename(codex_backend) == "hooks.json"

    def test_backend_without_hooks_key_falls_back_to_settings_json(self, tmp_path):
        backend = CLIBackend(
            name="other",
            label="Other",
            global_home=tmp_path,
            local_dir=str(tmp_path),
            layout={"settings": "settings.json"},
            features={},
            global_template=None,
        )
        assert _hooks_filename(backend) == "settings.json"

    def test_backend_with_no_hooks_or_settings_falls_back(self, tmp_path):
        backend = CLIBackend(
            name="other",
            label="Other",
            global_home=tmp_path,
            local_dir=str(tmp_path),
            layout={},
            features={},
            global_template=None,
        )
        assert _hooks_filename(backend) == "settings.json"


# ---------------------------------------------------------------------------
# _install_codex_session_hook
# ---------------------------------------------------------------------------

class TestInstallCodexSessionHook:
    def test_creates_hooks_json(self, codex_backend, tmp_path):
        hooks_path = codex_backend.global_home / "hooks.json"
        assert not hooks_path.exists()

        _install_codex_session_hook(codex_backend, "global")

        assert hooks_path.exists()

    def test_hooks_json_has_session_start_entry(self, codex_backend, tmp_path):
        _install_codex_session_hook(codex_backend, "global")

        hooks_path = codex_backend.global_home / "hooks.json"
        data = json.loads(hooks_path.read_text())
        assert "SessionStart" in data.get("hooks", {}), (
            "hooks.json must contain a 'SessionStart' event key"
        )

    def test_session_start_command_cats_context_file(self, codex_backend):
        _install_codex_session_hook(codex_backend, "global")

        hooks_path = codex_backend.global_home / "hooks.json"
        data = json.loads(hooks_path.read_text())
        session_hooks = data["hooks"]["SessionStart"]
        commands = [
            h["command"]
            for entry in session_hooks
            for h in entry.get("hooks", [])
        ]
        assert any("agent-notes-context.md" in cmd for cmd in commands), (
            f"No command cats agent-notes-context.md. Commands: {commands}"
        )

    def test_install_is_idempotent(self, codex_backend):
        _install_codex_session_hook(codex_backend, "global")
        _install_codex_session_hook(codex_backend, "global")

        hooks_path = codex_backend.global_home / "hooks.json"
        data = json.loads(hooks_path.read_text())
        # Count how many SessionStart entries mention agent-notes-context.md
        session_hooks = data["hooks"].get("SessionStart", [])
        matching = [
            h
            for entry in session_hooks
            for h in entry.get("hooks", [])
            if "agent-notes-context.md" in h.get("command", "")
        ]
        assert len(matching) == 1, (
            f"Expected exactly 1 SessionStart hook after idempotent install, got {len(matching)}"
        )


# ---------------------------------------------------------------------------
# _uninstall_codex_session_hook
# ---------------------------------------------------------------------------

class TestUninstallCodexSessionHook:
    def test_removes_session_start_hook(self, codex_backend):
        _install_codex_session_hook(codex_backend, "global")
        hooks_path = codex_backend.global_home / "hooks.json"

        # Verify it's installed first
        data = json.loads(hooks_path.read_text())
        assert "SessionStart" in data.get("hooks", {})

        _uninstall_codex_session_hook(codex_backend, "global")

        data_after = json.loads(hooks_path.read_text())
        session_hooks = data_after.get("hooks", {}).get("SessionStart", [])
        remaining = [
            h
            for entry in session_hooks
            for h in entry.get("hooks", [])
            if "agent-notes-context.md" in h.get("command", "")
        ]
        assert remaining == [], (
            f"SessionStart hook not removed after uninstall. Remaining: {remaining}"
        )

    def test_uninstall_missing_hooks_json_is_noop(self, codex_backend):
        """Uninstall when hooks.json doesn't exist should not raise."""
        hooks_path = codex_backend.global_home / "hooks.json"
        assert not hooks_path.exists()
        # Should not raise
        _uninstall_codex_session_hook(codex_backend, "global")


# ---------------------------------------------------------------------------
# _plan_codex_session_hook
# ---------------------------------------------------------------------------

class TestPlanCodexSessionHook:
    def test_install_action_when_hooks_json_absent(self, codex_backend):
        actions = _plan_codex_session_hook(codex_backend, "global")
        assert len(actions) == 1
        assert actions[0].action == "install"

    def test_modify_action_when_hook_absent_from_existing_file(self, codex_backend):
        hooks_path = codex_backend.global_home / "hooks.json"
        hooks_path.write_text(json.dumps({"hooks": {}}))

        actions = _plan_codex_session_hook(codex_backend, "global")
        assert len(actions) == 1
        assert actions[0].action in ("install", "modify")

    def test_skip_action_when_hook_already_present(self, codex_backend):
        # Actually install it, then plan again
        _install_codex_session_hook(codex_backend, "global")

        actions = _plan_codex_session_hook(codex_backend, "global")
        assert len(actions) == 1
        assert actions[0].action == "skip"


# ---------------------------------------------------------------------------
# plan_install with codex selected
# ---------------------------------------------------------------------------

def _make_registry_with_codex(tmp_path: Path):
    """Return a CLIRegistry whose codex backend has global_home pointing to tmp_path.

    global_home_override no longer redirects non-claude backends (fix #3), so tests
    that need to avoid touching real ~/.codex must inject a pre-redirected backend
    via a custom registry instead.
    """
    from agent_notes.registries.cli_registry import CLIRegistry
    real_registry = load_registry()
    try:
        real_codex = real_registry.get("codex")
    except KeyError:
        return None, None

    fake_global = tmp_path / "fake_codex_global"
    fake_global.mkdir(parents=True, exist_ok=True)
    redirected = real_codex.with_global_home(fake_global)
    # Rebuild a registry with only the redirected codex backend (others unused here)
    registry = CLIRegistry([redirected])
    return registry, fake_global


class TestPlanInstallCodex:
    def test_plan_install_codex_includes_hooks_json_action(self, tmp_path):
        registry, fake_global = _make_registry_with_codex(tmp_path)
        if registry is None:
            pytest.skip("codex backend not in registry")

        with patch("agent_notes.services.settings_writer.has_hook", return_value=False):
            actions = plan_install(
                scope="global",
                registry=registry,
                selected_clis={"codex"},
            )

        hooks_actions = [a for a in actions if "hooks.json" in str(a.dst)]
        assert hooks_actions, (
            "Expected at least one action targeting hooks.json for codex install"
        )

    def test_plan_install_codex_includes_toml_agent_actions(self, tmp_path, built_dist):
        """plan_install with codex selected should include .toml agent files."""
        registry, fake_global = _make_registry_with_codex(tmp_path)
        if registry is None:
            pytest.skip("codex backend not in registry")

        with patch("agent_notes.services.settings_writer.has_hook", return_value=False):
            actions = plan_install(
                scope="global",
                registry=registry,
                selected_clis={"codex"},
            )

        toml_actions = [a for a in actions if str(a.src).endswith(".toml")]
        assert toml_actions, (
            "Expected at least one .toml file action in codex install plan"
        )

    def test_plan_install_codex_includes_agents_md(self, tmp_path, built_dist):
        """plan_install with codex selected should include AGENTS.md config."""
        registry, fake_global = _make_registry_with_codex(tmp_path)
        if registry is None:
            pytest.skip("codex backend not in registry")

        with patch("agent_notes.services.settings_writer.has_hook", return_value=False):
            actions = plan_install(
                scope="global",
                registry=registry,
                selected_clis={"codex"},
            )

        config_actions = [a for a in actions if "AGENTS.md" in str(a.dst)]
        assert config_actions, (
            "Expected at least one action targeting AGENTS.md for codex install"
        )
