"""Tests for wizard step functions."""
import os
import pytest
from pathlib import Path
from unittest.mock import MagicMock


import agent_notes.commands.wizard as wizard_mod
import agent_notes.services.ui as ui_mod


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _noop(*a, **kw):
    pass


def _force_non_interactive(monkeypatch):
    monkeypatch.setattr("agent_notes.services.ui._can_interactive", lambda: False)
    monkeypatch.setattr("agent_notes.commands.wizard._clear_screen", _noop, raising=False)
    # _clear_screen and _render_step_header are imported inside functions — patch at source
    monkeypatch.setattr("agent_notes.services.ui._clear_screen", _noop)
    monkeypatch.setattr("agent_notes.services.ui._render_step_header", _noop)


# ---------------------------------------------------------------------------
# TestSelectCli
# ---------------------------------------------------------------------------

class TestSelectCli:
    def test_select_cli_returns_set(self, monkeypatch):
        _force_non_interactive(monkeypatch)

        def fake_fallback(title, options, defaults=None, **kw):
            return defaults if defaults is not None else set()

        monkeypatch.setattr("agent_notes.commands.wizard._checkbox_select_fallback", fake_fallback)

        result = wizard_mod._select_cli()
        assert isinstance(result, set)

    def test_select_cli_fallback_returns_defaults(self, monkeypatch):
        """Non-interactive path returns the defaults passed to the fallback."""
        _force_non_interactive(monkeypatch)
        captured = {}

        def fake_fallback(title, options, defaults=None, **kw):
            captured["defaults"] = defaults
            captured["options"] = options
            return defaults if defaults is not None else set()

        monkeypatch.setattr("agent_notes.commands.wizard._checkbox_select_fallback", fake_fallback)

        result = wizard_mod._select_cli()
        # Defaults are {"claude"} per wizard source
        assert "claude" in captured["defaults"]
        assert isinstance(result, set)

    def test_select_cli_single_selection(self, monkeypatch):
        """When fallback returns a single-item set, result has exactly one item."""
        _force_non_interactive(monkeypatch)

        def fake_fallback(title, options, defaults=None, **kw):
            # Return only the first available option value
            if options:
                return {options[0][1]}
            return set()

        monkeypatch.setattr("agent_notes.commands.wizard._checkbox_select_fallback", fake_fallback)

        result = wizard_mod._select_cli()
        assert len(result) == 1

    def test_select_cli_result_contains_valid_backend_names(self, monkeypatch):
        """Every name in the result must exist in the CLI registry."""
        _force_non_interactive(monkeypatch)

        def fake_fallback(title, options, defaults=None, **kw):
            return defaults if defaults is not None else set()

        monkeypatch.setattr("agent_notes.commands.wizard._checkbox_select_fallback", fake_fallback)

        from agent_notes.registries.cli_registry import load_registry
        registry = load_registry()
        valid_names = {b.name for b in registry.all()}

        result = wizard_mod._select_cli()
        for name in result:
            assert name in valid_names, f"'{name}' is not a registered CLI backend"

    def test_select_cli_empty_selection_allowed(self, monkeypatch):
        """Fallback that returns empty set produces an empty set result."""
        _force_non_interactive(monkeypatch)

        monkeypatch.setattr(
            "agent_notes.commands.wizard._checkbox_select_fallback",
            lambda title, options, defaults=None, **kw: set(),
        )

        result = wizard_mod._select_cli()
        assert result == set()


# ---------------------------------------------------------------------------
# TestSelectScope
# ---------------------------------------------------------------------------

class TestSelectScope:
    def test_select_scope_default_is_global(self, monkeypatch):
        """Fallback with default index 0 returns 'global'."""
        _force_non_interactive(monkeypatch)

        def fake_fallback(title, options, default=0, **kw):
            return options[default][1]

        monkeypatch.setattr("agent_notes.commands.wizard._radio_select_fallback", fake_fallback)

        result = wizard_mod._select_scope()
        assert result == "global"

    def test_select_scope_can_return_local(self, monkeypatch):
        """When fallback returns 'local', result is 'local'."""
        _force_non_interactive(monkeypatch)

        monkeypatch.setattr(
            "agent_notes.commands.wizard._radio_select_fallback",
            lambda title, options, default=0, **kw: "local",
        )

        result = wizard_mod._select_scope()
        assert result == "local"

    def test_select_scope_with_clis_filter(self, monkeypatch):
        """Passing clis= does not break scope selection."""
        _force_non_interactive(monkeypatch)

        def fake_fallback(title, options, default=0, **kw):
            return options[default][1]

        monkeypatch.setattr("agent_notes.commands.wizard._radio_select_fallback", fake_fallback)

        result = wizard_mod._select_scope(clis={"claude"})
        assert result in ("global", "local")

    def test_select_scope_returns_string(self, monkeypatch):
        _force_non_interactive(monkeypatch)

        monkeypatch.setattr(
            "agent_notes.commands.wizard._radio_select_fallback",
            lambda title, options, default=0, **kw: options[default][1],
        )

        result = wizard_mod._select_scope()
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# TestSelectMode
# ---------------------------------------------------------------------------

class TestSelectMode:
    def test_select_mode_default_is_symlink(self, monkeypatch):
        """Default (index 0) is 'symlink', so returns False."""
        _force_non_interactive(monkeypatch)

        def fake_fallback(title, options, default=0, **kw):
            return options[default][1]

        monkeypatch.setattr("agent_notes.commands.wizard._radio_select_fallback", fake_fallback)

        result = wizard_mod._select_mode()
        assert result is False

    def test_select_mode_copy_returns_true(self, monkeypatch):
        """When 'copy' is selected, returns True."""
        _force_non_interactive(monkeypatch)

        monkeypatch.setattr(
            "agent_notes.commands.wizard._radio_select_fallback",
            lambda title, options, default=0, **kw: "copy",
        )

        result = wizard_mod._select_mode()
        assert result is True

    def test_select_mode_returns_bool(self, monkeypatch):
        _force_non_interactive(monkeypatch)

        monkeypatch.setattr(
            "agent_notes.commands.wizard._radio_select_fallback",
            lambda title, options, default=0, **kw: options[default][1],
        )

        result = wizard_mod._select_mode()
        assert isinstance(result, bool)

    def test_select_mode_symlink_selection_returns_false(self, monkeypatch):
        """Explicitly returning 'symlink' from fallback yields False."""
        _force_non_interactive(monkeypatch)

        monkeypatch.setattr(
            "agent_notes.commands.wizard._radio_select_fallback",
            lambda title, options, default=0, **kw: "symlink",
        )

        result = wizard_mod._select_mode()
        assert result is False


# ---------------------------------------------------------------------------
# TestSelectSkills
# ---------------------------------------------------------------------------

class TestSelectSkills:
    def _patch_skill_groups(self, monkeypatch, groups):
        monkeypatch.setattr("agent_notes.commands.wizard._get_skill_groups", lambda: groups)

    def test_select_skills_empty_groups_returns_empty(self, monkeypatch):
        _force_non_interactive(monkeypatch)
        self._patch_skill_groups(monkeypatch, {})

        result = wizard_mod._select_skills()
        assert result == []

    def test_select_skills_includes_process_skills(self, monkeypatch):
        """Process skills are always included regardless of domain selection."""
        _force_non_interactive(monkeypatch)
        self._patch_skill_groups(monkeypatch, {
            "process": ["obsidian-memory", "session-context"],
            "Git": ["git"],
        })

        # Fallback returns nothing for domain skills
        monkeypatch.setattr(
            "agent_notes.commands.wizard._checkbox_select_fallback",
            lambda title, options, defaults=None, **kw: set(),
        )

        result = wizard_mod._select_skills()
        assert "obsidian-memory" in result
        assert "session-context" in result

    def test_select_skills_default_includes_all_domain_skills(self, monkeypatch):
        """Default fallback (returns defaults) includes all domain skills."""
        _force_non_interactive(monkeypatch)
        self._patch_skill_groups(monkeypatch, {
            "process": ["obsidian-memory"],
            "Git": ["git"],
            "Rails": ["rails-core"],
        })

        def fake_fallback(title, options, defaults=None, **kw):
            return defaults if defaults is not None else set()

        monkeypatch.setattr("agent_notes.commands.wizard._checkbox_select_fallback", fake_fallback)

        result = wizard_mod._select_skills()
        assert "obsidian-memory" in result
        assert "git" in result
        assert "rails-core" in result

    def test_select_skills_domain_skills_selectable(self, monkeypatch):
        """Only the skills returned by fallback (plus process) appear in result."""
        _force_non_interactive(monkeypatch)
        self._patch_skill_groups(monkeypatch, {
            "process": ["obsidian-memory"],
            "Git": ["git"],
            "Docker": ["docker-compose"],
        })

        # Only "git" selected, not docker-compose
        monkeypatch.setattr(
            "agent_notes.commands.wizard._checkbox_select_fallback",
            lambda title, options, defaults=None, **kw: {"git"},
        )

        result = wizard_mod._select_skills()
        assert "git" in result
        assert "obsidian-memory" in result  # process always included
        assert "docker-compose" not in result

    def test_select_skills_no_tech_groups_only_process(self, monkeypatch):
        """When only process group exists, no checkbox is shown and all process skills returned."""
        _force_non_interactive(monkeypatch)
        self._patch_skill_groups(monkeypatch, {
            "process": ["obsidian-memory", "session-context"],
        })

        called = []
        monkeypatch.setattr(
            "agent_notes.commands.wizard._checkbox_select_fallback",
            lambda *a, **kw: called.append(1) or set(),
        )

        result = wizard_mod._select_skills()
        # No tech groups means no checkbox call
        assert called == []
        assert "obsidian-memory" in result
        assert "session-context" in result

    def test_select_skills_returns_list(self, monkeypatch):
        _force_non_interactive(monkeypatch)
        self._patch_skill_groups(monkeypatch, {"process": ["obsidian-memory"]})

        result = wizard_mod._select_skills()
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# TestSelectMemory
# ---------------------------------------------------------------------------

class TestSelectMemory:
    def _patch_non_interactive(self, monkeypatch):
        _force_non_interactive(monkeypatch)

    def _patch_detect_vaults(self, monkeypatch, vaults=None):
        monkeypatch.setattr(
            "agent_notes.commands.wizard._detect_obsidian_vaults",
            lambda: vaults if vaults is not None else [],
        )

    def _patch_path_input(self, monkeypatch, return_value):
        monkeypatch.setattr(
            "agent_notes.commands.wizard._path_input",
            lambda prompt, default: return_value,
        )

    def test_select_memory_local_default(self, monkeypatch):
        """Default selection (index 0 = 'local') returns ('local', '', 'single-brain')."""
        self._patch_non_interactive(monkeypatch)

        monkeypatch.setattr(
            "agent_notes.commands.wizard._radio_select_fallback",
            lambda title, options, default=0, **kw: options[default][1],
        )

        backend, path, strategy = wizard_mod._select_memory(step=6, total=7)
        assert backend == "local"
        assert path == ""
        assert strategy == "single-brain"

    def test_select_memory_no_none_option(self, monkeypatch):
        """The provider menu must not contain a 'none' option."""
        self._patch_non_interactive(monkeypatch)

        captured_options = {}

        def fake_fallback(title, options, default=0, **kw):
            captured_options["options"] = options
            return options[default][1]

        monkeypatch.setattr(
            "agent_notes.commands.wizard._radio_select_fallback",
            fake_fallback,
        )

        wizard_mod._select_memory(step=6, total=7)
        values = [v for _, v in captured_options.get("options", [])]
        assert "none" not in values, f"'none' must not appear in provider options: {values}"

    def test_select_memory_returns_tuple(self, monkeypatch):
        """_select_memory returns a 3-tuple: (backend, path, strategy)."""
        self._patch_non_interactive(monkeypatch)

        monkeypatch.setattr(
            "agent_notes.commands.wizard._radio_select_fallback",
            lambda title, options, default=0, **kw: options[default][1],
        )

        result = wizard_mod._select_memory(step=6, total=7)
        assert isinstance(result, tuple)
        assert len(result) == 3

    def test_select_memory_obsidian_session_backend(self, monkeypatch):
        """Selecting obsidian returns ('obsidian', path ending in /projects, strategy)."""
        self._patch_non_interactive(monkeypatch)
        self._patch_detect_vaults(monkeypatch, [])
        self._patch_path_input(monkeypatch, "/tmp/MyVault")

        # First call: provider → "obsidian"; second call: strategy → "single-brain"
        calls = iter(["obsidian", "single-brain"])
        monkeypatch.setattr(
            "agent_notes.commands.wizard._radio_select_fallback",
            lambda title, options, default=0, **kw: next(calls),
        )

        backend, path, strategy = wizard_mod._select_memory(step=6, total=7)
        assert backend == "obsidian"
        assert path.endswith("/projects")
        assert strategy == "single-brain"

    def test_select_memory_obsidian_per_project_strategy(self, monkeypatch, tmp_path):
        """Selecting obsidian with per-project strategy records the strategy."""
        self._patch_non_interactive(monkeypatch)
        self._patch_detect_vaults(monkeypatch, [])
        self._patch_path_input(monkeypatch, str(tmp_path / "Vault"))

        calls = iter(["obsidian", "per-project"])
        monkeypatch.setattr(
            "agent_notes.commands.wizard._radio_select_fallback",
            lambda title, options, default=0, **kw: next(calls),
        )

        backend, path, strategy = wizard_mod._select_memory(step=6, total=7)
        assert backend == "obsidian"
        assert strategy == "per-project"

    def test_select_memory_local_no_strategy_prompt(self, monkeypatch):
        """Selecting local must not trigger a strategy radio call (no second radio prompt)."""
        self._patch_non_interactive(monkeypatch)

        call_count = [0]

        def counting_fallback(title, options, default=0, **kw):
            call_count[0] += 1
            return options[default][1]  # always return local (first option)

        monkeypatch.setattr(
            "agent_notes.commands.wizard._radio_select_fallback",
            counting_fallback,
        )

        backend, path, strategy = wizard_mod._select_memory(step=6, total=7)
        assert backend == "local"
        assert call_count[0] == 1, f"local must trigger exactly 1 radio call, got {call_count[0]}"
        assert strategy == "single-brain"

    def test_select_memory_vault_path_with_subfolder(self, monkeypatch, tmp_path):
        """Final path is vault + subfolder."""
        self._patch_non_interactive(monkeypatch)
        vault_dir = tmp_path / "MyVault"
        self._patch_detect_vaults(monkeypatch, [])
        self._patch_path_input(monkeypatch, str(vault_dir))

        calls = iter(["obsidian", "single-brain"])
        monkeypatch.setattr(
            "agent_notes.commands.wizard._radio_select_fallback",
            lambda title, options, default=0, **kw: next(calls),
        )

        backend, path, strategy = wizard_mod._select_memory(step=6, total=7)
        expected = str(vault_dir / "projects")
        assert path == expected

    def test_select_memory_detects_vaults_uses_first_as_default(self, monkeypatch, tmp_path):
        """When vaults are detected, the first one is the default for path input."""
        self._patch_non_interactive(monkeypatch)
        vault1 = tmp_path / "Vault1"
        vault2 = tmp_path / "Vault2"
        self._patch_detect_vaults(monkeypatch, [vault1, vault2])

        received_default = {}

        def fake_path_input(prompt, default):
            received_default["value"] = default
            return default

        monkeypatch.setattr("agent_notes.commands.wizard._path_input", fake_path_input)

        calls = iter(["obsidian", "single-brain"])
        monkeypatch.setattr(
            "agent_notes.commands.wizard._radio_select_fallback",
            lambda title, options, default=0, **kw: next(calls),
        )

        wizard_mod._select_memory(step=6, total=7)
        assert received_default["value"] == str(vault1)

    def test_select_memory_no_vaults_uses_documents_default(self, monkeypatch):
        """When no vaults detected, default is ~/Documents/Obsidian Vault."""
        self._patch_non_interactive(monkeypatch)
        self._patch_detect_vaults(monkeypatch, [])

        received_default = {}

        def fake_path_input(prompt, default):
            received_default["value"] = default
            return default

        monkeypatch.setattr("agent_notes.commands.wizard._path_input", fake_path_input)

        calls = iter(["obsidian", "single-brain"])
        monkeypatch.setattr(
            "agent_notes.commands.wizard._radio_select_fallback",
            lambda title, options, default=0, **kw: next(calls),
        )

        wizard_mod._select_memory(step=6, total=7)
        assert "Obsidian" in received_default["value"] or "obsidian" in received_default["value"].lower()

    def test_select_memory_empty_path_input_uses_default(self, monkeypatch, tmp_path):
        """When _path_input returns empty string, wizard falls back to default vault path."""
        self._patch_non_interactive(monkeypatch)
        vault1 = tmp_path / "DefaultVault"
        self._patch_detect_vaults(monkeypatch, [vault1])

        # Return empty string — wizard should use default_vault
        monkeypatch.setattr(
            "agent_notes.commands.wizard._path_input",
            lambda prompt, default: "",
        )

        calls = iter(["obsidian", "single-brain"])
        monkeypatch.setattr(
            "agent_notes.commands.wizard._radio_select_fallback",
            lambda title, options, default=0, **kw: next(calls),
        )

        backend, path, strategy = wizard_mod._select_memory(step=6, total=7)
        # Empty input → uses default_vault which is vault1
        assert path == str(vault1 / "projects")
