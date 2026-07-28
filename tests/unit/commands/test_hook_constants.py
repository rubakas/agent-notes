"""Assert that hook subaction strings match Hooks.MEMORY_BRIDGE and Hooks.PRECOMPACT_MEMORY_BRIDGE.

Step 6 of the memory-subsystem colocation refactor moved the implementation of
_memory_bridge and _precompact_memory_bridge into agent_notes/commands/hook/__init__.py.
These tests verify the dispatch table in hook() and the install.py helpers are aligned
with the Hooks constants defined in agent_notes/constants.py.
"""
from agent_notes.constants import Hooks


class TestHookSubactionStrings:
    """The literal subaction strings dispatched in hook() equal the Hooks constants."""

    def test_memory_bridge_constant_matches_hook_subaction(self):
        # Hooks.MEMORY_BRIDGE is "agent-notes hook <subaction>".
        # Split off the prefix to recover the subaction that hook() dispatches on.
        prefix = "agent-notes hook "
        assert Hooks.MEMORY_BRIDGE.startswith(prefix)
        subaction = Hooks.MEMORY_BRIDGE[len(prefix):]
        assert subaction == "memory-bridge"

    def test_precompact_memory_bridge_constant_matches_hook_subaction(self):
        prefix = "agent-notes hook "
        assert Hooks.PRECOMPACT_MEMORY_BRIDGE.startswith(prefix)
        subaction = Hooks.PRECOMPACT_MEMORY_BRIDGE[len(prefix):]
        assert subaction == "precompact-memory-bridge"

    def test_hook_dispatches_memory_bridge_subaction(self):
        """hook() calls _memory_bridge() when invoked with the memory-bridge subaction."""
        from agent_notes.commands.hook import hook
        import unittest.mock as mock

        with mock.patch("agent_notes.commands.hook._memory_bridge") as patched:
            hook("memory-bridge")
        patched.assert_called_once_with()

    def test_hook_dispatches_precompact_memory_bridge_subaction(self):
        """hook() calls _precompact_memory_bridge() when invoked with the precompact subaction."""
        from agent_notes.commands.hook import hook
        import unittest.mock as mock

        with mock.patch("agent_notes.commands.hook._precompact_memory_bridge") as patched:
            hook("precompact-memory-bridge")
        patched.assert_called_once_with()

    def test_install_uses_hooks_memory_bridge_constant(self):
        """install_memory_hooks() installs exactly Hooks.MEMORY_BRIDGE, not a hardcoded string."""
        from agent_notes.memory.install import install_memory_hooks
        import unittest.mock as mock
        from pathlib import Path

        captured = []
        with mock.patch(
            "agent_notes.services.settings_writer.install_hook",
            side_effect=lambda *a, **kw: captured.append(a),
        ):
            install_memory_hooks(Path("/fake/settings.json"), "obsidian")

        session_start_commands = [cmd for _, hook_type, cmd in captured if hook_type == "SessionStart"]
        assert any(cmd == Hooks.MEMORY_BRIDGE for cmd in session_start_commands), (
            f"Expected {Hooks.MEMORY_BRIDGE!r} in SessionStart hooks, got {session_start_commands!r}"
        )

    def test_install_uses_hooks_precompact_memory_bridge_constant(self):
        """install_memory_hooks() installs exactly Hooks.PRECOMPACT_MEMORY_BRIDGE."""
        from agent_notes.memory.install import install_memory_hooks
        import unittest.mock as mock
        from pathlib import Path

        captured = []
        with mock.patch(
            "agent_notes.services.settings_writer.install_hook",
            side_effect=lambda *a, **kw: captured.append(a),
        ):
            install_memory_hooks(Path("/fake/settings.json"), "obsidian")

        precompact_commands = [cmd for _, hook_type, cmd in captured if hook_type == "PreCompact"]
        assert any(cmd == Hooks.PRECOMPACT_MEMORY_BRIDGE for cmd in precompact_commands), (
            f"Expected {Hooks.PRECOMPACT_MEMORY_BRIDGE!r} in PreCompact hooks, got {precompact_commands!r}"
        )
