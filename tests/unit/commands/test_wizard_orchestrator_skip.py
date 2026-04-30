"""Tests for orchestrator-role skip logic in _select_models_per_role."""
import os
import pytest


class TestSelectModelsPerRole:
    def test_claude_backend_skips_orchestrator_role(self, monkeypatch):
        """When configuring the claude CLI, orchestrator must not appear in result."""
        # Use non-interactive fallback so no TTY is needed
        monkeypatch.setattr("agent_notes.services.ui._can_interactive", lambda: False)
        # Intercept _radio_select_fallback to record calls and return the first option value
        selected_roles = []

        def fake_radio(title, options, default=0, **kwargs):
            # Extract role name from the title line that reads "Role  <label>"
            for line in title.splitlines():
                stripped = line.strip()
                if stripped.startswith("Role"):
                    selected_roles.append(stripped)
                    break
            return options[default][1]

        monkeypatch.setattr("agent_notes.commands.wizard._radio_select_fallback", fake_radio)
        monkeypatch.setattr("agent_notes.commands.wizard._radio_select", fake_radio)

        from agent_notes.commands.wizard import _select_models_per_role

        result = _select_models_per_role({"claude"})

        # The result dict should not contain orchestrator for claude
        assert "claude" in result
        assert "orchestrator" not in result["claude"], (
            f"orchestrator should be skipped for claude backend, got: {result['claude']}"
        )

    def test_other_backends_keep_orchestrator_role(self, monkeypatch):
        """Non-claude backends (e.g. opencode) keep all roles including orchestrator."""
        from agent_notes.registries.cli_registry import load_registry
        registry = load_registry()

        # Find a non-claude backend that supports agents
        non_claude = [b for b in registry.all() if b.name != "claude" and b.supports("agents")]
        if not non_claude:
            pytest.skip("No non-claude backend that supports agents found")

        backend_name = non_claude[0].name

        monkeypatch.setattr("agent_notes.services.ui._can_interactive", lambda: False)

        def fake_radio(title, options, default=0, **kwargs):
            return options[default][1]

        monkeypatch.setattr("agent_notes.commands.wizard._radio_select_fallback", fake_radio)
        monkeypatch.setattr("agent_notes.commands.wizard._radio_select", fake_radio)

        from agent_notes.commands.wizard import _select_models_per_role

        result = _select_models_per_role({backend_name})

        if backend_name in result:
            assert "orchestrator" in result[backend_name], (
                f"orchestrator should be present for {backend_name}, got: {result[backend_name]}"
            )

    def test_claude_result_contains_other_roles(self, monkeypatch):
        """Roles other than orchestrator (e.g. worker, scout) are still configured for claude."""
        monkeypatch.setattr("agent_notes.services.ui._can_interactive", lambda: False)

        def fake_radio(title, options, default=0, **kwargs):
            return options[default][1]

        monkeypatch.setattr("agent_notes.commands.wizard._radio_select_fallback", fake_radio)
        monkeypatch.setattr("agent_notes.commands.wizard._radio_select", fake_radio)

        from agent_notes.commands.wizard import _select_models_per_role
        from agent_notes.registries.role_registry import load_role_registry

        result = _select_models_per_role({"claude"})
        all_roles = {r.name for r in load_role_registry().all()}
        non_orchestrator_roles = all_roles - {"orchestrator"}

        assert "claude" in result
        configured_roles = set(result["claude"].keys())
        assert configured_roles == non_orchestrator_roles, (
            f"Expected roles {non_orchestrator_roles}, got {configured_roles}"
        )
