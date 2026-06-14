"""Regression test: _session_hook_paths must shell-quote the home path so that
paths containing spaces or shell metacharacters do not break the generated hook command.

Bug: f"cat {home}/agent-notes-context.md 2>/dev/null || true" embeds the path
unquoted, so a home like '/home/user name' produces a two-token cat invocation.
Fix: use shlex.quote(str(home)) around the path.
"""

import shlex
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from agent_notes.services.installer import _session_hook_paths


def _make_backend(home: Path) -> MagicMock:
    backend = MagicMock()
    backend.global_home = home
    backend.local_dir = str(home)
    return backend


class TestSessionHookPathQuoting:
    def test_path_with_space_is_quoted_global(self, tmp_path):
        """A home path with a space must be shell-quoted in the global hook command."""
        home = tmp_path / "my home"
        home.mkdir()
        backend = _make_backend(home)

        _, _, hook_command = _session_hook_paths(backend, "global")

        quoted = shlex.quote(str(home / "agent-notes-context.md"))
        assert quoted in hook_command, (
            f"Expected shell-quoted full path {quoted!r} in hook command, got: {hook_command!r}"
        )

    def test_path_with_space_is_quoted_local(self, tmp_path):
        """A local_dir path with a space must be shell-quoted in the local hook command."""
        home = tmp_path / "my project dir"
        home.mkdir()
        backend = _make_backend(home)

        _, _, hook_command = _session_hook_paths(backend, "local")

        quoted = shlex.quote(str(home / "agent-notes-context.md"))
        assert quoted in hook_command, (
            f"Expected shell-quoted full path {quoted!r} in hook command, got: {hook_command!r}"
        )

    def test_path_with_semicolon_is_quoted(self, tmp_path):
        """A home path with a semicolon must be shell-quoted (semicolons are shell metacharacters)."""
        # Simulate via a path whose string representation would contain a special char;
        # we mock global_home.parts aren't validated by the OS, so use monkeypatching.
        backend = MagicMock()
        # Use a string that contains a shell-special char by faking the path
        special_path = "/home/user;evil"
        mock_home = MagicMock(spec=Path)
        mock_home.__str__ = lambda self: special_path
        mock_home.__truediv__ = lambda self, other: Path(special_path) / other
        backend.global_home = mock_home
        backend.local_dir = special_path

        _, _, hook_command = _session_hook_paths(backend, "global")

        # The semicolon must not appear unquoted in the command
        full_path = special_path + "/agent-notes-context.md"
        quoted = shlex.quote(full_path)
        assert quoted in hook_command, (
            f"Expected shell-quoted path in hook command, got: {hook_command!r}. "
            f"Unquoted semicolon would allow shell injection."
        )

    def test_normal_path_unchanged_semantics(self, tmp_path):
        """A normal path without special chars still works correctly after quoting."""
        home = tmp_path / "myhome"
        home.mkdir()
        backend = _make_backend(home)

        _, _, hook_command = _session_hook_paths(backend, "global")

        # The command should still contain the path and be functionally correct
        assert str(home) in hook_command
        assert "agent-notes-context.md" in hook_command
        assert "2>/dev/null" in hook_command
