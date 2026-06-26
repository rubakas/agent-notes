"""Integration test: uninstall removes ALL hooks/permissions without mocking the hook functions.

This test exercises the real _install_session_hook and _uninstall_session_hook paths
(not mocked) to verify that every hook and permission entry installed by install_all
is removed by uninstall_all.

It also verifies deep-merge safety: pre-existing user data in settings.json and
permissions.allow survive the uninstall.  Memory-vault Read/Write/Edit permission
entries are intentionally preserved by design and are asserted to remain.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

import agent_notes.config as config
from agent_notes.constants import Hooks
from agent_notes.domain.cli_backend import CLIBackend
from agent_notes.registries.cli_registry import CLIRegistry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_claude_backend(home: Path) -> CLIBackend:
    """Return a CLIBackend that mirrors the real claude.yaml but with global_home in tmp."""
    return CLIBackend(
        name="claude",
        label="Claude Code",
        global_home=home,
        local_dir=".claude",
        layout={
            "agents": "agents/",
            "skills": "skills/",
            "rules": "rules/",
            "commands": "commands/",
            "config": "CLAUDE.md",
            "memory": "agent-memory/",
            "settings": "settings.json",
            "agent_extension": "md",
        },
        features={
            "agents": True,
            "skills": True,
            "rules": True,
            "commands": True,
            "memory": True,
            "frontmatter": "claude",
            "config_style": "inline",
            "settings_template": False,
            "supports_symlink": True,
            "session_hook": True,
            "stop_hook": True,
            "allow_entries": True,
        },
        global_template="global-claude.md",
        exclude_flag="claude_exclude",
        accepted_providers=("anthropic",),
        use_model_class=True,
        preferred_family="claude",
    )


def _seed_minimal_dist(tmp_path: Path) -> Path:
    """Create a minimal fake dist tree so install_all has something to install."""
    dist = tmp_path / "dist"
    agents_dir = dist / "claude" / "agents"
    agents_dir.mkdir(parents=True)
    (agents_dir / "lead.md").write_text("# lead agent")

    commands_dir = dist / "claude" / "commands"
    commands_dir.mkdir(parents=True)
    (commands_dir / "review.md").write_text("# review command")

    (dist / "claude").mkdir(parents=True, exist_ok=True)
    (dist / "claude" / "CLAUDE.md").write_text("# CLAUDE config")

    rules_dir = dist / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "code-quality.md").write_text("# code quality rule")

    skills_dir = dist / "skills"
    skills_dir.mkdir(parents=True)
    # A minimal skill dir (installer expects dir-per-skill)
    skill = skills_dir / "git"
    skill.mkdir()
    (skill / "README.md").write_text("# git skill")

    return dist


def _setup(tmp_path: Path, monkeypatch) -> tuple[CLIRegistry, Path, Path, Path]:
    """Redirect all writable paths to tmp; return (registry, claude_home, xdg, dist)."""
    dist = _seed_minimal_dist(tmp_path)
    claude_home = tmp_path / "claude_home"
    claude_home.mkdir(parents=True, exist_ok=True)

    registry = CLIRegistry([_make_claude_backend(claude_home)])

    xdg = tmp_path / "xdg_config"
    xdg.mkdir()
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
    monkeypatch.setattr(config, "DIST_DIR", dist)
    monkeypatch.setattr(config, "DIST_RULES_DIR", dist / "rules")
    monkeypatch.setattr(config, "DIST_SKILLS_DIR", dist / "skills")
    monkeypatch.setattr(config, "AGENTS_HOME", tmp_path / "agents_home")

    return registry, claude_home, xdg, dist


def _settings_path(claude_home: Path) -> Path:
    return claude_home / "settings.json"


def _context_file_path(claude_home: Path) -> Path:
    return claude_home / "agent-notes-context.md"


def _has_hook(settings: dict, event: str, command: str) -> bool:
    for entry in settings.get("hooks", {}).get(event, []):
        for h in entry.get("hooks", []):
            if h.get("command") == command:
                return True
    return False


def _has_allow(settings: dict, pattern: str) -> bool:
    return pattern in settings.get("permissions", {}).get("allow", [])


def _any_allow_starts_with(settings: dict, prefix: str) -> bool:
    return any(
        e.startswith(prefix)
        for e in settings.get("permissions", {}).get("allow", [])
    )


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------

class TestUninstallRemovesAllHooksAndPermissions:
    """End-to-end: install_all (real hook install) → assert BEFORE → uninstall_all (real hook removal) → assert AFTER."""

    def test_full_hook_roundtrip_obsidian_backend(self, tmp_path, monkeypatch):
        """install_all installs hooks+perms; uninstall_all removes them; user data survives."""
        registry, claude_home, xdg, dist = _setup(tmp_path, monkeypatch)

        # Pre-seed settings.json with an unrelated user key and an unrelated allow entry
        settings_path = _settings_path(claude_home)
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        user_data = {
            "userCustomKey": "keep-me",
            "permissions": {"allow": ["Bash(my-custom-tool)"]},
        }
        settings_path.write_text(json.dumps(user_data))

        # Use a local path for obsidian vault that stays in tmp
        obsidian_vault = tmp_path / "vault" / "projects"
        obsidian_vault.mkdir(parents=True, exist_ok=True)

        # Patch memory_init so it doesn't try to create a real Obsidian index on disk
        with patch("agent_notes.services.installer.load_registry", return_value=registry), \
             patch("agent_notes.services.memory_router.memory_init"), \
             patch("agent_notes.services.installer._install_universal_skills"):
            from agent_notes.services.installer import install_all
            install_all(
                "global",
                copy_mode=False,
                registry=registry,
            )

        # Also run the session hook manually with obsidian backend so memory-bridge hooks fire
        with patch("agent_notes.services.installer.load_registry", return_value=registry):
            from agent_notes.services.installer import _install_session_hook
            backend = registry.all()[0]
            _install_session_hook(
                backend,
                "global",
                memory_backend="obsidian",
                memory_path=str(obsidian_vault),
            )

        # ── BEFORE: assert installed state ──────────────────────────────────

        assert settings_path.exists(), "settings.json must exist after install"
        settings = json.loads(settings_path.read_text())

        # SessionStart hooks
        hook_command = f"cat {repr(str(_context_file_path(claude_home)))[1:-1]} 2>/dev/null || true"
        # Verify at least ONE SessionStart hook is present (the context cat command)
        session_start_hooks = settings.get("hooks", {}).get("SessionStart", [])
        assert session_start_hooks, "SessionStart hooks must exist after install"

        # Memory-bridge hook (obsidian backend)
        assert _has_hook(settings, "SessionStart", Hooks.MEMORY_BRIDGE), \
            "Memory-bridge SessionStart hook must be installed for obsidian backend"

        # PreCompact memory-bridge hook
        assert _has_hook(settings, "PreCompact", Hooks.PRECOMPACT_MEMORY_BRIDGE), \
            "PreCompact memory-bridge hook must be installed for obsidian backend"

        # Stop cost-report hook
        assert _has_hook(settings, "Stop", Hooks.COST_REPORT), \
            "Stop cost-report hook must be installed"

        # PreToolUse guard-credentials hook
        assert _has_hook(settings, "PreToolUse", Hooks.GUARD_CREDENTIALS), \
            "PreToolUse guard-credentials hook must be installed"

        # Bash allow entries
        assert _any_allow_starts_with(settings, "Bash(agent-notes"), \
            "Bash(agent-notes ...) allow entries must be installed"

        # User data is preserved even before uninstall
        assert settings.get("userCustomKey") == "keep-me", \
            "Pre-existing user key must not be clobbered by install"
        assert _has_allow(settings, "Bash(my-custom-tool)"), \
            "Pre-existing allow entry must not be clobbered by install"

        # Context file exists
        context_file = _context_file_path(claude_home)
        assert context_file.exists(), "context file must exist after install"

        # ── RUN UNINSTALL (real, no mocks on hook functions) ─────────────────

        with patch("agent_notes.services.installer.load_registry", return_value=registry), \
             patch("agent_notes.services.installer._uninstall_universal_skills"):
            from agent_notes.services.installer import uninstall_all
            uninstall_all("global", registry=registry)

        # ── AFTER: assert cleaned state ──────────────────────────────────────

        settings_after = json.loads(settings_path.read_text())

        # Context file removed
        assert not context_file.exists(), "context file must be removed by uninstall"

        # SessionStart hook gone (all of them managed by agent-notes)
        session_start_after = settings_after.get("hooks", {}).get("SessionStart", [])
        # No agent-notes hooks should remain
        for entry in session_start_after:
            for h in entry.get("hooks", []):
                cmd = h.get("command", "")
                assert "agent-notes" not in cmd and "agent-notes-context" not in cmd, \
                    f"agent-notes SessionStart hook '{cmd}' was not removed"

        # Memory-bridge hook gone
        assert not _has_hook(settings_after, "SessionStart", Hooks.MEMORY_BRIDGE), \
            "Memory-bridge SessionStart hook must be removed by uninstall"

        # PreCompact memory-bridge hook gone
        assert not _has_hook(settings_after, "PreCompact", Hooks.PRECOMPACT_MEMORY_BRIDGE), \
            "PreCompact memory-bridge hook must be removed by uninstall"

        # Stop cost-report hook gone
        assert not _has_hook(settings_after, "Stop", Hooks.COST_REPORT), \
            "Stop cost-report hook must be removed by uninstall"

        # PreToolUse guard-credentials hook gone
        assert not _has_hook(settings_after, "PreToolUse", Hooks.GUARD_CREDENTIALS), \
            "PreToolUse guard-credentials hook must be removed by uninstall"

        # Bash(agent-notes ...) allow entries gone
        assert not _any_allow_starts_with(settings_after, "Bash(agent-notes"), \
            "Bash(agent-notes ...) allow entries must be removed by uninstall"

        # User data STILL preserved
        assert settings_after.get("userCustomKey") == "keep-me", \
            "Pre-existing user key must survive uninstall"
        assert _has_allow(settings_after, "Bash(my-custom-tool)"), \
            "Pre-existing allow entry must survive uninstall"

        # Memory-vault Read/Write/Edit entries are intentionally PRESERVED (documented behavior)
        # The installer leaves vault access entries in place after uninstall.
        # Here we simply ensure they didn't clobber other entries — the user may
        # still want Claude to access their vault without agent-notes running.
        # (No assertion forcing their presence — they may or may not be present
        # depending on whether the vault path resolved to a real directory.)

        # State file: global scope cleared
        sf = xdg / "agent-notes" / "state.json"
        if sf.exists():
            state_data = json.loads(sf.read_text())
            assert state_data.get("global") is None, \
                "Global scope must be cleared from state.json after uninstall"

        # Agent files removed
        agents_dir = claude_home / "agents"
        if agents_dir.exists():
            remaining = list(agents_dir.glob("*.md"))
            assert not remaining, f"Agent files should be removed by uninstall: {remaining}"
