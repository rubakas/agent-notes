"""Shared test fixtures."""
import os
import shutil
import subprocess
import sys
import tempfile
import pytest
from pathlib import Path

from agent_notes.config import DIST_DIR

REPO_ROOT = Path(__file__).resolve().parent.parent

# Files that test deleted wiki package functionality — removed with the wiki backend.
collect_ignore = [
    "unit/services/test_credential_filter.py",
]

# Session-scoped temp dir used for cache isolation.  Set in pytest_configure
# (before pytest_sessionstart) so the shelled-out `agent-notes build` subprocess
# inherits XDG_CACHE_HOME and never reads the developer's personal cache.
_SESSION_CACHE_DIR: str | None = None


def pytest_configure(config):
    """Pin XDG_CACHE_HOME to a temp dir before any test infrastructure runs.

    This must happen before pytest_sessionstart (which shells out to
    ``agent-notes build``) so the subprocess inherits the isolation.
    An autouse fixture fires too late — the hook has already run by then.
    """
    global _SESSION_CACHE_DIR
    _SESSION_CACHE_DIR = tempfile.mkdtemp(prefix="agent-notes-test-cache-")
    os.environ["XDG_CACHE_HOME"] = _SESSION_CACHE_DIR


def pytest_unconfigure(config):
    """Remove the session cache isolation dir on teardown."""
    global _SESSION_CACHE_DIR
    if _SESSION_CACHE_DIR:
        shutil.rmtree(_SESSION_CACHE_DIR, ignore_errors=True)
        _SESSION_CACHE_DIR = None


def pytest_sessionstart(session):
    """Build dist before collection so module-level discovery in test files works."""
    result = subprocess.run(
        [sys.executable, "-m", "agent_notes", "build"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        pytest.exit(
            f"agent-notes build failed during test session setup:\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}",
            returncode=1,
        )


@pytest.fixture(scope="session", autouse=True)
def built_dist():
    """Build dist once at suite start. If build fails, the entire suite errors loudly — no silent skips.

    Tests that need a built dist depend on this implicitly (autouse). Tests that don't
    consume it pay only the one-time build cost.
    """
    yield DIST_DIR
