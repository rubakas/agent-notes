"""Shared test fixtures."""
import subprocess
import pytest
from pathlib import Path

from agent_notes.config import DIST_DIR

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session", autouse=True)
def built_dist():
    """Build dist once at suite start. If build fails, the entire suite errors loudly — no silent skips.

    Tests that need a built dist depend on this implicitly (autouse). Tests that don't
    consume it pay only the one-time build cost.
    """
    result = subprocess.run(
        ["python3", "-m", "agent_notes", "build"],
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
    yield DIST_DIR
