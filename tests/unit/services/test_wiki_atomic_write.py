"""Regression test: _atomic_write must propagate the original exception from
os.replace, not mask it with EBADF from a double os.close(fd).

Bug: os.close(fd) was called unconditionally in the except block even though fd
was already closed before os.replace. When os.replace raised, the except block
called os.close(fd) a second time, which raised EBADF and hid the original error.
Fix: track fd_closed state and only call os.close if fd is still open.
"""

import os
import pytest
from pathlib import Path
from unittest.mock import patch

from agent_notes.services.wiki._wiki_utils import _atomic_write


class TestAtomicWrite:
    def test_successful_write(self, tmp_path):
        """Normal path: file is written with the given content."""
        target = tmp_path / "output.md"
        _atomic_write(target, "hello world\n")
        assert target.read_text() == "hello world\n"

    def test_replace_failure_propagates_original_exception(self, tmp_path, monkeypatch):
        """When os.replace raises, the original error (not EBADF) must propagate."""
        target = tmp_path / "output.md"

        class _OriginalError(RuntimeError):
            pass

        def _bad_replace(src, dst):
            raise _OriginalError("simulated replace failure")

        monkeypatch.setattr(os, "replace", _bad_replace)

        with pytest.raises(_OriginalError, match="simulated replace failure"):
            _atomic_write(target, "content")

    def test_replace_failure_cleans_up_temp_file(self, tmp_path, monkeypatch):
        """When os.replace raises, the temp file must not be left behind."""
        target = tmp_path / "output.md"

        def _bad_replace(src, dst):
            raise RuntimeError("simulated replace failure")

        monkeypatch.setattr(os, "replace", _bad_replace)

        before = set(tmp_path.iterdir())
        with pytest.raises(RuntimeError):
            _atomic_write(target, "content")

        after = set(tmp_path.iterdir())
        # No new files should remain (temp file cleaned up)
        assert after == before, f"Temp file(s) left behind: {after - before}"

    def test_replace_failure_does_not_raise_bad_fd(self, tmp_path, monkeypatch):
        """os.replace failure must NOT result in an OSError about a bad file descriptor."""
        target = tmp_path / "output.md"

        def _bad_replace(src, dst):
            raise RuntimeError("replace failed")

        monkeypatch.setattr(os, "replace", _bad_replace)

        try:
            _atomic_write(target, "content")
        except RuntimeError:
            pass  # expected
        except OSError as e:
            pytest.fail(
                f"Got OSError (likely EBADF from double-close) instead of original error: {e}"
            )
